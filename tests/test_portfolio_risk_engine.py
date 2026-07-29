from __future__ import annotations

import unittest
from dataclasses import replace

from group_test_support import (
    ManualClock,
    action_for,
    execution_plan,
    three_leg_basket,
    two_leg_basket,
)
from portfolio_risk_test_support import (
    BTC_FACTOR,
    NOW,
    exact,
    margin_scope,
    policy,
    portfolio_snapshot,
    position_view,
    product,
    publication,
    sensitivity,
)

from cex_quant.core import (
    FixedPoint,
    Money,
    PortfolioReservationId,
    Price,
    Quantity,
    Rate,
    SpreadRiskId,
    UnixNanos,
)
from cex_quant.instruments import (
    ContractValueType,
    Instrument,
    InstrumentKind,
)
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.oms import (
    OrderGroupAdmission,
    OrderGroupStatus,
    OrderGroupView,
)
from cex_quant.portfolio import (
    PositionLiquidationReference,
    PositionRiskReadiness,
)
from cex_quant.risk import (
    InstrumentSensitivity,
    LiquidationRequirement,
    PortfolioApprovalEvidence,
    PortfolioRiskDecisionStatus,
    PortfolioRiskDirectiveKind,
    PortfolioRiskEngine,
    PortfolioRiskRejectReason,
    PortfolioRiskReservationState,
    PortfolioRiskReservationView,
    RiskFactorLimit,
    SpreadRiskInput,
    SpreadRiskLimit,
    WorkingOrderRiskView,
)
from cex_quant.runtime import OrderGroupRuntime
from cex_quant.snapshots import ObservationId
from cex_quant.strategy import BasketTargetIntent, basket_target_intent_checksum


def two_leg_inputs() -> tuple[
    Instrument,
    Instrument,
    InstrumentSensitivity,
    InstrumentSensitivity,
]:
    spot = product(InstrumentKind.SPOT, "BTCUSDT")
    perp = product(InstrumentKind.PERPETUAL, "BTCUSDT")
    return (
        spot,
        perp,
        sensitivity(spot.instrument_id, delta="1", margin="0"),
        sensitivity(perp.instrument_id, delta="1", margin="10"),
    )


def group_for_approval(
    approval: PortfolioApprovalEvidence,
    *,
    basket: BasketTargetIntent,
) -> tuple[OrderGroupRuntime, OrderGroupView]:
    clock = ManualClock(value=2_010)
    runtime = OrderGroupRuntime(now_ns=clock)
    created = runtime.create_group(
        OrderGroupAdmission(
            approval_id=approval.approval_id,
            basket=basket,
            basket_checksum=basket_target_intent_checksum(basket),
            approved_at_ns=approval.approved_at_ns,
            valid_until_ns=approval.valid_until_ns,
            risk_policy_version=approval.risk_policy_version,
        ),
        execution_plan(),
    )
    return runtime, runtime.activate_group(created.order_group_id)


class PortfolioRiskEngineTests(unittest.TestCase):
    def test_freshness_horizon_and_failure_statuses_are_explicit(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        selected_policy = replace(
            policy(instruments),
            approval_lifetime_ns=2_000,
            max_margin_age_ns=60,
        )
        snapshot = portfolio_snapshot(
            instruments,
            (spot_sensitivity, perp_sensitivity),
        )
        snapshot = replace(snapshot, margins=(margin_scope(),))
        engine = PortfolioRiskEngine()
        allowed = engine.assess_basket(
            two_leg_basket(),
            publication(snapshot),
            selected_policy,
            now_ns=NOW,
        )
        assert allowed.approval is not None
        self.assertEqual(
            allowed.risk_snapshot_metadata.market_data_as_of_ns,
            UnixNanos(1_950),
        )
        self.assertEqual(
            allowed.risk_snapshot_metadata.portfolio_state_as_of_ns,
            UnixNanos(1_950),
        )
        self.assertEqual(
            allowed.risk_snapshot_metadata.valid_until_ns,
            UnixNanos(2_010),
        )
        self.assertEqual(allowed.approval.valid_until_ns, UnixNanos(2_010))

        stale = engine.assess_basket(
            two_leg_basket(),
            publication(snapshot),
            selected_policy,
            now_ns=UnixNanos(2_011),
        )
        self.assertEqual(stale.status, PortfolioRiskDecisionStatus.STALE)
        insufficient = engine.assess_basket(
            two_leg_basket(),
            publication(replace(snapshot, sensitivities=())),
            selected_policy,
            now_ns=NOW,
        )
        self.assertEqual(
            insufficient.status,
            PortfolioRiskDecisionStatus.INSUFFICIENT_DATA,
        )

    def test_recovery_group_action_has_recovery_required_status(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        selected_policy = policy(instruments)
        engine = PortfolioRiskEngine()
        basket = two_leg_basket()
        admitted = engine.assess_basket(
            basket,
            publication(
                portfolio_snapshot(
                    instruments,
                    (spot_sensitivity, perp_sensitivity),
                )
            ),
            selected_policy,
            now_ns=NOW,
        )
        assert admitted.approval is not None
        runtime, active = group_for_approval(admitted.approval, basket=basket)
        recovery = runtime.require_recovery(
            active.order_group_id,
            reason="synthetic unknown",
        )
        reservation = PortfolioRiskReservationView(
            reservation_id=PortfolioReservationId("recovery-reservation"),
            approval_id=admitted.approval.approval_id,
            strategy_id=basket.strategy_id,
            basket=basket,
            state=PortfolioRiskReservationState.ATTACHED_TO_GROUP,
            created_at_ns=NOW,
            valid_until_ns=UnixNanos(2_400),
            resource_claims=admitted.approval.resource_claims,
            group_id=recovery.order_group_id,
        )
        action = action_for(
            recovery,
            leg_index=0,
            now_ns=UnixNanos(2_010),
            quantity="1",
        )
        decision = engine.authorize_action(
            recovery,
            action,
            publication(
                portfolio_snapshot(
                    instruments,
                    (spot_sensitivity, perp_sensitivity),
                    reservations=(reservation,),
                )
            ),
            selected_policy,
            now_ns=UnixNanos(2_010),
        )
        self.assertEqual(
            decision.status,
            PortfolioRiskDecisionStatus.RECOVERY_REQUIRED,
        )

    def test_whole_basket_projects_complete_delta_neutral_target(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        snapshot = portfolio_snapshot(
            instruments,
            (spot_sensitivity, perp_sensitivity),
        )
        decision = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(snapshot),
            policy(instruments),
            now_ns=NOW,
        )

        self.assertEqual(
            decision.status,
            PortfolioRiskDecisionStatus.ALLOW,
        )
        self.assertIsNotNone(decision.approval)
        self.assertEqual(
            decision.projected_exposure.factors[0].net_delta.as_decimal(),
            FixedPoint.from_str("0").as_decimal(),
        )
        self.assertEqual(
            decision.projected_exposure.factors[0].gross_delta.as_decimal(),
            FixedPoint.from_str("20").as_decimal(),
        )
        self.assertEqual(
            decision.projected_exposure.initial_margin.as_decimal(),
            FixedPoint.from_str("100").as_decimal(),
        )

    def test_working_order_and_spread_limits_reject_whole_basket(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        snapshot = portfolio_snapshot(
            instruments,
            (spot_sensitivity, perp_sensitivity),
            working_orders=(
                WorkingOrderRiskView(
                    account_id=two_leg_basket().legs[0].account_id,
                    instrument_id=spot.instrument_id,
                    signed_remaining_quantity=Quantity.from_str("2"),
                ),
            ),
        )
        snapshot = replace(
            snapshot,
            spread_inputs=(
                SpreadRiskInput(
                    spread_id=SpreadRiskId("btc-basis"),
                    value=exact("5", unit="USDT"),
                ),
            ),
        )
        strict_policy = replace(
            policy(instruments),
            factor_limits=(
                RiskFactorLimit(
                    risk_factor_id=BTC_FACTOR,
                    max_abs_net_delta=FixedPoint.from_str("1"),
                    max_gross_delta=FixedPoint.from_str("100"),
                ),
            ),
            spread_limits=(
                SpreadRiskLimit(
                    spread_id=SpreadRiskId("btc-basis"),
                    max_abs_value=FixedPoint.from_str("2"),
                ),
            ),
        )
        decision = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(snapshot),
            strict_policy,
            now_ns=NOW,
        )

        self.assertEqual(
            decision.status,
            PortfolioRiskDecisionStatus.REJECT,
        )
        self.assertIn(
            PortfolioRiskRejectReason.RISK_FACTOR_LIMIT,
            decision.reasons,
        )
        self.assertIn(
            PortfolioRiskRejectReason.SPREAD_LIMIT,
            decision.reasons,
        )
        self.assertIsNone(decision.approval)

    def test_three_leg_options_use_supplied_greeks_by_underlying(self) -> None:
        option_a = product(InstrumentKind.OPTION, "BTC-30000-C")
        option_b = product(InstrumentKind.OPTION, "BTC-35000-C")
        perp = product(InstrumentKind.PERPETUAL, "BTCUSDT")
        instruments = (option_a, option_b, perp)
        sensitivities = (
            sensitivity(
                option_a.instrument_id,
                delta="0.50",
                margin="5",
                gamma="0.01",
                vega="2",
            ),
            sensitivity(
                option_b.instrument_id,
                delta="0.20",
                margin="5",
                gamma="0.02",
                vega="3",
            ),
            sensitivity(perp.instrument_id, delta="1", margin="10"),
        )
        decision = PortfolioRiskEngine().assess_basket(
            three_leg_basket(),
            publication(portfolio_snapshot(instruments, sensitivities)),
            policy(instruments),
            now_ns=NOW,
        )

        self.assertTrue(decision.allowed)
        factor = decision.projected_exposure.factors[0]
        self.assertEqual(
            factor.net_delta.as_decimal(),
            FixedPoint.from_str("-0.35").as_decimal()
            + FixedPoint.from_str("3").as_decimal(),
        )
        self.assertEqual(
            factor.gamma.as_decimal(),
            FixedPoint.from_str("-0.1").as_decimal(),
        )
        self.assertEqual(
            factor.vega.as_decimal(),
            FixedPoint.from_str("-10").as_decimal(),
        )

    def test_original_causation_stale_inputs_and_unit_mismatch_reject(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        bad_sensitivity = replace(
            perp_sensitivity,
            delta_per_quantity=exact("1", unit="contracts"),
        )
        snapshot = portfolio_snapshot(
            instruments,
            (spot_sensitivity, bad_sensitivity),
        )
        snapshot = replace(snapshot, original_decision_snapshot_ids=())
        decision = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(snapshot),
            policy(instruments),
            now_ns=UnixNanos(4_000),
        )
        self.assertIn(
            PortfolioRiskRejectReason.SCOPE_INCOMPLETE,
            decision.reasons,
        )
        self.assertIn(
            PortfolioRiskRejectReason.SNAPSHOT_EXPIRED,
            decision.reasons,
        )
        self.assertIn(
            PortfolioRiskRejectReason.MARK_STALE,
            decision.reasons,
        )
        self.assertIn(
            PortfolioRiskRejectReason.SENSITIVITY_UNIT_MISMATCH,
            decision.reasons,
        )

    def test_exact_action_is_assessed_against_current_residual(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        engine = PortfolioRiskEngine()
        basket = two_leg_basket()
        initial = engine.assess_basket(
            basket,
            publication(
                portfolio_snapshot(
                    instruments,
                    (spot_sensitivity, perp_sensitivity),
                )
            ),
            policy(instruments),
            now_ns=NOW,
        )
        assert initial.approval is not None
        runtime, group = group_for_approval(
            initial.approval,
            basket=basket,
        )
        reservation = PortfolioRiskReservationView(
            reservation_id=PortfolioReservationId("reservation-1"),
            approval_id=initial.approval.approval_id,
            strategy_id=basket.strategy_id,
            basket=basket,
            state=PortfolioRiskReservationState.ATTACHED_TO_GROUP,
            created_at_ns=NOW,
            valid_until_ns=UnixNanos(2_400),
            resource_claims=initial.approval.resource_claims,
            group_id=group.order_group_id,
        )
        risk_view = portfolio_snapshot(
            instruments,
            (spot_sensitivity, perp_sensitivity),
            positions=position_view({spot.instrument_id: "10"}),
            groups=(group,),
            reservations=(reservation,),
        )
        action = action_for(
            group,
            leg_index=0,
            now_ns=UnixNanos(2_020),
            quantity="10",
        )
        action_decision = engine.authorize_action(
            group,
            action,
            publication(risk_view),
            policy(instruments),
            now_ns=UnixNanos(2_020),
        )

        self.assertTrue(action_decision.allowed)
        self.assertEqual(
            action_decision.current_exposure.factors[0].net_delta.as_decimal(),
            FixedPoint.from_str("10").as_decimal(),
        )
        self.assertEqual(
            action_decision.projected_exposure.factors[0].net_delta.raw,
            0,
        )
        assert action_decision.permit is not None
        self.assertEqual(
            action_decision.permit.expected_group_revision,
            group.revision,
        )

        changed_group = runtime.suspend_group(
            group.order_group_id,
            reason="material change",
        )
        rejected = engine.authorize_action(
            changed_group,
            action,
            publication(risk_view),
            policy(instruments),
            now_ns=UnixNanos(2_030),
        )
        self.assertIn(
            PortfolioRiskRejectReason.GROUP_REVISION_MISMATCH,
            rejected.reasons,
        )

    def test_supervision_returns_semantic_directive_only(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        initial = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(
                portfolio_snapshot(
                    instruments,
                    (spot_sensitivity, perp_sensitivity),
                )
            ),
            policy(instruments),
            now_ns=NOW,
        )
        assert initial.approval is not None
        _, group = group_for_approval(
            initial.approval,
            basket=two_leg_basket(),
        )
        directive = PortfolioRiskEngine().supervise_group(
            group,
            publication(
                portfolio_snapshot(
                    instruments,
                    (spot_sensitivity, perp_sensitivity),
                    positions=position_view(
                        readiness=PositionRiskReadiness.RECOVERY_REQUIRED,
                    ),
                )
            ),
            policy(instruments),
            now_ns=NOW,
        )
        self.assertEqual(
            directive.kind,
            PortfolioRiskDirectiveKind.RECONCILIATION_REQUIRED,
        )
        self.assertEqual(group.status, OrderGroupStatus.ACTIVE)

    def test_margin_liquidation_and_health_fail_closed(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        instruments = (spot, perp)
        strict_policy = replace(
            policy(instruments),
            required_liquidation_references=(
                LiquidationRequirement(
                    account_id=two_leg_basket().legs[0].account_id,
                    instrument_id=perp.instrument_id,
                ),
            ),
            min_liquidation_buffer=Rate.from_str("0.02"),
        )
        snapshot = portfolio_snapshot(
            instruments,
            (spot_sensitivity, perp_sensitivity),
        )
        missing = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(snapshot),
            strict_policy,
            now_ns=NOW,
        )
        self.assertIn(
            PortfolioRiskRejectReason.SCOPE_INCOMPLETE,
            missing.reasons,
        )

        liquidation = PositionLiquidationReference(
            observation_id=ObservationId("liquidation"),
            account_id=two_leg_basket().legs[0].account_id,
            instrument_id=perp.instrument_id,
            liquidation_price=Price.from_str("99"),
            maintenance_margin=Money.from_str("1"),
            as_of_ns=UnixNanos(1_950),
        )
        unhealthy_snapshot = replace(
            snapshot,
            liquidation_references=(liquidation,),
            health=HealthReport(
                component="portfolio-risk-inputs",
                status=HealthStatus.UNHEALTHY,
                observed_at_ns=NOW,
            ),
        )
        unsafe = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(unhealthy_snapshot),
            strict_policy,
            now_ns=NOW,
        )
        self.assertIn(
            PortfolioRiskRejectReason.LIQUIDATION_BUFFER_LIMIT,
            unsafe.reasons,
        )
        self.assertIn(
            PortfolioRiskRejectReason.HEALTH_NOT_READY,
            unsafe.reasons,
        )

    def test_unsupported_contract_and_future_intent_reject(self) -> None:
        spot, perp, spot_sensitivity, perp_sensitivity = two_leg_inputs()
        assert hasattr(perp.specification, "value_type")
        quanto = replace(
            perp,
            specification=replace(
                perp.specification,
                value_type=ContractValueType.QUANTO,
            ),
        )
        instruments = (spot, quanto)
        rejected = PortfolioRiskEngine().assess_basket(
            replace(
                two_leg_basket(),
                decision_time_ns=UnixNanos(2_500),
                valid_until_ns=UnixNanos(3_000),
            ),
            publication(
                portfolio_snapshot(
                    instruments,
                    (spot_sensitivity, perp_sensitivity),
                )
            ),
            policy(instruments),
            now_ns=NOW,
        )
        self.assertIn(
            PortfolioRiskRejectReason.BASKET_FROM_FUTURE,
            rejected.reasons,
        )
        self.assertIn(
            PortfolioRiskRejectReason.UNSUPPORTED_INSTRUMENT_MODEL,
            rejected.reasons,
        )


if __name__ == "__main__":
    unittest.main()
