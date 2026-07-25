"""Binance server-time probes and bounded asynchronous scheduling."""

from __future__ import annotations

import asyncio
import json
import math
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from cex_quant.core import UnixNanos
from cex_quant.execution.adapters.binance import BinanceProduct
from cex_quant.execution.adapters.binance_authenticated import (
    BinanceHttpRequest,
    BinanceHttpTransport,
)
from cex_quant.observability.clock import ClockHealthMonitor, VenueClockSample

Sleep = Callable[[float], Awaitable[None]]

_SERVER_TIME_PATHS = {
    BinanceProduct.SPOT: "/api/v3/time",
    BinanceProduct.USD_M: "/fapi/v1/time",
    BinanceProduct.COIN_M: "/dapi/v1/time",
}


class BinanceServerTimeError(RuntimeError):
    """A sanitized server-time query or response failure."""


@dataclass(slots=True, kw_only=True)
class BinanceServerTimeAdapter:
    """Query one Binance product clock and feed its local midpoint sample."""

    product: BinanceProduct
    transport: BinanceHttpTransport = field(repr=False)
    monitor: ClockHealthMonitor = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.product, BinanceProduct):
            raise ValueError("product must be a BinanceProduct")

    async def probe(self) -> VenueClockSample:
        probe = self.monitor.start_probe()
        request = BinanceHttpRequest(
            method="GET",
            path=_SERVER_TIME_PATHS[self.product],
            query="",
            headers={},
        )
        try:
            response = await self.transport.send(self.product, request)
        except asyncio.CancelledError:
            raise
        except Exception:
            raise BinanceServerTimeError(
                "Binance server-time transport failed"
            ) from None
        if response.status_code != 200:
            raise BinanceServerTimeError(
                f"Binance server-time request failed with HTTP "
                f"{response.status_code}"
            )
        try:
            decoded = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BinanceServerTimeError(
                "Binance server-time response is not valid JSON"
            ) from None
        if not isinstance(decoded, dict):
            raise BinanceServerTimeError(
                "Binance server-time response must be an object"
            )
        payload = cast(dict[str, object], decoded)
        server_time = payload.get("serverTime")
        if (
            isinstance(server_time, bool)
            or not isinstance(server_time, int)
            or server_time < 0
        ):
            raise BinanceServerTimeError(
                "Binance server-time response has invalid serverTime"
            )
        return self.monitor.finish_probe(
            probe,
            venue_time_ns=UnixNanos(server_time * 1_000_000),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceClockProbePolicy:
    interval_seconds: float = 30.0
    base_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 30.0
    backoff_multiplier: int = 2
    history_size: int = 32

    def __post_init__(self) -> None:
        values = (
            self.interval_seconds,
            self.base_backoff_seconds,
            self.max_backoff_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in values
        ):
            raise ValueError("clock probe time bounds must be finite and positive")
        if self.max_backoff_seconds < self.base_backoff_seconds:
            raise ValueError(
                "max_backoff_seconds cannot be less than base_backoff_seconds"
            )
        if (
            isinstance(self.backoff_multiplier, bool)
            or not isinstance(self.backoff_multiplier, int)
            or self.backoff_multiplier < 1
        ):
            raise ValueError("backoff_multiplier must be at least one")
        if (
            isinstance(self.history_size, bool)
            or not isinstance(self.history_size, int)
            or self.history_size < 1
        ):
            raise ValueError("history_size must be positive")

    def failure_delay(self, consecutive_failures: int) -> float:
        if (
            isinstance(consecutive_failures, bool)
            or not isinstance(consecutive_failures, int)
            or consecutive_failures < 1
        ):
            raise ValueError("consecutive_failures must be positive")
        delay = self.base_backoff_seconds
        if self.backoff_multiplier == 1:
            return delay
        for _ in range(consecutive_failures - 1):
            if delay >= (
                self.max_backoff_seconds / self.backoff_multiplier
            ):
                return self.max_backoff_seconds
            delay *= self.backoff_multiplier
        return delay


class BinanceClockProbeState(StrEnum):
    NEW = "new"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceClockProbeRecord:
    sequence: int
    sample: VenueClockSample | None
    error: str | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        if (self.sample is None) == (self.error is None):
            raise ValueError("record requires exactly one sample or error")


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceClockProbeSnapshot:
    state: BinanceClockProbeState
    product: BinanceProduct
    probes: int
    successes: int
    failures: int
    consecutive_failures: int
    records: tuple[BinanceClockProbeRecord, ...]
    last_error: str | None


class BinanceClockProbeService:
    """Run immediate and periodic clock probes with interruptible waits."""

    def __init__(
        self,
        *,
        adapter: BinanceServerTimeAdapter,
        policy: BinanceClockProbePolicy | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._adapter = adapter
        self._policy = policy or BinanceClockProbePolicy()
        self._sleep = sleep
        self._state = BinanceClockProbeState.NEW
        self._probes = 0
        self._successes = 0
        self._failures = 0
        self._consecutive_failures = 0
        self._last_error: str | None = None
        self._records: deque[BinanceClockProbeRecord] = deque(
            maxlen=self._policy.history_size
        )
        self._stop_requested = False
        self._stop_event: asyncio.Event | None = None
        self._active_probe: asyncio.Task[VenueClockSample] | None = None

    @property
    def state(self) -> BinanceClockProbeState:
        return self._state

    def snapshot(self) -> BinanceClockProbeSnapshot:
        return BinanceClockProbeSnapshot(
            state=self._state,
            product=self._adapter.product,
            probes=self._probes,
            successes=self._successes,
            failures=self._failures,
            consecutive_failures=self._consecutive_failures,
            records=tuple(self._records),
            last_error=self._last_error,
        )

    def request_stop(self) -> None:
        if self._state in {
            BinanceClockProbeState.NEW,
            BinanceClockProbeState.STOPPED,
        }:
            self._state = BinanceClockProbeState.STOPPED
            return
        self._state = BinanceClockProbeState.STOPPING
        self._stop_requested = True
        if self._stop_event is not None:
            self._stop_event.set()
        if self._active_probe is not None:
            self._active_probe.cancel()

    async def run(self, *, max_probes: int | None = None) -> int:
        if max_probes is not None and (
            isinstance(max_probes, bool)
            or not isinstance(max_probes, int)
            or max_probes < 1
        ):
            raise ValueError("max_probes must be positive")
        if self._state is not BinanceClockProbeState.NEW:
            raise RuntimeError(
                f"cannot run clock probe service from {self._state.value}"
            )
        self._state = BinanceClockProbeState.RUNNING
        self._stop_event = asyncio.Event()
        try:
            while self._state is BinanceClockProbeState.RUNNING and (
                max_probes is None or self._probes < max_probes
            ):
                self._probes += 1
                self._active_probe = asyncio.create_task(self._adapter.probe())
                succeeded = False
                try:
                    sample = await self._active_probe
                except asyncio.CancelledError:
                    if self._stop_requested:
                        break
                    raise
                except Exception as error:
                    self._record_failure(error)
                else:
                    self._record_success(sample)
                    succeeded = True
                finally:
                    self._active_probe = None
                if self._state is not BinanceClockProbeState.RUNNING or (
                    max_probes is not None and self._probes >= max_probes
                ):
                    break
                delay = (
                    self._policy.interval_seconds
                    if succeeded
                    else self._policy.failure_delay(
                        self._consecutive_failures
                    )
                )
                await self._wait_or_stop(delay)
            return self._probes
        finally:
            active_probe = self._active_probe
            if active_probe is not None:
                active_probe.cancel()
                await asyncio.gather(active_probe, return_exceptions=True)
                self._active_probe = None
            self._stop_event = None
            self._state = BinanceClockProbeState.STOPPED

    def _record_success(self, sample: VenueClockSample) -> None:
        self._successes += 1
        self._consecutive_failures = 0
        self._last_error = None
        self._records.append(
            BinanceClockProbeRecord(
                sequence=self._probes,
                sample=sample,
                error=None,
            )
        )

    def _record_failure(self, error: Exception) -> None:
        self._failures += 1
        self._consecutive_failures += 1
        rendered = (
            str(error)
            if isinstance(error, BinanceServerTimeError)
            else f"{type(error).__name__}: clock probe failed"
        )
        self._last_error = rendered
        self._records.append(
            BinanceClockProbeRecord(
                sequence=self._probes,
                sample=None,
                error=rendered,
            )
        )

    async def _wait_or_stop(self, delay_seconds: float) -> None:
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
            if sleep_task in done:
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


async def _wait_until_set(event: asyncio.Event) -> None:
    await event.wait()


__all__ = [
    "BinanceClockProbePolicy",
    "BinanceClockProbeRecord",
    "BinanceClockProbeService",
    "BinanceClockProbeSnapshot",
    "BinanceClockProbeState",
    "BinanceServerTimeAdapter",
    "BinanceServerTimeError",
    "Sleep",
]
