import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from threading import Thread

from cex_quant.accounting import (
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceKind,
    LedgerMappingPolicy,
    ObservedFinancialFact,
)
from cex_quant.accounting.journal import (
    AccountingJournalEntry,
    AccountingJournalIntegrityError,
    JsonLinesAccountingJournal,
)
from cex_quant.accounting.ledger import (
    AccountingIdentityConflictError,
    AccountingLedger,
    AccountingPersistenceError,
    AccountingWriterViolationError,
    LedgerIngestDisposition,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    FinancialObservationId,
    Money,
    UnixNanos,
    VenueId,
)


class MemoryAccountingJournal:
    def __init__(self) -> None:
        self.entries: list[AccountingJournalEntry] = []
        self.failure: BaseException | None = None

    def read(self):
        yield from self.entries

    def append(self, entry: AccountingJournalEntry) -> None:
        if self.failure is not None:
            raise self.failure
        self.entries.append(entry)


def observed(
    *,
    fact_id: str = "funding-1",
    observation_id: str = "observation-1",
    amount: str = "120",
    source: FinancialSourceKind = FinancialSourceKind.PRIVATE_STREAM,
) -> ObservedFinancialFact:
    fact = AccountCashFlowFact(
        metadata=FinancialFactMetadata(
            fact_id=FinancialFactId(fact_id),
            venue=VenueId("binance"),
            account_id=AccountId("account-1"),
            venue_reference=fact_id,
            effective_time_ns=UnixNanos(1_000),
            schema_version=1,
        ),
        cash_flow_type=AccountCashFlowType.FUNDING,
        component=CashComponent(
            asset=AssetId("USDT"),
            signed_amount=Money.from_str(amount),
        ),
    )
    observation = FinancialFactObservation(
        observation_id=FinancialObservationId(observation_id),
        fact_id=FinancialFactId(fact_id),
        source_kind=source,
        observed_at_ns=UnixNanos(2_000),
        payload_fingerprint=(
            "a" if source is FinancialSourceKind.PRIVATE_STREAM else "b"
        )
        * 64,
    )
    return ObservedFinancialFact(fact=fact, observation=observation)


def ledger(journal):
    return AccountingLedger(
        journal,
        mapping_policy=LedgerMappingPolicy(version=1, instruments=()),
    )


class AccountingJournalTests(unittest.TestCase):
    def test_durable_ingest_converges_observations_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounting.jsonl"
            first_journal = JsonLinesAccountingJournal(path)
            first = ledger(first_journal)

            posted = first.ingest(
                observed(),
                posted_at_ns=UnixNanos(3_000),
            )
            duplicate = first.ingest(
                observed(),
                posted_at_ns=UnixNanos(3_001),
            )
            history = first.ingest(
                observed(
                    observation_id="observation-history",
                    source=FinancialSourceKind.AUTHENTICATED_HISTORY,
                ),
                posted_at_ns=UnixNanos(3_002),
            )

            self.assertEqual(posted.disposition, LedgerIngestDisposition.POSTED)
            self.assertEqual(
                duplicate.disposition,
                LedgerIngestDisposition.DUPLICATE_OBSERVATION,
            )
            self.assertEqual(
                history.disposition,
                LedgerIngestDisposition.EXISTING_FACT_NEW_OBSERVATION,
            )
            self.assertEqual(first.view().fact_count, 1)
            self.assertEqual(first.view().observation_count, 2)
            self.assertEqual(first.view().ledger_sequence, 1)
            first_journal.close()

            second_journal = JsonLinesAccountingJournal(path)
            replayed = ledger(second_journal)
            self.assertEqual(replayed.view(), first.view())
            second_journal.close()

    def test_append_failure_does_not_publish_ledger_success(self) -> None:
        journal = MemoryAccountingJournal()
        journal.failure = OSError("disk unavailable")
        state = ledger(journal)

        with self.assertRaises(AccountingPersistenceError):
            state.ingest(observed(), posted_at_ns=UnixNanos(3_000))

        view = state.view()
        self.assertEqual(view.fact_count, 0)
        self.assertEqual(view.ledger_sequence, 0)
        self.assertFalse(view.healthy)

    def test_fact_and_observation_identity_conflicts_latch_failure(self) -> None:
        state = ledger(MemoryAccountingJournal())
        state.ingest(observed(), posted_at_ns=UnixNanos(3_000))

        with self.assertRaises(AccountingIdentityConflictError):
            state.ingest(
                observed(amount="121", observation_id="observation-2"),
                posted_at_ns=UnixNanos(3_001),
            )
        self.assertFalse(state.view().healthy)

        second = ledger(MemoryAccountingJournal())
        second.ingest(observed(), posted_at_ns=UnixNanos(3_000))
        changed_observation = replace(
            observed().observation,
            payload_fingerprint="c" * 64,
        )
        with self.assertRaises(AccountingIdentityConflictError):
            second.ingest(
                ObservedFinancialFact(
                    fact=observed().fact,
                    observation=changed_observation,
                ),
                posted_at_ns=UnixNanos(3_001),
            )

    def test_reversal_is_durable_exact_and_single_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounting.jsonl"
            journal = JsonLinesAccountingJournal(path)
            state = ledger(journal)
            original = state.ingest(
                observed(),
                posted_at_ns=UnixNanos(3_000),
            ).transactions[0]
            correction = observed(
                fact_id="correction-1",
                observation_id="correction-observation-1",
                amount="-120",
                source=FinancialSourceKind.AUTHENTICATED_HISTORY,
            )

            result = state.reverse(
                correction,
                transaction_id=original.transaction_id,
                posted_at_ns=UnixNanos(4_000),
            )

            self.assertEqual(
                result.disposition,
                LedgerIngestDisposition.REVERSED,
            )
            self.assertEqual(
                result.transactions[0].reverses_transaction_id,
                original.transaction_id,
            )
            self.assertTrue(
                all(item.balance.raw == 0 for item in state.view().balances)
            )
            with self.assertRaises(AccountingIdentityConflictError):
                state.reverse(
                    observed(
                        fact_id="correction-2",
                        observation_id="correction-observation-2",
                        amount="-120",
                    ),
                    transaction_id=original.transaction_id,
                    posted_at_ns=UnixNanos(4_001),
                )
            journal.close()

            replay_journal = JsonLinesAccountingJournal(path)
            replayed = ledger(replay_journal)
            self.assertEqual(replayed.view(), state.view())
            replay_journal.close()

    def test_corruption_and_truncation_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounting.jsonl"
            journal = JsonLinesAccountingJournal(path)
            ledger(journal).ingest(
                observed(),
                posted_at_ns=UnixNanos(3_000),
            )
            journal.close()
            path.write_bytes(
                path.read_bytes().replace(
                    b'"posted_at_ns":3000',
                    b'"posted_at_ns":3001',
                )
            )
            with self.assertRaises(AccountingJournalIntegrityError):
                JsonLinesAccountingJournal(path)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounting.jsonl"
            path.write_bytes(b'{"truncated":true}')
            with self.assertRaises(AccountingJournalIntegrityError):
                JsonLinesAccountingJournal(path)

    def test_single_writer_is_enforced(self) -> None:
        state = ledger(MemoryAccountingJournal())
        errors: list[BaseException] = []

        def mutate() -> None:
            try:
                state.ingest(observed(), posted_at_ns=UnixNanos(3_000))
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=mutate)
        thread.start()
        thread.join()
        self.assertIsInstance(errors[0], AccountingWriterViolationError)


if __name__ == "__main__":
    unittest.main()
