import unittest

from cex_quant.accounting import (
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    EconomicOwnerRef,
    EconomicOwnerTypeRef,
    ExecutionFillFact,
    FillSide,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceKind,
    ObservedFinancialFact,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
    FinancialFactId,
    FinancialObservationId,
    Money,
    Price,
    Quantity,
    TradeId,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind


def metadata() -> FinancialFactMetadata:
    return FinancialFactMetadata(
        fact_id=FinancialFactId("fact-1"),
        venue=VenueId("binance"),
        account_id=AccountId("account-1"),
        venue_reference="income-1",
        effective_time_ns=UnixNanos(1_000),
        schema_version=1,
    )


def observation() -> FinancialFactObservation:
    return FinancialFactObservation(
        observation_id=FinancialObservationId("observation-1"),
        fact_id=FinancialFactId("fact-1"),
        source_kind=FinancialSourceKind.AUTHENTICATED_HISTORY,
        observed_at_ns=UnixNanos(2_000),
        source_cursor="page:1",
        payload_fingerprint="a" * 64,
    )


class AccountingFactTests(unittest.TestCase):
    def test_funding_fact_keeps_economic_and_observation_time_separate(
        self,
    ) -> None:
        fact = AccountCashFlowFact(
            metadata=metadata(),
            cash_flow_type=AccountCashFlowType.FUNDING,
            component=CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str("120"),
            ),
        )
        observed = ObservedFinancialFact(fact=fact, observation=observation())

        self.assertEqual(observed.fact.metadata.effective_time_ns, 1_000)
        self.assertEqual(observed.observation.observed_at_ns, 2_000)
        self.assertEqual(observed.fact.component.signed_amount.as_decimal(), 120)

    def test_fill_contract_retains_trade_fee_and_settlement_evidence(self) -> None:
        fact = ExecutionFillFact(
            metadata=metadata(),
            instrument_id=InstrumentId(
                venue=VenueId("binance"),
                kind=InstrumentKind.PERPETUAL,
                symbol="BTCUSDT",
            ),
            client_order_id=ClientOrderId("client-1"),
            venue_order_id=VenueOrderId("venue-order-1"),
            venue_trade_id=TradeId("trade-1"),
            side=FillSide.SELL,
            fill_quantity=Quantity.from_str("10"),
            fill_price=Price.from_str("50000"),
            quote_asset=AssetId("USDT"),
            quote_amount=Money.from_str("500000"),
            commission=(
                CashComponent(
                    asset=AssetId("USDT"),
                    signed_amount=Money.from_str("-100"),
                ),
            ),
            realized_pnl=(
                CashComponent(
                    asset=AssetId("USDT"),
                    signed_amount=Money.from_str("20"),
                ),
            ),
        )

        self.assertEqual(fact.venue_trade_id, "trade-1")
        self.assertEqual(fact.commission[0].signed_amount.as_decimal(), -100)
        self.assertEqual(fact.realized_pnl[0].signed_amount.as_decimal(), 20)

    def test_fact_observation_identity_mismatch_is_rejected(self) -> None:
        fact = AccountCashFlowFact(
            metadata=metadata(),
            cash_flow_type=AccountCashFlowType.FUNDING,
            component=CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str("1"),
            ),
        )
        mismatch = FinancialFactObservation(
            observation_id=FinancialObservationId("observation-2"),
            fact_id=FinancialFactId("other"),
            source_kind=FinancialSourceKind.PRIVATE_STREAM,
            observed_at_ns=UnixNanos(2_000),
            payload_fingerprint="b" * 64,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            ObservedFinancialFact(fact=fact, observation=mismatch)

    def test_component_order_and_fingerprint_are_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            FinancialFactObservation(
                observation_id=FinancialObservationId("observation-1"),
                fact_id=FinancialFactId("fact-1"),
                source_kind=FinancialSourceKind.PRIVATE_STREAM,
                observed_at_ns=UnixNanos(1),
                payload_fingerprint="not-a-hash",
            )

        with self.assertRaisesRegex(ValueError, "unique and sorted"):
            ExecutionFillFact(
                metadata=metadata(),
                instrument_id=InstrumentId(
                    venue=VenueId("binance"),
                    kind=InstrumentKind.SPOT,
                    symbol="BTCUSDT",
                ),
                client_order_id=ClientOrderId("client-1"),
                venue_order_id=VenueOrderId("venue-order-1"),
                venue_trade_id=TradeId("trade-1"),
                side=FillSide.BUY,
                fill_quantity=Quantity.from_str("1"),
                fill_price=Price.from_str("1"),
                quote_asset=AssetId("USDT"),
                quote_amount=Money.from_str("1"),
                commission=(
                    CashComponent(
                        asset=AssetId("USDT"),
                        signed_amount=Money.from_str("-1"),
                    ),
                    CashComponent(
                        asset=AssetId("BNB"),
                        signed_amount=Money.from_str("-1"),
                    ),
                ),
            )

    def test_owner_reference_is_versioned_and_opaque(self) -> None:
        owner = EconomicOwnerRef(
            owner_type=EconomicOwnerTypeRef(
                name="application.position",
                version=1,
            ),
            owner_id="carry-position-1",
        )
        self.assertEqual(
            owner.canonical,
            "application.position@1:carry-position-1",
        )
        with self.assertRaisesRegex(ValueError, "name is invalid"):
            EconomicOwnerTypeRef(name="Funding Strategy", version=1)


if __name__ == "__main__":
    unittest.main()
