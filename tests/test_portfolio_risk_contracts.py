from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from group_test_support import (
    ACCOUNT_ID,
    STRATEGY_ID,
    instrument,
    two_leg_basket,
)
from portfolio_risk_test_support import (
    CROSS_SCOPE,
    NOW,
    REPORTING_ASSET,
    policy,
    portfolio_snapshot,
    position_view,
    product,
    sensitivity,
)

from cex_quant.core import (
    ClientOrderId,
    EventId,
    FixedPoint,
    GroupActionId,
    IntentId,
    MarginScopeId,
    Money,
    OrderGroupId,
    PortfolioApprovalId,
    PortfolioConfirmationId,
    PortfolioReconciliationId,
    PortfolioReservationId,
    Price,
    Quantity,
    Rate,
    RecoveryAuthorizationId,
    RiskDirectiveId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentKind
from cex_quant.portfolio import (
    AccountPositionRiskView,
    CollateralAssetSnapshot,
    ExecutionCoverage,
    ExecutionPositionEffect,
    ExecutionPositionEffectBatch,
    InstrumentPositionRiskView,
    MarginMode,
    MarginScopeSnapshot,
    PositionLiquidationReference,
    PositionRiskReadiness,
)
from cex_quant.risk import (
    BasketPortfolioRiskDecision,
    ExactRiskValue,
    GroupRecoveryAuthorization,
    JsonLinesPortfolioRiskJournal,
    PortfolioApprovalEvidence,
    PortfolioExposure,
    PortfolioRiskDecisionStatus,
    PortfolioRiskDirective,
    PortfolioRiskDirectiveKind,
    PortfolioRiskJournalEntry,
    PortfolioRiskJournalEntryKind,
    PortfolioRiskJournalIntegrityError,
    PortfolioRiskPolicy,
    PortfolioRiskReservationState,
    PortfolioRiskReservationView,
    PortfolioTargetConfirmation,
    RecoveryAuthorizationMode,
)
from cex_quant.snapshots import DecisionSnapshotId, ObservationId


class PortfolioInputContractTests(unittest.TestCase):
    def test_position_coverage_contracts_reject_ambiguous_evidence(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionCoverage(through_oms_journal_sequence=-1)
        with self.assertRaises(ValueError):
            InstrumentPositionRiskView(
                instrument_id=instrument(InstrumentKind.SPOT, "BTCUSDT"),
                baseline_quantity=Quantity.from_str("1"),
                post_baseline_fill_delta=Quantity.from_str("1"),
                effective_quantity=Quantity.from_str("3"),
            )
        with self.assertRaises(ValueError):
            AccountPositionRiskView(
                account_id=ACCOUNT_ID,
                reconciliation_id=None,
                observation_id=None,
                coverage=ExecutionCoverage(
                    through_oms_journal_sequence=1
                ),
                positions=(),
                readiness=PositionRiskReadiness.READY,
            )
        with self.assertRaises(ValueError):
            AccountPositionRiskView(
                account_id=ACCOUNT_ID,
                reconciliation_id=None,
                observation_id=None,
                coverage=ExecutionCoverage(
                    through_oms_journal_sequence=1
                ),
                positions=(),
                readiness=PositionRiskReadiness.DIVERGENT,
            )

    def test_execution_effect_and_batch_bounds(self) -> None:
        base = ExecutionPositionEffect(
            effect_id=EventId("fill-1"),
            oms_journal_sequence=2,
            client_order_id=ClientOrderId("child-1"),
            account_id=ACCOUNT_ID,
            instrument_id=instrument(InstrumentKind.SPOT, "BTCUSDT"),
            cumulative_filled_quantity=Quantity.from_str("1"),
            signed_fill_delta=Quantity.from_str("1"),
            accepted_at_ns=UnixNanos(10),
        )
        invalid_changes = (
            {"oms_journal_sequence": 0},
            {
                "signed_fill_delta": replace(
                    base.signed_fill_delta,
                    raw=0,
                )
            },
            {
                "cumulative_filled_quantity": replace(
                    base.cumulative_filled_quantity,
                    raw=0,
                )
            },
        )
        for changes in invalid_changes:
            with (
                self.subTest(changes=changes),
                self.assertRaises(ValueError),
            ):
                replace(base, **changes)
        with self.assertRaises(ValueError):
            ExecutionPositionEffectBatch(
                from_sequence_exclusive=2,
                through_sequence_inclusive=2,
                effects=(),
            )
        with self.assertRaises(ValueError):
            ExecutionPositionEffectBatch(
                from_sequence_exclusive=2,
                through_sequence_inclusive=3,
                effects=(base,),
            )

    def test_margin_and_liquidation_inputs_fail_closed(self) -> None:
        collateral = CollateralAssetSnapshot(
            asset=REPORTING_ASSET,
            total=Money.from_str("10"),
            available=Money.from_str("8"),
            borrowed=Money.from_str("0"),
            accrued_interest=Money.from_str("0"),
            collateral_value=Money.from_str("8"),
        )
        with self.assertRaises(ValueError):
            replace(collateral, available=Money.from_str("11"))
        margin = MarginScopeSnapshot(
            scope_id=CROSS_SCOPE,
            observation_id=ObservationId("margin"),
            account_id=ACCOUNT_ID,
            venue=VenueId("BINANCE"),
            mode=MarginMode.CROSS,
            reporting_asset=REPORTING_ASSET,
            equity=Money.from_str("10"),
            collateral=(collateral,),
            initial_margin=Money.from_str("1"),
            maintenance_margin=Money.from_str("0.5"),
            available_margin=Money.from_str("9"),
            margin_ratio=Rate.from_str("0.1"),
            as_of_ns=UnixNanos(10),
            source_update_id="update",
        )
        with self.assertRaises(ValueError):
            replace(margin, collateral=(collateral, collateral))
        with self.assertRaises(ValueError):
            replace(margin, initial_margin=Money.from_str("-1"))
        liquidation = PositionLiquidationReference(
            observation_id=ObservationId("liq"),
            account_id=ACCOUNT_ID,
            instrument_id=instrument(
                InstrumentKind.PERPETUAL,
                "BTCUSDT",
            ),
            liquidation_price=Price.from_str("80"),
            maintenance_margin=Money.from_str("1"),
            as_of_ns=UnixNanos(10),
        )
        with self.assertRaises(ValueError):
            replace(liquidation, liquidation_price=Price.from_str("0"))
        with self.assertRaises(ValueError):
            replace(liquidation, maintenance_margin=Money.from_str("-1"))


class PortfolioRiskContractTests(unittest.TestCase):
    def _base_policy(self) -> PortfolioRiskPolicy:
        spot = product(InstrumentKind.SPOT, "BTCUSDT")
        perp = product(InstrumentKind.PERPETUAL, "BTCUSDT")
        return policy((spot, perp))

    def test_exact_values_policy_and_reservation_invariants(self) -> None:
        value = ExactRiskValue(
            value=FixedPoint.from_str("1"),
            unit="BTC",
            observation_id=ObservationId("value"),
            as_of_ns=UnixNanos(10),
            valid_until_ns=UnixNanos(20),
        )
        with self.assertRaises(ValueError):
            replace(value, valid_until_ns=UnixNanos(9))
        base_policy = self._base_policy()
        invalid_policy_changes = (
            {"version": 0},
            {"supported_model_versions": ()},
            {"max_snapshot_age_ns": 0},
            {"max_active_reservations": 0},
            {
                "required_margin_scope_ids": (
                    MarginScopeId("z"),
                    MarginScopeId("a"),
                )
            },
        )
        for changes in invalid_policy_changes:
            with (
                self.subTest(changes=changes),
                self.assertRaises(ValueError),
            ):
                replace(base_policy, **changes)

        basket = two_leg_basket()
        with self.assertRaises(ValueError):
            PortfolioRiskReservationView(
                reservation_id=PortfolioReservationId("reservation"),
                approval_id=PortfolioApprovalId("approval"),
                strategy_id=STRATEGY_ID,
                basket=basket,
                state=PortfolioRiskReservationState.ATTACHED_TO_GROUP,
                created_at_ns=UnixNanos(10),
                valid_until_ns=UnixNanos(20),
            )
        active = PortfolioRiskReservationView(
            reservation_id=PortfolioReservationId("reservation"),
            approval_id=PortfolioApprovalId("approval"),
            strategy_id=STRATEGY_ID,
            basket=basket,
            state=PortfolioRiskReservationState.ACTIVE,
            created_at_ns=UnixNanos(10),
            valid_until_ns=UnixNanos(20),
        )
        self.assertTrue(active.active)
        self.assertFalse(
            replace(
                active,
                state=PortfolioRiskReservationState.RELEASED,
            ).active
        )

    def test_decision_directive_recovery_and_confirmation_invariants(self) -> None:
        basket = two_leg_basket()
        exposure = PortfolioExposure(
            reporting_asset=REPORTING_ASSET,
            gross_notional=Money.from_str("0"),
            initial_margin=Money.from_str("0"),
            available_margin=Money.from_str("1"),
            factors=(),
            margin_scopes=(),
        )
        approval = PortfolioApprovalEvidence(
            approval_id=PortfolioApprovalId("a"),
            basket_intent_id=basket.intent_id,
            basket_checksum="a" * 64,
            risk_snapshot_id=DecisionSnapshotId("risk"),
            assessment_checksum="b" * 64,
            approved_at_ns=UnixNanos(1),
            valid_until_ns=UnixNanos(2),
            risk_policy_version=1,
        )
        allowed = BasketPortfolioRiskDecision(
            status=PortfolioRiskDecisionStatus.ALLOW,
            basket=basket,
            risk_snapshot_id=DecisionSnapshotId("risk"),
            risk_policy_version=1,
            reasons=(),
            current_exposure=exposure,
            projected_exposure=exposure,
            conservative_exposure=exposure,
            approval=approval,
        )
        self.assertTrue(allowed.allowed)
        with self.assertRaises(ValueError):
            replace(allowed, approval=None)
        with self.assertRaises(ValueError):
            PortfolioRiskDirective(
                directive_id=RiskDirectiveId("directive"),
                group_id=OrderGroupId("group"),
                expected_group_revision=1,
                risk_snapshot_id=DecisionSnapshotId("risk"),
                kind=PortfolioRiskDirectiveKind.BLOCK_NEW_ACTIONS,
                reasons=(),
                issued_at_ns=UnixNanos(1),
                risk_policy_version=1,
            )
        with self.assertRaises(ValueError):
            GroupRecoveryAuthorization(
                authorization_id=RecoveryAuthorizationId("recovery"),
                group_id=OrderGroupId("group"),
                expected_group_revision=1,
                mode=RecoveryAuthorizationMode.RESUME_GROUP,
                reconciliation_id=PortfolioReconciliationId("recon"),
                risk_snapshot_id=DecisionSnapshotId("risk"),
                issued_at_ns=UnixNanos(1),
                valid_until_ns=UnixNanos(2),
                risk_policy_version=1,
                action_id=GroupActionId("action"),
            )
        with self.assertRaises(ValueError):
            PortfolioTargetConfirmation(
                confirmation_id=PortfolioConfirmationId("confirmation"),
                group_id=OrderGroupId("group"),
                expected_group_revision=0,
                basket_intent_id=IntentId("basket"),
                risk_snapshot_id=DecisionSnapshotId("risk"),
                confirmed_at_ns=UnixNanos(1),
                risk_policy_version=1,
            )

    def test_snapshot_duplicate_sources_are_rejected(self) -> None:
        spot = product(InstrumentKind.SPOT, "BTCUSDT")
        sensitivity_value = sensitivity(
            spot.instrument_id,
            delta="1",
            margin="0",
        )
        snapshot = portfolio_snapshot((spot,), (sensitivity_value,))
        with self.assertRaises(ValueError):
            replace(snapshot, instruments=(spot, spot))
        with self.assertRaises(ValueError):
            replace(
                snapshot,
                positions=(position_view(), position_view()),
            )


class PortfolioRiskJournalContractTests(unittest.TestCase):
    def test_context_manager_roundtrip_and_truncation_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "risk.jsonl"
            entry = PortfolioRiskJournalEntry(
                kind=(
                    PortfolioRiskJournalEntryKind.AUTHORIZATION_GENERATION_CHANGED
                ),
                at_ns=NOW,
                payload={"generation": 2, "reason": "policy update"},
            )
            with JsonLinesPortfolioRiskJournal(path) as journal:
                journal.append(entry)
                self.assertEqual(tuple(journal.read()), (entry,))
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(PortfolioRiskJournalIntegrityError):
                JsonLinesPortfolioRiskJournal(path)

    def test_entry_and_constructor_bounds(self) -> None:
        with self.assertRaises(ValueError):
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.PERMIT_CONSUMED,
                at_ns=UnixNanos(-1),
                payload={"permit_id": "permit"},
            )
        with self.assertRaises(ValueError):
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.PERMIT_CONSUMED,
                at_ns=UnixNanos(1),
                payload={},
            )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "risk.jsonl"
            with self.assertRaises(ValueError):
                JsonLinesPortfolioRiskJournal(path, max_records=0)


if __name__ == "__main__":
    unittest.main()
