import asyncio
from unittest import IsolatedAsyncioTestCase

from cex_quant.runtime.private_stream_application import (
    PrivateStreamApplication,
    PrivateStreamApplicationState,
    PrivateStreamApplicationStateError,
)
from cex_quant.runtime.reconciliation import (
    StartupReconciliationReport,
    StartupReconciliationState,
)


class FakeSupervisor:
    def __init__(
        self,
        *,
        fail: Exception | None = None,
        ignore_cancellation: bool = False,
        become_active: bool = True,
    ) -> None:
        self.fail = fail
        self.ignore_cancellation = ignore_cancellation
        self.become_active = become_active
        self.started = asyncio.Event()
        self.active = asyncio.Event()
        self.release = asyncio.Event()
        self.stop_requests = 0

    async def run(self, *, max_cycles: int | None = None) -> int:
        del max_cycles
        self.started.set()
        if self.become_active:
            self.active.set()
        if self.fail is not None:
            raise self.fail
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            if not self.ignore_cancellation:
                raise
            await self.release.wait()
        return 1

    def request_stop(self) -> None:
        self.stop_requests += 1

    @property
    def connection_active(self) -> bool:
        return self.active.is_set()

    async def wait_until_active(self) -> None:
        await self.active.wait()


class FakeReconciliation:
    def __init__(
        self,
        *,
        report: StartupReconciliationReport | None = None,
        fail: Exception | None = None,
    ) -> None:
        self.report = report or StartupReconciliationReport(
            state=StartupReconciliationState.LIVE,
            queries=(),
            stream_observations=0,
        )
        self.fail = fail
        self.buffering_started = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    def begin_buffering(self) -> None:
        self.buffering_started = True

    async def reconcile_startup(self) -> StartupReconciliationReport:
        self.entered.set()
        await self.release.wait()
        if self.fail is not None:
            raise self.fail
        return self.report


def application(
    supervisor: FakeSupervisor,
    reconciliation: FakeReconciliation,
    *,
    start_timeout_seconds: float = 0.1,
    stop_timeout_seconds: float = 0.1,
) -> PrivateStreamApplication:
    return PrivateStreamApplication(
        supervisor=supervisor,  # type: ignore[arg-type]
        reconciliation=reconciliation,  # type: ignore[arg-type]
        start_timeout_seconds=start_timeout_seconds,
        stop_timeout_seconds=stop_timeout_seconds,
    )


class PrivateStreamApplicationTests(IsolatedAsyncioTestCase):
    async def test_ready_only_after_stream_and_reconciliation(self) -> None:
        supervisor = FakeSupervisor()
        reconciliation = FakeReconciliation()
        app = application(supervisor, reconciliation)

        snapshot = await app.start()

        self.assertTrue(reconciliation.buffering_started)
        self.assertTrue(supervisor.started.is_set())
        self.assertTrue(snapshot.ready)
        self.assertEqual(snapshot.state, PrivateStreamApplicationState.READY)
        self.assertIsNotNone(snapshot.reconciliation)

        stopped = await app.stop()
        self.assertEqual(stopped.state, PrivateStreamApplicationState.STOPPED)
        self.assertEqual(supervisor.stop_requests, 1)

    async def test_reconciliation_not_ready_is_degraded(self) -> None:
        supervisor = FakeSupervisor()
        reconciliation = FakeReconciliation(
            report=StartupReconciliationReport(
                state=StartupReconciliationState.DEGRADED,
                queries=(),
                stream_observations=2,
            )
        )
        app = application(supervisor, reconciliation)

        snapshot = await app.start()

        self.assertFalse(snapshot.ready)
        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.DEGRADED,
        )
        self.assertIn("degraded", snapshot.error)
        await app.stop()

    async def test_stream_failure_before_reconciliation_fails_closed(
        self,
    ) -> None:
        app = application(
            FakeSupervisor(fail=RuntimeError("authorization failed")),
            FakeReconciliation(),
        )

        snapshot = await app.start()

        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.FAILED,
        )
        self.assertIn("authorization failed", snapshot.error)
        self.assertFalse(snapshot.ready)

    async def test_connection_start_timeout_fails_closed(self) -> None:
        app = application(
            FakeSupervisor(become_active=False),
            FakeReconciliation(),
            start_timeout_seconds=0.01,
        )

        snapshot = await app.start()

        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.FAILED,
        )
        self.assertIn("did not become active", snapshot.error)
        self.assertFalse(snapshot.ready)

    async def test_reconciliation_exception_cancels_stream_and_fails_closed(
        self,
    ) -> None:
        supervisor = FakeSupervisor()
        app = application(
            supervisor,
            FakeReconciliation(fail=RuntimeError("query unavailable")),
        )

        snapshot = await app.start()

        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.FAILED,
        )
        self.assertIn("query unavailable", snapshot.error)
        self.assertFalse(snapshot.ready)

    async def test_unexpected_stream_end_after_ready_marks_failed(self) -> None:
        supervisor = FakeSupervisor()
        app = application(supervisor, FakeReconciliation())
        self.assertTrue((await app.start()).ready)

        supervisor.release.set()
        for _ in range(3):
            await asyncio.sleep(0)
            if (
                app.snapshot.state
                is PrivateStreamApplicationState.FAILED
            ):
                break

        snapshot = app.snapshot
        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.FAILED,
        )
        self.assertIn("stopped unexpectedly", snapshot.error)

    async def test_ready_snapshot_degrades_during_connection_gap(self) -> None:
        supervisor = FakeSupervisor()
        app = application(supervisor, FakeReconciliation())
        self.assertTrue((await app.start()).ready)

        supervisor.active.clear()

        snapshot = app.snapshot
        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.DEGRADED,
        )
        self.assertFalse(snapshot.ready)
        self.assertIn("not active", snapshot.error)
        supervisor.active.set()
        self.assertTrue(app.snapshot.ready)
        await app.stop()

    async def test_stop_is_bounded_when_task_ignores_cancellation(self) -> None:
        supervisor = FakeSupervisor(ignore_cancellation=True)
        app = application(
            supervisor,
            FakeReconciliation(),
            stop_timeout_seconds=0.01,
        )
        await app.start()

        snapshot = await app.stop()

        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.FAILED,
        )
        self.assertIn("did not stop", snapshot.error)
        supervisor.release.set()
        await asyncio.sleep(0)

    async def test_snapshot_is_immutable_and_lifecycle_is_guarded(self) -> None:
        supervisor = FakeSupervisor()
        app = application(supervisor, FakeReconciliation())
        initial = app.snapshot
        self.assertEqual(initial.state, PrivateStreamApplicationState.NEW)

        with self.assertRaisesRegex(
            PrivateStreamApplicationStateError,
            "cannot start",
        ):
            await app.start()
            await app.start()

        stopped = await app.stop()
        self.assertEqual(stopped.state, PrivateStreamApplicationState.STOPPED)
        self.assertEqual((await app.stop()).state, stopped.state)
        with self.assertRaises((AttributeError, TypeError)):
            initial.error = "changed"  # type: ignore[misc]

    async def test_stop_before_start_is_safe(self) -> None:
        app = application(FakeSupervisor(), FakeReconciliation())

        snapshot = await app.stop()

        self.assertEqual(
            snapshot.state,
            PrivateStreamApplicationState.STOPPED,
        )

    def test_invalid_stop_timeout_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "start timeout"):
            application(
                FakeSupervisor(),
                FakeReconciliation(),
                start_timeout_seconds=0,
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            application(
                FakeSupervisor(),
                FakeReconciliation(),
                stop_timeout_seconds=0,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
