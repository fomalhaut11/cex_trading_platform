import tempfile
from pathlib import Path
from threading import Thread
from unittest import TestCase

from carry_test_support import STRATEGY_ID, pair

from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.applications.carry.journal import (
    CarryJournalIntegrityError,
    JsonLinesCarryJournal,
)
from cex_quant.applications.carry.state import (
    CarryPersistenceError,
    CarryPositionBook,
    CarryRecoveryError,
    CarryStateError,
    CarryWriterViolationError,
)
from cex_quant.core import IntentId, OrderGroupId, Quantity, UnixNanos
from cex_quant.snapshots import DecisionSnapshotId


class MemoryCarryJournal:
    def __init__(self) -> None:
        self.facts = []
        self.failure: BaseException | None = None

    def read(self):
        yield from self.facts

    def append(self, fact) -> None:
        if self.failure is not None:
            raise self.failure
        self.facts.append(fact)


def ownership():
    configured_pair = pair()
    snapshot_id = DecisionSnapshotId("opening-snapshot")
    position_id = deterministic_application_position_id(
        strategy_id=STRATEGY_ID,
        pair_id=configured_pair.pair_id,
        opening_snapshot_id=snapshot_id,
    )
    return tuple(
        create_carry_leg_ownership(
            application_position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            baseline_quantity=Quantity.from_str("0"),
            intended_owned_delta=Quantity.from_str(delta),
            effective_from_ns=UnixNanos(1_000),
            source_snapshot_id=snapshot_id,
            policy_version=1,
        )
        for account_id, instrument_id, delta in (
            (
                configured_pair.spot_account_id,
                configured_pair.spot_instrument_id,
                "10",
            ),
            (
                configured_pair.perpetual_account_id,
                configured_pair.perpetual_instrument_id,
                "-10",
            ),
        )
    )


def create(book: CarryPositionBook):
    return book.create_position(
        strategy_id=STRATEGY_ID,
        pair_id=pair().pair_id,
        opening_snapshot_id=DecisionSnapshotId("opening-snapshot"),
        ownership=ownership(),
        occurred_at_ns=UnixNanos(1_000),
        policy_version=1,
    )


class CarryPositionBookTests(TestCase):
    def test_durable_lifecycle_links_and_replay_are_deterministic(self) -> None:
        journal = MemoryCarryJournal()
        first = CarryPositionBook(
            journal,
            now_ns=lambda: UnixNanos(2_000),
        )
        created = create(first)
        linked = first.link_intent(
            created.application_position_id,
            intent_id=IntentId("intent-open"),
            source_snapshot_id=DecisionSnapshotId("decision-open"),
            occurred_at_ns=UnixNanos(1_100),
            policy_version=1,
        )
        grouped = first.link_order_group(
            created.application_position_id,
            order_group_id=OrderGroupId("group-open"),
            source_snapshot_id=DecisionSnapshotId("decision-open"),
            occurred_at_ns=UnixNanos(1_200),
            policy_version=1,
        )
        opening = first.transition(
            created.application_position_id,
            lifecycle=CarryLifecycle.OPENING,
            hedge_state=CarryHedgeState.UNHEDGED,
            financial_state=CarryFinancialState.PROVISIONAL,
            source_snapshot_id=DecisionSnapshotId("monitor-1"),
            occurred_at_ns=UnixNanos(1_300),
            policy_version=1,
        )
        active = first.transition(
            created.application_position_id,
            lifecycle=CarryLifecycle.ACTIVE,
            hedge_state=CarryHedgeState.HEDGED,
            financial_state=CarryFinancialState.PROVISIONAL,
            source_snapshot_id=DecisionSnapshotId("monitor-2"),
            occurred_at_ns=UnixNanos(1_400),
            policy_version=1,
        )

        self.assertEqual(created.revision, 1)
        self.assertEqual(linked.intent_ids, (IntentId("intent-open"),))
        self.assertEqual(grouped.order_group_ids, (OrderGroupId("group-open"),))
        self.assertEqual(opening.lifecycle, CarryLifecycle.OPENING)
        self.assertEqual(active.lifecycle, CarryLifecycle.ACTIVE)
        replayed = CarryPositionBook(
            journal,
            now_ns=lambda: UnixNanos(2_001),
        )
        self.assertEqual(
            replayed.position(created.application_position_id),
            active,
        )

    def test_unknown_execution_requires_recovery_without_retry_fact(self) -> None:
        journal = MemoryCarryJournal()
        book = CarryPositionBook(journal, now_ns=lambda: UnixNanos(2_000))
        created = create(book)

        recovery = book.require_recovery(
            created.application_position_id,
            source_snapshot_id=DecisionSnapshotId("recovery-snapshot"),
            occurred_at_ns=UnixNanos(1_200),
            policy_version=1,
            reason="child submission outcome unknown",
        )

        self.assertEqual(
            recovery.lifecycle,
            CarryLifecycle.RECOVERY_REQUIRED,
        )
        self.assertEqual(recovery.hedge_state, CarryHedgeState.UNKNOWN)
        self.assertEqual(len(journal.facts), 2)
        self.assertFalse(hasattr(journal.facts[-1].payload, "order_request"))

    def test_invalid_transition_and_append_failure_fail_closed(self) -> None:
        journal = MemoryCarryJournal()
        book = CarryPositionBook(journal, now_ns=lambda: UnixNanos(2_000))
        created = create(book)
        with self.assertRaisesRegex(CarryStateError, "invalid"):
            book.transition(
                created.application_position_id,
                lifecycle=CarryLifecycle.CLOSED,
                hedge_state=CarryHedgeState.HEDGED,
                financial_state=CarryFinancialState.PROVISIONAL,
                source_snapshot_id=DecisionSnapshotId("close"),
                occurred_at_ns=UnixNanos(1_100),
                policy_version=1,
            )

        journal.failure = OSError("disk unavailable")
        with self.assertRaises(CarryPersistenceError):
            book.link_intent(
                created.application_position_id,
                intent_id=IntentId("intent-failed"),
                source_snapshot_id=DecisionSnapshotId("decision-failed"),
                occurred_at_ns=UnixNanos(1_200),
                policy_version=1,
            )
        self.assertEqual(book.position(created.application_position_id).revision, 1)
        with self.assertRaises(CarryPersistenceError):
            book.link_intent(
                created.application_position_id,
                intent_id=IntentId("intent-after-failure"),
                source_snapshot_id=DecisionSnapshotId("decision-after"),
                occurred_at_ns=UnixNanos(1_300),
                policy_version=1,
            )

    def test_json_journal_replay_corruption_and_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "carry.jsonl"
            journal = JsonLinesCarryJournal(path)
            book = CarryPositionBook(journal, now_ns=lambda: UnixNanos(2_000))
            created = create(book)
            journal.close()

            replay_journal = JsonLinesCarryJournal(path)
            replayed = CarryPositionBook(
                replay_journal,
                now_ns=lambda: UnixNanos(2_001),
            )
            self.assertEqual(
                replayed.position(created.application_position_id),
                created,
            )
            replay_journal.close()

            path.write_bytes(
                path.read_bytes().replace(
                    b'"policy_version":1',
                    b'"policy_version":2',
                    1,
                )
            )
            with self.assertRaises(CarryJournalIntegrityError):
                JsonLinesCarryJournal(path)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "carry.jsonl"
            path.write_bytes(b'{"truncated":true}')
            with self.assertRaises(CarryJournalIntegrityError):
                JsonLinesCarryJournal(path)

    def test_replay_revision_gap_and_non_owner_writer_are_rejected(self) -> None:
        journal = MemoryCarryJournal()
        book = CarryPositionBook(journal, now_ns=lambda: UnixNanos(2_000))
        created = create(book)
        book.link_intent(
            created.application_position_id,
            intent_id=IntentId("out-of-order-intent"),
            source_snapshot_id=DecisionSnapshotId("out-of-order-snapshot"),
            occurred_at_ns=UnixNanos(1_100),
            policy_version=1,
        )
        journal.facts = list(reversed(journal.facts))
        with self.assertRaises(CarryRecoveryError):
            CarryPositionBook(journal, now_ns=lambda: UnixNanos(2_001))

        errors: list[BaseException] = []

        def mutate() -> None:
            try:
                book.link_intent(
                    created.application_position_id,
                    intent_id=IntentId("thread-intent"),
                    source_snapshot_id=DecisionSnapshotId("thread-snapshot"),
                    occurred_at_ns=UnixNanos(1_200),
                    policy_version=1,
                )
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=mutate)
        thread.start()
        thread.join()
        self.assertIsInstance(errors[0], CarryWriterViolationError)


if __name__ == "__main__":
    import unittest

    unittest.main()
