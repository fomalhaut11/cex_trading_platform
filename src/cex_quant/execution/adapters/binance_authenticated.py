"""Authenticated Binance Spot and Futures execution boundary.

The module owns deterministic encoding and HMAC signing, but deliberately
leaves actual HTTP I/O behind a small injected protocol.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol
from urllib.parse import quote

from cex_quant.core import AccountId, VenueOrderId
from cex_quant.oms import OrderRequest

from ..contracts import (
    CancelOrder,
    CancelResult,
    ExecutionOutcome,
    SubmitResult,
)
from ..gateway import (
    ExecutionStateUnknownError,
    ExecutionTransportError,
)
from .binance import (
    BinanceProduct,
    BinanceRequest,
    map_binance_cancel,
    map_binance_submit,
)


class BinanceCredentials:
    """HMAC credentials whose representation never exposes either value."""

    __slots__ = ("_api_key", "_secret")

    def __init__(self, *, api_key: str, secret: str) -> None:
        if not api_key or not secret:
            raise ValueError("Binance credentials must be non-empty")
        self._api_key = api_key
        self._secret = secret

    def __repr__(self) -> str:
        return "BinanceCredentials(api_key=<redacted>, secret=<redacted>)"

    @property
    def api_key(self) -> str:
        return self._api_key

    def sign(self, payload: str) -> str:
        """Return the lowercase HMAC-SHA256 digest for an encoded payload."""

        return hmac.new(
            self._secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def redact(self, text: str) -> str:
        return text.replace(self._secret, "<redacted>").replace(
            self._api_key, "<redacted>"
        )


class BinanceCredentialProvider(Protocol):
    """Resolve credentials without making them part of adapter configuration."""

    def credentials_for(self, account_id: AccountId) -> BinanceCredentials: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceHttpRequest:
    method: str
    path: str
    query: str
    headers: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "headers", MappingProxyType(dict(self.headers))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceHttpResponse:
    status_code: int
    body: bytes


class BinanceHttpTransport(Protocol):
    """Minimal HTTP port; implementations select the product base URL."""

    async def send(
        self, product: BinanceProduct, request: BinanceHttpRequest
    ) -> BinanceHttpResponse: ...


class BinanceHttpTransportFailure(Exception):
    """Transport failure with explicit knowledge of whether bytes were sent."""

    def __init__(self, message: str, *, request_sent: bool) -> None:
        super().__init__(message)
        self.request_sent = request_sent


def canonical_query(parameters: Mapping[str, str]) -> str:
    """Encode parameters deterministically by key, independent of map order."""

    if "signature" in parameters:
        raise ValueError("signature must not be present before signing")
    return "&".join(
        f"{quote(key, safe='')}={quote(value, safe='')}"
        for key, value in sorted(parameters.items())
    )


def hmac_sha256_hex(secret: str, payload: str) -> str:
    """Pure signing helper useful for conformance tests."""

    if not secret:
        raise ValueError("secret must be non-empty")
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@dataclass(slots=True, kw_only=True)
class AuthenticatedBinanceExecutionAdapter:
    """Signed submit/cancel gateway for one Binance product."""

    product: BinanceProduct
    credential_provider: BinanceCredentialProvider = field(repr=False)
    transport: BinanceHttpTransport = field(repr=False)
    timestamp_ms: Callable[[], int] = field(repr=False)
    recv_window_ms: int = 5_000

    def __post_init__(self) -> None:
        if not isinstance(self.product, BinanceProduct):
            raise ValueError("product must be a BinanceProduct")
        if not 1 <= self.recv_window_ms <= 60_000:
            raise ValueError("recv_window_ms must be between 1 and 60000")

    async def submit(self, command: OrderRequest) -> SubmitResult:
        response = await self._send(
            command.account_id,
            map_binance_submit(self.product, command),
        )
        payload = self._decode_response(response)
        if response.status_code >= 400:
            return SubmitResult(
                client_order_id=command.client_order_id,
                outcome=ExecutionOutcome.REJECTED,
                rejection_code=_error_code(payload),
                rejection_message=_error_message(payload),
            )
        return SubmitResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
            venue_order_id=_venue_order_id(payload),
        )

    async def cancel(self, command: CancelOrder) -> CancelResult:
        response = await self._send(
            command.account_id,
            map_binance_cancel(self.product, command),
        )
        payload = self._decode_response(response)
        if response.status_code >= 400:
            return CancelResult(
                client_order_id=command.client_order_id,
                outcome=ExecutionOutcome.REJECTED,
                rejection_code=_error_code(payload),
                rejection_message=_error_message(payload),
            )
        return CancelResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
            venue_order_id=_venue_order_id(payload),
        )

    async def _send(
        self, account_id: AccountId, mapped: BinanceRequest
    ) -> BinanceHttpResponse:
        credentials = self.credential_provider.credentials_for(account_id)
        timestamp = self.timestamp_ms()
        if not isinstance(timestamp, int) or timestamp < 0:
            raise ValueError("timestamp_ms must return a non-negative int")
        parameters = dict(mapped.parameters)
        parameters["recvWindow"] = str(self.recv_window_ms)
        parameters["timestamp"] = str(timestamp)
        payload = canonical_query(parameters)
        signature = credentials.sign(payload)
        request = BinanceHttpRequest(
            method=mapped.method,
            path=mapped.path,
            query=f"{payload}&signature={signature}",
            headers={"X-MBX-APIKEY": credentials.api_key},
        )
        try:
            response = await self.transport.send(self.product, request)
        except BinanceHttpTransportFailure as exc:
            message = credentials.redact(str(exc))
            if exc.request_sent:
                raise ExecutionStateUnknownError(message) from None
            raise ExecutionTransportError(message) from None
        if response.status_code >= 500:
            message = _safe_http_error(response, credentials)
            raise ExecutionStateUnknownError(message)
        return response

    @staticmethod
    def _decode_response(
        response: BinanceHttpResponse,
    ) -> Mapping[str, Any]:
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExecutionTransportError(
                f"Binance returned malformed JSON (HTTP {response.status_code})"
            ) from exc
        if not isinstance(payload, dict):
            raise ExecutionTransportError(
                f"Binance returned non-object JSON (HTTP {response.status_code})"
            )
        return payload


def _venue_order_id(payload: Mapping[str, Any]) -> VenueOrderId:
    value = payload.get("orderId")
    if isinstance(value, (str, int)) and str(value):
        return VenueOrderId(str(value))
    raise ExecutionTransportError(
        "Binance accepted response does not contain orderId"
    )


def _error_code(payload: Mapping[str, Any]) -> str:
    value = payload.get("code")
    return str(value) if isinstance(value, (str, int)) else "HTTP_ERROR"


def _error_message(payload: Mapping[str, Any]) -> str:
    value = payload.get("msg")
    return value if isinstance(value, str) and value else "Binance rejected request"


def _safe_http_error(
    response: BinanceHttpResponse, credentials: BinanceCredentials
) -> str:
    try:
        value = response.body.decode("utf-8", errors="replace")
    except Exception:
        value = "<unreadable response>"
    return credentials.redact(
        f"Binance request state unknown (HTTP {response.status_code}): {value}"
    )


__all__ = [
    "AuthenticatedBinanceExecutionAdapter",
    "BinanceCredentialProvider",
    "BinanceCredentials",
    "BinanceHttpRequest",
    "BinanceHttpResponse",
    "BinanceHttpTransport",
    "BinanceHttpTransportFailure",
    "canonical_query",
    "hmac_sha256_hex",
]
