"""Owned WebSocket transports for Binance private account streams."""

from __future__ import annotations

import asyncio
import math
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

from cex_quant.core import AccountId

from ..gateway import ExecutionTransportError
from .binance import BinanceProduct
from .binance_authenticated import (
    BinanceCredentialProvider,
    BinanceCredentials,
)
from .binance_private_stream import (
    BinanceFuturesUserStreamControlAdapter,
    BinanceFuturesUserStreamLease,
    build_spot_user_stream_subscription,
    parse_spot_user_stream_subscription,
)


class BinancePrivateWebSocketConnection(Protocol):
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

    async def __anext__(self) -> str | bytes: ...

    async def send(self, message: str | bytes) -> None: ...

    async def close(self) -> None: ...


class BinancePrivateWebSocketConnector(Protocol):
    """Injectable connector implemented by the production WebSocket client."""

    def connect(
        self,
        uri: str,
    ) -> AbstractAsyncContextManager[BinancePrivateWebSocketConnection]: ...


TimestampMillis = Callable[[], int]
RequestIdFactory = Callable[[], str]
Sleep = Callable[[float], Awaitable[None]]


def _request_id() -> str:
    return uuid.uuid4().hex


@dataclass(slots=True, kw_only=True)
class BinanceSpotPrivateStreamTransport:
    """Connect and authenticate one current Spot WebSocket API stream."""

    product: BinanceProduct
    account_id: AccountId
    base_url: str
    credential_provider: BinanceCredentialProvider = field(repr=False)
    connector: BinancePrivateWebSocketConnector = field(repr=False)
    timestamp_ms: TimestampMillis = field(repr=False)
    request_id_factory: RequestIdFactory = field(
        default=_request_id,
        repr=False,
    )
    recv_window_ms: int = 5_000
    operation_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.product is not BinanceProduct.SPOT:
            raise ValueError("Spot private transport requires the Spot product")
        _validate_wss_base_url(self.base_url)
        if (
            isinstance(self.recv_window_ms, bool)
            or not isinstance(self.recv_window_ms, int)
            or not 1 <= self.recv_window_ms <= 60_000
        ):
            raise ValueError("recv_window_ms must be between 1 and 60000")
        _validate_timeout(self.operation_timeout_seconds)

    def connect(
        self,
    ) -> AbstractAsyncContextManager[BinancePrivateWebSocketConnection]:
        return self._connect()

    @asynccontextmanager
    async def _connect(
        self,
    ) -> AsyncIterator[BinancePrivateWebSocketConnection]:
        try:
            credentials = self.credential_provider.credentials_for(
                self.account_id
            )
            request_id = self.request_id_factory()
            timestamp = self.timestamp_ms()
            request = build_spot_user_stream_subscription(
                credentials,
                request_id=request_id,
                timestamp_ms=timestamp,
                recv_window_ms=self.recv_window_ms,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise ExecutionTransportError(
                "Spot private stream authorization failed: "
                f"{type(error).__name__}"
            ) from None
        async with _connected(
            self.connector,
            self.base_url,
            timeout_seconds=self.operation_timeout_seconds,
        ) as connection:
            await _spot_handshake(
                connection,
                request=request,
                request_id=request_id,
                credentials=credentials,
                timeout_seconds=self.operation_timeout_seconds,
            )
            yield connection


@dataclass(slots=True, kw_only=True)
class BinanceFuturesPrivateStreamTransport:
    """Own a Futures listenKey, WebSocket and renewal task as one resource."""

    product: BinanceProduct
    account_id: AccountId
    base_url: str
    control: BinanceFuturesUserStreamControlAdapter = field(repr=False)
    connector: BinancePrivateWebSocketConnector = field(repr=False)
    keepalive_interval_seconds: float = 30 * 60
    operation_timeout_seconds: float = 10.0
    sleep: Sleep = field(default=asyncio.sleep, repr=False)

    def __post_init__(self) -> None:
        if self.product not in {
            BinanceProduct.USD_M,
            BinanceProduct.COIN_M,
        }:
            raise ValueError("Futures private transport requires a Futures product")
        if self.control.product is not self.product:
            raise ValueError("Futures control and transport products must match")
        _validate_wss_base_url(self.base_url)
        _validate_positive_seconds(
            self.keepalive_interval_seconds,
            name="keepalive interval",
        )
        _validate_timeout(self.operation_timeout_seconds)

    def connect(
        self,
    ) -> AbstractAsyncContextManager[BinancePrivateWebSocketConnection]:
        return self._connect()

    @asynccontextmanager
    async def _connect(
        self,
    ) -> AsyncIterator[BinancePrivateWebSocketConnection]:
        lease = await _lease_operation(
            self.control.open(self.account_id),
            stage="open",
            timeout_seconds=self.operation_timeout_seconds,
        )
        if not isinstance(lease, BinanceFuturesUserStreamLease):
            raise ExecutionTransportError(
                "Futures listenKey open returned an invalid lease"
            )
        primary_failure = False
        try:
            uri = lease.websocket_uri(self.base_url)
            async with _connected(
                self.connector,
                uri,
                timeout_seconds=self.operation_timeout_seconds,
            ) as connection:
                renewal = asyncio.create_task(
                    self._renew(lease),
                    name=f"binance-{self.product.value}-listen-key-renewal",
                )
                wrapped = _RenewingConnection(
                    connection=connection,
                    renewal=renewal,
                    timeout_seconds=self.operation_timeout_seconds,
                )
                try:
                    yield wrapped
                except BaseException:
                    primary_failure = True
                    raise
                finally:
                    renewal.cancel()
                    await asyncio.gather(renewal, return_exceptions=True)
        except BaseException:
            primary_failure = True
            raise
        finally:
            try:
                await _lease_operation(
                    self.control.close(self.account_id, lease),
                    stage="close",
                    timeout_seconds=self.operation_timeout_seconds,
                )
            except BaseException:
                if not primary_failure:
                    raise

    async def _renew(self, lease: BinanceFuturesUserStreamLease) -> None:
        while True:
            await self.sleep(self.keepalive_interval_seconds)
            await _lease_operation(
                self.control.keepalive(self.account_id, lease),
                stage="keepalive",
                timeout_seconds=self.operation_timeout_seconds,
            )


@dataclass(slots=True)
class _RenewingConnection:
    connection: BinancePrivateWebSocketConnection
    renewal: asyncio.Task[None]
    timeout_seconds: float

    def __aiter__(self) -> _RenewingConnection:
        return self

    async def __anext__(self) -> str | bytes:
        if self.renewal.done():
            _raise_renewal_failure(self.renewal)
        receive = asyncio.create_task(anext(self.connection))
        try:
            done, _ = await asyncio.wait(
                {receive, self.renewal},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self.renewal in done:
                receive.cancel()
                await asyncio.gather(receive, return_exceptions=True)
                _raise_renewal_failure(self.renewal)
            return await receive
        except BaseException:
            if not receive.done():
                receive.cancel()
                await asyncio.gather(receive, return_exceptions=True)
            raise

    async def send(self, message: str | bytes) -> None:
        await _bounded(
            self.connection.send(message),
            stage="WebSocket send",
            timeout_seconds=self.timeout_seconds,
        )

    async def close(self) -> None:
        await _bounded(
            self.connection.close(),
            stage="WebSocket close",
            timeout_seconds=self.timeout_seconds,
        )


async def _spot_handshake(
    connection: BinancePrivateWebSocketConnection,
    *,
    request: bytes,
    request_id: str,
    credentials: BinanceCredentials,
    timeout_seconds: float,
) -> None:
    try:
        await asyncio.wait_for(
            connection.send(request),
            timeout=timeout_seconds,
        )
        response = await asyncio.wait_for(
            anext(connection),
            timeout=timeout_seconds,
        )
        parse_spot_user_stream_subscription(
            response,
            expected_request_id=request_id,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise ExecutionTransportError(
            "Spot private stream subscription timed out"
        ) from None
    except Exception as error:
        # Never include the underlying exception: WebSocket clients may echo
        # the sensitive subscription frame in their error text.
        del credentials
        raise ExecutionTransportError(
            "Spot private stream subscription failed: "
            f"{type(error).__name__}"
        ) from None


@asynccontextmanager
async def _connected(
    connector: BinancePrivateWebSocketConnector,
    uri: str,
    *,
    timeout_seconds: float,
) -> AsyncIterator[BinancePrivateWebSocketConnection]:
    context = connector.connect(uri)
    try:
        connection = await asyncio.wait_for(
            context.__aenter__(),
            timeout=timeout_seconds,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise ExecutionTransportError(
            "private WebSocket connection timed out"
        ) from None
    except Exception as error:
        raise ExecutionTransportError(
            "private WebSocket connection failed: "
            f"{type(error).__name__}"
        ) from None

    try:
        yield connection
    except BaseException:
        error_info = sys.exc_info()
        with suppress(BaseException):
            await asyncio.wait_for(
                context.__aexit__(*error_info),
                timeout=timeout_seconds,
            )
        raise
    else:
        try:
            await asyncio.wait_for(
                context.__aexit__(None, None, None),
                timeout=timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise ExecutionTransportError(
                "private WebSocket close timed out"
            ) from None
        except Exception as error:
            raise ExecutionTransportError(
                "private WebSocket close failed: "
                f"{type(error).__name__}"
            ) from None


async def _lease_operation(
    operation: Awaitable[object],
    *,
    stage: str,
    timeout_seconds: float,
) -> object:
    return await _bounded(
        operation,
        stage=f"Futures listenKey {stage}",
        timeout_seconds=timeout_seconds,
    )


async def _bounded(
    operation: Awaitable[object],
    *,
    stage: str,
    timeout_seconds: float,
) -> object:
    try:
        return await asyncio.wait_for(operation, timeout=timeout_seconds)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise ExecutionTransportError(f"{stage} timed out") from None
    except Exception as error:
        raise ExecutionTransportError(
            f"{stage} failed: {type(error).__name__}"
        ) from None


def _raise_renewal_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        raise ExecutionTransportError(
            "Futures listenKey renewal stopped unexpectedly"
        )
    error = task.exception()
    if error is None:
        raise ExecutionTransportError(
            "Futures listenKey renewal stopped unexpectedly"
        )
    raise ExecutionTransportError(
        f"Futures listenKey renewal failed: {type(error).__name__}"
    ) from None


def _validate_wss_base_url(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "wss"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
        or base_url.rstrip("/") != base_url
        or any(character.isspace() for character in base_url)
    ):
        raise ValueError(
            "base_url must be a credential-free wss URL without "
            "query, fragment or trailing slash"
        )


def _validate_timeout(timeout_seconds: float) -> None:
    _validate_positive_seconds(timeout_seconds, name="operation timeout")


def _validate_positive_seconds(value: float, *, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a finite positive number")


__all__ = [
    "BinanceFuturesPrivateStreamTransport",
    "BinancePrivateWebSocketConnection",
    "BinancePrivateWebSocketConnector",
    "BinanceSpotPrivateStreamTransport",
]
