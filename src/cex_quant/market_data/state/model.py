"""Shared market-state statuses, update results and immutable views."""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import EventId, Rate, UnixNanos
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
class FundingView:
    """Latest venue Funding fact with exact Snapshot-source provenance."""

    instrument_id: InstrumentId
    funding_rate: Rate
    next_funding_time_ns: UnixNanos | None
    event_id: EventId
    as_of_ns: UnixNanos
    received_at_ns: UnixNanos
    source_sequence: int | None
    status: MarketStateStatus

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("Funding event_id cannot be empty")
        if self.as_of_ns < 0 or self.received_at_ns < 0:
            raise ValueError("Funding observation times cannot be negative")
        if (
            self.next_funding_time_ns is not None
            and self.next_funding_time_ns < self.as_of_ns
        ):
            raise ValueError("next Funding time precedes the observation")
        if self.source_sequence is not None and self.source_sequence < 0:
            raise ValueError("Funding source sequence cannot be negative")
        if self.status is not MarketStateStatus.LIVE:
            raise ValueError("published Funding view must be LIVE")


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
    "FundingView",
    "InstrumentMismatchError",
    "L1View",
    "MarketStateStatus",
    "OrderBookView",
    "PartialBookView",
    "StateBufferOverflowError",
    "StateUpdateResult",
    "UpdateDisposition",
]
