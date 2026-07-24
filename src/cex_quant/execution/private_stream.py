"""Transport-neutral private-order stream session with bounded renewal."""

from __future__ import annotations

import asyncio
import time
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
MonotonicNow = Callable[[], MonotonicNanos]


def _monotonic_now() -> MonotonicNanos:
    return MonotonicNanos(time.monotonic_ns())


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
        monotonic_now: MonotonicNow = _monotonic_now,
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
        self._monotonic_now = monotonic_now
        self._active_event = asyncio.Event()

    @property
    def lifecycle(self) -> ConnectionLifecycle:
        return self._lifecycle

    async def wait_until_active(self) -> None:
        """Wait until the current physical connection is confirmed active."""

        await self._active_event.wait()

    async def run_once(self, transport: PrivateStreamTransport) -> None:
        """Run one connection; callers own reconnect-delay scheduling."""

        self._active_event.clear()
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
                self._lifecycle.connected(now_ns=self._monotonic_now())
                self._active_event.set()
                consumer = asyncio.create_task(self._consume(connection))
                renewal = (
                    asyncio.create_task(self._renew_forever())
                    if self._keepalive is not None
                    else None
                )
                tasks = {consumer}
                if renewal is not None:
                    tasks.add(renewal)
                try:
                    done, _ = await asyncio.wait(
                        tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if renewal is not None and renewal in done:
                        error = renewal.exception()
                        if error is not None:
                            raise error
                    await consumer
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
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
        self._active_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._running = False

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    @property
    def connection_active(self) -> bool:
        """Return whether the current physical private stream is active."""

        return self._session.lifecycle.state is ConnectionState.ACTIVE

    def request_stop(self) -> None:
        self._stop_requested = True
        stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        lifecycle = self._session.lifecycle
        if lifecycle.state is not ConnectionState.STOPPED:
            lifecycle.request_stop()
        active_task = self._active_task
        if active_task is not None:
            active_task.cancel()

    async def wait_until_active(self) -> None:
        """Wait until the supervised session confirms a physical connection."""

        await self._session.wait_until_active()

    async def run(self, *, max_cycles: int | None = None) -> int:
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        if self._running:
            raise RuntimeError("private stream supervisor is already running")
        self._running = True
        self._stop_event = asyncio.Event()
        cycles = 0
        consecutive_failures = 0
        try:
            while not self._stop_requested and (
                max_cycles is None or cycles < max_cycles
            ):
                cycles += 1
                consecutive_failures += 1
                self._active_task = asyncio.create_task(self._run_cycle())
                try:
                    await self._active_task
                    self._last_error = None
                except asyncio.CancelledError:
                    if self._stop_requested:
                        break
                    raise
                except Exception as error:
                    self._last_error = error
                finally:
                    self._active_task = None
                if self._stop_requested or (
                    max_cycles is not None and cycles >= max_cycles
                ):
                    break
                delay_ns = self._policy.reconnect.delay_ns(
                    attempt=consecutive_failures
                )
                await self._wait_for_stop(
                    int(delay_ns) / 1_000_000_000
                )
            return cycles
        finally:
            active_task = self._active_task
            if active_task is not None:
                active_task.cancel()
                await _finish_cancelled(active_task)
                self._active_task = None
            self._finish_lifecycle_stop()
            self._stop_event = None
            self._running = False

    async def _run_cycle(self) -> None:
        transport = await self._transport_factory()
        await self._session.run_once(transport)

    async def _wait_for_stop(self, delay_seconds: float) -> None:
        stop_event = self._stop_event
        assert stop_event is not None
        sleep_task: asyncio.Future[None] = asyncio.ensure_future(
            self._sleep(delay_seconds)
        )
        stop_task = asyncio.create_task(_wait_until_set(stop_event))
        try:
            done, _ = await asyncio.wait(
                {sleep_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done:
                return
            await sleep_task
        finally:
            for task in (sleep_task, stop_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                sleep_task,
                stop_task,
                return_exceptions=True,
            )

    def _finish_lifecycle_stop(self) -> None:
        lifecycle = self._session.lifecycle
        if lifecycle.state is ConnectionState.STOPPED:
            return
        if lifecycle.state is not ConnectionState.STOPPING:
            lifecycle.request_stop()
        if lifecycle.state is ConnectionState.STOPPING:
            lifecycle.stopped()


async def _finish_cancelled(task: asyncio.Task[None]) -> None:
    with suppress(asyncio.CancelledError):
        await task


async def _wait_until_set(event: asyncio.Event) -> None:
    await event.wait()


__all__ = [
    "Keepalive",
    "MonotonicNow",
    "PrivateOrderStreamSession",
    "PrivateOrderStreamSupervisor",
    "PrivateStreamConnection",
    "PrivateStreamTransport",
    "Sleep",
    "SnapshotHandler",
    "TransportFactory",
]
