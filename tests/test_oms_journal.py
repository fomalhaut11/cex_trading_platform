import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

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
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    JsonLinesOmsJournal,
    OmsJournalEntry,
    OmsJournalIntegrityError,
    OrderEvent,
    OrderReconciliationSnapshot,
    OrderSide,
    OrderStatus,
    OrderType,
    ReconciliationDisposition,
    ReconciliationSource,
)
from cex_quant.risk import RiskDecision, RiskDecisionStatus
from cex_quant.runtime import (
    CanonicalOmsApplicationService,
    OmsPersistenceError,
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


def service(
    journal: JsonLinesOmsJournal | _FailingJournal,
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
        average_fill_price=(
            None if cumulative == "0" else Price.from_str("100")
        ),
        event_time_ns=UnixNanos(at_ns),
    )


class OmsJournalTests(unittest.TestCase):
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
                update = venue_event(
                    "open-1", OrderStatus.OPEN, "0", at_ns=170
                )
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
