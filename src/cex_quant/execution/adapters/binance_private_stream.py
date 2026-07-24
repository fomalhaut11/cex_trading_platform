"""Binance private-order stream protocol mapping and message classification."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias, cast
from urllib.parse import quote

from cex_quant.core import AccountId
from cex_quant.oms import OrderReconciliationSnapshot

from ..gateway import ExecutionQueryError, ExecutionTransportError
from .binance import BinanceProduct
from .binance_authenticated import (
    BinanceCredentialProvider,
    BinanceCredentials,
    BinanceHttpRequest,
    BinanceHttpResponse,
    BinanceHttpTransport,
    BinanceHttpTransportFailure,
    canonical_query,
)
from .binance_reconciliation import (
    BinanceOrderNormalizationError,
    BinanceOrderNormalizationErrorCode,
    normalize_binance_user_order_update,
)

JsonObject: TypeAlias = dict[str, object]


class BinancePrivateStreamDisposition(StrEnum):
    ORDER_UPDATE = "order_update"
    IGNORED = "ignored"
    RECONNECT_REQUIRED = "reconnect_required"


class BinanceUserStreamLeaseExpiredError(ExecutionQueryError):
    """Futures listenKey is no longer valid and must be recreated."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinancePrivateStreamMessage:
    disposition: BinancePrivateStreamDisposition
    snapshot: OrderReconciliationSnapshot | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if (
            self.disposition is BinancePrivateStreamDisposition.ORDER_UPDATE
        ) != (self.snapshot is not None):
            raise ValueError("only order-update messages contain a snapshot")


_RECONNECT_EVENTS = frozenset(
    {
        "eventStreamTerminated",
        "listenKeyExpired",
        "serverShutdown",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BinancePrivateOrderStreamProcessor:
    """Classify one private-stream frame and normalize order updates."""

    product: BinanceProduct

    def __post_init__(self) -> None:
        if not isinstance(self.product, BinanceProduct):
            raise ValueError("product must be a BinanceProduct")

    def process(self, payload: str | bytes) -> BinancePrivateStreamMessage:
        raw = _payload_object(payload)
        event = _event_object(self.product, raw)
        event_type = event.get("e")
        if not isinstance(event_type, str) or not event_type:
            raise _malformed("private stream event type must be a string")
        if event_type in _RECONNECT_EVENTS:
            return BinancePrivateStreamMessage(
                disposition=(
                    BinancePrivateStreamDisposition.RECONNECT_REQUIRED
                ),
                reason=event_type,
            )
        expected_order_event = (
            "executionReport"
            if self.product is BinanceProduct.SPOT
            else "ORDER_TRADE_UPDATE"
        )
        if event_type != expected_order_event:
            return BinancePrivateStreamMessage(
                disposition=BinancePrivateStreamDisposition.IGNORED,
                reason=event_type,
            )
        return BinancePrivateStreamMessage(
            disposition=BinancePrivateStreamDisposition.ORDER_UPDATE,
            snapshot=normalize_binance_user_order_update(
                self.product,
                raw,
            ),
        )


class BinanceFuturesUserStreamLease:
    """Opaque Futures listenKey that never appears in representations."""

    __slots__ = ("_listen_key", "product")

    def __init__(
        self,
        *,
        product: BinanceProduct,
        listen_key: str,
    ) -> None:
        if product not in {BinanceProduct.USD_M, BinanceProduct.COIN_M}:
            raise ValueError("Futures lease requires USD-M or COIN-M")
        if not listen_key or listen_key.strip() != listen_key:
            raise ValueError("listen_key must be non-empty and trimmed")
        self.product = product
        self._listen_key = listen_key

    def __repr__(self) -> str:
        return (
            "BinanceFuturesUserStreamLease("
            f"product={self.product.value!r}, listen_key=<redacted>)"
        )

    def websocket_uri(self, base_url: str) -> str:
        if not base_url.startswith("wss://"):
            raise ValueError("base_url must use wss")
        return f"{base_url.rstrip('/')}/ws/{quote(self._listen_key, safe='')}"

    def matches(self, other: BinanceFuturesUserStreamLease) -> bool:
        return (
            self.product is other.product
            and self._listen_key == other._listen_key
        )


@dataclass(slots=True, kw_only=True)
class BinanceFuturesUserStreamControlAdapter:
    """Create, renew and close the 60-minute Futures listenKey lease."""

    product: BinanceProduct
    credential_provider: BinanceCredentialProvider = field(repr=False)
    transport: BinanceHttpTransport = field(repr=False)

    def __post_init__(self) -> None:
        if self.product not in {
            BinanceProduct.USD_M,
            BinanceProduct.COIN_M,
        }:
            raise ValueError("Futures stream control does not support Spot")

    async def open(
        self,
        account_id: AccountId,
    ) -> BinanceFuturesUserStreamLease:
        response = await self._send(account_id, method="POST")
        payload = _response_object(response)
        listen_key = payload.get("listenKey")
        if not isinstance(listen_key, str) or not listen_key:
            raise ExecutionTransportError(
                "Binance listenKey response is malformed"
            )
        return BinanceFuturesUserStreamLease(
            product=self.product,
            listen_key=listen_key,
        )

    async def keepalive(
        self,
        account_id: AccountId,
        lease: BinanceFuturesUserStreamLease,
    ) -> None:
        self._require_lease(lease)
        await self._send(account_id, method="PUT")

    async def close(
        self,
        account_id: AccountId,
        lease: BinanceFuturesUserStreamLease,
    ) -> None:
        self._require_lease(lease)
        await self._send(account_id, method="DELETE")

    async def _send(
        self,
        account_id: AccountId,
        *,
        method: str,
    ) -> BinanceHttpResponse:
        credentials = self.credential_provider.credentials_for(account_id)
        request = BinanceHttpRequest(
            method=method,
            path=_FUTURES_LISTEN_KEY_PATHS[self.product],
            query="",
            headers={"X-MBX-APIKEY": credentials.api_key},
        )
        try:
            response = await self.transport.send(self.product, request)
        except BinanceHttpTransportFailure as error:
            raise ExecutionTransportError(
                credentials.redact(str(error))
            ) from None
        if response.status_code >= 400:
            payload = _response_object(response)
            code = payload.get("code", "HTTP_ERROR")
            message = payload.get("msg", "user stream control failed")
            rendered = credentials.redact(f"Binance {code}: {message}")
            if str(code) == "-1125":
                raise BinanceUserStreamLeaseExpiredError(rendered)
            if response.status_code >= 500:
                raise ExecutionTransportError(rendered)
            raise ExecutionQueryError(rendered)
        return response

    def _require_lease(
        self,
        lease: BinanceFuturesUserStreamLease,
    ) -> None:
        if lease.product is not self.product:
            raise ValueError("listenKey lease belongs to another product")


_FUTURES_LISTEN_KEY_PATHS = {
    BinanceProduct.USD_M: "/fapi/v1/listenKey",
    BinanceProduct.COIN_M: "/dapi/v1/listenKey",
}


def build_spot_user_stream_subscription(
    credentials: BinanceCredentials,
    *,
    request_id: str,
    timestamp_ms: int,
    recv_window_ms: int = 5_000,
) -> bytes:
    """Build the current Spot WebSocket API signature subscription request."""

    if not request_id or request_id.strip() != request_id:
        raise ValueError("request_id must be non-empty and trimmed")
    if (
        isinstance(timestamp_ms, bool)
        or not isinstance(timestamp_ms, int)
        or timestamp_ms < 0
    ):
        raise ValueError("timestamp_ms must be a non-negative integer")
    if not 1 <= recv_window_ms <= 60_000:
        raise ValueError("recv_window_ms must be between 1 and 60000")
    parameters = {
        "apiKey": credentials.api_key,
        "recvWindow": str(recv_window_ms),
        "timestamp": str(timestamp_ms),
    }
    parameters["signature"] = credentials.sign(canonical_query(parameters))
    return json.dumps(
        {
            "id": request_id,
            "method": "userDataStream.subscribe.signature",
            "params": parameters,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def parse_spot_user_stream_subscription(
    payload: str | bytes,
    *,
    expected_request_id: str,
) -> int:
    """Validate a Spot subscription response and return subscriptionId."""

    raw = _payload_object(payload)
    if raw.get("id") != expected_request_id:
        raise _malformed("subscription response request ID does not match")
    status = raw.get("status")
    if isinstance(status, bool) or not isinstance(status, int):
        raise _malformed("subscription response status must be an integer")
    if status != 200:
        error = raw.get("error")
        reason = "Spot user stream subscription was rejected"
        if isinstance(error, dict):
            message = error.get("msg")
            if isinstance(message, str) and message:
                reason = message
        raise BinanceOrderNormalizationError(
            code=BinanceOrderNormalizationErrorCode.MALFORMED_PAYLOAD,
            reason=reason,
        )
    result = raw.get("result")
    if not isinstance(result, dict):
        raise _malformed("subscription result must be an object")
    subscription_id = result.get("subscriptionId")
    if (
        isinstance(subscription_id, bool)
        or not isinstance(subscription_id, int)
        or subscription_id < 0
    ):
        raise _malformed("subscriptionId must be a non-negative integer")
    return subscription_id


def _event_object(
    product: BinanceProduct,
    raw: JsonObject,
) -> JsonObject:
    if product is not BinanceProduct.SPOT:
        return raw
    event = raw.get("event")
    if event is None:
        return raw
    if not isinstance(event, dict):
        raise _malformed("Spot event envelope must contain an object")
    return cast(JsonObject, event)


def _payload_object(payload: str | bytes) -> JsonObject:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _malformed("private stream payload is not valid JSON") from error
    if not isinstance(value, dict):
        raise _malformed("private stream payload must be an object")
    return cast(JsonObject, value)


def _response_object(response: BinanceHttpResponse) -> JsonObject:
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutionTransportError(
            f"Binance returned malformed JSON (HTTP {response.status_code})"
        ) from error
    if not isinstance(value, dict):
        raise ExecutionTransportError(
            f"Binance returned non-object JSON (HTTP {response.status_code})"
        )
    return cast(JsonObject, value)


def _malformed(reason: str) -> BinanceOrderNormalizationError:
    return BinanceOrderNormalizationError(
        code=BinanceOrderNormalizationErrorCode.MALFORMED_PAYLOAD,
        reason=reason,
    )


__all__ = [
    "BinanceFuturesUserStreamControlAdapter",
    "BinanceFuturesUserStreamLease",
    "BinancePrivateOrderStreamProcessor",
    "BinancePrivateStreamDisposition",
    "BinancePrivateStreamMessage",
    "BinanceUserStreamLeaseExpiredError",
    "build_spot_user_stream_subscription",
    "parse_spot_user_stream_subscription",
]
