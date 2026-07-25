from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    JsonLinesOperatorCommandJournal,
    OperatorAction,
    OperatorCommandConflictError,
    OperatorCommandRecord,
    OperatorControlDurabilityError,
    OperatorController,
    OperatorJournalIntegrityError,
    OperatorMode,
)
from tests.test_runtime_operations import ManualClock, command


class FailingJournal:
    def read(self) -> Iterator[OperatorCommandRecord]:
        return iter(())

    def append(self, record: OperatorCommandRecord) -> None:
        del record
        raise OSError("sensitive-operational-detail")


class InvalidRecoveryJournal:
    def __init__(self, record: OperatorCommandRecord) -> None:
        self.record = record

    def read(self) -> Iterator[OperatorCommandRecord]:
        yield self.record
        yield self.record

    def append(self, record: OperatorCommandRecord) -> None:
        raise AssertionError(record)


class OperatorJournalTests(TestCase):
    def test_fsync_journal_restores_exact_mode_and_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            clock = ManualClock(1_000)
            with JsonLinesOperatorCommandJournal(path) as journal:
                controller = OperatorController(
                    clock=clock,
                    journal=journal,
                )
                active = controller.apply(
                    command("activate", OperatorAction.ACTIVATE)
                )
                clock.now = 2_000
                reduced = controller.apply(
                    command(
                        "reduce",
                        OperatorAction.ENABLE_REDUCE_ONLY,
                    )
                )

            with JsonLinesOperatorCommandJournal(path) as reopened:
                restored = OperatorController(
                    clock=ManualClock(9_000),
                    journal=reopened,
                    command_history_size=1,
                )
                self.assertEqual(restored.snapshot, reduced)
                self.assertEqual(restored.snapshot.generation, 2)
                self.assertEqual(
                    restored.snapshot.changed_at_ns,
                    clock.wall_time_ns(),
                )
                self.assertEqual(
                    restored.health().status,
                    HealthStatus.DEGRADED,
                )

                before = path.read_bytes()
                self.assertEqual(
                    restored.apply(
                        command("activate", OperatorAction.ACTIVATE)
                    ),
                    active,
                )
                self.assertEqual(path.read_bytes(), before)
                with self.assertRaises(OperatorCommandConflictError):
                    restored.apply(
                        command("activate", OperatorAction.HALT)
                    )

    def test_append_failure_latches_halted_before_state_change(self) -> None:
        controller = OperatorController(
            clock=ManualClock(),
            journal=FailingJournal(),
        )
        with self.assertRaises(OperatorControlDurabilityError) as caught:
            controller.apply(
                command("activate", OperatorAction.ACTIVATE)
            )

        self.assertNotIn(
            "sensitive-operational-detail",
            str(caught.exception),
        )
        self.assertEqual(controller.snapshot.mode, OperatorMode.HALTED)
        self.assertEqual(controller.snapshot.generation, 0)
        self.assertEqual(controller.health().status, HealthStatus.UNHEALTHY)
        self.assertEqual(
            controller.health().issues[0].code,
            "JOURNAL_FAILED",
        )

    def test_truncation_checksum_and_record_limit_fail_closed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "operator.jsonl"
            with JsonLinesOperatorCommandJournal(path) as journal:
                controller = OperatorController(
                    clock=ManualClock(),
                    journal=journal,
                )
                controller.apply(
                    command("activate", OperatorAction.ACTIVATE)
                )

            original = path.read_bytes()
            path.write_bytes(original[:-1])
            with self.assertRaises(OperatorJournalIntegrityError):
                JsonLinesOperatorCommandJournal(path)

            corrupted = bytearray(original)
            corrupted[20] ^= 1
            path.write_bytes(corrupted)
            with self.assertRaises(OperatorJournalIntegrityError):
                JsonLinesOperatorCommandJournal(path)

            path.write_bytes(b"")
            with JsonLinesOperatorCommandJournal(
                path,
                max_records=1,
            ) as limited:
                controller = OperatorController(
                    clock=ManualClock(),
                    journal=limited,
                )
                controller.apply(
                    command("activate", OperatorAction.ACTIVATE)
                )
                with self.assertRaises(OperatorControlDurabilityError):
                    controller.apply(
                        command("halt", OperatorAction.HALT)
                    )
                self.assertEqual(
                    controller.snapshot.mode,
                    OperatorMode.HALTED,
                )

    def test_inconsistent_recovery_is_rejected(self) -> None:
        record: OperatorCommandRecord
        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            with JsonLinesOperatorCommandJournal(path) as journal:
                controller = OperatorController(
                    clock=ManualClock(),
                    journal=journal,
                )
                controller.apply(
                    command("activate", OperatorAction.ACTIVATE)
                )
                record = next(journal.read())

        with self.assertRaises(OperatorControlDurabilityError):
            OperatorController(
                clock=ManualClock(),
                journal=InvalidRecoveryJournal(record),
            )

    def test_external_change_is_detected_before_idempotent_retry(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            with JsonLinesOperatorCommandJournal(path) as journal:
                controller = OperatorController(
                    clock=ManualClock(),
                    journal=journal,
                )
                activate = command("activate", OperatorAction.ACTIVATE)
                controller.apply(activate)
                path.write_bytes(b"")

                with self.assertRaises(OperatorControlDurabilityError):
                    controller.apply(activate)

                self.assertEqual(
                    controller.snapshot.mode,
                    OperatorMode.HALTED,
                )
                self.assertEqual(
                    controller.health().issues[0].code,
                    "JOURNAL_FAILED",
                )

    def test_constructor_contracts_are_strict(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (
                ("max_record_bytes", True),
                ("max_records", 0),
                ("sync_on_append", 1),
            ):
                values: dict[str, object] = {
                    "max_record_bytes": 4_096,
                    "max_records": 10,
                    "sync_on_append": True,
                }
                values[name] = value
                with self.subTest(name=name), self.assertRaises(ValueError):
                    JsonLinesOperatorCommandJournal(
                        root / f"{name}.jsonl",
                        **values,  # type: ignore[arg-type]
                    )


if __name__ == "__main__":
    import unittest

    unittest.main()
