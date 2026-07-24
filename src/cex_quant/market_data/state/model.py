"""Shared market-state statuses, update results and immutable views."""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import UnixNanos
from cex_quant.instruments import InstrumentId
from cex_quant.market_data.events import BookLevel


class MarketStateStatus(StrEnum):
    EMPTY = "empty"
    BUFFERING = "buffering"
    LIVE = "live"
    GAP = "gap"
    INVALID = "invalid"


class UpdateDisposition(StrEnum):
    APPLIED = "applied"
    INITIALIZED = "initialized"
    BUFFERED = "buffered"
    IGNORED_STALE = "ignored_stale"
    GAP_DETECTED = "gap_detected"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True, kw_only=True)
class StateUpdateResult:
    disposition: UpdateDisposition
    status: MarketStateStatus
    sequence: int | None
    reason: str | None = None


class InstrumentMismatchError(ValueError):
    pass


class StateBufferOverflowError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class L1View:
    instrument_id: InstrumentId
    bid: BookLevel
    ask: BookLevel
    as_of_ns: UnixNanos
    sequence: int | None
    status: MarketStateStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class PartialBookView:
    instrument_id: InstrumentId
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    as_of_ns: UnixNanos
    sequence: int | None
    status: MarketStateStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderBookView:
    instrument_id: InstrumentId
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    as_of_ns: UnixNanos
    sequence: int
    status: MarketStateStatus


__all__ = [
    "InstrumentMismatchError",
    "L1View",
    "MarketStateStatus",
    "OrderBookView",
    "PartialBookView",
    "StateBufferOverflowError",
    "StateUpdateResult",
    "UpdateDisposition",
]
