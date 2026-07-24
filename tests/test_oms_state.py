import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    ApprovedOrderIntent,
    DuplicateUpdateConflictError,
    InvalidFillProgressError,
    InvalidOrderTransitionError,
    OrderEvent,
    OrderIdentityError,
    OrderRequest,
    OrderSide,
    OrderStateMachine,
    OrderStatus,
    OrderType,
    OrderWriterViolationError,
    UpdateDisposition,
)

INSTRUMENT = InstrumentId(
    venue=VenueId("test"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)


def request(client_order_id: str = "client-1") -> OrderRequest:
    approved = ApprovedOrderIntent(
        approval_id="approval-1",
        intent_id=IntentId("intent-1"),
        account_id=AccountId("account-1"),
        instrument_id=INSTRUMENT,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Quantity(raw=10, scale=0),
        limit_price=Price(raw=100, scale=0),
        approved_at_ns=UnixNanos(10),
    )
    return OrderRequest.from_approved_intent(
        approved,
        client_order_id=ClientOrderId(client_order_id),
        created_at_ns=UnixNanos(20),
    )


def event(
    update_id: str,
    status: OrderStatus,
    cumulative: str,
    *,
    client_order_id: str = "client-1",
    reason: str = "",
) -> OrderEvent:
    return OrderEvent(
        venue_update_id=update_id,
        client_order_id=ClientOrderId(client_order_id),
        venue_order_id=VenueOrderId("venue-1"),
        status=status,
        cumulative_filled_quantity=Quantity.from_str(cumulative),
        average_fill_price=(
            Price(raw=101, scale=0)
            if Quantity.from_str(cumulative).raw > 0
            else None
        ),
        event_time_ns=UnixNanos(100 + int(update_id.rsplit("-", 1)[-1])),
        reason=reason,
    )


class OmsStateTests(unittest.TestCase):
    def test_full_lifecycle_and_immutable_views(self) -> None:
        state = OrderStateMachine(request())
        self.assertEqual(state.view().status, OrderStatus.CREATED)
        state.mark_submitting(at_ns=UnixNanos(30))
        state.apply_venue_update(event("update-1", OrderStatus.OPEN, "0"))
        partial = state.apply_venue_update(
            event("update-2", OrderStatus.PARTIALLY_FILLED, "2.5")
        )
        self.assertEqual(partial.after.remaining_quantity.as_decimal(), 7.5)
        filled = state.apply_venue_update(
            event("update-3", OrderStatus.FILLED, "10.0")
        )
        self.assertTrue(filled.after.is_terminal)
        self.assertEqual(filled.after.status, OrderStatus.FILLED)
        with self.assertRaises(FrozenInstanceError):
            filled.after.reason = "changed"  # type: ignore[misc]

    def test_identical_venue_update_is_idempotent(self) -> None:
        state = OrderStateMachine(request())
        state.mark_submitting(at_ns=UnixNanos(30))
        update = event("update-1", OrderStatus.OPEN, "0")
        state.apply_venue_update(update)
        duplicate = state.apply_venue_update(update)
        self.assertEqual(duplicate.disposition, UpdateDisposition.DUPLICATE)
        self.assertIs(duplicate.before, duplicate.after)

    def test_reused_update_id_with_different_content_is_rejected(self) -> None:
        state = OrderStateMachine(request())
        state.mark_submitting(at_ns=UnixNanos(30))
        state.apply_venue_update(event("update-1", OrderStatus.OPEN, "0"))
        with self.assertRaises(DuplicateUpdateConflictError):
            state.apply_venue_update(
                event("update-1", OrderStatus.REJECTED, "0", reason="changed")
            )

    def test_cumulative_fill_cannot_decrease_or_exceed_total(self) -> None:
        state = OrderStateMachine(request())
        state.mark_submitting(at_ns=UnixNanos(30))
        state.apply_venue_update(
            event("update-1", OrderStatus.PARTIALLY_FILLED, "4")
        )
        with self.assertRaises(InvalidFillProgressError):
            state.apply_venue_update(
                event("update-2", OrderStatus.PARTIALLY_FILLED, "3")
            )
        with self.assertRaises(InvalidFillProgressError):
            state.apply_venue_update(
                event("update-3", OrderStatus.FILLED, "11")
            )
        self.assertEqual(
            state.view().cumulative_filled_quantity.as_decimal(), 4
        )

    def test_illegal_transition_is_rejected_without_mutation(self) -> None:
        state = OrderStateMachine(request())
        with self.assertRaises(InvalidOrderTransitionError):
            state.apply_venue_update(event("update-1", OrderStatus.OPEN, "0"))
        self.assertEqual(state.view().status, OrderStatus.CREATED)

    def test_cancel_pending_accepts_racing_fill_then_cancel(self) -> None:
        state = OrderStateMachine(request())
        state.mark_submitting(at_ns=UnixNanos(30))
        state.apply_venue_update(event("update-1", OrderStatus.OPEN, "0"))
        state.request_cancel(at_ns=UnixNanos(120))
        state.apply_venue_update(
            event("update-2", OrderStatus.PARTIALLY_FILLED, "2")
        )
        state.request_cancel(at_ns=UnixNanos(130))
        canceled = state.apply_venue_update(
            event("update-3", OrderStatus.CANCELED, "2")
        )
        self.assertEqual(canceled.after.status, OrderStatus.CANCELED)
        self.assertEqual(canceled.after.remaining_quantity.as_decimal(), 8)

    def test_terminal_order_rejects_new_update(self) -> None:
        state = OrderStateMachine(request())
        state.mark_submitting(at_ns=UnixNanos(30))
        state.apply_venue_update(
            event("update-1", OrderStatus.REJECTED, "0")
        )
        with self.assertRaises(InvalidOrderTransitionError):
            state.apply_venue_update(
                event("update-2", OrderStatus.CANCELED, "0")
            )

    def test_mismatched_order_identity_is_rejected(self) -> None:
        state = OrderStateMachine(request())
        state.mark_submitting(at_ns=UnixNanos(30))
        with self.assertRaises(OrderIdentityError):
            state.apply_venue_update(
                event(
                    "update-1",
                    OrderStatus.OPEN,
                    "0",
                    client_order_id="other",
                )
            )

    def test_mutation_from_non_owner_thread_is_rejected(self) -> None:
        state = OrderStateMachine(request())
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                state.mark_submitting, at_ns=UnixNanos(30)
            )
            with self.assertRaises(OrderWriterViolationError):
                future.result()
        self.assertEqual(state.view().status, OrderStatus.CREATED)


if __name__ == "__main__":
    unittest.main()
