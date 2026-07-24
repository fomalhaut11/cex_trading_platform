"""Canonical order contracts and deterministic single-writer lifecycle state.

Risk-approved instructions enter through :class:`ApprovedOrderIntent`.
Venue adapters normalize acknowledgements and fills into :class:`OrderEvent`.
OMS is the sole writer of canonical order state and exposes immutable views.
Durable journals replay accepted mutations; reconciliation snapshots unify
REST queries and user-stream observations without importing venue payloads.
"""

from cex_quant.core import ClientOrderId

from .journal import (
    CancelRequestedEntry,
    JsonLinesOmsJournal,
    OmsJournal,
    OmsJournalEntry,
    OmsJournalEntryType,
    OmsJournalError,
    OmsJournalIntegrityError,
    OmsJournalIoError,
    OrderCreatedEntry,
    OrderSubmittingEntry,
    VenueEventEntry,
)
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
from .reconciliation import (
    OrderReconciliationSnapshot,
    ReconciliationDisposition,
    ReconciliationResult,
    ReconciliationSource,
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
    "CancelRequestedEntry",
    "ClientOrderId",
    "DuplicateUpdateConflictError",
    "InvalidFillProgressError",
    "InvalidOrderTransitionError",
    "JsonLinesOmsJournal",
    "OmsJournal",
    "OmsJournalEntry",
    "OmsJournalEntryType",
    "OmsJournalError",
    "OmsJournalIntegrityError",
    "OmsJournalIoError",
    "OrderCreatedEntry",
    "OrderEvent",
    "OrderIdentityError",
    "OrderReconciliationSnapshot",
    "OrderRequest",
    "OrderSide",
    "OrderStateError",
    "OrderStateMachine",
    "OrderStatus",
    "OrderSubmittingEntry",
    "OrderType",
    "OrderUpdateResult",
    "OrderView",
    "OrderWriterViolationError",
    "PositionSide",
    "ReconciliationDisposition",
    "ReconciliationResult",
    "ReconciliationSource",
    "TimeInForce",
    "UpdateDisposition",
    "VenueEventEntry",
]
