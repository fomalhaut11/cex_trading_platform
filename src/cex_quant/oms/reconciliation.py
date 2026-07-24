"""Venue-neutral REST and user-stream order reconciliation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    ClientOrderId,
    Price,
    Quantity,
    UnixNanos,
    VenueOrderId,
)

from .model import OrderEvent, OrderStatus, OrderView


class ReconciliationSource(StrEnum):
    REST_QUERY = "rest_query"
    USER_STREAM = "user_stream"


_VENUE_STATUSES = frozenset(
    {
        OrderStatus.OPEN,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderReconciliationSnapshot:
    """One authoritative venue observation normalized outside OMS."""

    source: ReconciliationSource
    source_update_id: str
    client_order_id: ClientOrderId
    status: OrderStatus
    cumulative_filled_quantity: Quantity
    observed_at_ns: UnixNanos
    venue_order_id: VenueOrderId | None = None
    average_fill_price: Price | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.source, ReconciliationSource):
            raise ValueError("source must be a ReconciliationSource")
        if (
            not self.source_update_id
            or self.source_update_id.strip() != self.source_update_id
        ):
            raise ValueError("source_update_id must be non-empty and trimmed")
        if self.status not in _VENUE_STATUSES:
            raise ValueError("snapshot status must be venue-observable")
        if self.cumulative_filled_quantity.raw < 0:
            raise ValueError("cumulative fill cannot be negative")
        if (
            self.average_fill_price is not None
            and self.average_fill_price.raw <= 0
        ):
            raise ValueError("average_fill_price must be positive")

    def as_order_event(self) -> OrderEvent:
        return OrderEvent(
            venue_update_id=(
                f"reconcile:{self.source.value}:{self.source_update_id}"
            ),
            client_order_id=self.client_order_id,
            status=self.status,
            cumulative_filled_quantity=self.cumulative_filled_quantity,
            event_time_ns=self.observed_at_ns,
            venue_order_id=self.venue_order_id,
            average_fill_price=self.average_fill_price,
            reason=self.reason,
        )


class ReconciliationDisposition(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    ALREADY_CONSISTENT = "already_consistent"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciliationResult:
    disposition: ReconciliationDisposition
    order: OrderView
    reason: str = ""


__all__ = [
    "OrderReconciliationSnapshot",
    "ReconciliationDisposition",
    "ReconciliationResult",
    "ReconciliationSource",
]
