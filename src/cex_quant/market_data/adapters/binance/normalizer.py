"""Binance JSON stream normalization without network or SDK dependencies."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from json import JSONDecodeError
from typing import Any, Protocol

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventTimeSource,
    Price,
    Quantity,
    Rate,
    SchemaVersion,
    TimePrecision,
    TradeId,
    UnixNanos,
    VenueId,
    microseconds_to_nanos,
    milliseconds_to_nanos,
)
from cex_quant.instruments import InstrumentId
from cex_quant.market_data.events import (
    AggregateTrade,
    AggressorSide,
    BestBidAsk,
    BookLevel,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    OrderBookDelta,
    PartialBookFrame,
)
from cex_quant.market_data.normalization import (
    MarketEvent,
    NormalizationError,
    NormalizationErrorCode,
    RawMarketMessage,
)

BINANCE_VENUE = VenueId("BINANCE")


class BinanceProduct(StrEnum):
    SPOT = "spot"
    USD_M_FUTURES = "usd_m_futures"
    COIN_M_FUTURES = "coin_m_futures"
    OPTIONS = "options"


class InstrumentResolver(Protocol):
    def resolve(self, product: BinanceProduct, symbol: str) -> InstrumentId | None:
        """Return a canonical instrument for an exact venue symbol."""
        ...


class StaticInstrumentResolver:
    """Explicit symbol table suitable for tests and immutable runtime snapshots."""

    def __init__(
        self,
        instruments: Mapping[tuple[BinanceProduct, str], InstrumentId],
    ) -> None:
        self._instruments = dict(instruments)

    def resolve(self, product: BinanceProduct, symbol: str) -> InstrumentId | None:
        return self._instruments.get((product, symbol))


class BinanceMarketDataNormalizer:
    """Normalize selected Binance raw or combined WebSocket stream payloads."""

    def __init__(
        self,
        *,
        product: BinanceProduct,
        instruments: InstrumentResolver,
        timestamp_precision: TimePrecision = TimePrecision.MILLISECOND,
    ) -> None:
        if timestamp_precision not in {
            TimePrecision.MILLISECOND,
            TimePrecision.MICROSECOND,
        }:
            raise ValueError(
                "Binance JSON timestamps must be milliseconds or microseconds"
            )
        self._product = product
        self._instruments = instruments
        self._timestamp_precision = timestamp_precision

    def normalize(self, message: RawMarketMessage) -> tuple[MarketEvent, ...]:
        if message.source.venue != BINANCE_VENUE:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "source venue is not BINANCE",
                "source.venue",
            )
        payload, stream = self._decode(message)
        event_type = payload.get("e")
        channel = (stream or message.source.channel).lower()

        if event_type == "trade":
            return (self._trade(message, payload),)
        if event_type == "aggTrade":
            return (self._aggregate_trade(message, payload),)
        if event_type == "depthUpdate":
            return (self._depth(message, payload),)
        if event_type == "markPriceUpdate":
            return self._mark_price_bundle(message, payload)
        if event_type == "kline":
            return (self._kline(message, payload),)
        if event_type == "bookTicker" or "bookticker" in channel:
            return (self._book_ticker(message, payload),)
        if "lastUpdateId" in payload and "bids" in payload and "asks" in payload:
            return (self._partial_book(message, payload, stream),)

        raise self._error(
            message,
            NormalizationErrorCode.UNSUPPORTED_MESSAGE,
            f"unsupported Binance event type: {event_type!r}",
            "e",
        )

    def _decode(
        self, message: RawMarketMessage
    ) -> tuple[dict[str, Any], str | None]:
        try:
            decoded = json.loads(message.payload)
        except (JSONDecodeError, UnicodeDecodeError) as error:
            raise self._error(
                message,
                NormalizationErrorCode.MALFORMED_PAYLOAD,
                "payload is not valid UTF-8 JSON",
            ) from error
        if not isinstance(decoded, dict):
            raise self._error(
                message,
                NormalizationErrorCode.MALFORMED_PAYLOAD,
                "top-level payload must be an object",
            )
        stream = decoded.get("stream")
        if "data" in decoded:
            data = decoded["data"]
            if not isinstance(data, dict):
                raise self._error(
                    message,
                    NormalizationErrorCode.MALFORMED_PAYLOAD,
                    "combined stream data must be an object",
                    "data",
                )
            decoded = data
        return decoded, stream if isinstance(stream, str) else None

    def _trade(self, message: RawMarketMessage, data: dict[str, Any]) -> MarketTrade:
        instrument = self._instrument(message, data)
        return MarketTrade(
            metadata=self._metadata(message, data, preferred_time_field="T"),
            instrument_id=instrument,
            trade_id=TradeId(str(self._required(data, "t", message))),
            price=self._price(data, "p", message),
            quantity=self._quantity(data, "q", message),
            aggressor_side=self._aggressor(data, message),
        )

    def _aggregate_trade(
        self, message: RawMarketMessage, data: dict[str, Any]
    ) -> AggregateTrade:
        instrument = self._instrument(message, data)
        aggregate_id = TradeId(str(self._required(data, "a", message)))
        first_id = TradeId(str(data.get("f", data["a"])))
        last_id = TradeId(str(data.get("l", data["a"])))
        return AggregateTrade(
            metadata=self._metadata(message, data, preferred_time_field="T"),
            instrument_id=instrument,
            aggregate_trade_id=aggregate_id,
            first_trade_id=first_id,
            last_trade_id=last_id,
            price=self._price(data, "p", message),
            quantity=self._quantity(data, "q", message),
            aggressor_side=self._aggressor(data, message),
        )

    def _book_ticker(
        self, message: RawMarketMessage, data: dict[str, Any]
    ) -> BestBidAsk:
        instrument = self._instrument(message, data)
        sequence = self._optional_non_negative_int(data, "u", message)
        return BestBidAsk(
            metadata=self._metadata(
                message,
                data,
                preferred_time_field="T",
                sequence=sequence,
            ),
            instrument_id=instrument,
            bid=BookLevel(
                price=self._price(data, "b", message),
                quantity=self._quantity(data, "B", message),
            ),
            ask=BookLevel(
                price=self._price(data, "a", message),
                quantity=self._quantity(data, "A", message),
            ),
        )

    def _depth(
        self, message: RawMarketMessage, data: dict[str, Any]
    ) -> OrderBookDelta:
        instrument = self._instrument(message, data)
        first_sequence = self._non_negative_int(data, "U", message)
        last_sequence = self._non_negative_int(data, "u", message)
        previous = self._optional_non_negative_int(data, "pu", message)
        return OrderBookDelta(
            metadata=self._metadata(
                message,
                data,
                preferred_time_field="T",
                sequence=last_sequence,
            ),
            instrument_id=instrument,
            bids=self._levels(data, "b", message, descending=True),
            asks=self._levels(data, "a", message, descending=False),
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            previous_sequence=previous,
        )

    def _partial_book(
        self,
        message: RawMarketMessage,
        data: dict[str, Any],
        stream: str | None,
    ) -> PartialBookFrame:
        symbol = self._symbol(data, stream, message)
        instrument = self._resolve_symbol(symbol, message)
        sequence = self._non_negative_int(data, "lastUpdateId", message)
        return PartialBookFrame(
            metadata=self._metadata(message, data, sequence=sequence),
            instrument_id=instrument,
            bids=self._levels(data, "bids", message, descending=True),
            asks=self._levels(data, "asks", message, descending=False),
            sequence=sequence,
        )

    def _mark_price_bundle(
        self, message: RawMarketMessage, data: dict[str, Any]
    ) -> tuple[MarketEvent, ...]:
        instrument = self._instrument(message, data)
        events: list[MarketEvent] = []
        if "p" in data:
            events.append(
                MarkPriceUpdate(
                    metadata=self._metadata(message, data, discriminator="mark"),
                    instrument_id=instrument,
                    mark_price=self._price(data, "p", message),
                )
            )
        if "i" in data:
            events.append(
                IndexPriceUpdate(
                    metadata=self._metadata(message, data, discriminator="index"),
                    instrument_id=instrument,
                    index_price=self._price(data, "i", message),
                )
            )
        if "r" in data:
            try:
                rate = Rate.from_str(str(data["r"]))
            except ValueError as error:
                raise self._error(
                    message,
                    NormalizationErrorCode.INVALID_FIELD,
                    str(error),
                    "r",
                ) from error
            next_funding = (
                self._to_nanos(self._non_negative_int(data, "T", message))
                if "T" in data
                else None
            )
            events.append(
                FundingRateUpdate(
                    metadata=self._metadata(message, data, discriminator="funding"),
                    instrument_id=instrument,
                    funding_rate=rate,
                    next_funding_time_ns=next_funding,
                )
            )
        if not events:
            raise self._error(
                message,
                NormalizationErrorCode.MISSING_FIELD,
                "mark price update contains no mark, index or funding value",
            )
        return tuple(events)

    def _kline(self, message: RawMarketMessage, data: dict[str, Any]) -> KlineUpdate:
        instrument = self._instrument(message, data)
        raw_kline = self._required(data, "k", message)
        if not isinstance(raw_kline, dict):
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "kline payload must be an object",
                "k",
            )
        interval = self._required(raw_kline, "i", message)
        closed = self._required(raw_kline, "x", message)
        if not isinstance(interval, str) or not interval:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "kline interval must be a non-empty string",
                "k.i",
            )
        if not isinstance(closed, bool):
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "kline closed flag must be boolean",
                "k.x",
            )
        return KlineUpdate(
            metadata=self._metadata(message, data, discriminator="kline"),
            instrument_id=instrument,
            interval=interval,
            start_time_ns=self._to_nanos(
                self._non_negative_int(raw_kline, "t", message)
            ),
            end_time_ns=self._to_nanos(
                self._non_negative_int(raw_kline, "T", message)
            ),
            open_price=self._price(raw_kline, "o", message),
            high_price=self._price(raw_kline, "h", message),
            low_price=self._price(raw_kline, "l", message),
            close_price=self._price(raw_kline, "c", message),
            volume=self._quantity(raw_kline, "v", message),
            trade_count=self._non_negative_int(raw_kline, "n", message),
            is_closed=closed,
        )

    def _metadata(
        self,
        message: RawMarketMessage,
        data: dict[str, Any],
        *,
        preferred_time_field: str | None = None,
        sequence: int | None = None,
        discriminator: str = "",
    ) -> EventMetadata:
        time_field = None
        if preferred_time_field is not None and preferred_time_field in data:
            time_field = preferred_time_field
        elif "E" in data:
            time_field = "E"
        if time_field is None:
            event_time = message.receive_time_ns
            time_source = EventTimeSource.RECEIVE_CLOCK
            precision = TimePrecision.NANOSECOND
        else:
            timestamp = self._non_negative_int(data, time_field, message)
            event_time = self._to_nanos(timestamp)
            time_source = EventTimeSource.VENUE
            precision = self._timestamp_precision
        return EventMetadata(
            event_id=self._event_id(message, discriminator),
            event_time_ns=event_time,
            receive_time_ns=message.receive_time_ns,
            source=message.source,
            schema_version=SchemaVersion(1),
            source_time_precision=precision,
            event_time_source=time_source,
            sequence=sequence,
        )

    def _instrument(
        self, message: RawMarketMessage, data: dict[str, Any]
    ) -> InstrumentId:
        symbol = self._required(data, "s", message)
        if not isinstance(symbol, str) or not symbol:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "symbol must be a non-empty string",
                "s",
            )
        return self._resolve_symbol(symbol, message)

    def _resolve_symbol(
        self, symbol: str, message: RawMarketMessage
    ) -> InstrumentId:
        instrument = self._instruments.resolve(self._product, symbol.upper())
        if instrument is None:
            raise self._error(
                message,
                NormalizationErrorCode.UNKNOWN_INSTRUMENT,
                f"symbol is not registered for {self._product.value}: {symbol}",
                "s",
            )
        return instrument

    def _symbol(
        self,
        data: dict[str, Any],
        stream: str | None,
        message: RawMarketMessage,
    ) -> str:
        symbol = data.get("s")
        if isinstance(symbol, str) and symbol:
            return symbol
        source = stream or message.source.channel
        if "@" in source:
            candidate = source.split("@", 1)[0]
            if candidate:
                return candidate
        raise self._error(
            message,
            NormalizationErrorCode.MISSING_FIELD,
            "symbol is absent and cannot be inferred from stream name",
            "s",
        )

    def _levels(
        self,
        data: dict[str, Any],
        field: str,
        message: RawMarketMessage,
        *,
        descending: bool,
    ) -> tuple[BookLevel, ...]:
        raw_levels = self._required(data, field, message)
        if not isinstance(raw_levels, list):
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "book levels must be an array",
                field,
            )
        levels: list[BookLevel] = []
        for index, raw_level in enumerate(raw_levels):
            if not isinstance(raw_level, list) or len(raw_level) < 2:
                raise self._error(
                    message,
                    NormalizationErrorCode.INVALID_FIELD,
                    "book level must contain price and quantity",
                    f"{field}[{index}]",
                )
            try:
                level = BookLevel(
                    price=Price.from_str(str(raw_level[0])),
                    quantity=Quantity.from_str(str(raw_level[1])),
                )
            except ValueError as error:
                raise self._error(
                    message,
                    NormalizationErrorCode.INVALID_FIELD,
                    str(error),
                    f"{field}[{index}]",
                ) from error
            levels.append(level)
        levels.sort(key=lambda level: level.price.as_decimal(), reverse=descending)
        return tuple(levels)

    def _price(
        self, data: dict[str, Any], field: str, message: RawMarketMessage
    ) -> Price:
        try:
            return Price.from_str(str(self._required(data, field, message)))
        except ValueError as error:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                str(error),
                field,
            ) from error

    def _quantity(
        self, data: dict[str, Any], field: str, message: RawMarketMessage
    ) -> Quantity:
        try:
            return Quantity.from_str(str(self._required(data, field, message)))
        except ValueError as error:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                str(error),
                field,
            ) from error

    def _aggressor(
        self, data: dict[str, Any], message: RawMarketMessage
    ) -> AggressorSide:
        buyer_is_maker = self._required(data, "m", message)
        if not isinstance(buyer_is_maker, bool):
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "maker flag must be boolean",
                "m",
            )
        return AggressorSide.SELL if buyer_is_maker else AggressorSide.BUY

    def _non_negative_int(
        self, data: dict[str, Any], field: str, message: RawMarketMessage
    ) -> int:
        value = self._required(data, field, message)
        if isinstance(value, bool):
            value = None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "field must be an integer",
                field,
            ) from error
        if parsed < 0:
            raise self._error(
                message,
                NormalizationErrorCode.INVALID_FIELD,
                "field must be non-negative",
                field,
            )
        return parsed

    def _optional_non_negative_int(
        self, data: dict[str, Any], field: str, message: RawMarketMessage
    ) -> int | None:
        if field not in data:
            return None
        return self._non_negative_int(data, field, message)

    def _required(
        self, data: dict[str, Any], field: str, message: RawMarketMessage
    ) -> Any:
        if field not in data:
            raise self._error(
                message,
                NormalizationErrorCode.MISSING_FIELD,
                "required field is absent",
                field,
            )
        return data[field]

    def _event_id(self, message: RawMarketMessage, discriminator: str) -> EventId:
        digest = hashlib.blake2b(digest_size=16)
        digest.update(str(message.source.venue).encode())
        digest.update(message.source.channel.encode())
        digest.update(str(message.receive_time_ns).encode())
        digest.update(message.payload)
        digest.update(discriminator.encode())
        return EventId(digest.hexdigest())

    def _to_nanos(self, timestamp: int) -> UnixNanos:
        if self._timestamp_precision is TimePrecision.MICROSECOND:
            return microseconds_to_nanos(timestamp)
        return milliseconds_to_nanos(timestamp)

    @staticmethod
    def _error(
        message: RawMarketMessage,
        code: NormalizationErrorCode,
        reason: str,
        field: str | None = None,
    ) -> NormalizationError:
        return NormalizationError(
            code=code,
            source=message.source,
            reason=reason,
            field=field,
        )


__all__ = [
    "BINANCE_VENUE",
    "BinanceMarketDataNormalizer",
    "BinanceProduct",
    "InstrumentResolver",
    "StaticInstrumentResolver",
]
