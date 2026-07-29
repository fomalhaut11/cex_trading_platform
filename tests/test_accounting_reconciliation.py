import unittest

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
from cex_quant.accounting.reconciliation import (
    AuthoritativeBalance,
    ReconciliationState,
    SourceCompletenessProof,
    reconcile_balance,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    FinancialObservationId,
    FinancialReconciliationId,
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


def ledger_with_funding() -> AccountingLedger:
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
            effective_time_ns=UnixNanos(1_500),
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
                source_kind=FinancialSourceKind.AUTHENTICATED_HISTORY,
                observed_at_ns=UnixNanos(2_000),
                payload_fingerprint="a" * 64,
            ),
        ),
        posted_at_ns=UnixNanos(3_000),
    )
    return state


def completeness(*, exhausted: bool = True) -> SourceCompletenessProof:
    return SourceCompletenessProof(
        reconciliation_id=FinancialReconciliationId("reconciliation-1"),
        venue=VenueId("binance"),
        account_id=AccountId("account-1"),
        source_kind=FinancialSourceKind.AUTHENTICATED_HISTORY,
        window_start_ns=UnixNanos(1_000),
        window_end_ns=UnixNanos(2_000),
        fact_ids=(FinancialFactId("funding-1"),),
        start_cursor="start",
        end_cursor="end",
        exhausted=exhausted,
    )


def balance(value: str, as_of_ns: int, evidence_id: str) -> AuthoritativeBalance:
    return AuthoritativeBalance(
        venue=VenueId("binance"),
        account_id=AccountId("account-1"),
        asset=AssetId("USDT"),
        amount=Money.from_str(value),
        as_of_ns=UnixNanos(as_of_ns),
        evidence_id=evidence_id,
    )


class AccountingReconciliationTests(unittest.TestCase):
    def test_source_completeness_and_balance_proof_are_separate(self) -> None:
        proof = reconcile_balance(
            ledger_with_funding().view(),
            reconciliation_id=FinancialReconciliationId("reconciliation-1"),
            opening=balance("1000", 1_000, "opening"),
            closing=balance("1120", 2_000, "closing"),
            source_completeness=completeness(),
        )

        self.assertEqual(proof.source_completeness.state, ReconciliationState.MATCHED)
        self.assertEqual(proof.accepted_movement, Money.from_str("120"))
        self.assertEqual(proof.difference.raw, 0)
        self.assertEqual(proof.state, ReconciliationState.MATCHED)

    def test_matching_balance_does_not_imply_source_completeness(self) -> None:
        proof = reconcile_balance(
            ledger_with_funding().view(),
            reconciliation_id=FinancialReconciliationId("reconciliation-1"),
            opening=balance("1000", 1_000, "opening"),
            closing=balance("1120", 2_000, "closing"),
            source_completeness=completeness(exhausted=False),
        )

        self.assertEqual(proof.difference.raw, 0)
        self.assertEqual(proof.state, ReconciliationState.INCOMPLETE)

    def test_complete_source_with_wrong_balance_is_mismatch(self) -> None:
        proof = reconcile_balance(
            ledger_with_funding().view(),
            reconciliation_id=FinancialReconciliationId("reconciliation-1"),
            opening=balance("1000", 1_000, "opening"),
            closing=balance("1119", 2_000, "closing"),
            source_completeness=completeness(),
        )

        self.assertEqual(proof.difference, Money.from_str("-1"))
        self.assertEqual(proof.state, ReconciliationState.MISMATCH)


if __name__ == "__main__":
    unittest.main()
