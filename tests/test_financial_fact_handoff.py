import unittest
from threading import Event

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
from cex_quant.accounting.journal import AccountingJournalEntry
from cex_quant.accounting.ledger import AccountingLedger
from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    FinancialObservationId,
    Money,
    UnixNanos,
    VenueId,
)
from cex_quant.observability import HealthStatus
from cex_quant.runtime.financial_fact_handoff import (
    FinancialFactHandoff,
    FinancialFactOverflowError,
    FinancialFactWorkerFailedError,
)


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[AccountingJournalEntry] = []

    def read(self):
        yield from self.entries

    def append(self, entry: AccountingJournalEntry) -> None:
        self.entries.append(entry)


def observed(index: int) -> ObservedFinancialFact:
    fact_id = FinancialFactId(f"funding-{index}")
    return ObservedFinancialFact(
        fact=AccountCashFlowFact(
            metadata=FinancialFactMetadata(
                fact_id=fact_id,
                venue=VenueId("binance"),
                account_id=AccountId("account-1"),
                venue_reference=str(fact_id),
                effective_time_ns=UnixNanos(1_000 + index),
                schema_version=1,
            ),
            cash_flow_type=AccountCashFlowType.FUNDING,
            component=CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str("1"),
            ),
        ),
        observation=FinancialFactObservation(
            observation_id=FinancialObservationId(f"observation-{index}"),
            fact_id=fact_id,
            source_kind=FinancialSourceKind.PRIVATE_STREAM,
            observed_at_ns=UnixNanos(2_000 + index),
            payload_fingerprint=f"{index}" * 64,
        ),
    )


class AccountingFactory:
    def __init__(self) -> None:
        self.journal = MemoryJournal()
        self.ledger: AccountingLedger | None = None

    def __call__(self) -> AccountingLedger:
        self.ledger = AccountingLedger(
            self.journal,
            mapping_policy=LedgerMappingPolicy(version=1, instruments=()),
        )
        return self.ledger


class BlockingSink:
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()

    def ingest(self, observed, *, posted_at_ns):
        self.entered.set()
        self.release.wait()
        raise RuntimeError("stop after overflow test")


class FailingSink:
    def ingest(self, observed, *, posted_at_ns):
        raise OSError("disk unavailable")


class FinancialFactHandoffTests(unittest.TestCase):
    def test_worker_owns_ledger_and_durable_drain_publishes_success(self) -> None:
        factory = AccountingFactory()
        clock_value = 3_000

        def clock() -> UnixNanos:
            nonlocal clock_value
            clock_value += 1
            return UnixNanos(clock_value)

        handoff = FinancialFactHandoff(
            factory,
            capacity=4,
            maximum_queue_age_ns=1_000_000_000,
            posting_clock=clock,
        )
        handoff.start()
        handoff.submit(observed(1))
        handoff.submit(observed(2))
        handoff.drain()

        self.assertEqual(handoff.snapshot().durably_processed, 2)
        self.assertIsNotNone(factory.ledger)
        assert factory.ledger is not None
        self.assertEqual(factory.ledger.view().fact_count, 2)
        handoff.stop()

    def test_overflow_is_explicit_and_marks_health_unhealthy(self) -> None:
        sink = BlockingSink()
        handoff = FinancialFactHandoff(
            lambda: sink,
            capacity=1,
            maximum_queue_age_ns=1_000_000_000,
            posting_clock=lambda: UnixNanos(3_000),
        )
        handoff.start()
        handoff.submit(observed(1))
        self.assertTrue(sink.entered.wait(timeout=1))
        handoff.submit(observed(2))

        with self.assertRaises(FinancialFactOverflowError):
            handoff.submit(observed(3))
        self.assertEqual(handoff.health().status, HealthStatus.UNHEALTHY)
        sink.release.set()
        with self.assertRaises(FinancialFactWorkerFailedError):
            handoff.drain()
        with self.assertRaises(FinancialFactWorkerFailedError):
            handoff.stop()

    def test_sink_failure_is_latched_and_never_reported_as_success(self) -> None:
        handoff = FinancialFactHandoff(
            FailingSink,
            capacity=2,
            maximum_queue_age_ns=1_000_000_000,
            posting_clock=lambda: UnixNanos(3_000),
        )
        handoff.start()
        handoff.submit(observed(1))

        with self.assertRaises(FinancialFactWorkerFailedError):
            handoff.drain()
        snapshot = handoff.snapshot()
        self.assertEqual(snapshot.durably_processed, 0)
        self.assertFalse(snapshot.healthy)
        self.assertEqual(handoff.health().status, HealthStatus.UNHEALTHY)
        with self.assertRaises(FinancialFactWorkerFailedError):
            handoff.stop()


if __name__ == "__main__":
    unittest.main()
