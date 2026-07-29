import unittest

from cex_quant.accounting import (
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    EconomicOwnerRef,
    EconomicOwnerTypeRef,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceKind,
    LedgerMappingPolicy,
    ObservedFinancialFact,
)
from cex_quant.accounting.allocation import (
    UNALLOCATED_OWNER,
    AllocationBook,
    AllocationError,
    create_allocation,
)
from cex_quant.accounting.journal import AccountingJournalEntry
from cex_quant.accounting.ledger import AccountingLedger
from cex_quant.accounting.model import LedgerAccountType
from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    FinancialObservationId,
    Money,
    UnixNanos,
    VenueId,
)


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[AccountingJournalEntry] = []

    def read(self):
        yield from self.entries

    def append(self, entry: AccountingJournalEntry) -> None:
        self.entries.append(entry)


def ledger_view():
    state = AccountingLedger(
        MemoryJournal(),
        mapping_policy=LedgerMappingPolicy(version=1, instruments=()),
    )
    fact = AccountCashFlowFact(
        metadata=FinancialFactMetadata(
            fact_id=FinancialFactId("funding-1"),
            venue=VenueId("binance"),
            account_id=AccountId("account-1"),
            venue_reference="funding-1",
            effective_time_ns=UnixNanos(1_000),
            schema_version=1,
        ),
        cash_flow_type=AccountCashFlowType.FUNDING,
        component=CashComponent(
            asset=AssetId("USDT"),
            signed_amount=Money.from_str("120"),
        ),
    )
    state.ingest(
        ObservedFinancialFact(
            fact=fact,
            observation=FinancialFactObservation(
                observation_id=FinancialObservationId("observation-1"),
                fact_id=fact.metadata.fact_id,
                source_kind=FinancialSourceKind.PRIVATE_STREAM,
                observed_at_ns=UnixNanos(2_000),
                payload_fingerprint="a" * 64,
            ),
        ),
        posted_at_ns=UnixNanos(3_000),
    )
    return state.view()


OWNER = EconomicOwnerRef(
    owner_type=EconomicOwnerTypeRef(name="application.position", version=1),
    owner_id="carry-1",
)


class AccountingAllocationTests(unittest.TestCase):
    def test_allocation_preserves_posting_and_exposes_remainder(self) -> None:
        view = ledger_view()
        posting = next(
            item
            for item in view.transactions[0].postings
            if item.account.account_type is LedgerAccountType.FUNDING_INCOME
        )
        book = AllocationBook(view)
        first = create_allocation(
            transaction_id=view.transactions[0].transaction_id,
            posting_id=posting.posting_id,
            owner=OWNER,
            signed_amount=Money.from_str("-70"),
            asset=posting.asset,
            policy_version=1,
            evidence_ids=("position-window-1",),
        )

        self.assertTrue(book.append(first))
        self.assertFalse(book.append(first))
        self.assertEqual(book.unallocated(posting.posting_id), Money.from_str("-50"))
        self.assertEqual(posting.signed_amount, Money.from_str("-120"))

    def test_overallocation_and_fake_unallocated_owner_are_rejected(self) -> None:
        view = ledger_view()
        posting = view.transactions[0].postings[0]
        book = AllocationBook(view)

        with self.assertRaises(AllocationError):
            book.append(
                create_allocation(
                    transaction_id=view.transactions[0].transaction_id,
                    posting_id=posting.posting_id,
                    owner=OWNER,
                    signed_amount=Money.from_str("121"),
                    asset=posting.asset,
                    policy_version=1,
                    evidence_ids=("proof",),
                )
            )
        with self.assertRaises(AllocationError):
            book.append(
                create_allocation(
                    transaction_id=view.transactions[0].transaction_id,
                    posting_id=posting.posting_id,
                    owner=UNALLOCATED_OWNER,
                    signed_amount=Money.from_str("1"),
                    asset=posting.asset,
                    policy_version=1,
                    evidence_ids=("guess",),
                )
            )

    def test_reallocation_is_append_only_reversal_then_new_evidence(self) -> None:
        view = ledger_view()
        posting = view.transactions[0].postings[0]
        book = AllocationBook(view)
        original = create_allocation(
            transaction_id=view.transactions[0].transaction_id,
            posting_id=posting.posting_id,
            owner=OWNER,
            signed_amount=Money.from_str("120"),
            asset=posting.asset,
            policy_version=1,
            evidence_ids=("old-proof",),
        )
        book.append(original)
        reversal = create_allocation(
            transaction_id=original.transaction_id,
            posting_id=original.posting_id,
            owner=original.owner,
            signed_amount=Money.from_str("-120"),
            asset=original.asset,
            policy_version=2,
            evidence_ids=("correction",),
            reverses_allocation_id=original.allocation_id,
        )
        book.append(reversal)
        replacement = create_allocation(
            transaction_id=original.transaction_id,
            posting_id=original.posting_id,
            owner=OWNER,
            signed_amount=Money.from_str("80"),
            asset=original.asset,
            policy_version=2,
            evidence_ids=("new-proof",),
        )
        book.append(replacement)

        self.assertEqual(len(book.records), 3)
        self.assertEqual(book.unallocated(posting.posting_id), Money.from_str("40"))
        rebuilt = AllocationBook(view, records=book.records)
        self.assertEqual(rebuilt.records, book.records)


if __name__ == "__main__":
    unittest.main()
