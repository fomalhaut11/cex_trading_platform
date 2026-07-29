"""Bounded single-writer handoff for durable Accounting facts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from queue import Full, Queue
from threading import Event, Lock, Thread
from time import monotonic_ns
from typing import Final, Protocol

from cex_quant.accounting import ObservedFinancialFact
from cex_quant.accounting.ledger import LedgerIngestResult
from cex_quant.core import UnixNanos
from cex_quant.observability import (
    HealthIssue,
    HealthReport,
    HealthStatus,
)


class FinancialFactSink(Protocol):
    def ingest(
        self,
        observed: ObservedFinancialFact,
        *,
        posted_at_ns: UnixNanos,
    ) -> LedgerIngestResult: ...


class FinancialFactHandoffStatus(StrEnum):
    NEW = "new"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


class FinancialFactHandoffError(RuntimeError):
    pass


class FinancialFactOverflowError(FinancialFactHandoffError):
    pass


class FinancialFactExpiredError(FinancialFactHandoffError):
    pass


class FinancialFactHandoffStateError(FinancialFactHandoffError):
    pass


class FinancialFactWorkerFailedError(FinancialFactHandoffError):
    def __init__(self, cause: BaseException) -> None:
        self.cause = cause
        super().__init__(
            "financial fact worker failed with "
            f"{type(cause).__name__}: {cause}"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialFactHandoffSnapshot:
    status: FinancialFactHandoffStatus
    capacity: int
    maximum_queue_age_ns: int
    queued: int
    accepted: int
    durably_processed: int
    rejected_overflow: int
    expired: int
    abandoned_after_failure: int
    worker_alive: bool
    error_type: str | None
    error_message: str | None

    @property
    def healthy(self) -> bool:
        return (
            self.status
            in {
                FinancialFactHandoffStatus.NEW,
                FinancialFactHandoffStatus.RUNNING,
                FinancialFactHandoffStatus.DRAINING,
                FinancialFactHandoffStatus.STOPPED,
            }
            and self.rejected_overflow == 0
            and self.expired == 0
            and self.error_type is None
        )


@dataclass(frozen=True, slots=True)
class _FactItem:
    observed: ObservedFinancialFact
    enqueued_at_ns: int


@dataclass(frozen=True, slots=True)
class _DrainItem:
    completed: Event


@dataclass(frozen=True, slots=True)
class _StopItem:
    completed: Event


_QueueItem = _FactItem | _DrainItem | _StopItem
_WORKER_NAME: Final = "cex-quant-accounting"


class FinancialFactHandoff:
    """Retain accepted facts durably without blocking an OMS lifecycle path."""

    def __init__(
        self,
        sink_factory: Callable[[], FinancialFactSink],
        *,
        capacity: int,
        maximum_queue_age_ns: int,
        posting_clock: Callable[[], UnixNanos],
        monotonic_clock: Callable[[], int] = monotonic_ns,
        worker_name: str = _WORKER_NAME,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if maximum_queue_age_ns <= 0:
            raise ValueError("maximum_queue_age_ns must be positive")
        if not worker_name:
            raise ValueError("worker_name must not be empty")
        self._sink_factory = sink_factory
        self._capacity = capacity
        self._maximum_queue_age_ns = maximum_queue_age_ns
        self._posting_clock = posting_clock
        self._monotonic_clock = monotonic_clock
        self._worker_name = worker_name
        self._queue: Queue[_QueueItem] = Queue(maxsize=capacity)
        self._state_lock = Lock()
        self._lifecycle_lock = Lock()
        self._initialized = Event()
        self._status = FinancialFactHandoffStatus.NEW
        self._worker: Thread | None = None
        self._failure: BaseException | None = None
        self._accepted = 0
        self._durably_processed = 0
        self._rejected_overflow = 0
        self._expired = 0
        self._abandoned_after_failure = 0

    @property
    def component(self) -> str:
        return "accounting.financial_fact_handoff"

    def start(self) -> None:
        with self._lifecycle_lock, self._state_lock:
            if self._status is not FinancialFactHandoffStatus.NEW:
                raise FinancialFactHandoffStateError(
                    f"cannot start handoff in {self._status.value} state"
                )
            worker = Thread(
                target=self._worker_main,
                name=self._worker_name,
                daemon=False,
            )
            self._worker = worker
            self._status = FinancialFactHandoffStatus.RUNNING
            worker.start()
        self._initialized.wait()
        with self._state_lock:
            self._raise_if_failed_locked()

    def submit(self, observed: ObservedFinancialFact) -> None:
        """Accept immediately or reject explicitly without dropping evidence."""

        with self._state_lock:
            self._raise_if_failed_locked()
            if self._status is not FinancialFactHandoffStatus.RUNNING:
                raise FinancialFactHandoffStateError(
                    f"cannot submit in {self._status.value} state"
                )
            try:
                self._queue.put_nowait(
                    _FactItem(
                        observed=observed,
                        enqueued_at_ns=self._monotonic_clock(),
                    )
                )
            except Full as error:
                self._rejected_overflow += 1
                raise FinancialFactOverflowError(
                    "financial fact queue capacity "
                    f"{self._capacity} exhausted"
                ) from error
            self._accepted += 1

    def drain(self) -> None:
        with self._lifecycle_lock:
            completed = Event()
            with self._state_lock:
                self._raise_if_failed_locked()
                if self._status is not FinancialFactHandoffStatus.RUNNING:
                    raise FinancialFactHandoffStateError(
                        f"cannot drain in {self._status.value} state"
                    )
                self._status = FinancialFactHandoffStatus.DRAINING
            self._queue.put(_DrainItem(completed))
            completed.wait()
            with self._state_lock:
                self._raise_if_failed_locked()
                self._status = FinancialFactHandoffStatus.RUNNING

    def stop(self) -> None:
        with self._lifecycle_lock:
            with self._state_lock:
                if self._status is FinancialFactHandoffStatus.STOPPED:
                    return
                if self._status is FinancialFactHandoffStatus.NEW:
                    self._status = FinancialFactHandoffStatus.STOPPED
                    return
                worker = self._worker
                if (
                    self._status is FinancialFactHandoffStatus.FAILED
                    and (worker is None or not worker.is_alive())
                ):
                    self._raise_if_failed_locked()
                if self._status not in {
                    FinancialFactHandoffStatus.RUNNING,
                    FinancialFactHandoffStatus.FAILED,
                }:
                    raise FinancialFactHandoffStateError(
                        f"cannot stop in {self._status.value} state"
                    )
                if self._failure is None:
                    self._status = FinancialFactHandoffStatus.DRAINING
                completed = Event()
            self._queue.put(_StopItem(completed))
            completed.wait()
            if worker is not None:
                worker.join()
            with self._state_lock:
                self._raise_if_failed_locked()

    def snapshot(self) -> FinancialFactHandoffSnapshot:
        with self._state_lock:
            failure = self._failure
            worker = self._worker
            return FinancialFactHandoffSnapshot(
                status=self._status,
                capacity=self._capacity,
                maximum_queue_age_ns=self._maximum_queue_age_ns,
                queued=self._queue.qsize(),
                accepted=self._accepted,
                durably_processed=self._durably_processed,
                rejected_overflow=self._rejected_overflow,
                expired=self._expired,
                abandoned_after_failure=self._abandoned_after_failure,
                worker_alive=worker is not None and worker.is_alive(),
                error_type=(
                    None if failure is None else type(failure).__name__
                ),
                error_message=None if failure is None else str(failure),
            )

    def health(self) -> HealthReport:
        snapshot = self.snapshot()
        issues: list[HealthIssue] = []
        if snapshot.rejected_overflow:
            issues.append(
                HealthIssue(
                    code="FINANCIAL_FACT_OVERFLOW",
                    message=(
                        f"{snapshot.rejected_overflow} financial facts "
                        "were rejected by the bounded inbox"
                    ),
                )
            )
        if snapshot.expired:
            issues.append(
                HealthIssue(
                    code="FINANCIAL_FACT_EXPIRED",
                    message=(
                        f"{snapshot.expired} queued financial facts "
                        "exceeded the age bound"
                    ),
                )
            )
        if snapshot.error_type is not None:
            issues.append(
                HealthIssue(
                    code="FINANCIAL_FACT_WORKER_FAILED",
                    message=(
                        f"{snapshot.error_type}: {snapshot.error_message}"
                    ),
                )
            )
        return HealthReport(
            component=self.component,
            status=(
                HealthStatus.HEALTHY
                if snapshot.healthy
                else HealthStatus.UNHEALTHY
            ),
            observed_at_ns=self._posting_clock(),
            issues=tuple(issues),
        )

    def __enter__(self) -> FinancialFactHandoff:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _worker_main(self) -> None:
        try:
            sink = self._sink_factory()
        except BaseException as error:
            with self._state_lock:
                self._latch_failure_locked(error)
            self._initialized.set()
            return
        self._initialized.set()
        while True:
            item = self._queue.get()
            try:
                if isinstance(item, _FactItem):
                    self._handle_fact(sink, item)
                elif isinstance(item, _DrainItem):
                    item.completed.set()
                else:
                    with self._state_lock:
                        if self._failure is None:
                            self._status = FinancialFactHandoffStatus.STOPPED
                    item.completed.set()
                    return
            finally:
                self._queue.task_done()

    def _handle_fact(
        self,
        sink: FinancialFactSink,
        item: _FactItem,
    ) -> None:
        with self._state_lock:
            failed = self._failure is not None
            if failed:
                self._abandoned_after_failure += 1
        if failed:
            return
        age_ns = self._monotonic_clock() - item.enqueued_at_ns
        if age_ns > self._maximum_queue_age_ns:
            error = FinancialFactExpiredError(
                f"financial fact queue age {age_ns} exceeds bound "
                f"{self._maximum_queue_age_ns}"
            )
            with self._state_lock:
                self._expired += 1
                self._abandoned_after_failure += 1
                self._latch_failure_locked(error)
            return
        try:
            sink.ingest(
                item.observed,
                posted_at_ns=self._posting_clock(),
            )
        except BaseException as error:
            with self._state_lock:
                self._abandoned_after_failure += 1
                self._latch_failure_locked(error)
        else:
            with self._state_lock:
                self._durably_processed += 1

    def _latch_failure_locked(self, failure: BaseException) -> None:
        if self._failure is None:
            self._failure = failure
            self._status = FinancialFactHandoffStatus.FAILED

    def _raise_if_failed_locked(self) -> None:
        if self._failure is not None:
            raise FinancialFactWorkerFailedError(
                self._failure
            ) from self._failure


__all__ = [
    "FinancialFactExpiredError",
    "FinancialFactHandoff",
    "FinancialFactHandoffError",
    "FinancialFactHandoffSnapshot",
    "FinancialFactHandoffStateError",
    "FinancialFactHandoffStatus",
    "FinancialFactOverflowError",
    "FinancialFactSink",
    "FinancialFactWorkerFailedError",
]
