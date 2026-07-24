"""Venue adapter boundary for raw market messages.

Normalizers are implemented inside venue adapter packages. They decode raw
bytes, resolve instruments and return canonical immutable market events. This
module defines the stable boundary without depending on any venue SDK.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias, runtime_checkable

from cex_quant.core import EventSource, UnixNanos

from .events import (
    AggregateTrade,
    BestBidAsk,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    OpenInterestUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)

MarketEvent: TypeAlias = (
    MarketTrade
    | AggregateTrade
    | BestBidAsk
    | OrderBookDelta
    | PartialBookFrame
    | MarkPriceUpdate
    | IndexPriceUpdate
    | KlineUpdate
    | FundingRateUpdate
    | OpenInterestUpdate
    | VenueOptionAnalyticsUpdate
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RawMarketMessage:
    """Raw message captured once at the connector boundary."""

    payload: bytes
    source: EventSource
    receive_time_ns: UnixNanos

    def __post_init__(self) -> None:
        if not self.payload:
            raise ValueError("raw market payload cannot be empty")
        if self.receive_time_ns < 0:
            raise ValueError("receive_time_ns cannot be negative")


class NormalizationErrorCode(StrEnum):
    MALFORMED_PAYLOAD = "malformed_payload"
    UNSUPPORTED_MESSAGE = "unsupported_message"
    UNKNOWN_INSTRUMENT = "unknown_instrument"
    MISSING_FIELD = "missing_field"
    INVALID_FIELD = "invalid_field"
    INVALID_TIMESTAMP = "invalid_timestamp"


class NormalizationError(ValueError):
    """Typed adapter failure safe to route to metrics or a dead-letter sink."""

    def __init__(
        self,
        *,
        code: NormalizationErrorCode,
        source: EventSource,
        reason: str,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.source = source
        self.reason = reason
        self.field = field
        message = f"{code.value} from {source.venue}/{source.channel}: {reason}"
        if field is not None:
            message = f"{message} [field={field}]"
        super().__init__(message)


@runtime_checkable
class MarketDataNormalizer(Protocol):
    """Adapter contract for deterministic raw-to-canonical conversion."""

    def normalize(self, message: RawMarketMessage) -> tuple[MarketEvent, ...]:
        """Normalize one raw message, preserving exchange event ordering."""
        ...


__all__ = [
    "MarketDataNormalizer",
    "MarketEvent",
    "NormalizationError",
    "NormalizationErrorCode",
    "RawMarketMessage",
]
