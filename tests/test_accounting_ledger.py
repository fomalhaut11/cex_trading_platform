import unittest
from dataclasses import replace

from cex_quant.accounting import (
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    ExecutionFillFact,
    FillSide,
    FinancialFactMetadata,
    FinancialMappingError,
    LedgerAccountType,
    LedgerMappingPolicy,
    LedgerTransactionType,
    map_financial_fact,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
    FinancialFactId,
    Money,
    Price,
    Quantity,
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


def policy() -> LedgerMappingPolicy:
    instruments = tuple(
        sorted(
            (spot(), perpetual()),
            key=lambda item: str(item.instrument_id),
        )
    )
    return LedgerMappingPolicy(version=1, instruments=instruments)


def metadata(fact_id: str = "fact-1") -> FinancialFactMetadata:
    return FinancialFactMetadata(
        fact_id=FinancialFactId(fact_id),
        venue=VenueId("binance"),
        account_id=AccountId("account-1"),
        venue_reference=fact_id,
        effective_time_ns=UnixNanos(1_000),
        schema_version=1,
    )


class AccountingLedgerMappingTests(unittest.TestCase):
    def test_funding_receipt_is_balanced_per_asset(self) -> None:
        draft = map_financial_fact(
            AccountCashFlowFact(
                metadata=metadata(),
                cash_flow_type=AccountCashFlowType.FUNDING,
                component=CashComponent(
                    asset=AssetId("USDT"),
                    signed_amount=Money.from_str("120"),
                ),
            ),
            policy(),
        )[0]

        self.assertEqual(draft.transaction_type, LedgerTransactionType.FUNDING)
        self.assertEqual(
            [item.account.account_type for item in draft.postings],
            [LedgerAccountType.VENUE_CASH, LedgerAccountType.FUNDING_INCOME],
        )
        self.assertEqual(
            sum(item.signed_amount.as_decimal() for item in draft.postings),
            0,
        )

    def test_spot_buy_balances_base_quote_and_third_asset_fee(self) -> None:
        draft = map_financial_fact(
            ExecutionFillFact(
                metadata=metadata(),
                instrument_id=spot().instrument_id,
                client_order_id=ClientOrderId("client-1"),
                venue_order_id=VenueOrderId("order-1"),
                venue_trade_id=TradeId("trade-1"),
                side=FillSide.BUY,
                fill_quantity=Quantity.from_str("1"),
                fill_price=Price.from_str("50000"),
                quote_asset=AssetId("USDT"),
                quote_amount=Money.from_str("50000"),
                commission=(
                    CashComponent(
                        asset=AssetId("BNB"),
                        signed_amount=Money.from_str("-0.01"),
                    ),
                ),
            ),
            policy(),
        )[0]

        self.assertEqual(draft.transaction_type, LedgerTransactionType.SPOT_FILL)
        totals: dict[str, object] = {}
        for asset in ("BTC", "USDT", "BNB"):
            totals[asset] = sum(
                item.signed_amount.as_decimal()
                for item in draft.postings
                if item.asset == asset
            )
        self.assertEqual(totals, {"BTC": 0, "USDT": 0, "BNB": 0})
        self.assertEqual(len(draft.postings), 6)

    def test_derivative_fill_maps_only_realized_and_fee_components(self) -> None:
        draft = map_financial_fact(
            ExecutionFillFact(
                metadata=metadata(),
                instrument_id=perpetual().instrument_id,
                client_order_id=ClientOrderId("client-1"),
                venue_order_id=VenueOrderId("order-1"),
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
                        signed_amount=Money.from_str("25"),
                    ),
                ),
            ),
            policy(),
        )[0]

        self.assertEqual(
            draft.transaction_type,
            LedgerTransactionType.DERIVATIVE_FILL,
        )
        self.assertEqual(len(draft.postings), 4)

    def test_mapping_identity_is_deterministic_and_policy_versioned(self) -> None:
        fact = AccountCashFlowFact(
            metadata=metadata(),
            cash_flow_type=AccountCashFlowType.BORROW_INTEREST,
            component=CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str("-3"),
            ),
        )
        first = map_financial_fact(fact, policy())[0]
        second = map_financial_fact(fact, policy())[0]
        changed = map_financial_fact(
            fact,
            replace(policy(), version=2),
        )[0]

        self.assertEqual(first, second)
        self.assertNotEqual(first.transaction_id, changed.transaction_id)

    def test_quote_asset_and_positive_commission_fail_closed(self) -> None:
        base = ExecutionFillFact(
            metadata=metadata(),
            instrument_id=spot().instrument_id,
            client_order_id=ClientOrderId("client-1"),
            venue_order_id=VenueOrderId("order-1"),
            venue_trade_id=TradeId("trade-1"),
            side=FillSide.BUY,
            fill_quantity=Quantity.from_str("1"),
            fill_price=Price.from_str("1"),
            quote_asset=AssetId("USDT"),
            quote_amount=Money.from_str("1"),
        )
        with self.assertRaisesRegex(FinancialMappingError, "quote asset"):
            map_financial_fact(
                replace(base, quote_asset=AssetId("USD")),
                policy(),
            )
        with self.assertRaisesRegex(FinancialMappingError, "negative"):
            map_financial_fact(
                replace(
                    base,
                    commission=(
                        CashComponent(
                            asset=AssetId("USDT"),
                            signed_amount=Money.from_str("1"),
                        ),
                    ),
                ),
                policy(),
            )


if __name__ == "__main__":
    unittest.main()
