import unittest
from queue import Queue
from threading import Event, Thread
from typing import cast

from cex_quant.market_data import MarketEvent
from cex_quant.recorder import AppendResult
from cex_quant.runtime import (
    OverflowPolicy,
    RecorderHandoff,
    RecorderHandoffOverflowError,
    RecorderHandoffStateError,
    RecorderHandoffStatus,
    RecorderWorkerFailedError,
)
from tests.test_recorder_codec import canonical_events


def event_at(index: int) -> MarketEvent:
    return cast(MarketEvent, canonical_events()[index])


class CollectingRecorder:
    def __init__(self) -> None:
        self.events: list[MarketEvent] = []
        self.flush_count = 0

    def append(self, event: MarketEvent) -> AppendResult:
        self.events.append(event)
        return AppendResult(offset=len(self.events) - 1, byte_length=1)

    def flush(self) -> None:
        self.flush_count += 1


class BlockingRecorder(CollectingRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.append_started = Event()
        self.append_release = Event()

    def append(self, event: MarketEvent) -> AppendResult:
        self.append_started.set()
        if not self.append_release.wait(timeout=2):
            raise AssertionError("test did not release blocked recorder")
        return super().append(event)


class FailingRecorder(CollectingRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.append_started = Event()
        self.append_release = Event()
        self.failure = OSError("disk unavailable")

    def append(self, event: MarketEvent) -> AppendResult:
        self.append_started.set()
        if not self.append_release.wait(timeout=2):
            raise AssertionError("test did not release failing recorder")
        raise self.failure


class FlushFailingRecorder(CollectingRecorder):
    def flush(self) -> None:
        raise OSError("flush failed")


class GatedControlQueue(Queue[object]):
    """Expose the lifecycle state after it changes but before control enqueue."""

    def __init__(self, maxsize: int) -> None:
        super().__init__(maxsize)
        self.gate_control_put = False
        self.control_put_started = Event()
        self.control_put_release = Event()

    def put(
        self,
        item: object,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        if self.gate_control_put and block:
            self.control_put_started.set()
            if not self.control_put_release.wait(timeout=2):
                raise AssertionError("test did not release lifecycle control put")
        super().put(item, block, timeout)


class RecorderHandoffTests(unittest.TestCase):
    def assert_queue_accounting_completes(
        self,
        handoff: RecorderHandoff,
    ) -> None:
        completed = Event()

        def join_queue() -> None:
            handoff._queue.join()
            completed.set()

        waiter = Thread(target=join_queue)
        waiter.start()
        self.assertTrue(
            completed.wait(timeout=2),
            "worker left queue tasks permanently unfinished",
        )
        waiter.join()

    def test_lifecycle_preserves_order_and_reports_health(self) -> None:
        recorder = CollectingRecorder()
        handoff = RecorderHandoff(recorder, capacity=2)

        initial = handoff.snapshot()
        self.assertEqual(initial.status, RecorderHandoffStatus.NEW)
        self.assertTrue(initial.healthy)
        self.assertEqual(handoff.overflow_policy, OverflowPolicy.REJECT)

        handoff.start()
        events = [event_at(0), event_at(1)]
        for event in events:
            handoff.submit(event)
        handoff.drain()

        drained = handoff.snapshot()
        self.assertEqual(recorder.events, events)
        self.assertEqual(drained.status, RecorderHandoffStatus.RUNNING)
        self.assertEqual(drained.accepted, 2)
        self.assertEqual(drained.appended, 2)
        self.assertEqual(drained.queued, 0)
        self.assertEqual(recorder.flush_count, 1)

        handoff.stop()
        stopped = handoff.snapshot()
        self.assertEqual(stopped.status, RecorderHandoffStatus.STOPPED)
        self.assertFalse(stopped.worker_alive)
        self.assertEqual(recorder.flush_count, 2)
        handoff.stop()

    def test_full_queue_rejects_without_blocking_or_silent_drop(self) -> None:
        recorder = BlockingRecorder()
        handoff = RecorderHandoff(recorder, capacity=1)
        handoff.start()
        handoff.submit(event_at(0))
        self.assertTrue(recorder.append_started.wait(timeout=2))
        handoff.submit(event_at(1))

        with self.assertRaises(RecorderHandoffOverflowError):
            handoff.submit(event_at(2))
        full = handoff.snapshot()
        self.assertEqual(full.accepted, 2)
        self.assertEqual(full.rejected_overflow, 1)

        recorder.append_release.set()
        handoff.stop()
        self.assertEqual(recorder.events, [event_at(0), event_at(1)])

    def test_append_failure_is_latched_and_pending_events_are_counted(self) -> None:
        recorder = FailingRecorder()
        handoff = RecorderHandoff(recorder, capacity=2)
        handoff.start()
        handoff.submit(event_at(0))
        self.assertTrue(recorder.append_started.wait(timeout=2))
        handoff.submit(event_at(1))
        recorder.append_release.set()

        with self.assertRaises(RecorderWorkerFailedError) as caught:
            handoff.drain()
        self.assertIs(caught.exception.cause, recorder.failure)

        failed = handoff.snapshot()
        self.assertEqual(failed.status, RecorderHandoffStatus.FAILED)
        self.assertFalse(failed.healthy)
        self.assertEqual(failed.accepted, 2)
        self.assertEqual(failed.appended, 0)
        self.assertEqual(failed.abandoned_after_failure, 2)
        self.assertEqual(failed.error_type, "OSError")
        self.assertEqual(failed.error_message, "disk unavailable")

        with self.assertRaises(RecorderWorkerFailedError):
            handoff.submit(event_at(2))
        with self.assertRaises(RecorderWorkerFailedError):
            handoff.stop()
        self.assertFalse(handoff.snapshot().worker_alive)
        self.assert_queue_accounting_completes(handoff)
        with self.assertRaises(RecorderWorkerFailedError):
            handoff.stop()

    def test_flush_failure_is_latched_by_drain(self) -> None:
        handoff = RecorderHandoff(FlushFailingRecorder(), capacity=1)
        handoff.start()
        handoff.submit(event_at(0))
        with self.assertRaises(RecorderWorkerFailedError):
            handoff.drain()
        self.assertEqual(handoff.snapshot().error_message, "flush failed")
        with self.assertRaises(RecorderWorkerFailedError):
            handoff.stop()
        self.assertFalse(handoff.snapshot().worker_alive)
        self.assert_queue_accounting_completes(handoff)
        with self.assertRaises(RecorderWorkerFailedError):
            handoff.stop()

    def test_submit_cannot_cross_drain_boundary(self) -> None:
        recorder = BlockingRecorder()
        handoff = RecorderHandoff(recorder, capacity=2)
        queue = GatedControlQueue(maxsize=2)
        handoff._queue = queue  # type: ignore[assignment]
        handoff.start()
        handoff.submit(event_at(0))
        self.assertTrue(recorder.append_started.wait(timeout=2))
        queue.gate_control_put = True
        errors: list[BaseException] = []

        def drain() -> None:
            try:
                handoff.drain()
            except BaseException as exc:
                errors.append(exc)

        drainer = Thread(target=drain)
        drainer.start()
        self.assertTrue(queue.control_put_started.wait(timeout=2))
        self.assertEqual(
            handoff.snapshot().status,
            RecorderHandoffStatus.DRAINING,
        )
        with self.assertRaises(RecorderHandoffStateError):
            handoff.submit(event_at(1))
        queue.gate_control_put = False
        queue.control_put_release.set()
        recorder.append_release.set()
        drainer.join(timeout=2)
        self.assertFalse(drainer.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(
            handoff.snapshot().status,
            RecorderHandoffStatus.RUNNING,
        )
        handoff.stop()

    def test_submit_cannot_cross_stop_boundary(self) -> None:
        recorder = BlockingRecorder()
        handoff = RecorderHandoff(recorder, capacity=2)
        queue = GatedControlQueue(maxsize=2)
        handoff._queue = queue  # type: ignore[assignment]
        handoff.start()
        handoff.submit(event_at(0))
        self.assertTrue(recorder.append_started.wait(timeout=2))
        queue.gate_control_put = True
        errors: list[BaseException] = []

        def stop() -> None:
            try:
                handoff.stop()
            except BaseException as exc:
                errors.append(exc)

        stopper = Thread(target=stop)
        stopper.start()
        self.assertTrue(queue.control_put_started.wait(timeout=2))
        self.assertEqual(
            handoff.snapshot().status,
            RecorderHandoffStatus.DRAINING,
        )
        with self.assertRaises(RecorderHandoffStateError):
            handoff.submit(event_at(1))
        queue.control_put_release.set()
        recorder.append_release.set()
        stopper.join(timeout=2)
        self.assertFalse(stopper.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(
            handoff.snapshot().status,
            RecorderHandoffStatus.STOPPED,
        )

    def test_invalid_capacity_and_lifecycle_operations_fail(self) -> None:
        recorder = CollectingRecorder()
        with self.assertRaises(ValueError):
            RecorderHandoff(recorder, capacity=0)

        handoff = RecorderHandoff(recorder, capacity=1)
        with self.assertRaises(RecorderHandoffStateError):
            handoff.submit(event_at(0))
        with self.assertRaises(RecorderHandoffStateError):
            handoff.drain()
        handoff.start()
        with self.assertRaises(RecorderHandoffStateError):
            handoff.start()
        handoff.stop()
        with self.assertRaises(RecorderHandoffStateError):
            handoff.submit(event_at(0))

    def test_stop_before_start_is_safe(self) -> None:
        handoff = RecorderHandoff(CollectingRecorder(), capacity=1)
        handoff.stop()
        self.assertEqual(handoff.snapshot().status, RecorderHandoffStatus.STOPPED)
        handoff.stop()


if __name__ == "__main__":
    unittest.main()
