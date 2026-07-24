"""Normalize Binance private order payloads into OMS reconciliation facts."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TypeAlias, cast

from cex_quant.core import (
    ClientOrderId,
    Price,
    Quantity,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.oms import (
    OrderReconciliationSnapshot,
    OrderStatus,
    ReconciliationSource,
)

from .binance import BinanceProduct

JsonObject: TypeAlias = dict[str, object]


class BinanceOrderNormalizationErrorCode(StrEnum):
    MALFORMED_PAYLOAD = "malformed_payload"
    WRONG_EVENT_TYPE = "wrong_event_type"
    UNSUPPORTED_STATUS = "unsupported_status"
    IDENTITY_MISMATCH = "identity_mismatch"


class BinanceOrderNormalizationError(ValueError):
    def __init__(
        self,
        *,
        code: BinanceOrderNormalizationErrorCode,
        reason: str,
    ) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


_STATUS_MAP: dict[str, OrderStatus] = {
    "PENDING_NEW": OrderStatus.OPEN,
    "NEW": OrderStatus.OPEN,
    "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
    "FILLED": OrderStatus.FILLED,
    "PENDING_CANCEL": OrderStatus.CANCEL_PENDING,
    "CANCELED": OrderStatus.CANCELED,
    "REJECTED": OrderStatus.REJECTED,
    "EXPIRED": OrderStatus.EXPIRED,
    "EXPIRED_IN_MATCH": OrderStatus.EXPIRED,
}


def normalize_binance_order_query(
    product: BinanceProduct,
    payload: bytes | JsonObject,
    *,
    received_at_ns: UnixNanos,
    expected_client_order_id: ClientOrderId | None = None,
) -> OrderReconciliationSnapshot:
    """Normalize a successful Spot, USD-M or COIN-M query-order response."""

    _require_product(product)
    raw = _payload_object(payload)
    client_order_id = ClientOrderId(_string(raw, "clientOrderId"))
    _verify_identity(client_order_id, expected_client_order_id)
    status_text = _string(raw, "status")
    status = _status(status_text)
    filled_text = _decimal_string(raw, "executedQty")
    update_ms = _optional_integer(raw, "updateTime")
    observed_at_ns = (
        received_at_ns
        if update_ms is None
        else _milliseconds_to_nanos(update_ms, "updateTime")
    )
    order_id = _identifier(raw, "orderId")
    average_fill_price = _query_average_price(
        product,
        raw,
        filled_text=filled_text,
    )
    return OrderReconciliationSnapshot(
        source=ReconciliationSource.REST_QUERY,
        source_update_id=(
            f"{product.value}:{order_id}:"
            f"{update_ms if update_ms is not None else 'no-update-time'}:"
            f"{status_text}:{filled_text}"
        ),
        client_order_id=client_order_id,
        venue_order_id=VenueOrderId(order_id),
        status=status,
        cumulative_filled_quantity=Quantity.from_str(filled_text),
        average_fill_price=average_fill_price,
        observed_at_ns=observed_at_ns,
        reason=_reason(raw, status_text),
    )


def normalize_binance_user_order_update(
    product: BinanceProduct,
    payload: bytes | JsonObject,
    *,
    expected_client_order_id: ClientOrderId | None = None,
) -> OrderReconciliationSnapshot:
    """Normalize Spot executionReport or Futures ORDER_TRADE_UPDATE."""

    _require_product(product)
    root = _payload_object(payload)
    if product is BinanceProduct.SPOT:
        return _spot_user_update(root, expected_client_order_id)
    return _futures_user_update(product, root, expected_client_order_id)


def _spot_user_update(
    root: JsonObject,
    expected_client_order_id: ClientOrderId | None,
) -> OrderReconciliationSnapshot:
    event_value = root.get("event")
    raw = _object(event_value, "event") if event_value is not None else root
    if _string(raw, "e") != "executionReport":
        raise BinanceOrderNormalizationError(
            code=BinanceOrderNormalizationErrorCode.WRONG_EVENT_TYPE,
            reason="Spot user event is not executionReport",
        )
    client_order_id = ClientOrderId(_string(raw, "c"))
    _verify_identity(client_order_id, expected_client_order_id)
    status_text = _string(raw, "X")
    filled_text = _decimal_string(raw, "z")
    order_id = _identifier(raw, "i")
    transaction_ms = _integer(raw, "T")
    execution_id = _optional_identifier(raw, "I")
    if execution_id is None:
        execution_id = (
            f"{transaction_ms}:{_string(raw, 'x')}:"
            f"{_optional_identifier(raw, 't') or '-1'}"
        )
    return OrderReconciliationSnapshot(
        source=ReconciliationSource.USER_STREAM,
        source_update_id=f"spot:{order_id}:{execution_id}",
        client_order_id=client_order_id,
        venue_order_id=VenueOrderId(order_id),
        status=_status(status_text),
        cumulative_filled_quantity=Quantity.from_str(filled_text),
        average_fill_price=_average_from_quote_and_quantity(
            _decimal_string(raw, "Z"),
            filled_text,
        ),
        observed_at_ns=_milliseconds_to_nanos(transaction_ms, "T"),
        reason=_reason(raw, status_text, reject_key="r"),
    )


def _futures_user_update(
    product: BinanceProduct,
    root: JsonObject,
    expected_client_order_id: ClientOrderId | None,
) -> OrderReconciliationSnapshot:
    if _string(root, "e") != "ORDER_TRADE_UPDATE":
        raise BinanceOrderNormalizationError(
            code=BinanceOrderNormalizationErrorCode.WRONG_EVENT_TYPE,
            reason="Futures user event is not ORDER_TRADE_UPDATE",
        )
    raw = _object(root.get("o"), "o")
    client_order_id = ClientOrderId(_string(raw, "c"))
    _verify_identity(client_order_id, expected_client_order_id)
    status_text = _string(raw, "X")
    filled_text = _decimal_string(raw, "z")
    order_id = _identifier(raw, "i")
    transaction_ms = _integer(root, "T")
    event_ms = _integer(root, "E")
    source_update_id = (
        f"{product.value}:{order_id}:{event_ms}:{transaction_ms}:"
        f"{_string(raw, 'x')}:{_optional_identifier(raw, 't') or '-1'}"
    )
    return OrderReconciliationSnapshot(
        source=ReconciliationSource.USER_STREAM,
        source_update_id=source_update_id,
        client_order_id=client_order_id,
        venue_order_id=VenueOrderId(order_id),
        status=_status(status_text),
        cumulative_filled_quantity=Quantity.from_str(filled_text),
        average_fill_price=_positive_price_or_none(
            _decimal_string(raw, "ap")
        ),
        observed_at_ns=_milliseconds_to_nanos(transaction_ms, "T"),
        reason=_reason(raw, status_text),
    )


def _query_average_price(
    product: BinanceProduct,
    raw: JsonObject,
    *,
    filled_text: str,
) -> Price | None:
    if product is BinanceProduct.SPOT:
        return _average_from_quote_and_quantity(
            _decimal_string(raw, "cummulativeQuoteQty"),
            filled_text,
        )
    return _positive_price_or_none(_decimal_string(raw, "avgPrice"))


def _average_from_quote_and_quantity(
    quote_text: str,
    quantity_text: str,
) -> Price | None:
    try:
        quantity = Decimal(quantity_text)
        if quantity == 0:
            return None
        average = Decimal(quote_text) / quantity
    except (InvalidOperation, ZeroDivisionError) as error:
        raise _malformed("invalid average-price inputs") from error
    if not average.is_finite() or average <= 0:
        raise _malformed("derived average fill price must be positive")
    return Price.from_str(format(average, "f"))


def _positive_price_or_none(value: str) -> Price | None:
    price = Price.from_str(value)
    return None if price.raw == 0 else price


def _status(value: str) -> OrderStatus:
    try:
        return _STATUS_MAP[value]
    except KeyError as error:
        raise BinanceOrderNormalizationError(
            code=BinanceOrderNormalizationErrorCode.UNSUPPORTED_STATUS,
            reason=f"unsupported Binance order status: {value}",
        ) from error


def _reason(
    raw: JsonObject,
    status: str,
    *,
    reject_key: str | None = None,
) -> str:
    details: list[str] = []
    if status in {"REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}:
        details.append(f"binance_status={status}")
    if reject_key is not None:
        reject = raw.get(reject_key)
        if isinstance(reject, str) and reject not in {"", "NONE"}:
            details.append(f"binance_reason={reject}")
    expiry = raw.get("expiryReason")
    if isinstance(expiry, str) and expiry:
        details.append(f"binance_expiry_reason={expiry}")
    return ";".join(details)


def _verify_identity(
    actual: ClientOrderId,
    expected: ClientOrderId | None,
) -> None:
    if expected is not None and actual != expected:
        raise BinanceOrderNormalizationError(
            code=BinanceOrderNormalizationErrorCode.IDENTITY_MISMATCH,
            reason="Binance payload client order ID does not match query",
        )


def _payload_object(payload: bytes | JsonObject) -> JsonObject:
    if isinstance(payload, dict):
        return payload
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _malformed("payload is not valid JSON") from error
    return _object(value, "payload")


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise _malformed(f"{name} must be an object")
    return cast(JsonObject, value)


def _string(raw: JsonObject, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise _malformed(f"{key} must be a non-empty string")
    return value


def _decimal_string(raw: JsonObject, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise _malformed(f"{key} must be a non-empty decimal string")
    try:
        decimal = Decimal(value)
    except InvalidOperation as error:
        raise _malformed(f"{key} must be a decimal string") from error
    if not decimal.is_finite() or decimal < 0:
        raise _malformed(f"{key} must be a non-negative finite decimal")
    return value


def _integer(raw: JsonObject, key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _malformed(f"{key} must be an integer")
    return value


def _optional_integer(raw: JsonObject, key: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _malformed(f"{key} must be an integer or null")
    return value


def _identifier(raw: JsonObject, key: str) -> str:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise _malformed(f"{key} must be a string or integer identifier")
    text = str(value)
    if not text:
        raise _malformed(f"{key} cannot be empty")
    return text


def _optional_identifier(raw: JsonObject, key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise _malformed(f"{key} must be a string, integer or null")
    return str(value)


def _milliseconds_to_nanos(value: int, field_name: str) -> UnixNanos:
    if value < 0:
        raise _malformed(f"{field_name} cannot be negative")
    return UnixNanos(value * 1_000_000)


def _require_product(product: BinanceProduct) -> None:
    if not isinstance(product, BinanceProduct):
        raise ValueError("product must be a BinanceProduct")


def _malformed(reason: str) -> BinanceOrderNormalizationError:
    return BinanceOrderNormalizationError(
        code=BinanceOrderNormalizationErrorCode.MALFORMED_PAYLOAD,
        reason=reason,
    )


__all__ = [
    "BinanceOrderNormalizationError",
    "BinanceOrderNormalizationErrorCode",
    "normalize_binance_order_query",
    "normalize_binance_user_order_update",
]
