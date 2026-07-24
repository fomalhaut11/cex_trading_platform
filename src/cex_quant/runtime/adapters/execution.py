"""Safe synchronous bridge to an asynchronous execution gateway."""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Event, Lock, Thread

from cex_quant.execution import ExecutionGateway, SubmitResult
from cex_quant.oms import OrderRequest


class ExecutionBridgeError(RuntimeError):
    pass


class ExecutionBridgeStateError(ExecutionBridgeError):
    pass


class AsyncExecutionPortBridge:
    """Run gateway coroutines on one explicitly owned background loop.

    ``submit`` is intentionally a blocking synchronous port. It must be called
    from a non-event-loop thread. Async applications should call their gateway
    directly or move the whole synchronous pipeline to an executor.
    """

    def __init__(
        self,
        gateway: ExecutionGateway,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._gateway = gateway
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
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise ExecutionBridgeStateError(
                "blocking submit cannot run inside an active event loop; "
                "move TradingPipeline.process to a worker thread"
            )
        loop = self._loop
        if loop is None or not self.running:
            raise ExecutionBridgeStateError("execution bridge is not running")
        future = asyncio.run_coroutine_threadsafe(
            self._gateway.submit(request),
            loop,
        )
        try:
            return future.result(timeout=self._timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise ExecutionBridgeError("execution submit timed out") from error

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


__all__ = [
    "AsyncExecutionPortBridge",
    "ExecutionBridgeError",
    "ExecutionBridgeStateError",
]
