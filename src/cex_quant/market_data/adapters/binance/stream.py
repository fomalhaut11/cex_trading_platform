"""Bounded Binance stream session independent of a WebSocket library."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

from cex_quant.core import (
    EventSource,
    MonotonicNanos,
    TimePrecision,
    UnixNanos,
)
from cex_quant.market_data import (
    MarketDataValidator,
    MarketEvent,
    RawMarketMessage,
    ValidationResult,
)

from .connection import ConnectionLifecycle, ConnectionState
from .normalizer import BINANCE_VENUE, BinanceMarketDataNormalizer


class WebSocketConnection(Protocol):
    def __aiter__(self) -> AsyncIterator[str | bytes]:
        ...

    async def close(self) -> None:
        ...


class WebSocketTransport(Protocol):
    def connect(
        self, uri: str
    ) -> AbstractAsyncContextManager[WebSocketConnection]:
        ...


class Clock(Protocol):
    def unix_ns(self) -> UnixNanos:
        ...

    def monotonic_ns(self) -> MonotonicNanos:
        ...


EventHandler = Callable[[MarketEvent], Awaitable[None]]
ValidationHandler = Callable[[ValidationResult], Awaitable[None]]


@dataclass(frozen=True, slots=True, kw_only=True)
class CombinedStreamRequest:
    """Validated combined-stream URI inputs.

    `base_url` is injected from environment configuration so production,
    testnet and regional endpoints do not leak into domain logic.
    """

    base_url: str
    streams: tuple[str, ...]
    timestamp_precision: TimePrecision = TimePrecision.MILLISECOND
    max_streams: int = 1024

    def __post_init__(self) -> None:
        if not self.base_url.startswith("wss://"):
            raise ValueError("base_url must use wss")
        if not self.streams:
            raise ValueError("at least one stream is required")
        if len(self.streams) > self.max_streams:
            raise ValueError("stream count exceeds configured connection limit")
        if len(set(self.streams)) != len(self.streams):
            raise ValueError("duplicate streams are not allowed")
        if any(
            not stream
            or stream != stream.lower()
            or any(character.isspace() for character in stream)
            for stream in self.streams
        ):
            raise ValueError("stream names must be non-empty lowercase tokens")
        if self.timestamp_precision not in {
            TimePrecision.MILLISECOND,
            TimePrecision.MICROSECOND,
        }:
            raise ValueError("Binance stream precision must be milli- or microsecond")

    def uri(self) -> str:
        stream_path = quote("/".join(self.streams), safe="@_!/+:-")
        separator = "&" if "?" in self.base_url else "?"
        uri = f"{self.base_url.rstrip('/')}{separator}streams={stream_path}"
        if self.timestamp_precision is TimePrecision.MICROSECOND:
            uri += "&timeUnit=MICROSECOND"
        return uri


class BinanceStreamSession:
    """Run one physical connection with sequential event backpressure."""

    def __init__(
        self,
        *,
        request: CombinedStreamRequest,
        normalizer: BinanceMarketDataNormalizer,
        validator: MarketDataValidator,
        clock: Clock,
        on_event: EventHandler,
        on_validation: ValidationHandler,
        connection_id: str,
        lifecycle: ConnectionLifecycle | None = None,
    ) -> None:
        if not connection_id:
            raise ValueError("connection_id cannot be empty")
        self._request = request
        self._normalizer = normalizer
        self._validator = validator
        self._clock = clock
        self._on_event = on_event
        self._on_validation = on_validation
        self._connection_id = connection_id
        self._lifecycle = lifecycle or ConnectionLifecycle()

    @property
    def lifecycle(self) -> ConnectionLifecycle:
        return self._lifecycle

    async def run_once(self, transport: WebSocketTransport) -> None:
        """Run until a connection ends; caller owns retry scheduling."""

        self._lifecycle.start()
        try:
            async with transport.connect(self._request.uri()) as connection:
                self._lifecycle.connected(now_ns=self._clock.monotonic_ns())
                async for payload in connection:
                    encoded = (
                        payload.encode("utf-8")
                        if isinstance(payload, str)
                        else payload
                    )
                    raw = RawMarketMessage(
                        payload=encoded,
                        source=EventSource(
                            venue=BINANCE_VENUE,
                            channel="combined",
                            connection_id=self._connection_id,
                        ),
                        receive_time_ns=self._clock.unix_ns(),
                    )
                    for event in self._normalizer.normalize(raw):
                        result = self._validator.validate(
                            event,
                            now_ns=self._clock.unix_ns(),
                        )
                        await self._on_validation(result)
                        if result.is_valid:
                            await self._on_event(event)
                if self._lifecycle.state is ConnectionState.ACTIVE:
                    self._lifecycle.connection_lost(reason="stream ended")
        except BaseException as error:
            if self._lifecycle.state in {
                ConnectionState.CONNECTING,
                ConnectionState.ACTIVE,
            }:
                self._lifecycle.connection_lost(
                    reason=f"{type(error).__name__}: {error}"
                )
            raise


__all__ = [
    "BinanceStreamSession",
    "Clock",
    "CombinedStreamRequest",
    "EventHandler",
    "ValidationHandler",
    "WebSocketConnection",
    "WebSocketTransport",
]
