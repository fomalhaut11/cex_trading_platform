"""Safe synchronous bridge to an asynchronous execution gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Event, Lock, Thread
from typing import Any, TypeVar, cast

from cex_quant.execution import (
    CancelOrder,
    CancelResult,
    ExecutionGateway,
    ExecutionQueryError,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    OrderReconciliationGateway,
    QueryOrder,
    SubmitResult,
)
from cex_quant.oms import OrderReconciliationSnapshot, OrderRequest

_ResultT = TypeVar("_ResultT")


class ExecutionBridgeError(RuntimeError):
    pass


class ExecutionBridgeStateError(ExecutionBridgeError, ExecutionTransportError):
    """The bridge rejected submission before dispatch to the gateway."""


class ExecutionBridgeUnknownError(
    ExecutionBridgeError,
    ExecutionStateUnknownError,
):
    """The bridge timed out after dispatch; venue state may exist."""


class ExecutionBridgeQueryError(ExecutionBridgeError, ExecutionQueryError):
    """A read-only query failed without changing venue state."""


class AsyncExecutionPortBridge:
    """Expose one async execution gateway through synchronous runtime ports.

    ``submit``, ``cancel`` and ``query_order`` are intentionally blocking. They
    must be called from a non-event-loop thread. Async applications should call
    their gateway directly or move the synchronous runtime to an executor.
    """

    def __init__(
        self,
        gateway: ExecutionGateway,
        *,
        reconciliation_gateway: OrderReconciliationGateway | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._gateway = gateway
        self._reconciliation_gateway: OrderReconciliationGateway | None
        if reconciliation_gateway is not None:
            self._reconciliation_gateway = reconciliation_gateway
        elif hasattr(gateway, "query_order"):
            self._reconciliation_gateway = cast(OrderReconciliationGateway, gateway)
        else:
            self._reconciliation_gateway = None
        self._timeout_seconds = timeout_seconds
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._started = Event()
        self._lock = Lock()

    @property
    def running(self) -> bool:
        return (
            self._loop is not None
            and self._thread is not None
            and self._thread.is_alive()
        )

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self._started.clear()
            self._thread = Thread(
                target=self._run_loop,
                name="cex-quant-execution-loop",
                daemon=True,
            )
            self._thread.start()
        if not self._started.wait(timeout=self._timeout_seconds):
            raise ExecutionBridgeStateError("execution loop failed to start")

    def submit(self, request: OrderRequest) -> SubmitResult:
        loop = self._loop_for_blocking_call("submit")
        return self._dispatch(
            loop,
            self._gateway.submit(request),
            timeout_error=ExecutionBridgeUnknownError(
                "execution submit timed out after dispatch"
            ),
        )

    def cancel(self, command: CancelOrder) -> CancelResult:
        loop = self._loop_for_blocking_call("cancel")
        return self._dispatch(
            loop,
            self._gateway.cancel(command),
            timeout_error=ExecutionBridgeUnknownError(
                "execution cancel timed out after dispatch"
            ),
        )

    def query_order(
        self,
        command: QueryOrder,
    ) -> OrderReconciliationSnapshot | None:
        loop = self._loop_for_blocking_call("query_order")
        gateway = self._reconciliation_gateway
        if gateway is None:
            raise ExecutionBridgeStateError(
                "execution gateway does not support order reconciliation"
            )
        return self._dispatch(
            loop,
            gateway.query_order(command),
            timeout_error=ExecutionBridgeQueryError(
                "execution order query timed out"
            ),
        )

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            if loop is None or thread is None:
                return
            loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=self._timeout_seconds)
        if thread.is_alive():
            raise ExecutionBridgeStateError("execution loop failed to stop")
        with self._lock:
            self._loop = None
            self._thread = None

    def __enter__(self) -> AsyncExecutionPortBridge:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._started.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()

    def _loop_for_blocking_call(
        self,
        operation: str,
    ) -> asyncio.AbstractEventLoop:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise ExecutionBridgeStateError(
                f"blocking {operation} cannot run inside an active event loop; "
                "move the synchronous runtime to a worker thread"
            )
        loop = self._loop
        if loop is None or not self.running:
            raise ExecutionBridgeStateError("execution bridge is not running")
        return loop

    def _dispatch(
        self,
        loop: asyncio.AbstractEventLoop,
        coroutine: Coroutine[Any, Any, _ResultT],
        *,
        timeout_error: BaseException,
    ) -> _ResultT:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=self._timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise timeout_error from error


__all__ = [
    "AsyncExecutionPortBridge",
    "ExecutionBridgeError",
    "ExecutionBridgeQueryError",
    "ExecutionBridgeStateError",
    "ExecutionBridgeUnknownError",
]
