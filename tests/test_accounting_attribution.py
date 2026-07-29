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
from cex_quant.accounting.allocation import AllocationBook, create_allocation
from cex_quant.accounting.attribution import (
    AttributionCompleteness,
    PnlComponentType,
    build_pnl_attribution,
)
from cex_quant.accounting.journal import AccountingJournalEntry
from cex_quant.accounting.ledger import AccountingLedger
from cex_quant.accounting.model import LedgerAccountType
from cex_quant.accounting.valuation import (
    ConversionTimeBasis,
    ValuationPolicyRef,
    ValuationRoundingMode,
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
from cex_quant.snapshots import DecisionSnapshotId


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[AccountingJournalEntry] = []

    def read(self):
        yield from self.entries

    def append(self, entry: AccountingJournalEntry) -> None:
        self.entries.append(entry)


OWNER = EconomicOwnerRef(
    owner_type=EconomicOwnerTypeRef(name="application.position", version=1),
    owner_id="carry-1",
)
VALUATION_ID = DecisionSnapshotId("valuation-1")


def attribution_policy() -> ValuationPolicyRef:
    return ValuationPolicyRef(
        name="reporting.usdt",
        version=1,
        reporting_asset=AssetId("USDT"),
        allowed_source_ids=(),
        path_priority=(),
        maximum_age_ns=100,
        maximum_coherence_ns=10,
        maximum_hops=2,
        output_scale=2,
        rounding_mode=ValuationRoundingMode.HALF_EVEN,
        time_basis=ConversionTimeBasis.SNAPSHOT_TIME,
    )


def accounting_state() -> AccountingLedger:
    state = AccountingLedger(
        MemoryJournal(),
        mapping_policy=LedgerMappingPolicy(version=1, instruments=()),
    )
    for index, (flow_type, amount) in enumerate(
        (
            (AccountCashFlowType.FUNDING, "120"),
            (AccountCashFlowType.COMMISSION, "-20"),
            (AccountCashFlowType.TRANSFER, "1000"),
        ),
        start=1,
    ):
        fact_id = FinancialFactId(f"fact-{index}")
        fact = AccountCashFlowFact(
            metadata=FinancialFactMetadata(
                fact_id=fact_id,
                venue=VenueId("binance"),
                account_id=AccountId("account-1"),
                venue_reference=str(fact_id),
                effective_time_ns=UnixNanos(1_000 + index),
                schema_version=1,
            ),
            cash_flow_type=flow_type,
            component=CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str(amount),
            ),
        )
        state.ingest(
            ObservedFinancialFact(
                fact=fact,
                observation=FinancialFactObservation(
                    observation_id=FinancialObservationId(
                        f"observation-{index}"
                    ),
                    fact_id=fact_id,
                    source_kind=FinancialSourceKind.PRIVATE_STREAM,
                    observed_at_ns=UnixNanos(2_000 + index),
                    payload_fingerprint=f"{index}" * 64,
                ),
            ),
            posted_at_ns=UnixNanos(3_000 + index),
        )
    return state


def allocated_book(state: AccountingLedger) -> AllocationBook:
    view = state.view()
    book = AllocationBook(view)
    for transaction in view.transactions:
        for posting in transaction.postings:
            if posting.account.account_type in (
                LedgerAccountType.FUNDING_INCOME,
                LedgerAccountType.COMMISSION_EXPENSE,
                LedgerAccountType.TRANSFER_CLEARING,
            ):
                book.append(
                    create_allocation(
                        transaction_id=transaction.transaction_id,
                        posting_id=posting.posting_id,
                        owner=OWNER,
                        signed_amount=posting.signed_amount,
                        asset=posting.asset,
                        policy_version=1,
                        evidence_ids=("owner-proof",),
                    )
                )
    return book


class AccountingAttributionTests(unittest.TestCase):
    def test_realized_and_marked_pnl_use_account_semantics(self) -> None:
        state = accounting_state()
        view = build_pnl_attribution(
            owner=OWNER,
            interval_start_ns=UnixNanos(1_000),
            interval_end_ns=UnixNanos(2_000),
            ledger=state.view(),
            allocations=allocated_book(state),
            valuation_snapshot_id=VALUATION_ID,
            valuation_reference_ns=UnixNanos(4_000),
            valuation_policy=attribution_policy(),
            conversion_evidence=(),
            ledger_complete=True,
            ownership_complete=True,
            unrealized_change=Money.from_str("5"),
            valuation_snapshot_ids=(VALUATION_ID,),
        )

        self.assertEqual(view.realized_net_pnl, Money.from_str("100.00"))
        self.assertEqual(view.total_marked_pnl, Money.from_str("105.00"))
        self.assertEqual(view.completeness, AttributionCompleteness.COMPLETE)
        self.assertEqual(
            tuple(item.component_type for item in view.components),
            (PnlComponentType.FUNDING, PnlComponentType.COMMISSION),
        )

    def test_incomplete_ownership_withholds_total_not_components(self) -> None:
        state = accounting_state()
        view = build_pnl_attribution(
            owner=OWNER,
            interval_start_ns=UnixNanos(1_000),
            interval_end_ns=UnixNanos(2_000),
            ledger=state.view(),
            allocations=allocated_book(state),
            valuation_snapshot_id=VALUATION_ID,
            valuation_reference_ns=UnixNanos(4_000),
            valuation_policy=attribution_policy(),
            conversion_evidence=(),
            ledger_complete=True,
            ownership_complete=False,
        )

        self.assertEqual(len(view.components), 2)
        self.assertIsNone(view.realized_net_pnl)
        self.assertEqual(
            view.completeness,
            AttributionCompleteness.INCOMPLETE,
        )


if __name__ == "__main__":
    unittest.main()
