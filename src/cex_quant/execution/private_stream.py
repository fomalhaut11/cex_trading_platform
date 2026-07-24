"""Transport-neutral private-order stream session with bounded renewal."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, suppress
from typing import Protocol

from cex_quant.core import MonotonicNanos
from cex_quant.market_data.adapters.binance import (
    ConnectionLifecycle,
    ConnectionPolicy,
    ConnectionState,
)
from cex_quant.oms import OrderReconciliationSnapshot

from .adapters.binance_private_stream import (
    BinancePrivateOrderStreamProcessor,
    BinancePrivateStreamDisposition,
)


class PrivateStreamConnection(Protocol):
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

    async def close(self) -> None: ...


class PrivateStreamTransport(Protocol):
    """Open one already-authorized account stream connection."""

    def connect(
        self,
    ) -> AbstractAsyncContextManager[PrivateStreamConnection]: ...


SnapshotHandler = Callable[
    [OrderReconciliationSnapshot],
    Awaitable[None],
]
Keepalive = Callable[[], Awaitable[None]]
Sleep = Callable[[float], Awaitable[None]]
TransportFactory = Callable[[], Awaitable[PrivateStreamTransport]]


class PrivateOrderStreamSession:
    """Consume one private connection and renew its authorization if required."""

    def __init__(
        self,
        *,
        processor: BinancePrivateOrderStreamProcessor,
        on_snapshot: SnapshotHandler,
        keepalive: Keepalive | None = None,
        keepalive_interval_seconds: float | None = None,
        sleep: Sleep = asyncio.sleep,
        lifecycle: ConnectionLifecycle | None = None,
    ) -> None:
        if (keepalive is None) != (keepalive_interval_seconds is None):
            raise ValueError(
                "keepalive and keepalive_interval_seconds must be set together"
            )
        if (
            keepalive_interval_seconds is not None
            and keepalive_interval_seconds <= 0
        ):
            raise ValueError("keepalive interval must be positive")
        self._processor = processor
        self._on_snapshot = on_snapshot
        self._keepalive = keepalive
        self._keepalive_interval_seconds = keepalive_interval_seconds
        self._sleep = sleep
        self._lifecycle = lifecycle or ConnectionLifecycle()

    @property
    def lifecycle(self) -> ConnectionLifecycle:
        return self._lifecycle

    async def run_once(self, transport: PrivateStreamTransport) -> None:
        """Run one connection; callers own reconnect-delay scheduling."""

        if self._lifecycle.state is ConnectionState.STOPPED:
            self._lifecycle.start()
        elif self._lifecycle.state is ConnectionState.RECONNECT_WAIT:
            self._lifecycle.retry()
        else:
            raise RuntimeError(
                f"cannot run private stream from {self._lifecycle.state.value}"
            )
        try:
            async with transport.connect() as connection:
                self._lifecycle.connected(now_ns=MonotonicNanos(0))
                consumer = asyncio.create_task(self._consume(connection))
                renewal = (
                    asyncio.create_task(self._renew_forever())
                    if self._keepalive is not None
                    else None
                )
                tasks = {consumer}
                if renewal is not None:
                    tasks.add(renewal)
                done, _ = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                try:
                    if renewal is not None and renewal in done:
                        error = renewal.exception()
                        if error is not None:
                            consumer.cancel()
                            await _finish_cancelled(consumer)
                            raise error
                    await consumer
                finally:
                    if renewal is not None:
                        renewal.cancel()
                        await _finish_cancelled(renewal)
                self._mark_stream_ended()
        except BaseException as error:
            if self._lifecycle.state in {
                ConnectionState.CONNECTING,
                ConnectionState.ACTIVE,
            }:
                self._lifecycle.connection_lost(
                    reason=f"{type(error).__name__}: {error}"
                )
            raise

    async def _consume(self, connection: PrivateStreamConnection) -> None:
        async for payload in connection:
            message = self._processor.process(payload)
            if (
                message.disposition
                is BinancePrivateStreamDisposition.RECONNECT_REQUIRED
            ):
                self._lifecycle.connection_lost(reason=message.reason)
                return
            if message.snapshot is not None:
                await self._on_snapshot(message.snapshot)

    async def _renew_forever(self) -> None:
        assert self._keepalive is not None
        assert self._keepalive_interval_seconds is not None
        while True:
            await self._sleep(self._keepalive_interval_seconds)
            await self._keepalive()

    def _mark_stream_ended(self) -> None:
        if self._lifecycle.state is ConnectionState.ACTIVE:
            self._lifecycle.connection_lost(reason="stream ended")


class PrivateOrderStreamSupervisor:
    """Recreate authorized transports with deterministic reconnect backoff."""

    def __init__(
        self,
        *,
        session: PrivateOrderStreamSession,
        transport_factory: TransportFactory,
        policy: ConnectionPolicy | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._session = session
        self._transport_factory = transport_factory
        self._policy = policy or ConnectionPolicy()
        self._sleep = sleep
        self._stop_requested = False
        self._last_error: Exception | None = None

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    def request_stop(self) -> None:
        self._stop_requested = True

    async def run(self, *, max_cycles: int | None = None) -> int:
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        cycles = 0
        while not self._stop_requested and (
            max_cycles is None or cycles < max_cycles
        ):
            try:
                transport = await self._transport_factory()
                await self._session.run_once(transport)
                self._last_error = None
            except Exception as error:
                self._last_error = error
            cycles += 1
            if self._stop_requested or (
                max_cycles is not None and cycles >= max_cycles
            ):
                break
            attempt = max(self._session.lifecycle.reconnect_attempt, 1)
            delay_ns = self._policy.reconnect.delay_ns(attempt=attempt)
            await self._sleep(int(delay_ns) / 1_000_000_000)
        return cycles


async def _finish_cancelled(task: asyncio.Task[None]) -> None:
    with suppress(asyncio.CancelledError):
        await task


__all__ = [
    "Keepalive",
    "PrivateOrderStreamSession",
    "PrivateOrderStreamSupervisor",
    "PrivateStreamConnection",
    "PrivateStreamTransport",
    "Sleep",
    "SnapshotHandler",
    "TransportFactory",
]
