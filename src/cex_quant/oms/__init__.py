"""Canonical order contracts and deterministic single-writer lifecycle state.

Risk-approved instructions enter through :class:`ApprovedOrderIntent`.
Venue adapters normalize acknowledgements and fills into :class:`OrderEvent`.
OMS is the sole writer of canonical order state and exposes immutable views.
"""

from cex_quant.core import ClientOrderId

from .model import (
    TERMINAL_ORDER_STATUSES,
    ApprovedOrderIntent,
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    OrderView,
    PositionSide,
    TimeInForce,
)
from .state import (
    DuplicateUpdateConflictError,
    InvalidFillProgressError,
    InvalidOrderTransitionError,
    OrderIdentityError,
    OrderStateError,
    OrderStateMachine,
    OrderUpdateResult,
    OrderWriterViolationError,
    UpdateDisposition,
)

__all__ = [
    "TERMINAL_ORDER_STATUSES",
    "ApprovedOrderIntent",
    "ClientOrderId",
    "DuplicateUpdateConflictError",
    "InvalidFillProgressError",
    "InvalidOrderTransitionError",
    "OrderEvent",
    "OrderIdentityError",
    "OrderRequest",
    "OrderSide",
    "OrderStateError",
    "OrderStateMachine",
    "OrderStatus",
    "OrderType",
    "OrderUpdateResult",
    "OrderView",
    "OrderWriterViolationError",
    "PositionSide",
    "TimeInForce",
    "UpdateDisposition",
]
