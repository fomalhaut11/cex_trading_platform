from unittest import TestCase

from cex_quant.core import AssetId, Money, Price, Quantity, UnixNanos, VenueId
from cex_quant.instruments import (
    ContractValueType,
    ExerciseStyle,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    OptionSide,
    OptionSpecification,
    PerpetualSpecification,
    SettlementType,
    SpotSpecification,
)


class InstrumentTest(TestCase):
    def test_constructs_spot_instrument(self) -> None:
        instrument = Instrument(
            instrument_id=InstrumentId(
                venue=VenueId("BINANCE"),
                kind=InstrumentKind.SPOT,
                symbol="BTCUSDT",
            ),
            base_asset=AssetId("BTC"),
            quote_asset=AssetId("USDT"),
            price_increment=Price.from_str("0.01"),
            quantity_increment=Quantity.from_str("0.00001"),
            min_quantity=Quantity.from_str("0.00001"),
            min_notional=Money.from_str("5"),
            status=InstrumentStatus.ACTIVE,
            specification=SpotSpecification(),
        )

        self.assertEqual(str(instrument.instrument_id), "BINANCE:spot:BTCUSDT")

    def test_rejects_specification_kind_mismatch(self) -> None:
        perpetual_specification = PerpetualSpecification(
            settlement_asset=AssetId("USDT"),
            margin_asset=AssetId("USDT"),
            contract_size=Quantity.from_str("1"),
            contract_size_asset=AssetId("BTC"),
            value_type=ContractValueType.LINEAR,
        )
        with self.assertRaisesRegex(ValueError, "SpotSpecification"):
            Instrument(
                instrument_id=InstrumentId(
                    venue=VenueId("BINANCE"),
                    kind=InstrumentKind.SPOT,
                    symbol="BTCUSDT",
                ),
                base_asset=AssetId("BTC"),
                quote_asset=AssetId("USDT"),
                price_increment=Price.from_str("0.01"),
                quantity_increment=Quantity.from_str("0.001"),
                status=InstrumentStatus.ACTIVE,
                specification=perpetual_specification,
            )

    def test_constructs_option_with_explicit_underlying(self) -> None:
        underlying = InstrumentId(
            venue=VenueId("DERIBIT"),
            kind=InstrumentKind.PERPETUAL,
            symbol="BTC-PERPETUAL",
        )
        option = Instrument(
            instrument_id=InstrumentId(
                venue=VenueId("DERIBIT"),
                kind=InstrumentKind.OPTION,
                symbol="BTC-25SEP26-100000-C",
            ),
            base_asset=AssetId("BTC"),
            quote_asset=AssetId("USD"),
            price_increment=Price.from_str("0.0005"),
            quantity_increment=Quantity.from_str("0.1"),
            status=InstrumentStatus.ACTIVE,
            specification=OptionSpecification(
                underlying_id=underlying,
                settlement_asset=AssetId("BTC"),
                margin_asset=AssetId("BTC"),
                contract_size=Quantity.from_str("1"),
                contract_size_asset=AssetId("BTC"),
                strike=Price.from_str("100000"),
                option_side=OptionSide.CALL,
                exercise_style=ExerciseStyle.EUROPEAN,
                expiry_time_ns=UnixNanos(1_790_294_400_000_000_000),
                settlement_type=SettlementType.CASH,
            ),
        )

        self.assertIsInstance(option.specification, OptionSpecification)

    def test_rejects_non_positive_increment(self) -> None:
        with self.assertRaisesRegex(ValueError, "increments must be positive"):
            Instrument(
                instrument_id=InstrumentId(
                    venue=VenueId("BINANCE"),
                    kind=InstrumentKind.SPOT,
                    symbol="BTCUSDT",
                ),
                base_asset=AssetId("BTC"),
                quote_asset=AssetId("USDT"),
                price_increment=Price.from_str("0"),
                quantity_increment=Quantity.from_str("0.001"),
                status=InstrumentStatus.ACTIVE,
                specification=SpotSpecification(),
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
