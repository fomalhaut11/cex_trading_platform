import json
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

from group_test_support import (
    ManualClock,
    action_for,
    admission,
    execution_plan,
    permit_for,
)

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.execution import ExecutionOutcome, SubmitResult
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    JsonLinesOmsJournal,
    OmsJournal,
    OmsJournalEntry,
    OmsJournalIntegrityError,
    OrderEvent,
    OrderReconciliationSnapshot,
    OrderSide,
    OrderStatus,
    OrderSubmitOutcome,
    OrderType,
    ReconciliationDisposition,
    ReconciliationSource,
)
from cex_quant.risk import RiskDecision, RiskDecisionStatus
from cex_quant.runtime import (
    CanonicalOmsApplicationService,
    DurableExecutionHandoff,
    OmsPersistenceError,
    OrderGroupRuntime,
    OrderParameters,
)
from cex_quant.strategy import PositionTargetIntent

INSTRUMENT = InstrumentId(
    venue=VenueId("TEST"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)


def intent() -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId("intent-1"),
        strategy_id=StrategyId("strategy-1"),
        instrument_id=INSTRUMENT,
        target_quantity=Quantity.from_str("10"),
        decision_time_ns=UnixNanos(100),
        valid_until_ns=UnixNanos(1_000),
    )


def decision() -> RiskDecision:
    value = intent()
    return RiskDecision(
        status=RiskDecisionStatus.ALLOW,
        intent=value,
        reasons=(),
        projected_strategy_position=value.target_quantity,
        projected_global_position=value.target_quantity,
        projected_strategy_notional=None,
        projected_global_notional=None,
    )


class _Accounts:
    def account_id(self, value: PositionTargetIntent) -> AccountId:
        del value
        return AccountId("primary")


class _Identities:
    def approval_id(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> str:
        del value, approval
        return "approval-1"

    def client_order_id(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> ClientOrderId:
        del value, approval
        return ClientOrderId("client-1")


class _Orders:
    def parameters(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> OrderParameters:
        del value, approval
        return OrderParameters(
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Quantity.from_str("10"),
            limit_price=Price.from_str("100"),
        )


class _FailingJournal:
    def read(self) -> Iterator[OmsJournalEntry]:
        return iter(())

    def append(self, entry: OmsJournalEntry) -> None:
        del entry
        raise OSError("disk full")


class _NthFailJournal:
    def __init__(self, *, fail_at: int) -> None:
        self.entries: list[OmsJournalEntry] = []
        self.fail_at: int | None = fail_at

    def read(self) -> Iterator[OmsJournalEntry]:
        return iter(tuple(self.entries))

    def append(self, entry: OmsJournalEntry) -> None:
        if self.fail_at is not None and len(self.entries) + 1 == self.fail_at:
            raise OSError("injected journal failure")
        self.entries.append(entry)


def service(
    journal: OmsJournal,
) -> CanonicalOmsApplicationService:
    return CanonicalOmsApplicationService(
        accounts=_Accounts(),
        identities=_Identities(),
        orders=_Orders(),
        now_ns=lambda: UnixNanos(150),
        journal=journal,
    )


def venue_event(
    update_id: str,
    status: OrderStatus,
    cumulative: str,
    *,
    at_ns: int,
) -> OrderEvent:
    return OrderEvent(
        venue_update_id=update_id,
        client_order_id=ClientOrderId("client-1"),
        venue_order_id=VenueOrderId("venue-1"),
        status=status,
        cumulative_filled_quantity=Quantity.from_str(cumulative),
        average_fill_price=(None if cumulative == "0" else Price.from_str("100")),
        event_time_ns=UnixNanos(at_ns),
    )


class OmsJournalTests(unittest.TestCase):
    def test_crash_after_gateway_response_replays_submitting_for_recovery(
        self,
    ) -> None:
        journal = _NthFailJournal(fail_at=3)
        oms = service(journal)
        request = oms.create_order(intent(), decision())
        execution_calls: list[ClientOrderId] = []

        class Guard:
            def assert_submit_allowed(self, value) -> None:
                self.value = value

        class Execution:
            def submit(self, value):
                execution_calls.append(value.client_order_id)
                return SubmitResult(
                    client_order_id=value.client_order_id,
                    outcome=ExecutionOutcome.ACCEPTED,
                    venue_order_id=VenueOrderId("accepted-before-crash"),
                )

        with self.assertRaises(OmsPersistenceError):
            DurableExecutionHandoff(
                oms=oms,
                execution=Execution(),
                guard=Guard(),
            ).submit(request)

        self.assertEqual(execution_calls, [request.client_order_id])
        journal.fail_at = None
        recovered = service(journal)
        self.assertEqual(
            recovered.reconciliation_candidates(),
            (recovered.order(request.client_order_id),),
        )
        self.assertEqual(
            recovered.order(request.client_order_id).status,
            OrderStatus.SUBMITTING,
        )

    def test_mixed_legacy_and_group_records_replay_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            clock = ManualClock()
            with JsonLinesOmsJournal(path) as journal:
                single = service(journal)
                single_request = single.create_order(intent(), decision())
                single.prepare_submit(single_request)
                single.record_submit_failure(
                    single_request.client_order_id,
                    outcome=OrderSubmitOutcome.DEFINITELY_NOT_SENT,
                    reason="connect refused",
                )

                groups = OrderGroupRuntime(now_ns=clock, journal=journal)
                group = groups.create_group(admission(), execution_plan())
                clock.step()
                groups.activate_group(group.order_group_id)
                action = action_for(
                    groups.group(group.order_group_id),
                    leg_index=0,
                    now_ns=clock.step(),
                )
                child = groups.prepare_child_submit(
                    action=action,
                    permit=permit_for(action, issued_at_ns=clock()),
                )

            versions = [
                json.loads(line)["version"]
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(versions, [1, 1, 2, 2, 2, 2])
            with JsonLinesOmsJournal(path) as replay_journal:
                replayed_single = service(replay_journal)
                replayed_groups = OrderGroupRuntime(
                    now_ns=clock,
                    journal=replay_journal,
                )
                self.assertEqual(
                    replayed_single.order(single_request.client_order_id).status,
                    OrderStatus.FAILED,
                )
                self.assertEqual(
                    replayed_groups.child(child.client_order_id).status,
                    OrderStatus.SUBMITTING,
                )
                self.assertEqual(
                    replayed_groups.group(group.order_group_id).status.value,
                    "active",
                )

    def test_durable_submit_outcome_replays_after_submitting_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                oms = service(journal)
                request = oms.create_order(intent(), decision())
                oms.prepare_submit(request)
                expected = oms.record_submit_result(
                    SubmitResult(
                        client_order_id=request.client_order_id,
                        outcome=ExecutionOutcome.ACCEPTED,
                        venue_order_id=VenueOrderId("venue-immediate-1"),
                    )
                )

            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [item["version"] for item in records],
                [1, 1, 2],
            )
            self.assertEqual(expected.status, OrderStatus.SUBMITTING)
            with JsonLinesOmsJournal(path) as recovered_journal:
                recovered = service(recovered_journal)
                replayed = recovered.order(request.client_order_id)
                self.assertEqual(replayed, expected)
                self.assertEqual(
                    recovered.reconciliation_candidates(),
                    (expected,),
                )

    def test_unknown_submit_outcome_remains_reconciliation_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                oms = service(journal)
                request = oms.create_order(intent(), decision())
                oms.prepare_submit(request)
                expected = oms.record_submit_failure(
                    request.client_order_id,
                    outcome=OrderSubmitOutcome.UNKNOWN,
                    reason="timeout after send",
                )

            with JsonLinesOmsJournal(path) as recovered_journal:
                recovered = service(recovered_journal)
                self.assertEqual(
                    recovered.reconciliation_candidates(),
                    (expected,),
                )

    def test_restart_replays_complete_order_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                oms = service(journal)
                request = oms.create_order(intent(), decision())
                oms.mark_submitting(
                    request.client_order_id,
                    at_ns=UnixNanos(160),
                )
                oms.apply_venue_update(
                    venue_event("open-1", OrderStatus.OPEN, "0", at_ns=170)
                )
                oms.apply_venue_update(
                    venue_event(
                        "fill-1",
                        OrderStatus.PARTIALLY_FILLED,
                        "3",
                        at_ns=180,
                    )
                )
                oms.request_cancel(
                    request.client_order_id,
                    at_ns=UnixNanos(190),
                )
                expected = oms.apply_venue_update(
                    venue_event(
                        "cancel-1",
                        OrderStatus.CANCELED,
                        "3",
                        at_ns=200,
                    )
                )

            with JsonLinesOmsJournal(path) as recovered_journal:
                recovered = service(recovered_journal)
                self.assertEqual(
                    recovered.order(ClientOrderId("client-1")),
                    expected,
                )
                self.assertEqual(len(recovered.orders()), 1)
                self.assertEqual(
                    len(tuple(recovered_journal.read())),
                    6,
                )

    def test_duplicate_update_is_not_persisted_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                oms = service(journal)
                request = oms.create_order(intent(), decision())
                oms.mark_submitting(
                    request.client_order_id,
                    at_ns=UnixNanos(160),
                )
                update = venue_event("open-1", OrderStatus.OPEN, "0", at_ns=170)
                oms.apply_venue_update(update)
                oms.apply_venue_update(update)
                self.assertEqual(len(tuple(journal.read())), 3)

    def test_checksum_and_truncation_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                service(journal).create_order(intent(), decision())
            original = path.read_bytes()

            path.write_bytes(original.replace(b'"sequence":1', b'"sequence":2'))
            with self.assertRaisesRegex(
                OmsJournalIntegrityError,
                "checksum",
            ):
                JsonLinesOmsJournal(path)

            path.write_bytes(original[:-1])
            with self.assertRaisesRegex(
                OmsJournalIntegrityError,
                "truncated",
            ):
                JsonLinesOmsJournal(path)

    def test_reconciles_rest_and_user_stream_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                oms = service(journal)
                oms.create_order(intent(), decision())
                opened = oms.reconcile(
                    OrderReconciliationSnapshot(
                        source=ReconciliationSource.REST_QUERY,
                        source_update_id="rest-1",
                        client_order_id=ClientOrderId("client-1"),
                        venue_order_id=VenueOrderId("venue-1"),
                        status=OrderStatus.OPEN,
                        cumulative_filled_quantity=Quantity.from_str("0"),
                        observed_at_ns=UnixNanos(170),
                    )
                )
                partial = oms.reconcile(
                    OrderReconciliationSnapshot(
                        source=ReconciliationSource.USER_STREAM,
                        source_update_id="stream-1",
                        client_order_id=ClientOrderId("client-1"),
                        venue_order_id=VenueOrderId("venue-1"),
                        status=OrderStatus.PARTIALLY_FILLED,
                        cumulative_filled_quantity=Quantity.from_str("4"),
                        average_fill_price=Price.from_str("100"),
                        observed_at_ns=UnixNanos(180),
                    )
                )
                stale = oms.reconcile(
                    OrderReconciliationSnapshot(
                        source=ReconciliationSource.REST_QUERY,
                        source_update_id="rest-stale",
                        client_order_id=ClientOrderId("client-1"),
                        venue_order_id=VenueOrderId("venue-1"),
                        status=OrderStatus.OPEN,
                        cumulative_filled_quantity=Quantity.from_str("0"),
                        observed_at_ns=UnixNanos(190),
                    )
                )

                self.assertEqual(
                    opened.disposition,
                    ReconciliationDisposition.APPLIED,
                )
                self.assertEqual(
                    partial.disposition,
                    ReconciliationDisposition.APPLIED,
                )
                self.assertEqual(
                    stale.disposition,
                    ReconciliationDisposition.CONFLICT,
                )
                self.assertEqual(
                    stale.order.cumulative_filled_quantity.as_decimal(),
                    4,
                )

    def test_not_found_does_not_invent_terminal_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                oms = service(journal)
                request = oms.create_order(intent(), decision())
                result = oms.reconcile_not_found(
                    request.client_order_id,
                    source=ReconciliationSource.REST_QUERY,
                    observed_at_ns=UnixNanos(180),
                )
                self.assertEqual(
                    result.disposition,
                    ReconciliationDisposition.NOT_FOUND,
                )
                self.assertEqual(result.order.status, OrderStatus.CREATED)

    def test_persistence_failure_latches_mutations_fail_closed(self) -> None:
        oms = service(_FailingJournal())
        with self.assertRaisesRegex(OmsPersistenceError, "latched"):
            oms.create_order(intent(), decision())
        with self.assertRaisesRegex(OmsPersistenceError, "unhealthy"):
            oms.create_order(intent(), decision())


if __name__ == "__main__":
    unittest.main()
