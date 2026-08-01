from __future__ import annotations

import unittest
from dataclasses import replace

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
    CarryLifecycle,
    accounting_owner_for_position,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.applications.carry.state import CarryPositionBook
from cex_quant.core import (
    AssetId,
    AttributionAllocationId,
    FinancialReconciliationId,
    Money,
    ObjectiveTypeId,
    PortfolioApprovalId,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.oms import OrderGroupAdmission
from cex_quant.portfolio import PositionRiskReadiness
from cex_quant.runtime import (
    CarryFinancialEvidence,
    CarryReadSideProjector,
    OrderGroupRuntime,
)
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    BasketTargetLeg,
    ObjectiveTypeRef,
    basket_target_intent_checksum,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)
from tests.carry_test_support import STRATEGY_ID, pair, portfolio
from tests.group_test_support import execution_plan

OPENING_SNAPSHOT = DecisionSnapshotId("carry-projection-opening")


class _MemoryCarryJournal:
    def __init__(self) -> None:
        self.items: list[object] = []

    def read(self):
        yield from self.items

    def append(self, fact: object) -> None:
        self.items.append(fact)


class CarryReadSideProjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock_value = 2_000
        self.carry_pair = pair()
        position_id = deterministic_application_position_id(
            strategy_id=STRATEGY_ID,
            pair_id=self.carry_pair.pair_id,
            opening_snapshot_id=OPENING_SNAPSHOT,
        )
        ownership = tuple(
            create_carry_leg_ownership(
                application_position_id=position_id,
                account_id=account_id,
                instrument_id=instrument_id,
                baseline_quantity=Quantity.from_str("0"),
                intended_owned_delta=Quantity.from_str(delta),
                effective_from_ns=UnixNanos(1_000),
                source_snapshot_id=OPENING_SNAPSHOT,
                policy_version=1,
            )
            for account_id, instrument_id, delta in (
                (
                    self.carry_pair.spot_account_id,
                    self.carry_pair.spot_instrument_id,
                    "10",
                ),
                (
                    self.carry_pair.perpetual_account_id,
                    self.carry_pair.perpetual_instrument_id,
                    "-10",
                ),
            )
        )
        self.book = CarryPositionBook(
            _MemoryCarryJournal(),
            now_ns=self.now,
        )
        self.position = self.book.create_position(
            strategy_id=STRATEGY_ID,
            pair_id=self.carry_pair.pair_id,
            opening_snapshot_id=OPENING_SNAPSHOT,
            ownership=ownership,
            occurred_at_ns=UnixNanos(1_000),
            policy_version=1,
        )
        self.projector = CarryReadSideProjector(self.book, now_ns=self.now)
        self.basket = create_basket_target_intent(
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
                for account_id, instrument_id, target in (
                    (
                        self.carry_pair.spot_account_id,
                        self.carry_pair.spot_instrument_id,
                        "10",
                    ),
                    (
                        self.carry_pair.perpetual_account_id,
                        self.carry_pair.perpetual_instrument_id,
                        "-10",
                    ),
                )
            ),
            decision_time_ns=UnixNanos(1_000),
            valid_until_ns=UnixNanos(5_000),
            policy_version=1,
            reason="open Carry",
        )
        groups = OrderGroupRuntime(now_ns=self.now)
        created = groups.create_group(
            OrderGroupAdmission(
                approval_id=PortfolioApprovalId("carry-projection-approval"),
                basket=self.basket,
                basket_checksum=basket_target_intent_checksum(self.basket),
                approved_at_ns=UnixNanos(1_500),
                valid_until_ns=UnixNanos(5_000),
                risk_policy_version=1,
            ),
            execution_plan(),
        )
        self.group = groups.activate_group(created.order_group_id)

    def now(self) -> UnixNanos:
        self.clock_value += 1
        return UnixNanos(self.clock_value)

    def test_links_admission_and_promotes_only_from_authoritative_views(self) -> None:
        opening = self.projector.link_opening_admission(
            self.position.application_position_id,
            basket=self.basket,
            group=self.group,
        )
        self.assertEqual(opening.lifecycle, CarryLifecycle.OPENING)
        self.assertEqual(opening.intent_ids, (self.basket.intent_id,))
        self.assertEqual(opening.order_group_ids, (self.group.order_group_id,))

        active = self.projector.project(
            self.position.application_position_id,
            pair=self.carry_pair,
            positions=portfolio(
                spot_quantity="10",
                perpetual_quantity="-10",
            ).positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=not_ready_financial(),
            source_snapshot_id=DecisionSnapshotId("positions-ready"),
            policy_version=1,
        )
        self.assertEqual(active.position.lifecycle, CarryLifecycle.ACTIVE)
        self.assertEqual(active.position.hedge_state, CarryHedgeState.HEDGED)
        self.assertEqual(
            active.position.financial_state,
            CarryFinancialState.NOT_READY,
        )

        financially_final = self.projector.project(
            self.position.application_position_id,
            pair=self.carry_pair,
            positions=portfolio(
                spot_quantity="10",
                perpetual_quantity="-10",
            ).positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=reconciled_financial(
                self.position.application_position_id
            ),
            source_snapshot_id=DecisionSnapshotId("financial-ready"),
            policy_version=1,
        )
        self.assertEqual(
            financially_final.position.financial_state,
            CarryFinancialState.RECONCILED,
        )
        self.assertEqual(
            financially_final.position.lifecycle,
            CarryLifecycle.ACTIVE,
        )

    def test_rejected_second_leg_preserves_residual_and_requires_recovery(self) -> None:
        self.projector.link_opening_admission(
            self.position.application_position_id,
            basket=self.basket,
            group=self.group,
        )
        result = self.projector.project(
            self.position.application_position_id,
            pair=self.carry_pair,
            positions=portfolio(
                spot_quantity="10",
                perpetual_quantity="0",
            ).positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=not_ready_financial(),
            source_snapshot_id=DecisionSnapshotId("perpetual-rejected"),
            policy_version=1,
            execution_recovery_reason="perpetual child rejected",
        )
        self.assertEqual(
            result.position.lifecycle,
            CarryLifecycle.RECOVERY_REQUIRED,
        )
        self.assertEqual(result.position.hedge_state, CarryHedgeState.UNHEDGED)
        self.assertEqual(
            result.hedge.signed_residual_base_quantity,
            Quantity.from_str("10"),
        )
        self.assertEqual(
            result.position.financial_state,
            CarryFinancialState.NOT_READY,
        )

    def test_financial_evidence_can_arrive_before_position_reconciliation(
        self,
    ) -> None:
        self.projector.link_opening_admission(
            self.position.application_position_id,
            basket=self.basket,
            group=self.group,
        )
        ready_positions = portfolio(
            spot_quantity="10",
            perpetual_quantity="-10",
        ).positions
        unreconciled_positions = tuple(
            replace(
                item,
                readiness=PositionRiskReadiness.RECOVERY_REQUIRED,
                reason="position baseline unavailable",
            )
            for item in ready_positions
        )
        financial = reconciled_financial(
            self.position.application_position_id
        )
        facts_first = self.projector.project(
            self.position.application_position_id,
            pair=self.carry_pair,
            positions=unreconciled_positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=financial,
            source_snapshot_id=DecisionSnapshotId("facts-first"),
            policy_version=1,
        )
        self.assertEqual(
            facts_first.position.lifecycle,
            CarryLifecycle.RECOVERY_REQUIRED,
        )
        self.assertEqual(
            facts_first.position.hedge_state,
            CarryHedgeState.UNKNOWN,
        )
        self.assertEqual(
            facts_first.position.financial_state,
            CarryFinancialState.RECONCILED,
        )

        positions_second = self.projector.project(
            self.position.application_position_id,
            pair=self.carry_pair,
            positions=ready_positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=financial,
            source_snapshot_id=DecisionSnapshotId("positions-second"),
            policy_version=1,
        )
        self.assertEqual(
            positions_second.position.lifecycle,
            CarryLifecycle.ACTIVE,
        )
        self.assertEqual(
            positions_second.position.hedge_state,
            CarryHedgeState.HEDGED,
        )
        self.assertEqual(
            positions_second.position.financial_state,
            CarryFinancialState.RECONCILED,
        )

    def test_hedged_zero_and_hedged_open_are_not_confused(self) -> None:
        opening = self.projector.link_opening_admission(
            self.position.application_position_id,
            basket=self.basket,
            group=self.group,
        )
        empty = self.projector.project(
            opening.application_position_id,
            pair=self.carry_pair,
            positions=portfolio().positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=not_ready_financial(),
            source_snapshot_id=DecisionSnapshotId("still-empty"),
            policy_version=1,
        )
        self.assertEqual(empty.hedge.state, CarryHedgeState.HEDGED)
        self.assertEqual(empty.position.lifecycle, CarryLifecycle.OPENING)

        active = self.projector.project(
            opening.application_position_id,
            pair=self.carry_pair,
            positions=portfolio(
                spot_quantity="10",
                perpetual_quantity="-10",
            ).positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=not_ready_financial(),
            source_snapshot_id=DecisionSnapshotId("fully-open"),
            policy_version=1,
        )
        closing = self.book.transition(
            active.position.application_position_id,
            lifecycle=CarryLifecycle.CLOSING,
            hedge_state=CarryHedgeState.HEDGED,
            financial_state=active.position.financial_state,
            source_snapshot_id=DecisionSnapshotId("close-requested"),
            occurred_at_ns=self.now(),
            policy_version=1,
        )
        still_open = self.projector.project(
            closing.application_position_id,
            pair=self.carry_pair,
            positions=portfolio(
                spot_quantity="10",
                perpetual_quantity="-10",
            ).positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=not_ready_financial(),
            source_snapshot_id=DecisionSnapshotId("close-not-filled"),
            policy_version=1,
        )
        self.assertEqual(still_open.position.lifecycle, CarryLifecycle.CLOSING)

        closed = self.projector.project(
            closing.application_position_id,
            pair=self.carry_pair,
            positions=portfolio().positions,
            tolerance_base_quantity=Quantity.from_str("0.001"),
            financial=not_ready_financial(),
            source_snapshot_id=DecisionSnapshotId("close-filled"),
            policy_version=1,
        )
        self.assertEqual(closed.position.lifecycle, CarryLifecycle.CLOSED)
        self.assertEqual(closed.position.hedge_state, CarryHedgeState.HEDGED)


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


def reconciled_financial(position_id: str) -> CarryFinancialEvidence:
    ledger = replace(not_ready_financial().ledger, ledger_sequence=1)
    attribution = PnlAttributionView(
        owner=accounting_owner_for_position(position_id),
        interval_start_ns=UnixNanos(1_000),
        interval_end_ns=UnixNanos(2_000),
        reporting_asset=AssetId("USDT"),
        components=(),
        realized_net_pnl=Money.from_str("0"),
        unrealized_change=Money.from_str("0"),
        total_marked_pnl=Money.from_str("0"),
        ledger_sequence=1,
        valuation_snapshot_ids=(DecisionSnapshotId("valuation"),),
        completeness=AttributionCompleteness.COMPLETE,
        issues=(),
    )
    reconciliation_id = FinancialReconciliationId("carry-financial")
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
    balance = BalanceReconciliationProof(
        reconciliation_id=reconciliation_id,
        opening=opening,
        closing=replace(
            opening,
            as_of_ns=UnixNanos(2_000),
            evidence_id="closing",
        ),
        source_completeness=source,
        accepted_movement=Money.from_str("0"),
        expected_closing=Money.from_str("1000"),
        difference=Money.from_str("0"),
        ledger_sequence=1,
        state=ReconciliationState.MATCHED,
    )
    return CarryFinancialEvidence(
        attribution=attribution,
        source_proofs=(source,),
        balance_proofs=(balance,),
        allocation_ids=(AttributionAllocationId("carry-allocation"),),
        ledger=ledger,
    )


if __name__ == "__main__":
    unittest.main()
