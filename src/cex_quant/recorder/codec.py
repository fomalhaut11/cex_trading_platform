"""Deterministic JSON codec for canonical market events."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeAlias, TypedDict, TypeVar, cast

from cex_quant.core import (
    CorrelationId,
    EventId,
    EventMetadata,
    EventSource,
    EventTimeSource,
    Price,
    Quantity,
    Rate,
    SchemaVersion,
    TimePrecision,
    TradeId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    AggregateTrade,
    AggressorSide,
    BestBidAsk,
    BookLevel,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketEvent,
    MarketTrade,
    MarkPriceUpdate,
    OpenInterestUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)

FORMAT_NAME = "cex_quant.market_event"
FORMAT_VERSION = 1

JsonObject: TypeAlias = dict[str, Any]
IdentifierT = TypeVar("IdentifierT")


class _CommonFields(TypedDict):
    metadata: EventMetadata
    instrument_id: InstrumentId


def encode_event(event: MarketEvent) -> bytes:
    """Encode one event to deterministic UTF-8 JSON without a line terminator."""

    payload = _event_to_dict(event)
    payload_bytes = _json_bytes(payload)
    envelope = {
        "checksum": hashlib.sha256(payload_bytes).hexdigest(),
        "event_type": type(event).__name__,
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "payload": payload,
    }
    return _json_bytes(envelope)


def decode_event(encoded: bytes) -> MarketEvent:
    """Decode and validate one complete record without a line terminator."""

    try:
        raw = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("record is not valid UTF-8 JSON") from error
    if not isinstance(raw, dict):
        raise ValueError("record envelope must be an object")
    if raw.get("format") != FORMAT_NAME or raw.get("format_version") != FORMAT_VERSION:
        raise LookupError("unsupported recorder format or version")
    event_type = raw.get("event_type")
    payload = raw.get("payload")
    checksum = raw.get("checksum")
    if not isinstance(event_type, str) or not isinstance(payload, dict):
        raise ValueError("record event_type and payload are required")
    if not isinstance(checksum, str):
        raise ValueError("record checksum is required")
    actual_checksum = hashlib.sha256(_json_bytes(payload)).hexdigest()
    if checksum != actual_checksum:
        raise ArithmeticError("record checksum mismatch")
    decoder = _DECODERS.get(event_type)
    if decoder is None:
        raise TypeError(f"unsupported event type: {event_type}")
    try:
        return decoder(cast(JsonObject, payload))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid {event_type} payload") from error


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fixed(value: Price | Quantity | Rate) -> JsonObject:
    return {"raw": value.raw, "scale": value.scale}


def _price(value: object) -> Price:
    raw = _object(value, "fixed-point")
    return Price(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _quantity(value: object) -> Quantity:
    raw = _object(value, "fixed-point")
    return Quantity(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _rate(value: object) -> Rate:
    raw = _object(value, "fixed-point")
    return Rate(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _metadata(value: object) -> EventMetadata:
    raw = _object(value, "metadata")
    source = _object(raw["source"], "source")
    return EventMetadata(
        event_id=EventId(_string(raw, "event_id")),
        event_time_ns=UnixNanos(_integer(raw, "event_time_ns")),
        receive_time_ns=UnixNanos(_integer(raw, "receive_time_ns")),
        source=EventSource(
            venue=VenueId(_string(source, "venue")),
            channel=_string(source, "channel"),
            connection_id=_optional_string(source, "connection_id"),
        ),
        schema_version=SchemaVersion(_integer(raw, "schema_version")),
        source_time_precision=TimePrecision(_string(raw, "source_time_precision")),
        event_time_source=EventTimeSource(_string(raw, "event_time_source")),
        sequence=_optional_integer(raw, "sequence"),
        correlation_id=_optional_identifier(raw, "correlation_id", CorrelationId),
        causation_id=_optional_identifier(raw, "causation_id", EventId),
    )


def _metadata_dict(value: EventMetadata) -> JsonObject:
    return {
        "causation_id": value.causation_id,
        "correlation_id": value.correlation_id,
        "event_id": value.event_id,
        "event_time_ns": value.event_time_ns,
        "event_time_source": value.event_time_source.value,
        "receive_time_ns": value.receive_time_ns,
        "schema_version": value.schema_version,
        "sequence": value.sequence,
        "source": {
            "channel": value.source.channel,
            "connection_id": value.source.connection_id,
            "venue": value.source.venue,
        },
        "source_time_precision": value.source_time_precision.value,
    }


def _instrument(value: object) -> InstrumentId:
    raw = _object(value, "instrument")
    return InstrumentId(
        venue=VenueId(_string(raw, "venue")),
        kind=InstrumentKind(_string(raw, "kind")),
        symbol=_string(raw, "symbol"),
    )


def _instrument_dict(value: InstrumentId) -> JsonObject:
    return {
        "kind": value.kind.value,
        "symbol": value.symbol,
        "venue": value.venue,
    }


def _level(value: object) -> BookLevel:
    raw = _object(value, "book level")
    return BookLevel(price=_price(raw["price"]), quantity=_quantity(raw["quantity"]))


def _level_dict(value: BookLevel) -> JsonObject:
    return {"price": _fixed(value.price), "quantity": _fixed(value.quantity)}


def _base(event: MarketEvent) -> JsonObject:
    return {
        "instrument_id": _instrument_dict(event.instrument_id),
        "metadata": _metadata_dict(event.metadata),
    }


def _event_to_dict(event: MarketEvent) -> JsonObject:
    payload = _base(event)
    match event:
        case MarketTrade():
            payload.update(
                trade_id=event.trade_id,
                price=_fixed(event.price),
                quantity=_fixed(event.quantity),
                aggressor_side=_side_value(event.aggressor_side),
            )
        case AggregateTrade():
            payload.update(
                aggregate_trade_id=event.aggregate_trade_id,
                first_trade_id=event.first_trade_id,
                last_trade_id=event.last_trade_id,
                price=_fixed(event.price),
                quantity=_fixed(event.quantity),
                aggressor_side=_side_value(event.aggressor_side),
            )
        case BestBidAsk():
            payload.update(bid=_level_dict(event.bid), ask=_level_dict(event.ask))
        case OrderBookDelta():
            payload.update(
                bids=[_level_dict(level) for level in event.bids],
                asks=[_level_dict(level) for level in event.asks],
                first_sequence=event.first_sequence,
                last_sequence=event.last_sequence,
                previous_sequence=event.previous_sequence,
            )
        case PartialBookFrame():
            payload.update(
                bids=[_level_dict(level) for level in event.bids],
                asks=[_level_dict(level) for level in event.asks],
                sequence=event.sequence,
            )
        case KlineUpdate():
            payload.update(
                interval=event.interval,
                start_time_ns=event.start_time_ns,
                end_time_ns=event.end_time_ns,
                open_price=_fixed(event.open_price),
                high_price=_fixed(event.high_price),
                low_price=_fixed(event.low_price),
                close_price=_fixed(event.close_price),
                volume=_fixed(event.volume),
                trade_count=event.trade_count,
                is_closed=event.is_closed,
            )
        case MarkPriceUpdate():
            payload["mark_price"] = _fixed(event.mark_price)
        case IndexPriceUpdate():
            payload["index_price"] = _fixed(event.index_price)
        case FundingRateUpdate():
            payload.update(
                funding_rate=_fixed(event.funding_rate),
                next_funding_time_ns=event.next_funding_time_ns,
            )
        case OpenInterestUpdate():
            payload["open_interest"] = _fixed(event.open_interest)
        case VenueOptionAnalyticsUpdate():
            payload.update(
                implied_volatility=event.implied_volatility,
                delta=event.delta,
                gamma=event.gamma,
                vega=event.vega,
                theta=event.theta,
            )
        case _:
            raise TypeError(f"unsupported event type: {type(event).__name__}")
    return payload


def _common(raw: JsonObject) -> _CommonFields:
    return {
        "metadata": _metadata(raw["metadata"]),
        "instrument_id": _instrument(raw["instrument_id"]),
    }


def _decode_market_trade(raw: JsonObject) -> MarketEvent:
    return MarketTrade(
        **_common(raw),
        trade_id=TradeId(_string(raw, "trade_id")),
        price=_price(raw["price"]),
        quantity=_quantity(raw["quantity"]),
        aggressor_side=_side(raw.get("aggressor_side")),
    )


def _decode_aggregate_trade(raw: JsonObject) -> MarketEvent:
    return AggregateTrade(
        **_common(raw),
        aggregate_trade_id=TradeId(_string(raw, "aggregate_trade_id")),
        first_trade_id=TradeId(_string(raw, "first_trade_id")),
        last_trade_id=TradeId(_string(raw, "last_trade_id")),
        price=_price(raw["price"]),
        quantity=_quantity(raw["quantity"]),
        aggressor_side=_side(raw.get("aggressor_side")),
    )


def _decode_best_bid_ask(raw: JsonObject) -> MarketEvent:
    return BestBidAsk(**_common(raw), bid=_level(raw["bid"]), ask=_level(raw["ask"]))


def _decode_order_book_delta(raw: JsonObject) -> MarketEvent:
    return OrderBookDelta(
        **_common(raw),
        bids=_levels(raw["bids"]),
        asks=_levels(raw["asks"]),
        first_sequence=_integer(raw, "first_sequence"),
        last_sequence=_integer(raw, "last_sequence"),
        previous_sequence=_optional_integer(raw, "previous_sequence"),
    )


def _decode_partial_book(raw: JsonObject) -> MarketEvent:
    return PartialBookFrame(
        **_common(raw),
        bids=_levels(raw["bids"]),
        asks=_levels(raw["asks"]),
        sequence=_optional_integer(raw, "sequence"),
    )


def _decode_kline(raw: JsonObject) -> MarketEvent:
    return KlineUpdate(
        **_common(raw),
        interval=_string(raw, "interval"),
        start_time_ns=UnixNanos(_integer(raw, "start_time_ns")),
        end_time_ns=UnixNanos(_integer(raw, "end_time_ns")),
        open_price=_price(raw["open_price"]),
        high_price=_price(raw["high_price"]),
        low_price=_price(raw["low_price"]),
        close_price=_price(raw["close_price"]),
        volume=_quantity(raw["volume"]),
        trade_count=_integer(raw, "trade_count"),
        is_closed=_boolean(raw, "is_closed"),
    )


def _decode_mark_price(raw: JsonObject) -> MarketEvent:
    return MarkPriceUpdate(**_common(raw), mark_price=_price(raw["mark_price"]))


def _decode_index_price(raw: JsonObject) -> MarketEvent:
    return IndexPriceUpdate(**_common(raw), index_price=_price(raw["index_price"]))


def _decode_funding_rate(raw: JsonObject) -> MarketEvent:
    return FundingRateUpdate(
        **_common(raw),
        funding_rate=_rate(raw["funding_rate"]),
        next_funding_time_ns=_optional_unix_nanos(raw, "next_funding_time_ns"),
    )


def _decode_open_interest(raw: JsonObject) -> MarketEvent:
    return OpenInterestUpdate(
        **_common(raw), open_interest=_quantity(raw["open_interest"])
    )


def _decode_option_analytics(raw: JsonObject) -> MarketEvent:
    return VenueOptionAnalyticsUpdate(
        **_common(raw),
        implied_volatility=_optional_float(raw, "implied_volatility"),
        delta=_optional_float(raw, "delta"),
        gamma=_optional_float(raw, "gamma"),
        vega=_optional_float(raw, "vega"),
        theta=_optional_float(raw, "theta"),
    )


_DECODERS: dict[str, Callable[[JsonObject], MarketEvent]] = {
    "MarketTrade": _decode_market_trade,
    "AggregateTrade": _decode_aggregate_trade,
    "BestBidAsk": _decode_best_bid_ask,
    "OrderBookDelta": _decode_order_book_delta,
    "PartialBookFrame": _decode_partial_book,
    "KlineUpdate": _decode_kline,
    "MarkPriceUpdate": _decode_mark_price,
    "IndexPriceUpdate": _decode_index_price,
    "FundingRateUpdate": _decode_funding_rate,
    "OpenInterestUpdate": _decode_open_interest,
    "VenueOptionAnalyticsUpdate": _decode_option_analytics,
}


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return cast(JsonObject, value)


def _string(raw: JsonObject, key: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _optional_string(raw: JsonObject, key: str) -> str | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{key} must be a string or null")
    return value


def _integer(raw: JsonObject, key: str) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    return value


def _optional_integer(raw: JsonObject, key: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer or null")
    return value


def _boolean(raw: JsonObject, key: str) -> bool:
    value = raw[key]
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _optional_float(raw: JsonObject, key: str) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be a number or null")
    return float(value)


def _optional_identifier(
    raw: JsonObject,
    key: str,
    factory: Callable[[str], IdentifierT],
) -> IdentifierT | None:
    value = _optional_string(raw, key)
    return None if value is None else factory(value)


def _optional_unix_nanos(raw: JsonObject, key: str) -> UnixNanos | None:
    value = _optional_integer(raw, key)
    return None if value is None else UnixNanos(value)


def _levels(value: object) -> tuple[BookLevel, ...]:
    if not isinstance(value, list):
        raise TypeError("book levels must be an array")
    return tuple(_level(item) for item in value)


def _side_value(value: AggressorSide | None) -> str | None:
    return None if value is None else value.value


def _side(value: object) -> AggressorSide | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("aggressor_side must be a string or null")
    return AggressorSide(value)


__all__ = [
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "decode_event",
    "encode_event",
]
