from dataclasses import replace
from unittest import TestCase

from carry_test_support import STRATEGY_ID, pair, portfolio

from cex_quant.accounting import (
    AccountingLedgerView,
    AttributionCompleteness,
    AuthoritativeBalance,
    BalanceReconciliationProof,
    FinancialSourceKind,
    PnlAttributionView,
    ReconciliationState,
    SourceCompletenessProof,
)
from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeState,
    CarryRecoveryKind,
    CarryRecoveryProposal,
    accounting_owner_for_position,
    assess_carry_financial_state,
    assess_linear_funding_carry_hedge,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.core import (
    AssetId,
    AttributionAllocationId,
    FinancialReconciliationId,
    Money,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.portfolio import PositionRiskReadiness
from cex_quant.snapshots import DecisionSnapshotId


def ownership():
    configured_pair = pair()
    snapshot_id = DecisionSnapshotId("opening-snapshot")
    position_id = deterministic_application_position_id(
        strategy_id=STRATEGY_ID,
        pair_id=configured_pair.pair_id,
        opening_snapshot_id=snapshot_id,
    )
    return tuple(
        create_carry_leg_ownership(
            application_position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            baseline_quantity=Quantity.from_str("0"),
            intended_owned_delta=Quantity.from_str(delta),
            effective_from_ns=UnixNanos(1_000),
            source_snapshot_id=snapshot_id,
            policy_version=1,
        )
        for account_id, instrument_id, delta in (
            (
                configured_pair.spot_account_id,
                configured_pair.spot_instrument_id,
                "10",
            ),
            (
                configured_pair.perpetual_account_id,
                configured_pair.perpetual_instrument_id,
                "-10",
            ),
        )
    )


class CarryHedgeAssessmentTests(TestCase):
    def assess(self, *, spot: str, perpetual: str):
        return assess_linear_funding_carry_hedge(
            pair=pair(),
            ownership=ownership(),
            positions=portfolio(
                spot_quantity=spot,
                perpetual_quantity=perpetual,
            ).positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            assessed_at_ns=UnixNanos(2_000),
            policy_version=1,
        )

    def test_full_one_sided_and_reverse_residual_scenarios(self) -> None:
        hedged = self.assess(spot="10", perpetual="-10")
        one_sided = self.assess(spot="10", perpetual="0")
        reverse = self.assess(spot="5", perpetual="-10")

        self.assertEqual(hedged.state, CarryHedgeState.HEDGED)
        self.assertEqual(
            hedged.signed_residual_base_quantity,
            Quantity.from_str("0"),
        )
        self.assertEqual(one_sided.state, CarryHedgeState.UNHEDGED)
        self.assertEqual(
            one_sided.signed_residual_base_quantity,
            Quantity.from_str("10"),
        )
        self.assertEqual(reverse.state, CarryHedgeState.PARTIALLY_HEDGED)
        self.assertEqual(
            reverse.signed_residual_base_quantity,
            Quantity.from_str("-5"),
        )

    def test_unreconciled_portfolio_is_unknown_not_oms_failure(self) -> None:
        views = portfolio(
            spot_quantity="10",
            perpetual_quantity="-10",
        ).positions
        broken = (
            replace(
                views[0],
                readiness=PositionRiskReadiness.RECOVERY_REQUIRED,
                reason="cursor unresolved",
            ),
            views[1],
        )

        result = assess_linear_funding_carry_hedge(
            pair=pair(),
            ownership=ownership(),
            positions=broken,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            assessed_at_ns=UnixNanos(2_000),
            policy_version=1,
        )

        self.assertEqual(result.state, CarryHedgeState.UNKNOWN)
        self.assertIsNone(result.signed_residual_base_quantity)
        self.assertIn("Portfolio", result.reason)


class CarryFinancialAndRecoveryTests(TestCase):
    def test_only_complete_accounting_evidence_promotes_reconciled(self) -> None:
        owner = accounting_owner_for_position(
            ownership()[0].application_position_id
        )
        ledger = AccountingLedgerView(
            fact_count=1,
            observation_count=2,
            transactions=(),
            balances=(),
            ledger_sequence=1,
            healthy=True,
            error_type=None,
            error_message=None,
        )
        attribution = PnlAttributionView(
            owner=owner,
            interval_start_ns=UnixNanos(1_000),
            interval_end_ns=UnixNanos(2_000),
            reporting_asset=AssetId("USDT"),
            components=(),
            realized_net_pnl=Money.from_str("10"),
            unrealized_change=Money.from_str("0"),
            total_marked_pnl=Money.from_str("10"),
            ledger_sequence=1,
            valuation_snapshot_ids=(DecisionSnapshotId("valuation-1"),),
            completeness=AttributionCompleteness.COMPLETE,
            issues=(),
        )
        source, balance = reconciliation()

        complete = assess_carry_financial_state(
            attribution=attribution,
            source_proofs=(source,),
            balance_proofs=(balance,),
            allocation_ids=(AttributionAllocationId("allocation-1"),),
            ledger=ledger,
        )
        provisional = assess_carry_financial_state(
            attribution=attribution,
            source_proofs=(source,),
            balance_proofs=(balance,),
            allocation_ids=(),
            ledger=ledger,
        )
        unavailable = assess_carry_financial_state(
            attribution=attribution,
            source_proofs=(source,),
            balance_proofs=(balance,),
            allocation_ids=(AttributionAllocationId("allocation-1"),),
            ledger=replace(
                ledger,
                healthy=False,
                error_type="IoError",
                error_message="unavailable",
            ),
        )

        self.assertEqual(complete, CarryFinancialState.RECONCILED)
        self.assertEqual(provisional, CarryFinancialState.PROVISIONAL)
        self.assertEqual(unavailable, CarryFinancialState.NOT_READY)

    def test_recovery_proposal_is_not_order_or_execution_permission(self) -> None:
        position_id = ownership()[0].application_position_id
        proposal = CarryRecoveryProposal(
            application_position_id=position_id,
            kind=CarryRecoveryKind.WAIT_FOR_FACT_RECONCILIATION,
            source_snapshot_id=DecisionSnapshotId("recovery-snapshot"),
            proposed_target=None,
            proposed_at_ns=UnixNanos(2_000),
            policy_version=1,
            reason="child outcome remains unknown",
        )

        self.assertIsNone(proposal.proposed_target)
        self.assertFalse(hasattr(proposal, "permit"))
        self.assertFalse(hasattr(proposal, "order_request"))
        with self.assertRaisesRegex(ValueError, "requires exactly one"):
            CarryRecoveryProposal(
                application_position_id=position_id,
                kind=CarryRecoveryKind.FLATTEN_TO_BASELINE,
                source_snapshot_id=DecisionSnapshotId("recovery-snapshot"),
                proposed_target=None,
                proposed_at_ns=UnixNanos(2_000),
                policy_version=1,
                reason="flatten preferred",
            )


def reconciliation():
    reconciliation_id = FinancialReconciliationId("financial-reconciliation")
    source = SourceCompletenessProof(
        reconciliation_id=reconciliation_id,
        venue=VenueId("BINANCE"),
        account_id=pair().perpetual_account_id,
        source_kind=FinancialSourceKind.AUTHENTICATED_HISTORY,
        window_start_ns=UnixNanos(1_000),
        window_end_ns=UnixNanos(2_000),
        fact_ids=(),
        start_cursor="start",
        end_cursor="end",
        exhausted=True,
    )
    opening = AuthoritativeBalance(
        venue=VenueId("BINANCE"),
        account_id=pair().perpetual_account_id,
        asset=AssetId("USDT"),
        amount=Money.from_str("1000"),
        as_of_ns=UnixNanos(1_000),
        evidence_id="opening",
    )
    closing = replace(
        opening,
        as_of_ns=UnixNanos(2_000),
        evidence_id="closing",
    )
    balance = BalanceReconciliationProof(
        reconciliation_id=reconciliation_id,
        opening=opening,
        closing=closing,
        source_completeness=source,
        accepted_movement=Money.from_str("0"),
        expected_closing=Money.from_str("1000"),
        difference=Money.from_str("0"),
        ledger_sequence=1,
        state=ReconciliationState.MATCHED,
    )
    return source, balance


if __name__ == "__main__":
    import unittest

    unittest.main()
