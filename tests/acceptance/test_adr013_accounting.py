"""A016 offline acceptance for ADR-013 Accounting infrastructure."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_quant.accounting import (
    AccountCashFlowFact,
    AccountCashFlowType,
    AttributionCompleteness,
    AuthoritativeBalance,
    CashComponent,
    ConversionQuoteConvention,
    ConversionRateEvidence,
    ConversionTimeBasis,
    EconomicOwnerRef,
    EconomicOwnerTypeRef,
    ExecutionFillFact,
    FillSide,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceKind,
    LedgerAccountType,
    LedgerMappingPolicy,
    ObservedFinancialFact,
    PositionValueInput,
    ReconciliationState,
    SourceCompletenessProof,
    ValuationPolicyRef,
    ValuationRoundingMode,
    build_pnl_attribution,
    build_valuation_snapshot,
    reconcile_balance,
)
from cex_quant.accounting.allocation import AllocationBook, create_allocation
from cex_quant.accounting.journal import JsonLinesAccountingJournal
from cex_quant.accounting.ledger import (
    AccountingLedger,
    LedgerIngestDisposition,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
    FinancialFactId,
    FinancialObservationId,
    FinancialReconciliationId,
    Money,
    PositionId,
    Price,
    Quantity,
    Rate,
    TradeId,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import (
    ContractValueType,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.snapshots import DecisionSnapshotId

OWNER = EconomicOwnerRef(
    owner_type=EconomicOwnerTypeRef(name="application.position", version=1),
    owner_id="carry-position-1",
)
VALUATION_ID = DecisionSnapshotId("valuation-1")


def spot() -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("binance"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSDT",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USDT"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.00001"),
        status=InstrumentStatus.ACTIVE,
        specification=SpotSpecification(),
    )


def perpetual() -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("binance"),
            kind=InstrumentKind.PERPETUAL,
            symbol="BTCUSDT",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USDT"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.001"),
        status=InstrumentStatus.ACTIVE,
        specification=PerpetualSpecification(
            settlement_asset=AssetId("USDT"),
            margin_asset=AssetId("USDT"),
            contract_size=Quantity.from_str("1"),
            contract_size_asset=AssetId("BTC"),
            value_type=ContractValueType.LINEAR,
        ),
    )


def mapping_policy() -> LedgerMappingPolicy:
    return LedgerMappingPolicy(
        version=1,
        instruments=tuple(
            sorted((spot(), perpetual()), key=lambda item: str(item.instrument_id))
        ),
    )


def metadata(fact_id: str, effective_time_ns: int) -> FinancialFactMetadata:
    return FinancialFactMetadata(
        fact_id=FinancialFactId(fact_id),
        venue=VenueId("binance"),
        account_id=AccountId("account-1"),
        venue_reference=fact_id,
        effective_time_ns=UnixNanos(effective_time_ns),
        schema_version=1,
    )


def observe(
    fact,
    *,
    observation_id: str,
    source: FinancialSourceKind = FinancialSourceKind.PRIVATE_STREAM,
) -> ObservedFinancialFact:
    fingerprint_character = (
        "a"
        if source is FinancialSourceKind.PRIVATE_STREAM
        else "b"
    )
    return ObservedFinancialFact(
        fact=fact,
        observation=FinancialFactObservation(
            observation_id=FinancialObservationId(observation_id),
            fact_id=fact.metadata.fact_id,
            source_kind=source,
            observed_at_ns=UnixNanos(2_000),
            payload_fingerprint=fingerprint_character * 64,
        ),
    )


def valuation_policy() -> ValuationPolicyRef:
    return ValuationPolicyRef(
        name="reporting.usdt",
        version=1,
        reporting_asset=AssetId("USDT"),
        allowed_source_ids=("official-btc-usdt",),
        path_priority=((AssetId("BTC"), AssetId("USDT")),),
        maximum_age_ns=100,
        maximum_coherence_ns=10,
        maximum_hops=1,
        output_scale=2,
        rounding_mode=ValuationRoundingMode.HALF_EVEN,
        time_basis=ConversionTimeBasis.SNAPSHOT_TIME,
    )


class Adr013AcceptanceTests(unittest.TestCase):
    def test_spot_perp_funding_replay_reconcile_and_attribution(self) -> None:
        spot_fill = ExecutionFillFact(
            metadata=metadata("spot-fill-1", 1_000),
            instrument_id=spot().instrument_id,
            client_order_id=ClientOrderId("spot-client-1"),
            venue_order_id=VenueOrderId("spot-order-1"),
            venue_trade_id=TradeId("spot-trade-1"),
            side=FillSide.BUY,
            fill_quantity=Quantity.from_str("1"),
            fill_price=Price.from_str("50000"),
            quote_asset=AssetId("USDT"),
            quote_amount=Money.from_str("50000"),
            commission=(
                CashComponent(
                    asset=AssetId("USDT"),
                    signed_amount=Money.from_str("-50"),
                ),
            ),
        )
        perp_fill = ExecutionFillFact(
            metadata=metadata("perp-fill-1", 1_100),
            instrument_id=perpetual().instrument_id,
            client_order_id=ClientOrderId("perp-client-1"),
            venue_order_id=VenueOrderId("perp-order-1"),
            venue_trade_id=TradeId("perp-trade-1"),
            side=FillSide.SELL,
            fill_quantity=Quantity.from_str("1"),
            fill_price=Price.from_str("50100"),
            quote_asset=AssetId("USDT"),
            quote_amount=Money.from_str("50100"),
            commission=(
                CashComponent(
                    asset=AssetId("USDT"),
                    signed_amount=Money.from_str("-20"),
                ),
            ),
        )
        funding = AccountCashFlowFact(
            metadata=metadata("funding-1", 1_200),
            cash_flow_type=AccountCashFlowType.FUNDING,
            component=CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str("120"),
            ),
            instrument_id=perpetual().instrument_id,
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounting.jsonl"
            journal = JsonLinesAccountingJournal(path)
            ledger = AccountingLedger(
                journal,
                mapping_policy=mapping_policy(),
            )
            for index, fact in enumerate(
                (spot_fill, perp_fill, funding),
                start=1,
            ):
                result = ledger.ingest(
                    observe(fact, observation_id=f"observation-{index}"),
                    posted_at_ns=UnixNanos(3_000 + index),
                )
                self.assertEqual(
                    result.disposition,
                    LedgerIngestDisposition.POSTED,
                )
            historical = ledger.ingest(
                observe(
                    funding,
                    observation_id="funding-history-observation",
                    source=FinancialSourceKind.AUTHENTICATED_HISTORY,
                ),
                posted_at_ns=UnixNanos(3_100),
            )
            self.assertEqual(
                historical.disposition,
                LedgerIngestDisposition.EXISTING_FACT_NEW_OBSERVATION,
            )
            before_restart = ledger.view()
            journal.close()

            replay_journal = JsonLinesAccountingJournal(path)
            replayed = AccountingLedger(
                replay_journal,
                mapping_policy=mapping_policy(),
            )
            self.assertEqual(replayed.view(), before_restart)
            self.assertEqual(replayed.view().fact_count, 3)
            self.assertEqual(replayed.view().observation_count, 4)

            completeness = SourceCompletenessProof(
                reconciliation_id=FinancialReconciliationId(
                    "reconciliation-1"
                ),
                venue=VenueId("binance"),
                account_id=AccountId("account-1"),
                source_kind=FinancialSourceKind.AUTHENTICATED_HISTORY,
                window_start_ns=UnixNanos(900),
                window_end_ns=UnixNanos(2_000),
                fact_ids=tuple(
                    sorted(
                        (
                            spot_fill.metadata.fact_id,
                            perp_fill.metadata.fact_id,
                            funding.metadata.fact_id,
                        ),
                        key=str,
                    )
                ),
                start_cursor="start",
                end_cursor="end",
                exhausted=True,
            )
            proof = reconcile_balance(
                replayed.view(),
                reconciliation_id=completeness.reconciliation_id,
                opening=AuthoritativeBalance(
                    venue=VenueId("binance"),
                    account_id=AccountId("account-1"),
                    asset=AssetId("USDT"),
                    amount=Money.from_str("100000"),
                    as_of_ns=UnixNanos(900),
                    evidence_id="opening-balance",
                ),
                closing=AuthoritativeBalance(
                    venue=VenueId("binance"),
                    account_id=AccountId("account-1"),
                    asset=AssetId("USDT"),
                    amount=Money.from_str("50050"),
                    as_of_ns=UnixNanos(2_000),
                    evidence_id="closing-balance",
                ),
                source_completeness=completeness,
            )
            self.assertEqual(proof.state, ReconciliationState.MATCHED)

            book = AllocationBook(replayed.view())
            pnl_types = {
                LedgerAccountType.FUNDING_INCOME,
                LedgerAccountType.COMMISSION_EXPENSE,
            }
            for transaction in replayed.view().transactions:
                for posting in transaction.postings:
                    if posting.account.account_type in pnl_types:
                        book.append(
                            create_allocation(
                                transaction_id=transaction.transaction_id,
                                posting_id=posting.posting_id,
                                owner=OWNER,
                                signed_amount=posting.signed_amount,
                                asset=posting.asset,
                                policy_version=1,
                                evidence_ids=("carry-position-window",),
                            )
                        )

            conversion_path = (AssetId("BTC"), AssetId("USDT"))
            rate = ConversionRateEvidence(
                valuation_snapshot_id=VALUATION_ID,
                policy_version=1,
                source_asset=AssetId("BTC"),
                destination_asset=AssetId("USDT"),
                rate=Rate.from_str("60000"),
                quote_convention=(
                    ConversionQuoteConvention.DESTINATION_PER_SOURCE
                ),
                source_id="official-btc-usdt",
                source_as_of_ns=UnixNanos(1_490),
                observed_at_ns=UnixNanos(1_495),
                path=conversion_path,
                hop_index=0,
            )
            valuation = build_valuation_snapshot(
                valuation_snapshot_id=VALUATION_ID,
                as_of_ns=UnixNanos(1_500),
                positions=(
                    PositionValueInput(
                        position_id=PositionId("carry-position-1"),
                        owner=OWNER,
                        original_asset=AssetId("BTC"),
                        unrealized_value=Money.from_str("0.01"),
                    ),
                ),
                policy=valuation_policy(),
                evidence=(rate,),
            )
            attribution = build_pnl_attribution(
                owner=OWNER,
                interval_start_ns=UnixNanos(900),
                interval_end_ns=UnixNanos(2_000),
                ledger=replayed.view(),
                allocations=book,
                valuation_snapshot_id=VALUATION_ID,
                valuation_reference_ns=UnixNanos(1_500),
                valuation_policy=valuation_policy(),
                conversion_evidence=(rate,),
                ledger_complete=True,
                ownership_complete=True,
                unrealized_change=valuation.unrealized_pnl,
                valuation_snapshot_ids=(VALUATION_ID,),
            )
            self.assertEqual(
                attribution.realized_net_pnl,
                Money.from_str("50.00"),
            )
            self.assertEqual(
                attribution.total_marked_pnl,
                Money.from_str("650.00"),
            )
            self.assertEqual(
                attribution.completeness,
                AttributionCompleteness.COMPLETE,
            )
            replay_journal.close()


if __name__ == "__main__":
    unittest.main()
