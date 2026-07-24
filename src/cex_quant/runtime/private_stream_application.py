"""Fail-closed lifecycle for private streams and startup reconciliation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from cex_quant.execution import PrivateOrderStreamSupervisor

from .reconciliation import (
    StartupOrderReconciliationCoordinator,
    StartupReconciliationReport,
)


class PrivateStreamApplicationState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    RECONCILING = "reconciling"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class PrivateStreamApplicationStateError(RuntimeError):
    """Raised when a lifecycle operation is not valid in the current state."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PrivateStreamApplicationSnapshot:
    state: PrivateStreamApplicationState
    reconciliation: StartupReconciliationReport | None = None
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.state is PrivateStreamApplicationState.READY


class PrivateStreamApplication:
    """Supervise the private stream while startup state converges.

    The private stream starts buffering before REST reconciliation begins.
    Trading is ready only after reconciliation explicitly reaches ``LIVE``.
    """

    def __init__(
        self,
        *,
        supervisor: PrivateOrderStreamSupervisor,
        reconciliation: StartupOrderReconciliationCoordinator,
        start_timeout_seconds: float = 10.0,
        stop_timeout_seconds: float = 10.0,
    ) -> None:
        if start_timeout_seconds <= 0:
            raise ValueError("start timeout must be positive")
        if stop_timeout_seconds <= 0:
            raise ValueError("stop timeout must be positive")
        self._supervisor = supervisor
        self._reconciliation = reconciliation
        self._start_timeout_seconds = start_timeout_seconds
        self._stop_timeout_seconds = stop_timeout_seconds
        self._state = PrivateStreamApplicationState.NEW
        self._report: StartupReconciliationReport | None = None
        self._error = ""
        self._stream_task: asyncio.Task[int] | None = None

    @property
    def snapshot(self) -> PrivateStreamApplicationSnapshot:
        if (
            self._state is PrivateStreamApplicationState.READY
            and not self._supervisor.connection_active
        ):
            return PrivateStreamApplicationSnapshot(
                state=PrivateStreamApplicationState.DEGRADED,
                reconciliation=self._report,
                error="private stream connection is not active",
            )
        return PrivateStreamApplicationSnapshot(
            state=self._state,
            reconciliation=self._report,
            error=self._error,
        )

    async def start(self) -> PrivateStreamApplicationSnapshot:
        if self._state is not PrivateStreamApplicationState.NEW:
            raise PrivateStreamApplicationStateError(
                f"cannot start from {self._state.value}"
            )

        self._state = PrivateStreamApplicationState.STARTING
        try:
            self._reconciliation.begin_buffering()
            task = asyncio.create_task(
                self._supervisor.run(),
                name="private-order-stream-supervisor",
            )
            self._stream_task = task
            task.add_done_callback(self._stream_finished)

            if not await self._wait_for_active_stream(task):
                return self.snapshot

            self._state = PrivateStreamApplicationState.RECONCILING
            report = await self._reconciliation.reconcile_startup()
            self._report = report

            # stop() or an asynchronous stream failure may have changed state
            # while reconciliation was in flight.
            if self._state is not PrivateStreamApplicationState.RECONCILING:
                return self.snapshot
            if task.done():
                self._record_finished_task(task)
            elif report.ready and self._supervisor.connection_active:
                self._state = PrivateStreamApplicationState.READY
            else:
                self._state = PrivateStreamApplicationState.DEGRADED
                self._error = (
                    "startup readiness conditions were not met: "
                    f"reconciliation={report.state.value}, "
                    "private_stream_active="
                    f"{self._supervisor.connection_active}"
                )
        except asyncio.CancelledError:
            if self._state not in {
                PrivateStreamApplicationState.STOPPING,
                PrivateStreamApplicationState.STOPPED,
            }:
                self._state = PrivateStreamApplicationState.FAILED
                self._error = "startup was cancelled"
            raise
        except Exception as error:
            self._state = PrivateStreamApplicationState.FAILED
            self._error = _error_text(error)
            await self._cancel_stream_task(self._stop_timeout_seconds)
        return self.snapshot

    async def _wait_for_active_stream(
        self,
        stream_task: asyncio.Task[int],
    ) -> bool:
        active_task = asyncio.create_task(
            self._supervisor.wait_until_active(),
            name="private-order-stream-active",
        )
        try:
            done, _ = await asyncio.wait(
                {stream_task, active_task},
                timeout=self._start_timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stream_task in done:
                self._record_finished_task(stream_task)
                return False
            if active_task in done:
                error = active_task.exception()
                if error is not None:
                    raise error
                return True
            self._state = PrivateStreamApplicationState.FAILED
            self._error = (
                "private stream did not become active within "
                f"{self._start_timeout_seconds:g} seconds"
            )
            await self._cancel_stream_task(self._stop_timeout_seconds)
            return False
        finally:
            if not active_task.done():
                active_task.cancel()
            await asyncio.gather(active_task, return_exceptions=True)

    async def stop(self) -> PrivateStreamApplicationSnapshot:
        if self._state is PrivateStreamApplicationState.STOPPED:
            return self.snapshot
        if self._state is PrivateStreamApplicationState.NEW:
            self._state = PrivateStreamApplicationState.STOPPED
            return self.snapshot

        self._state = PrivateStreamApplicationState.STOPPING
        try:
            self._supervisor.request_stop()
        except Exception as error:
            self._state = PrivateStreamApplicationState.FAILED
            self._error = _error_text(error)
            return self.snapshot

        stopped = await self._cancel_stream_task(self._stop_timeout_seconds)
        if stopped:
            self._state = PrivateStreamApplicationState.STOPPED
        else:
            self._state = PrivateStreamApplicationState.FAILED
            self._error = (
                "private stream task did not stop within "
                f"{self._stop_timeout_seconds:g} seconds"
            )
        return self.snapshot

    async def _cancel_stream_task(self, timeout_seconds: float) -> bool:
        task = self._stream_task
        if task is None or task.done():
            if task is not None:
                self._consume_finished_task(task)
            return True
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
        if task in done:
            self._consume_finished_task(task)
            return True
        return False

    def _stream_finished(self, task: asyncio.Task[int]) -> None:
        if task is not self._stream_task:
            return
        self._consume_finished_task(task)
        if self._state in {
            PrivateStreamApplicationState.STOPPING,
            PrivateStreamApplicationState.STOPPED,
            PrivateStreamApplicationState.FAILED,
        }:
            return
        self._record_finished_task(task)

    def _record_finished_task(self, task: asyncio.Task[int]) -> None:
        self._state = PrivateStreamApplicationState.FAILED
        if task.cancelled():
            self._error = "private stream task was cancelled unexpectedly"
            return
        error = task.exception()
        self._error = (
            _error_text(error)
            if error is not None
            else "private stream supervisor stopped unexpectedly"
        )

    @staticmethod
    def _consume_finished_task(task: asyncio.Task[int]) -> None:
        if not task.cancelled():
            task.exception()


def _error_text(error: BaseException) -> str:
    message = str(error).strip()
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


__all__ = [
    "PrivateStreamApplication",
    "PrivateStreamApplicationSnapshot",
    "PrivateStreamApplicationState",
    "PrivateStreamApplicationStateError",
]
