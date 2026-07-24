"""Deterministic single-writer canonical order state."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from threading import get_ident

from cex_quant.core import (
    ClientOrderId,
    Price,
    Quantity,
    UnixNanos,
    VenueOrderId,
)

from .model import (
    OrderEvent,
    OrderRequest,
    OrderStatus,
    OrderView,
)


class OrderStateError(RuntimeError):
    """Base class for rejected OMS state mutations."""


class OrderWriterViolationError(OrderStateError):
    """Raised when a thread other than the state owner attempts a mutation."""


class OrderIdentityError(OrderStateError):
    """Raised when an update targets a different canonical order."""


class DuplicateUpdateConflictError(OrderStateError):
    """Raised when one venue update ID is reused with different content."""


class InvalidOrderTransitionError(OrderStateError):
    """Raised when an event requests an illegal lifecycle transition."""


class InvalidFillProgressError(OrderStateError):
    """Raised when cumulative fill decreases or exceeds requested quantity."""


class UpdateDisposition(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderUpdateResult:
    disposition: UpdateDisposition
    before: OrderView
    after: OrderView


_VENUE_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset(
        {OrderStatus.REJECTED, OrderStatus.FAILED}
    ),
    OrderStatus.SUBMITTING: frozenset(
        {
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.OPEN: frozenset(
        {
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.CANCEL_PENDING: frozenset(
        {
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.FAILED: frozenset(),
}


class OrderStateMachine:
    """Own one order's mutable state and expose only immutable snapshots."""

    def __init__(self, request: OrderRequest) -> None:
        self._writer_thread_id = get_ident()
        self._request = request
        self._status = OrderStatus.CREATED
        self._cumulative_filled_quantity = Quantity(raw=0, scale=0)
        self._venue_order_id: VenueOrderId | None = None
        self._average_fill_price: Price | None = None
        self._reason: str = ""
        self._last_event_time_ns = request.created_at_ns
        self._seen_updates: dict[str, OrderEvent] = {}

    @property
    def client_order_id(self) -> ClientOrderId:
        return self._request.client_order_id

    def view(self) -> OrderView:
        requested = self._request.quantity.as_decimal()
        filled = self._cumulative_filled_quantity.as_decimal()
        remaining = requested - filled
        return OrderView(
            request=self._request,
            status=self._status,
            cumulative_filled_quantity=self._cumulative_filled_quantity,
            remaining_quantity=_quantity_from_decimal(remaining),
            last_event_time_ns=self._last_event_time_ns,
            venue_order_id=self._venue_order_id,
            average_fill_price=self._average_fill_price,
            reason=self._reason,
        )

    def mark_submitting(self, *, at_ns: UnixNanos) -> OrderView:
        self._assert_writer()
        if self._status is not OrderStatus.CREATED:
            raise InvalidOrderTransitionError(
                f"cannot mark {self._status.value} order as submitting"
            )
        self._assert_time_not_before_creation(at_ns)
        self._status = OrderStatus.SUBMITTING
        self._last_event_time_ns = at_ns
        return self.view()

    def request_cancel(self, *, at_ns: UnixNanos) -> OrderView:
        self._assert_writer()
        if self._status not in {
            OrderStatus.SUBMITTING,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
        }:
            raise InvalidOrderTransitionError(
                f"cannot request cancellation from {self._status.value}"
            )
        self._assert_time_not_before_creation(at_ns)
        self._status = OrderStatus.CANCEL_PENDING
        self._last_event_time_ns = UnixNanos(
            max(self._last_event_time_ns, at_ns)
        )
        return self.view()

    def apply_venue_update(self, event: OrderEvent) -> OrderUpdateResult:
        self._assert_writer()
        if event.client_order_id != self._request.client_order_id:
            raise OrderIdentityError("venue update client_order_id mismatch")
        previous = self._seen_updates.get(event.venue_update_id)
        before = self.view()
        if previous is not None:
            if previous != event:
                raise DuplicateUpdateConflictError(
                    "venue_update_id was reused with different content"
                )
            return OrderUpdateResult(
                disposition=UpdateDisposition.DUPLICATE,
                before=before,
                after=before,
            )

        allowed = _VENUE_TRANSITIONS[self._status]
        if event.status not in allowed:
            raise InvalidOrderTransitionError(
                f"illegal transition {self._status.value} -> "
                f"{event.status.value}"
            )
        self._validate_fill(event)

        self._status = event.status
        self._cumulative_filled_quantity = event.cumulative_filled_quantity
        if event.venue_order_id is not None:
            self._venue_order_id = event.venue_order_id
        if event.average_fill_price is not None:
            self._average_fill_price = event.average_fill_price
        self._reason = event.reason
        self._last_event_time_ns = UnixNanos(
            max(self._last_event_time_ns, event.event_time_ns)
        )
        self._seen_updates[event.venue_update_id] = event
        return OrderUpdateResult(
            disposition=UpdateDisposition.APPLIED,
            before=before,
            after=self.view(),
        )

    def _validate_fill(self, event: OrderEvent) -> None:
        old = self._cumulative_filled_quantity.as_decimal()
        new = event.cumulative_filled_quantity.as_decimal()
        requested = self._request.quantity.as_decimal()
        if new < old:
            raise InvalidFillProgressError("cumulative fill cannot decrease")
        if new > requested:
            raise InvalidFillProgressError(
                "cumulative fill cannot exceed requested quantity"
            )
        if event.status is OrderStatus.FILLED and new != requested:
            raise InvalidFillProgressError(
                "FILLED status requires the full requested quantity"
            )
        if event.status is OrderStatus.PARTIALLY_FILLED and not (
            Decimal(0) < new < requested
        ):
            raise InvalidFillProgressError(
                "PARTIALLY_FILLED requires fill strictly between zero and total"
            )

    def _assert_writer(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise OrderWriterViolationError(
                "canonical order state may only be mutated by its owner thread"
            )

    def _assert_time_not_before_creation(self, at_ns: UnixNanos) -> None:
        if at_ns < self._request.created_at_ns:
            raise ValueError("state transition cannot precede order creation")


def _quantity_from_decimal(value: Decimal) -> Quantity:
    return Quantity.from_str(format(value, "f"))


__all__ = [
    "DuplicateUpdateConflictError",
    "InvalidFillProgressError",
    "InvalidOrderTransitionError",
    "OrderIdentityError",
    "OrderStateError",
    "OrderStateMachine",
    "OrderUpdateResult",
    "OrderWriterViolationError",
    "UpdateDisposition",
]
