from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_quant.accounting import AccountingLedgerView
from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.applications.carry.state import CarryPositionBook
from cex_quant.core import (
    AssetId,
    DurationNanos,
    FixedPoint,
    MarginScopeId,
    Money,
    MonotonicNanos,
    ObjectiveTypeId,
    PortfolioReconciliationId,
    Price,
    Quantity,
    Rate,
    RiskFactorId,
    UnixNanos,
    VenueId,
)
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.oms import JsonLinesOmsJournal, OrderEvent, OrderStatus
from cex_quant.portfolio import (
    AccountSnapshot,
    ExecutionConsistentPositionState,
    ExecutionCoverage,
    MarginMode,
    MarginScopeSnapshot,
    ReconciledAccountBaseline,
)
from cex_quant.risk import (
    ExactRiskValue,
    InstrumentRiskModelPolicy,
    InstrumentSensitivity,
    JsonLinesPortfolioRiskJournal,
    PortfolioRiskCoordinator,
    PortfolioRiskEngine,
    PortfolioRiskPolicy,
    PortfolioRiskReservationView,
    PortfolioRiskSnapshot,
    RiskFactorLimit,
    RiskMark,
)
from cex_quant.runtime import (
    CarryFinancialEvidence,
    CarryReadSideProjector,
    DeterministicOfflineExecutionPort,
    GroupedExecutionRuntime,
    GroupedExecutionStepDisposition,
    OfflineExecutionDirective,
    OfflineExecutionDirectiveKind,
    OmsExecutionEffectProjector,
    OrderGroupRuntime,
)
from cex_quant.snapshots import (
    DecisionSnapshotId,
    DecisionSnapshotMetadata,
    DecisionSnapshotPublication,
    ObservationId,
    SnapshotAssessment,
    SnapshotReadiness,
)
from cex_quant.strategy import (
    BasketTargetLeg,
    ObjectiveTypeRef,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)
from tests.carry_test_support import STRATEGY_ID, instruments, pair
from tests.group_test_support import ManualClock, execution_plan

OPENING_SNAPSHOT = DecisionSnapshotId("offline-promotion-opening")
RISK_FACTOR = RiskFactorId("BTC")
MARGIN_SCOPE = MarginScopeId("offline-perpetual-cross")
REPORTING_ASSET = AssetId("USDT")


class _AllowSubmitGuard:
    def assert_submit_allowed(self, request: object) -> None:
        del request


class _MemoryCarryJournal:
    def __init__(self) -> None:
        self.items: list[object] = []

    def read(self):
        yield from self.items

    def append(self, fact: object) -> None:
        self.items.append(fact)


class OfflineExecutionPromotionAcceptanceTests(unittest.TestCase):
    def test_two_leg_fill_converges_oms_portfolio_and_carry(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        with self.subTest("durable two-leg loop"):
            clock = ManualClock(value=2_000)
            carry_pair = pair()
            products = instruments()
            basket = opening_basket()
            oms_journal = JsonLinesOmsJournal(root / "oms.jsonl")
            risk_journal = JsonLinesPortfolioRiskJournal(root / "risk.jsonl")
            self.addCleanup(oms_journal.close)
            self.addCleanup(risk_journal.close)
            groups = OrderGroupRuntime(now_ns=clock, journal=oms_journal)
            policy = risk_policy(products)
            coordinator = PortfolioRiskCoordinator(
                journal=risk_journal,
                risk_policy_version=policy.version,
                reservation_lifetime_ns=policy.reservation_lifetime_ns,
                max_active_reservations=policy.max_active_reservations,
                now_ns=clock(),
            )
            execution = DeterministicOfflineExecutionPort(
                (
                    OfflineExecutionDirective(
                        kind=OfflineExecutionDirectiveKind.ACCEPT
                    ),
                    OfflineExecutionDirective(
                        kind=OfflineExecutionDirectiveKind.ACCEPT
                    ),
                )
            )
            runtime = GroupedExecutionRuntime(
                risk_engine=PortfolioRiskEngine(),
                risk_coordinator=coordinator,
                groups=groups,
                execution=execution,
                platform_guard=_AllowSubmitGuard(),
                execution_plan=execution_plan(),
                now_ns=clock,
            )
            runtime.start()
            position_states = {
                account_id: empty_position_state(account_id)
                for account_id in (
                    carry_pair.spot_account_id,
                    carry_pair.perpetual_account_id,
                )
            }
            admission = runtime.admit(
                basket,
                risk_publication(
                    products,
                    tuple(
                        state.view() for state in position_states.values()
                    ),
                ),
                policy,
            )
            assert admission.group is not None
            assert admission.reservation is not None

            position_id = deterministic_application_position_id(
                strategy_id=STRATEGY_ID,
                pair_id=carry_pair.pair_id,
                opening_snapshot_id=OPENING_SNAPSHOT,
            )
            book = CarryPositionBook(
                _MemoryCarryJournal(),
                now_ns=clock,
            )
            created = book.create_position(
                strategy_id=STRATEGY_ID,
                pair_id=carry_pair.pair_id,
                opening_snapshot_id=OPENING_SNAPSHOT,
                ownership=tuple(
                    create_carry_leg_ownership(
                        application_position_id=position_id,
                        account_id=account_id,
                        instrument_id=instrument_id,
                        baseline_quantity=Quantity.from_str("0"),
                        intended_owned_delta=Quantity.from_str(target),
                        effective_from_ns=UnixNanos(1_000),
                        source_snapshot_id=OPENING_SNAPSHOT,
                        policy_version=1,
                    )
                    for account_id, instrument_id, target in basket_targets()
                ),
                occurred_at_ns=UnixNanos(1_000),
                policy_version=1,
            )
            carry = CarryReadSideProjector(book, now_ns=clock)
            carry.link_opening_admission(
                created.application_position_id,
                basket=basket,
                group=admission.group,
            )

            for expected_submission_count in (1, 2):
                step = runtime.execute_next(
                    admission.group.order_group_id,
                    risk_publication(
                        products,
                        tuple(
                            state.view()
                            for state in position_states.values()
                        ),
                        groups=(
                            groups.group(admission.group.order_group_id),
                        ),
                        reservations=(admission.reservation,),
                    ),
                    policy,
                )
                self.assertEqual(
                    step.disposition,
                    GroupedExecutionStepDisposition.ACCEPTED,
                )
                assert step.action is not None
                action_view = next(
                    item
                    for item in step.group.actions
                    if item.action.action_id == step.action.action_id
                )
                clock.step()
                runtime.apply_child_event(
                    OrderEvent(
                        venue_update_id=(
                            f"offline-fill-{expected_submission_count}"
                        ),
                        client_order_id=action_view.child_order_id,
                        status=OrderStatus.FILLED,
                        cumulative_filled_quantity=step.action.quantity,
                        event_time_ns=clock(),
                        venue_order_id=action_view.venue_order_id,
                        average_fill_price=Price.from_str("100"),
                    )
                )
                project_positions(oms_journal, position_states)
                self.assertEqual(
                    len(execution.submissions),
                    expected_submission_count,
                )

            complete = runtime.execute_next(
                admission.group.order_group_id,
                risk_publication(
                    products,
                    tuple(
                        state.view() for state in position_states.values()
                    ),
                    groups=(groups.group(admission.group.order_group_id),),
                    reservations=(admission.reservation,),
                ),
                policy,
            )
            self.assertEqual(
                complete.disposition,
                GroupedExecutionStepDisposition.NO_ACTION,
            )
            result = carry.project(
                created.application_position_id,
                pair=carry_pair,
                positions=tuple(
                    state.view() for state in position_states.values()
                ),
                tolerance_base_quantity=Quantity.from_str("0.001"),
                financial=not_ready_financial(),
                source_snapshot_id=DecisionSnapshotId(
                    "offline-positions-complete"
                ),
                policy_version=1,
            )
            self.assertEqual(result.position.lifecycle, CarryLifecycle.ACTIVE)
            self.assertEqual(result.position.hedge_state, CarryHedgeState.HEDGED)
            self.assertEqual(
                result.position.financial_state,
                CarryFinancialState.NOT_READY,
            )


def basket_targets():
    configured = pair()
    return (
        (
            configured.spot_account_id,
            configured.spot_instrument_id,
            "10",
        ),
        (
            configured.perpetual_account_id,
            configured.perpetual_instrument_id,
            "-10",
        ),
    )


def opening_basket():
    return create_basket_target_intent(
        strategy_id=STRATEGY_ID,
        decision_snapshot_id=OPENING_SNAPSHOT,
        objective=ObjectiveTypeRef(
            objective_type_id=ObjectiveTypeId("carry.open"),
            version=1,
        ),
        legs=tuple(
            BasketTargetLeg(
                leg_id=deterministic_basket_leg_id(
                    decision_snapshot_id=OPENING_SNAPSHOT,
                    account_id=account_id,
                    instrument_id=instrument_id,
                ),
                account_id=account_id,
                instrument_id=instrument_id,
                target_quantity=Quantity.from_str(target),
            )
            for account_id, instrument_id, target in basket_targets()
        ),
        decision_time_ns=UnixNanos(1_000),
        valid_until_ns=UnixNanos(5_000),
        policy_version=1,
        reason="offline Carry open",
    )


def empty_position_state(account_id):
    state = ExecutionConsistentPositionState(account_id)
    state.accept_baseline(
        ReconciledAccountBaseline(
            reconciliation_id=PortfolioReconciliationId(
                f"offline-{account_id}"
            ),
            observation_id=ObservationId(f"offline-{account_id}"),
            account=AccountSnapshot(
                account_id=account_id,
                venue=VenueId("BINANCE"),
                balances=(),
                positions=(),
                as_of_time_ns=UnixNanos(1_950),
                sequence=1,
            ),
            coverage=ExecutionCoverage(
                through_oms_journal_sequence=0
            ),
            reconciled_at_ns=UnixNanos(1_960),
        )
    )
    return state


def project_positions(journal, states) -> None:
    projector = OmsExecutionEffectProjector(journal)
    for account_id, state in states.items():
        coverage = state.view().coverage.through_oms_journal_sequence
        batch = projector.project(
            account_id,
            from_sequence_exclusive=coverage,
        )
        if batch is not None:
            state.apply_execution_batch(batch)


def exact(value: str, *, unit: str, asset=None) -> ExactRiskValue:
    return ExactRiskValue(
        value=FixedPoint.from_str(value),
        unit=unit,
        asset=asset,
        observation_id=ObservationId(f"offline-{unit}"),
        as_of_ns=UnixNanos(1_950),
        valid_until_ns=UnixNanos(5_000),
    )


def sensitivities(products):
    return tuple(
        InstrumentSensitivity(
            instrument_id=item.instrument_id,
            model_version=1,
            risk_factor_id=RISK_FACTOR,
            margin_scope_id=(
                MARGIN_SCOPE
                if item.instrument_id.kind.value == "perpetual"
                else None
            ),
            delta_per_quantity=exact("1", unit="BTC/qty"),
            initial_margin_per_quantity=exact(
                "10" if item.instrument_id.kind.value == "perpetual" else "0",
                unit="USDT/qty",
                asset=REPORTING_ASSET,
            ),
        )
        for item in products
    )


def risk_policy(products):
    configured = pair()
    return PortfolioRiskPolicy(
        version=1,
        reporting_asset=REPORTING_ASSET,
        required_account_ids=tuple(
            sorted(
                (
                    configured.spot_account_id,
                    configured.perpetual_account_id,
                ),
                key=str,
            )
        ),
        required_instrument_ids=tuple(
            sorted((item.instrument_id for item in products), key=str)
        ),
        required_margin_scope_ids=(MARGIN_SCOPE,),
        required_liquidation_references=(),
        supported_model_versions=(1,),
        instrument_models=tuple(
            InstrumentRiskModelPolicy(
                instrument_id=item.instrument_id,
                model_version=1,
                delta_unit="BTC/qty",
                initial_margin_unit="USDT/qty",
            )
            for item in sorted(products, key=lambda item: str(item.instrument_id))
        ),
        factor_limits=(
            RiskFactorLimit(
                risk_factor_id=RISK_FACTOR,
                max_abs_net_delta=FixedPoint.from_str("100"),
                max_gross_delta=FixedPoint.from_str("1000"),
                max_abs_gamma=FixedPoint.from_str("100"),
                max_abs_vega=FixedPoint.from_str("10000"),
            ),
        ),
        spread_limits=(),
        max_gross_notional=Money.from_str("1000000"),
        max_initial_margin=Money.from_str("100000"),
        min_available_margin=Money.from_str("0"),
        min_liquidation_buffer=Rate.from_str("0"),
        max_snapshot_age_ns=DurationNanos(1_000),
        max_mark_age_ns=DurationNanos(1_000),
        max_sensitivity_age_ns=DurationNanos(1_000),
        max_margin_age_ns=DurationNanos(1_000),
        max_liquidation_age_ns=DurationNanos(1_000),
        approval_lifetime_ns=DurationNanos(500),
        permit_lifetime_ns=DurationNanos(100),
        reservation_lifetime_ns=DurationNanos(400),
        max_active_reservations=8,
    )


def risk_publication(
    products,
    positions,
    *,
    groups=(),
    reservations: tuple[PortfolioRiskReservationView, ...] = (),
):
    configured = pair()
    snapshot = PortfolioRiskSnapshot(
        original_decision_snapshot_ids=(OPENING_SNAPSHOT,),
        positions=tuple(sorted(positions, key=lambda item: str(item.account_id))),
        working_orders=(),
        groups=groups,
        margins=(
            MarginScopeSnapshot(
                scope_id=MARGIN_SCOPE,
                observation_id=ObservationId("offline-margin"),
                account_id=configured.perpetual_account_id,
                venue=VenueId("BINANCE"),
                mode=MarginMode.CROSS,
                reporting_asset=REPORTING_ASSET,
                equity=Money.from_str("1200"),
                collateral=(),
                initial_margin=Money.from_str("0"),
                maintenance_margin=Money.from_str("0"),
                available_margin=Money.from_str("1000"),
                margin_ratio=Rate.from_str("0"),
                as_of_ns=UnixNanos(1_950),
                source_update_id="offline-margin",
            ),
        ),
        liquidation_references=(),
        instruments=products,
        marks=tuple(
            RiskMark(
                instrument_id=item.instrument_id,
                price=exact(
                    "100",
                    unit="USDT",
                    asset=REPORTING_ASSET,
                ),
            )
            for item in products
        ),
        sensitivities=sensitivities(products),
        spread_inputs=(),
        active_reservations=reservations,
        health=HealthReport(
            component="offline-risk-inputs",
            status=HealthStatus.HEALTHY,
            observed_at_ns=UnixNanos(2_000),
        ),
    )
    return DecisionSnapshotPublication(
        metadata=DecisionSnapshotMetadata(
            snapshot_id=DecisionSnapshotId("offline-risk"),
            scope="offline-risk",
            snapshot_sequence=1,
            assembled_at_ns=UnixNanos(1_980),
            assembled_at_monotonic_ns=MonotonicNanos(500),
            policy_version=1,
            observation_ids=(ObservationId("offline-risk"),),
            coherence=(),
        ),
        assessment=SnapshotAssessment(
            readiness=SnapshotReadiness.READY,
            issues=(),
            policy_version=1,
        ),
        value=snapshot,
    )


def not_ready_financial() -> CarryFinancialEvidence:
    return CarryFinancialEvidence(
        attribution=None,
        source_proofs=(),
        balance_proofs=(),
        allocation_ids=(),
        ledger=AccountingLedgerView(
            fact_count=0,
            observation_count=0,
            transactions=(),
            balances=(),
            ledger_sequence=0,
            healthy=True,
            error_type=None,
            error_message=None,
        ),
    )


if __name__ == "__main__":
    unittest.main()
