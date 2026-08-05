from __future__ import annotations

import unittest
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from cex_quant.core import ClientOrderId, ExecutionStageId, OrderGroupId, UnixNanos
from cex_quant.oms import (
    ExecutionStageState,
    ExecutionStageView,
    GroupActionPreparedEntry,
    GroupStagePreparedEntry,
    JsonLinesOmsJournal,
    OmsJournalEntry,
    OrderGroupCapacityError,
    create_execution_stage_permit,
    decode_execution_stage,
    decode_execution_stage_permit,
    encode_execution_stage,
    encode_execution_stage_permit,
    validate_execution_stage_permit,
)
from cex_quant.runtime import OrderGroupPersistenceError, OrderGroupRuntime
from tests.group_test_support import (
    ManualClock,
    action_for,
    admission,
    execution_plan,
    permit_for,
    stage_for,
    stage_permit_for,
)


class MemoryOmsJournal:
    def __init__(self) -> None:
        self.entries: list[OmsJournalEntry] = []
        self.fail_next = False

    def read(self) -> Iterator[OmsJournalEntry]:
        yield from self.entries

    def append(self, entry: OmsJournalEntry) -> None:
        if self.fail_next:
            self.fail_next = False
            raise OSError("synthetic Stage journal failure")
        self.entries.append(entry)


class ExecutionStageContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ManualClock(value=1_200)
        self.groups = OrderGroupRuntime(now_ns=self.clock)
        created = self.groups.create_group(admission(), execution_plan())
        self.group = self.groups.activate_group(created.order_group_id)

    def test_wide_contract_and_permit_round_trip_without_enabling_host(self) -> None:
        stage = stage_for(
            self.group,
            leg_indices=(0, 1),
            now_ns=UnixNanos(1_210),
            dispatch_width=2,
        )
        permit = stage_permit_for(stage, issued_at_ns=UnixNanos(1_210))

        validate_execution_stage_permit(stage, permit)
        self.assertEqual(decode_execution_stage(encode_execution_stage(stage)), stage)
        self.assertEqual(
            decode_execution_stage_permit(encode_execution_stage_permit(permit)),
            permit,
        )
        self.assertEqual(len(stage.actions), 2)
        self.assertEqual(stage.dispatch_width, 2)

        corrupted = bytearray(encode_execution_stage(stage))
        corrupted[-2] = ord("0") if corrupted[-2] != ord("0") else ord("1")
        with self.assertRaises(ValueError):
            decode_execution_stage(bytes(corrupted))

    def test_stage_identity_rejects_changed_dispatch_content(self) -> None:
        stage = stage_for(
            self.group,
            leg_indices=(0, 1),
            now_ns=UnixNanos(1_210),
            dispatch_width=2,
        )
        with self.assertRaisesRegex(ValueError, "stage_id"):
            type(stage)(
                stage_id=stage.stage_id,
                group_id=stage.group_id,
                base_group_revision=stage.base_group_revision,
                execution_plan=stage.execution_plan,
                actions=stage.actions,
                dispatch_width=1,
                created_at_ns=stage.created_at_ns,
            )

    def test_stage_rejects_invalid_bounds_and_action_identity(self) -> None:
        stage = stage_for(self.group, now_ns=UnixNanos(1_210))
        cases = (
            ("base group revision", {"base_group_revision": 0}),
            ("action count", {"actions": ()}),
            ("dispatch width", {"dispatch_width": 0}),
            ("creation time", {"created_at_ns": UnixNanos(-1)}),
            ("identities", {"actions": (stage.actions[0], stage.actions[0])}),
            (
                "Stage identity",
                {
                    "actions": (
                        replace(
                            stage.actions[0],
                            expected_group_revision=(stage.base_group_revision + 1),
                        ),
                    )
                },
            ),
            (
                "cannot precede",
                {
                    "created_at_ns": UnixNanos(
                        int(stage.actions[0].created_at_ns) - 1
                    )
                },
            ),
            ("stage_id", {"stage_id": ExecutionStageId("0" * 64)}),
        )
        for message, changes in cases:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                replace(stage, **changes)

    def test_stage_permit_and_view_reject_mismatched_vectors(self) -> None:
        stage = stage_for(self.group, now_ns=UnixNanos(1_210))
        permit = stage_permit_for(stage, issued_at_ns=UnixNanos(1_210))
        with self.assertRaisesRegex(ValueError, "Action count"):
            replace(permit, action_permits=())
        with self.assertRaisesRegex(ValueError, "validity"):
            replace(permit, valid_until_ns=UnixNanos(1_200))
        with self.assertRaisesRegex(ValueError, "policy version"):
            replace(permit, risk_policy_version=0)
        with self.assertRaisesRegex(ValueError, "Action permit"):
            replace(permit, group_id=OrderGroupId("other-group"))
        with self.assertRaisesRegex(ValueError, "identity"):
            replace(permit, permit_id=type(permit.permit_id)("0" * 64))

        view = ExecutionStageView(
            stage=stage,
            permit_id=permit.permit_id,
            child_order_ids=(ClientOrderId("child"),),
            state=ExecutionStageState.PREPARED,
            last_transition_ns=stage.created_at_ns,
        )
        with self.assertRaisesRegex(ValueError, "width mismatch"):
            replace(view, child_order_ids=())
        with self.assertRaisesRegex(ValueError, "precede"):
            replace(view, last_transition_ns=UnixNanos(1_200))

        other_action = replace(
            stage.actions[0],
            action_id=type(stage.actions[0].action_id)("1" * 64),
        )
        other_permit = permit_for(
            other_action,
            issued_at_ns=permit.issued_at_ns,
            valid_until_ns=permit.valid_until_ns,
            permit_id="other-action-permit",
        )
        mismatched = create_execution_stage_permit(
            stage=stage,
            action_permits=(other_permit,),
            partial_execution_envelope_checksum=(
                permit.partial_execution_envelope_checksum
            ),
            risk_snapshot_id=permit.risk_snapshot_id,
            issued_at_ns=permit.issued_at_ns,
            valid_until_ns=permit.valid_until_ns,
            risk_policy_version=permit.risk_policy_version,
        )
        with self.assertRaisesRegex(ValueError, "vector"):
            validate_execution_stage_permit(stage, mismatched)

    def test_codec_rejects_empty_oversized_and_wrong_kind(self) -> None:
        stage = stage_for(self.group, now_ns=UnixNanos(1_210))
        for encoded in (b"", b"{" + b"x" * 262_144):
            with self.assertRaises(ValueError):
                decode_execution_stage(encoded)
        with self.assertRaisesRegex(ValueError, "kind mismatch"):
            decode_execution_stage_permit(encode_execution_stage(stage))
        with self.assertRaises(ValueError):
            decode_execution_stage(b"{}")


class ExecutionStageOmsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ManualClock(value=1_200)
        self.journal = MemoryOmsJournal()
        self.groups = OrderGroupRuntime(now_ns=self.clock, journal=self.journal)
        created = self.groups.create_group(admission(), execution_plan())
        self.group = self.groups.activate_group(created.order_group_id)

    def test_complete_stage_is_one_journal_mutation_and_replays(self) -> None:
        stage = stage_for(
            self.group,
            leg_indices=(0, 1),
            now_ns=self.clock(),
            dispatch_width=2,
        )
        permit = stage_permit_for(stage, issued_at_ns=self.clock())

        requests = self.groups.prepare_stage(stage=stage, permit=permit)

        self.assertEqual(len(requests), 2)
        stage_entries = tuple(
            item
            for item in self.journal.entries
            if isinstance(item, GroupStagePreparedEntry)
        )
        self.assertEqual(len(stage_entries), 1)
        self.assertEqual(stage_entries[0].requests, requests)
        view = self.groups.group(stage.group_id)
        self.assertEqual(view.revision, stage.base_group_revision + 1)
        self.assertEqual(len(view.actions), 2)
        self.assertEqual(view.stages[0].state, ExecutionStageState.PREPARED)

        recovered = OrderGroupRuntime(now_ns=self.clock, journal=self.journal)
        self.assertEqual(recovered.group(stage.group_id), view)

    def test_jsonl_stage_record_round_trip(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "oms-stage.jsonl"
            with JsonLinesOmsJournal(path) as journal:
                groups = OrderGroupRuntime(now_ns=self.clock, journal=journal)
                created = groups.create_group(admission(), execution_plan())
                group = groups.activate_group(created.order_group_id)
                stage = stage_for(group, now_ns=self.clock())
                groups.prepare_stage(
                    stage=stage,
                    permit=stage_permit_for(stage, issued_at_ns=self.clock()),
                )
                expected = groups.group(stage.group_id)
            with JsonLinesOmsJournal(path) as journal:
                recovered = OrderGroupRuntime(now_ns=self.clock, journal=journal)
                self.assertEqual(recovered.group(stage.group_id), expected)

    def test_failed_stage_append_installs_no_partial_state(self) -> None:
        stage = stage_for(self.group, now_ns=self.clock())
        permit = stage_permit_for(stage, issued_at_ns=self.clock())
        self.journal.fail_next = True

        with self.assertRaises(OrderGroupPersistenceError):
            self.groups.prepare_stage(stage=stage, permit=permit)

        view = self.groups.group(stage.group_id)
        self.assertEqual(view.revision, stage.base_group_revision)
        self.assertEqual(view.actions, ())
        self.assertEqual(view.stages, ())

    def test_current_state_host_rejects_overlapping_unresolved_stage(self) -> None:
        first = stage_for(self.group, now_ns=self.clock())
        self.groups.prepare_stage(
            stage=first,
            permit=stage_permit_for(first, issued_at_ns=self.clock()),
        )
        current = self.groups.group(first.group_id)
        second = stage_for(
            current,
            leg_indices=(1,),
            now_ns=self.clock(),
        )

        with self.assertRaisesRegex(OrderGroupCapacityError, "overlapping"):
            self.groups.prepare_stage(
                stage=second,
                permit=stage_permit_for(second, issued_at_ns=self.clock()),
            )

    def test_legacy_action_and_stage_records_replay_together(self) -> None:
        action = action_for(self.group, leg_index=0, now_ns=self.clock())
        self.groups.prepare_child_submit(
            action=action,
            permit=permit_for(action, issued_at_ns=self.clock()),
        )
        self.groups.mark_transmitting(action.group_id, action.action_id)
        self.groups.record_rejected(
            action.group_id,
            action.action_id,
            reason="synthetic terminal rejection",
        )
        current = self.groups.group(action.group_id)
        stage = stage_for(
            current,
            leg_indices=(1,),
            now_ns=self.clock(),
        )
        self.groups.prepare_stage(
            stage=stage,
            permit=stage_permit_for(stage, issued_at_ns=self.clock()),
        )

        self.assertTrue(
            any(
                isinstance(item, GroupActionPreparedEntry)
                for item in self.journal.entries
            )
        )
        recovered = OrderGroupRuntime(now_ns=self.clock, journal=self.journal)
        self.assertEqual(
            recovered.group(stage.group_id),
            self.groups.group(stage.group_id),
        )


if __name__ == "__main__":
    unittest.main()
