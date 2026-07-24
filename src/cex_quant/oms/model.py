"""Immutable order contracts at the risk-to-OMS and venue-to-OMS boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"


class TimeInForce(StrEnum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTX = "gtx"


class PositionSide(StrEnum):
    """Position leg used by derivatives venues with hedge mode."""

    NET = "net"
    LONG = "long"
    SHORT = "short"


class OrderStatus(StrEnum):
    CREATED = "created"
    SUBMITTING = "submitting"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    FAILED = "failed"


TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovedOrderIntent:
    """Risk-approved, venue-neutral order instruction accepted by OMS.

    This contract deliberately lives in OMS so the module does not depend on a
    particular risk-engine implementation.
    """

    approval_id: str
    intent_id: IntentId
    account_id: AccountId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    approved_at_ns: UnixNanos
    valid_until_ns: UnixNanos | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    limit_price: Price | None = None
    stop_price: Price | None = None
    reduce_only: bool = False
    post_only: bool = False
    position_side: PositionSide = PositionSide.NET

    def __post_init__(self) -> None:
        _validate_order_fields(
            instrument_id=self.instrument_id,
            order_type=self.order_type,
            quantity=self.quantity,
            time_in_force=self.time_in_force,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            reduce_only=self.reduce_only,
            post_only=self.post_only,
            position_side=self.position_side,
        )
        if not self.approval_id or self.approval_id.strip() != self.approval_id:
            raise ValueError("approval_id must be non-empty and trimmed")
        if not self.intent_id:
            raise ValueError("intent_id cannot be empty")
        if not self.account_id:
            raise ValueError("account_id cannot be empty")
        if (
            self.valid_until_ns is not None
            and self.valid_until_ns < self.approved_at_ns
        ):
            raise ValueError("valid_until_ns cannot precede approved_at_ns")


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderRequest:
    """Canonical request created by OMS from one approved instruction."""

    client_order_id: ClientOrderId
    approval_id: str
    intent_id: IntentId
    account_id: AccountId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    created_at_ns: UnixNanos
    time_in_force: TimeInForce = TimeInForce.GTC
    limit_price: Price | None = None
    stop_price: Price | None = None
    reduce_only: bool = False
    post_only: bool = False
    position_side: PositionSide = PositionSide.NET

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id cannot be empty")
        if not self.approval_id or self.approval_id.strip() != self.approval_id:
            raise ValueError("approval_id must be non-empty and trimmed")
        if not self.intent_id:
            raise ValueError("intent_id cannot be empty")
        if not self.account_id:
            raise ValueError("account_id cannot be empty")
        _validate_order_fields(
            instrument_id=self.instrument_id,
            order_type=self.order_type,
            quantity=self.quantity,
            time_in_force=self.time_in_force,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            reduce_only=self.reduce_only,
            post_only=self.post_only,
            position_side=self.position_side,
        )

    @classmethod
    def from_approved_intent(
        cls,
        approved: ApprovedOrderIntent,
        *,
        client_order_id: ClientOrderId,
        created_at_ns: UnixNanos,
    ) -> OrderRequest:
        if created_at_ns < approved.approved_at_ns:
            raise ValueError("order creation cannot precede approval")
        if (
            approved.valid_until_ns is not None
            and created_at_ns > approved.valid_until_ns
        ):
            raise ValueError("approved order intent has expired")
        return cls(
            client_order_id=client_order_id,
            approval_id=approved.approval_id,
            intent_id=approved.intent_id,
            account_id=approved.account_id,
            instrument_id=approved.instrument_id,
            side=approved.side,
            order_type=approved.order_type,
            quantity=approved.quantity,
            created_at_ns=created_at_ns,
            time_in_force=approved.time_in_force,
            limit_price=approved.limit_price,
            stop_price=approved.stop_price,
            reduce_only=approved.reduce_only,
            post_only=approved.post_only,
            position_side=approved.position_side,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderEvent:
    """One normalized venue update; `venue_update_id` is its idempotency key."""

    venue_update_id: str
    client_order_id: ClientOrderId
    status: OrderStatus
    cumulative_filled_quantity: Quantity
    event_time_ns: UnixNanos
    venue_order_id: VenueOrderId | None = None
    average_fill_price: Price | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if (
            not self.venue_update_id
            or self.venue_update_id.strip() != self.venue_update_id
        ):
            raise ValueError("venue_update_id must be non-empty and trimmed")
        if not self.client_order_id:
            raise ValueError("client_order_id cannot be empty")
        if self.cumulative_filled_quantity.raw < 0:
            raise ValueError("cumulative_filled_quantity cannot be negative")
        if (
            self.average_fill_price is not None
            and self.average_fill_price.raw <= 0
        ):
            raise ValueError("average_fill_price must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderView:
    """Immutable projection of canonical order state."""

    request: OrderRequest
    status: OrderStatus
    cumulative_filled_quantity: Quantity
    remaining_quantity: Quantity
    last_event_time_ns: UnixNanos
    venue_order_id: VenueOrderId | None = None
    average_fill_price: Price | None = None
    reason: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_ORDER_STATUSES


def _validate_order_fields(
    *,
    instrument_id: InstrumentId,
    order_type: OrderType,
    quantity: Quantity,
    time_in_force: TimeInForce,
    limit_price: Price | None,
    stop_price: Price | None,
    reduce_only: bool,
    post_only: bool,
    position_side: PositionSide,
) -> None:
    if quantity.raw <= 0:
        raise ValueError("quantity must be positive")
    needs_limit = order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT}
    needs_stop = order_type in {OrderType.STOP_MARKET, OrderType.STOP_LIMIT}
    if needs_limit != (limit_price is not None):
        raise ValueError("limit_price presence does not match order_type")
    if needs_stop != (stop_price is not None):
        raise ValueError("stop_price presence does not match order_type")
    if limit_price is not None and limit_price.raw <= 0:
        raise ValueError("limit_price must be positive")
    if stop_price is not None and stop_price.raw <= 0:
        raise ValueError("stop_price must be positive")
    if post_only and order_type is not OrderType.LIMIT:
        raise ValueError("post_only requires a limit order")
    if post_only and time_in_force is not TimeInForce.GTX:
        raise ValueError("post_only requires GTX time_in_force")
    if time_in_force is TimeInForce.GTX and not post_only:
        raise ValueError("GTX time_in_force requires post_only")
    if instrument_id.kind is InstrumentKind.SPOT:
        if reduce_only:
            raise ValueError("spot orders cannot be reduce_only")
        if position_side is not PositionSide.NET:
            raise ValueError("spot orders require NET position_side")


__all__ = [
    "TERMINAL_ORDER_STATUSES",
    "ApprovedOrderIntent",
    "OrderEvent",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "OrderView",
    "PositionSide",
    "TimeInForce",
]
