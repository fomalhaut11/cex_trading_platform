"""Bounded worker handoff for synchronous event recorders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from queue import Full, Queue
from threading import Event, Lock, Thread
from typing import Final

from cex_quant.market_data import MarketEvent
from cex_quant.recorder import EventRecorder


class OverflowPolicy(StrEnum):
    """Behavior when the bounded event queue has no free slot."""

    REJECT = "reject"


class RecorderHandoffStatus(StrEnum):
    NEW = "new"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


class RecorderHandoffError(RuntimeError):
    """Base class for explicit runtime handoff failures."""


class RecorderHandoffOverflowError(RecorderHandoffError):
    """The event was rejected because the bounded queue was full."""


class RecorderHandoffStateError(RecorderHandoffError):
    """The requested operation is invalid for the current lifecycle state."""


class RecorderWorkerFailedError(RecorderHandoffError):
    """The recorder worker latched a terminal append or flush failure."""

    def __init__(self, cause: BaseException) -> None:
        self.cause = cause
        super().__init__(
            f"recorder worker failed with {type(cause).__name__}: {cause}"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecorderHandoffSnapshot:
    status: RecorderHandoffStatus
    capacity: int
    queued: int
    accepted: int
    appended: int
    rejected_overflow: int
    abandoned_after_failure: int
    worker_alive: bool
    error_type: str | None
    error_message: str | None

    @property
    def healthy(self) -> bool:
        return self.status in {
            RecorderHandoffStatus.NEW,
            RecorderHandoffStatus.RUNNING,
            RecorderHandoffStatus.DRAINING,
            RecorderHandoffStatus.STOPPED,
        } and self.error_type is None


@dataclass(frozen=True, slots=True)
class _EventItem:
    event: MarketEvent


@dataclass(frozen=True, slots=True)
class _DrainItem:
    completed: Event


@dataclass(frozen=True, slots=True)
class _StopItem:
    completed: Event


_QueueItem = _EventItem | _DrainItem | _StopItem
_WORKER_NAME: Final = "cex-quant-recorder"


class RecorderHandoff:
    """Thread-safe, fail-fast handoff from a hot path to a blocking recorder.

    ``submit`` never waits for storage and rejects explicitly when the queue is
    full. One worker owns all recorder calls, preserving accepted event order.
    A recorder failure is terminal and remains visible in every later operation
    and health snapshot.
    """

    def __init__(
        self,
        recorder: EventRecorder,
        *,
        capacity: int,
        overflow_policy: OverflowPolicy = OverflowPolicy.REJECT,
        worker_name: str = _WORKER_NAME,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not worker_name:
            raise ValueError("worker_name must not be empty")
        if overflow_policy is not OverflowPolicy.REJECT:
            raise ValueError(f"unsupported overflow policy: {overflow_policy}")

        self._recorder = recorder
        self._capacity = capacity
        self._overflow_policy = overflow_policy
        self._worker_name = worker_name
        self._queue: Queue[_QueueItem] = Queue(maxsize=capacity)
        self._state_lock = Lock()
        self._lifecycle_lock = Lock()
        self._status = RecorderHandoffStatus.NEW
        self._worker: Thread | None = None
        self._failure: BaseException | None = None
        self._accepted = 0
        self._appended = 0
        self._rejected_overflow = 0
        self._abandoned_after_failure = 0

    @property
    def overflow_policy(self) -> OverflowPolicy:
        return self._overflow_policy

    def start(self) -> None:
        with self._lifecycle_lock, self._state_lock:
            if self._status is not RecorderHandoffStatus.NEW:
                raise RecorderHandoffStateError(
                    f"cannot start handoff in {self._status.value} state"
                )
            worker = Thread(
                target=self._worker_main,
                name=self._worker_name,
                daemon=False,
            )
            self._worker = worker
            self._status = RecorderHandoffStatus.RUNNING
            worker.start()

    def submit(self, event: MarketEvent) -> None:
        """Accept an event immediately or raise without silently dropping it."""

        with self._state_lock:
            self._raise_if_failed_locked()
            if self._status is not RecorderHandoffStatus.RUNNING:
                raise RecorderHandoffStateError(
                    f"cannot submit in {self._status.value} state"
                )
            try:
                self._queue.put_nowait(_EventItem(event))
            except Full as exc:
                self._rejected_overflow += 1
                raise RecorderHandoffOverflowError(
                    f"recorder queue capacity {self._capacity} exhausted"
                ) from exc
            self._accepted += 1

    def drain(self) -> None:
        """Wait until prior accepted events are appended and flush succeeds."""

        with self._lifecycle_lock:
            completed = Event()
            with self._state_lock:
                self._raise_if_failed_locked()
                if self._status is not RecorderHandoffStatus.RUNNING:
                    raise RecorderHandoffStateError(
                        f"cannot drain in {self._status.value} state"
                    )
                self._status = RecorderHandoffStatus.DRAINING
            self._queue.put(_DrainItem(completed))
            completed.wait()
            with self._state_lock:
                self._raise_if_failed_locked()
                self._status = RecorderHandoffStatus.RUNNING

    def stop(self) -> None:
        """Drain, flush and join the worker; this operation is idempotent."""

        with self._lifecycle_lock:
            with self._state_lock:
                if self._status is RecorderHandoffStatus.STOPPED:
                    return
                if self._status is RecorderHandoffStatus.NEW:
                    self._status = RecorderHandoffStatus.STOPPED
                    return
                worker = self._worker
                if (
                    self._status is RecorderHandoffStatus.FAILED
                    and (worker is None or not worker.is_alive())
                ):
                    self._raise_if_failed_locked()
                if self._status not in {
                    RecorderHandoffStatus.RUNNING,
                    RecorderHandoffStatus.FAILED,
                }:
                    raise RecorderHandoffStateError(
                        f"cannot stop in {self._status.value} state"
                    )
                if self._failure is None:
                    self._status = RecorderHandoffStatus.DRAINING
                completed = Event()
            self._queue.put(_StopItem(completed))
            completed.wait()
            if worker is not None:
                worker.join()
            with self._state_lock:
                self._raise_if_failed_locked()

    def snapshot(self) -> RecorderHandoffSnapshot:
        with self._state_lock:
            failure = self._failure
            worker = self._worker
            return RecorderHandoffSnapshot(
                status=self._status,
                capacity=self._capacity,
                queued=self._queue.qsize(),
                accepted=self._accepted,
                appended=self._appended,
                rejected_overflow=self._rejected_overflow,
                abandoned_after_failure=self._abandoned_after_failure,
                worker_alive=worker is not None and worker.is_alive(),
                error_type=None if failure is None else type(failure).__name__,
                error_message=None if failure is None else str(failure),
            )

    def __enter__(self) -> RecorderHandoff:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _worker_main(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if isinstance(item, _EventItem):
                    self._handle_event(item)
                elif isinstance(item, _DrainItem):
                    self._handle_flush()
                    item.completed.set()
                else:
                    self._handle_flush()
                    with self._state_lock:
                        if self._failure is None:
                            self._status = RecorderHandoffStatus.STOPPED
                    item.completed.set()
                    return
            finally:
                self._queue.task_done()

    def _handle_event(self, item: _EventItem) -> None:
        with self._state_lock:
            failed = self._failure is not None
            if failed:
                self._abandoned_after_failure += 1
        if failed:
            return
        try:
            self._recorder.append(item.event)
        except BaseException as exc:
            with self._state_lock:
                self._abandoned_after_failure += 1
                self._latch_failure_locked(exc)
        else:
            with self._state_lock:
                self._appended += 1

    def _handle_flush(self) -> None:
        with self._state_lock:
            if self._failure is not None:
                return
        try:
            self._recorder.flush()
        except BaseException as exc:
            with self._state_lock:
                self._latch_failure_locked(exc)

    def _latch_failure_locked(self, failure: BaseException) -> None:
        if self._failure is None:
            self._failure = failure
            self._status = RecorderHandoffStatus.FAILED

    def _raise_if_failed_locked(self) -> None:
        if self._failure is not None:
            raise RecorderWorkerFailedError(self._failure) from self._failure


__all__ = [
    "OverflowPolicy",
    "RecorderHandoff",
    "RecorderHandoffError",
    "RecorderHandoffOverflowError",
    "RecorderHandoffSnapshot",
    "RecorderHandoffStateError",
    "RecorderHandoffStatus",
    "RecorderWorkerFailedError",
]
