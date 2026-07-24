"""Immutable venue-neutral market facts.

Objects in this module describe observations only. Validation and mutable market
state belong to separate components. Venue analytics are explicitly labelled
and cannot be confused with registered system features.
"""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import EventMetadata, Price, Quantity, Rate, TradeId, UnixNanos
from cex_quant.instruments import InstrumentId


class AggressorSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True, kw_only=True)
class BookLevel:
    """Price level; zero quantity represents deletion in a delta."""

    price: Price
    quantity: Quantity

    def __post_init__(self) -> None:
        if self.price.raw <= 0:
            raise ValueError("book price must be positive")
        if self.quantity.raw < 0:
            raise ValueError("book quantity cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketTrade:
    metadata: EventMetadata
    instrument_id: InstrumentId
    trade_id: TradeId
    price: Price
    quantity: Quantity
    aggressor_side: AggressorSide | None

    def __post_init__(self) -> None:
        _require_positive_trade(self.price, self.quantity)


@dataclass(frozen=True, slots=True, kw_only=True)
class AggregateTrade:
    metadata: EventMetadata
    instrument_id: InstrumentId
    aggregate_trade_id: TradeId
    first_trade_id: TradeId
    last_trade_id: TradeId
    price: Price
    quantity: Quantity
    aggressor_side: AggressorSide | None

    def __post_init__(self) -> None:
        _require_positive_trade(self.price, self.quantity)


@dataclass(frozen=True, slots=True, kw_only=True)
class BestBidAsk:
    metadata: EventMetadata
    instrument_id: InstrumentId
    bid: BookLevel
    ask: BookLevel

    def __post_init__(self) -> None:
        if self.bid.quantity.raw == 0 or self.ask.quantity.raw == 0:
            raise ValueError("best bid and ask quantities must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderBookDelta:
    metadata: EventMetadata
    instrument_id: InstrumentId
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    first_sequence: int
    last_sequence: int
    previous_sequence: int | None = None

    def __post_init__(self) -> None:
        if self.first_sequence < 0 or self.last_sequence < self.first_sequence:
            raise ValueError("invalid order-book sequence range")
        if self.previous_sequence is not None and self.previous_sequence < 0:
            raise ValueError("previous_sequence must be non-negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class PartialBookFrame:
    metadata: EventMetadata
    instrument_id: InstrumentId
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    sequence: int | None

    def __post_init__(self) -> None:
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if any(level.quantity.raw == 0 for level in (*self.bids, *self.asks)):
            raise ValueError("partial-book levels must have positive quantity")


@dataclass(frozen=True, slots=True, kw_only=True)
class KlineUpdate:
    """Venue-published interval bar update; not a derived registered feature."""

    metadata: EventMetadata
    instrument_id: InstrumentId
    interval: str
    start_time_ns: UnixNanos
    end_time_ns: UnixNanos
    open_price: Price
    high_price: Price
    low_price: Price
    close_price: Price
    volume: Quantity
    trade_count: int
    is_closed: bool

    def __post_init__(self) -> None:
        if not self.interval:
            raise ValueError("kline interval cannot be empty")
        if self.start_time_ns < 0 or self.end_time_ns < self.start_time_ns:
            raise ValueError("invalid kline time range")
        prices = (
            self.open_price,
            self.high_price,
            self.low_price,
            self.close_price,
        )
        if any(price.raw <= 0 for price in prices):
            raise ValueError("kline prices must be positive")
        decimal_prices = tuple(price.as_decimal() for price in prices)
        if self.high_price.as_decimal() != max(decimal_prices):
            raise ValueError("high_price must be the highest OHLC price")
        if self.low_price.as_decimal() != min(decimal_prices):
            raise ValueError("low_price must be the lowest OHLC price")
        if self.volume.raw < 0 or self.trade_count < 0:
            raise ValueError("kline volume and trade_count cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkPriceUpdate:
    metadata: EventMetadata
    instrument_id: InstrumentId
    mark_price: Price

    def __post_init__(self) -> None:
        if self.mark_price.raw <= 0:
            raise ValueError("mark_price must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexPriceUpdate:
    metadata: EventMetadata
    instrument_id: InstrumentId
    index_price: Price

    def __post_init__(self) -> None:
        if self.index_price.raw <= 0:
            raise ValueError("index_price must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingRateUpdate:
    metadata: EventMetadata
    instrument_id: InstrumentId
    funding_rate: Rate
    next_funding_time_ns: UnixNanos | None


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenInterestUpdate:
    metadata: EventMetadata
    instrument_id: InstrumentId
    open_interest: Quantity

    def __post_init__(self) -> None:
        if self.open_interest.raw < 0:
            raise ValueError("open_interest cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class VenueOptionAnalyticsUpdate:
    """Venue-published reference analytics, never authoritative features."""

    metadata: EventMetadata
    instrument_id: InstrumentId
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None
    theta: float | None = None


def _require_positive_trade(price: Price, quantity: Quantity) -> None:
    if price.raw <= 0 or quantity.raw <= 0:
        raise ValueError("trade price and quantity must be positive")


__all__ = [
    "AggregateTrade",
    "AggressorSide",
    "BestBidAsk",
    "BookLevel",
    "FundingRateUpdate",
    "IndexPriceUpdate",
    "KlineUpdate",
    "MarkPriceUpdate",
    "MarketTrade",
    "OpenInterestUpdate",
    "OrderBookDelta",
    "PartialBookFrame",
    "VenueOptionAnalyticsUpdate",
]
