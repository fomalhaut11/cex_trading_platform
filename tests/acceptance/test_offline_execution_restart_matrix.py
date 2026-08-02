from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_quant.accounting.journal import JsonLinesAccountingJournal
from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.applications.carry.journal import JsonLinesCarryJournal
from cex_quant.applications.carry.state import CarryPositionBook
from cex_quant.core import (
    IntentId,
    PortfolioReconciliationId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentKind
from cex_quant.oms import (
    JsonLinesOmsJournal,
    OrderEvent,
    OrderStatus,
)
from cex_quant.portfolio import (
    AccountSnapshot,
    ExecutionConsistentPositionState,
    ExecutionCoverage,
    ReconciledAccountBaseline,
)
from cex_quant.risk import (
    JsonLinesPortfolioRiskJournal,
    PortfolioRiskCoordinator,
    PortfolioRiskEngine,
)
from cex_quant.runtime import (
    GROUPED_BOOTSTRAP_ORDER,
    DeterministicOfflineExecutionPort,
    GroupedBootstrapEvidence,
    GroupedExecutionRuntime,
    GroupedExecutionRuntimeStateError,
    GroupedExecutionRuntimeStatus,
    OfflineExecutionDirective,
    OfflineExecutionDirectiveKind,
    OmsExecutionEffectProjector,
    OrderGroupRuntime,
)
from cex_quant.snapshots import DecisionSnapshotId, ObservationId
from tests.carry_test_support import STRATEGY_ID, pair
from tests.group_test_support import (
    ACCOUNT_ID,
    ManualClock,
    action_for,
    admission,
    execution_plan,
    permit_for,
)
from tests.portfolio_risk_test_support import NOW, policy, product
from tests.test_accounting_journal import ledger, observed


class _AllowSubmitGuard:
    def assert_submit_allowed(self, request: object) -> None:
        del request


class OfflineExecutionRestartMatrixTests(unittest.TestCase):
    def test_every_durable_non_terminal_boundary_replays_fail_closed(
        self,
    ) -> None:
        cases = {
            "created": GroupedExecutionRuntimeStatus.HALTED,
            "active": GroupedExecutionRuntimeStatus.HALTED,
            "suspended": GroupedExecutionRuntimeStatus.HALTED,
            "closing": GroupedExecutionRuntimeStatus.HALTED,
            "prepared": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
            "transmitting": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
            "submitting": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
            "open": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
            "partially_filled": (
                GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED
            ),
            "cancel_pending": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
            "retry_eligible": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
            "unknown": GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        }
        for boundary, expected_status in cases.items():
            with self.subTest(boundary=boundary):
                self._assert_boundary(boundary, expected_status)

    def test_restart_rebuilds_oms_portfolio_carry_and_accounting_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oms_path = root / "oms.jsonl"
            carry_path = root / "carry.jsonl"
            accounting_path = root / "accounting.jsonl"
            clock = ManualClock(value=int(NOW))

            with JsonLinesOmsJournal(oms_path) as oms_journal:
                groups = OrderGroupRuntime(
                    now_ns=clock,
                    journal=oms_journal,
                )
                group = _persist_boundary(groups, "partially_filled", clock)
                expected_group = groups.group(group.order_group_id)
                first_positions = _rebuild_position(oms_journal)
                expected_position = first_positions.view()

            configured_pair = pair()
            opening_snapshot = DecisionSnapshotId("a018-opening")
            position_id = deterministic_application_position_id(
                strategy_id=STRATEGY_ID,
                pair_id=configured_pair.pair_id,
                opening_snapshot_id=opening_snapshot,
            )
            ownership = tuple(
                create_carry_leg_ownership(
                    application_position_id=position_id,
                    account_id=account_id,
                    instrument_id=instrument_id,
                    baseline_quantity=Quantity.from_str("0"),
                    intended_owned_delta=Quantity.from_str(delta),
                    effective_from_ns=UnixNanos(1_000),
                    source_snapshot_id=opening_snapshot,
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
            with JsonLinesCarryJournal(carry_path) as carry_journal:
                carry = CarryPositionBook(carry_journal, now_ns=clock)
                created = carry.create_position(
                    strategy_id=STRATEGY_ID,
                    pair_id=configured_pair.pair_id,
                    opening_snapshot_id=opening_snapshot,
                    ownership=ownership,
                    occurred_at_ns=UnixNanos(1_000),
                    policy_version=1,
                )
                carry.link_intent(
                    created.application_position_id,
                    intent_id=IntentId("a018-open-intent"),
                    source_snapshot_id=opening_snapshot,
                    occurred_at_ns=UnixNanos(1_100),
                    policy_version=1,
                )
                expected_carry = carry.transition(
                    created.application_position_id,
                    lifecycle=CarryLifecycle.OPENING,
                    hedge_state=CarryHedgeState.PARTIALLY_HEDGED,
                    financial_state=CarryFinancialState.PROVISIONAL,
                    source_snapshot_id=DecisionSnapshotId("a018-partial"),
                    occurred_at_ns=UnixNanos(1_200),
                    policy_version=1,
                )

            with JsonLinesAccountingJournal(accounting_path) as journal:
                accounting = ledger(journal)
                accounting.ingest(
                    observed(),
                    posted_at_ns=UnixNanos(2_100),
                )
                expected_ledger = accounting.view()

            with JsonLinesOmsJournal(oms_path) as replay_oms:
                replayed_groups = OrderGroupRuntime(
                    now_ns=clock,
                    journal=replay_oms,
                )
                replayed_position = _rebuild_position(replay_oms).view()
                self.assertEqual(
                    replayed_groups.group(expected_group.order_group_id),
                    expected_group,
                )
                self.assertEqual(replayed_position, expected_position)
            with JsonLinesCarryJournal(carry_path) as replay_carry:
                replayed_book = CarryPositionBook(
                    replay_carry,
                    now_ns=clock,
                )
                self.assertEqual(
                    replayed_book.position(expected_carry.application_position_id),
                    expected_carry,
                )
            with JsonLinesAccountingJournal(accounting_path) as replay_accounting:
                self.assertEqual(
                    ledger(replay_accounting).view(),
                    expected_ledger,
                )

    def _assert_boundary(
        self,
        boundary: str,
        expected_status: GroupedExecutionRuntimeStatus,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oms_path = root / "oms.jsonl"
            risk_path = root / "risk.jsonl"
            clock = ManualClock(value=int(NOW))
            with JsonLinesOmsJournal(oms_path) as first_journal:
                first = OrderGroupRuntime(
                    now_ns=clock,
                    journal=first_journal,
                )
                expected = _persist_boundary(first, boundary, clock)

            with JsonLinesOmsJournal(oms_path) as replay_journal:
                replayed = OrderGroupRuntime(
                    now_ns=clock,
                    journal=replay_journal,
                )
                actual = replayed.group(expected.order_group_id)
                self.assertEqual(actual, expected)

                risk_journal = JsonLinesPortfolioRiskJournal(risk_path)
                try:
                    instruments = (
                        product(InstrumentKind.SPOT, "BTCUSDT"),
                        product(InstrumentKind.PERPETUAL, "BTCUSDT"),
                    )
                    risk_policy = policy(instruments)
                    coordinator = PortfolioRiskCoordinator(
                        journal=risk_journal,
                        risk_policy_version=risk_policy.version,
                        reservation_lifetime_ns=(
                            risk_policy.reservation_lifetime_ns
                        ),
                        max_active_reservations=(
                            risk_policy.max_active_reservations
                        ),
                        now_ns=clock(),
                    )
                    execution = DeterministicOfflineExecutionPort(
                        (
                            OfflineExecutionDirective(
                                kind=OfflineExecutionDirectiveKind.ACCEPT
                            ),
                        )
                    )
                    runtime = GroupedExecutionRuntime(
                        risk_engine=PortfolioRiskEngine(),
                        risk_coordinator=coordinator,
                        groups=replayed,
                        execution=execution,
                        platform_guard=_AllowSubmitGuard(),
                        execution_plan=execution_plan(),
                        now_ns=clock,
                    )
                    runtime.start()
                    self.assertEqual(runtime.status, expected_status)
                    self.assertEqual(execution.submissions, ())

                    evidence = GroupedBootstrapEvidence(
                        completed_steps=GROUPED_BOOTSTRAP_ORDER,
                        external_io_disabled=True,
                        healthy=True,
                    )
                    if boundary == "active":
                        runtime.complete_bootstrap(evidence)
                        self.assertEqual(
                            runtime.status,
                            GroupedExecutionRuntimeStatus.RUNNING,
                        )
                    else:
                        with self.assertRaises(
                            GroupedExecutionRuntimeStateError
                        ):
                            runtime.complete_bootstrap(
                                evidence,
                                recovery_authorization_id="offline-recovery",
                            )
                    self.assertEqual(execution.submissions, ())
                finally:
                    risk_journal.close()


def _persist_boundary(
    groups: OrderGroupRuntime,
    boundary: str,
    clock: ManualClock,
):
    created = groups.create_group(admission(), execution_plan())
    if boundary == "created":
        return created
    active = groups.activate_group(created.order_group_id)
    if boundary == "active":
        return active
    if boundary == "suspended":
        return groups.suspend_group(
            active.order_group_id,
            reason="offline restart matrix",
        )
    if boundary == "closing":
        return groups.begin_closing(active.order_group_id)

    action = action_for(
        active,
        leg_index=0,
        now_ns=clock.step(),
        quantity="10",
    )
    permit = permit_for(action, issued_at_ns=clock.step())
    request = groups.prepare_child_submit(action=action, permit=permit)
    if boundary == "prepared":
        return groups.group(active.order_group_id)
    groups.mark_transmitting(active.order_group_id, action.action_id)
    if boundary == "transmitting":
        return groups.group(active.order_group_id)
    if boundary == "retry_eligible":
        return groups.record_definitely_not_sent(
            active.order_group_id,
            action.action_id,
            reason="offline transport unavailable",
        )
    if boundary == "unknown":
        return groups.record_unknown(
            active.order_group_id,
            action.action_id,
            reason="offline outcome unknown",
        )
    acknowledged = groups.record_acknowledged(
        active.order_group_id,
        action.action_id,
        venue_order_id=VenueOrderId("offline-order"),
    )
    if boundary == "submitting":
        return acknowledged
    clock.step()
    opened = groups.apply_child_event(
        OrderEvent(
            venue_update_id="offline-open",
            client_order_id=request.client_order_id,
            status=OrderStatus.OPEN,
            cumulative_filled_quantity=Quantity.from_str("0"),
            event_time_ns=clock(),
            venue_order_id=VenueOrderId("offline-order"),
        )
    )
    if boundary == "open":
        return opened
    clock.step()
    partially_filled = groups.apply_child_event(
        OrderEvent(
            venue_update_id="offline-partial",
            client_order_id=request.client_order_id,
            status=OrderStatus.PARTIALLY_FILLED,
            cumulative_filled_quantity=Quantity.from_str("4"),
            event_time_ns=clock(),
            venue_order_id=VenueOrderId("offline-order"),
            average_fill_price=Price.from_str("100"),
        )
    )
    if boundary == "partially_filled":
        return partially_filled
    if boundary == "cancel_pending":
        clock.step()
        return groups.apply_child_event(
            OrderEvent(
                venue_update_id="offline-cancel-pending",
                client_order_id=request.client_order_id,
                status=OrderStatus.CANCEL_PENDING,
                cumulative_filled_quantity=Quantity.from_str("4"),
                event_time_ns=clock(),
                venue_order_id=VenueOrderId("offline-order"),
                average_fill_price=Price.from_str("100"),
            )
        )
    raise AssertionError(f"unsupported restart boundary: {boundary}")


def _rebuild_position(journal: JsonLinesOmsJournal):
    state = ExecutionConsistentPositionState(ACCOUNT_ID)
    state.accept_baseline(
        ReconciledAccountBaseline(
            reconciliation_id=PortfolioReconciliationId("a018-baseline"),
            observation_id=ObservationId("a018-account"),
            account=AccountSnapshot(
                account_id=ACCOUNT_ID,
                venue=VenueId("BINANCE"),
                balances=(),
                positions=(),
                as_of_time_ns=UnixNanos(1_900),
                sequence=1,
            ),
            coverage=ExecutionCoverage(
                through_oms_journal_sequence=0,
            ),
            reconciled_at_ns=UnixNanos(1_950),
        )
    )
    batch = OmsExecutionEffectProjector(journal).project(
        ACCOUNT_ID,
        from_sequence_exclusive=0,
    )
    assert batch is not None
    state.apply_execution_batch(batch)
    return state


if __name__ == "__main__":
    unittest.main()
