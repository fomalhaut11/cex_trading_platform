from pathlib import Path
from unittest import TestCase

from cex_quant.core import AssetId
from cex_quant.instruments import (
    ContractValueType,
    FutureSpecification,
    InstrumentKind,
    InstrumentStatus,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.market_data.adapters.binance import (
    BinanceExchangeInfoParser,
    BinanceProduct,
    InstrumentMappingError,
    InstrumentMappingErrorCode,
)

FIXTURES = Path(__file__).parent / "fixtures" / "binance"


class BinanceExchangeInfoTest(TestCase):
    def test_maps_spot_filters_not_precision_fields(self) -> None:
        (instrument,) = BinanceExchangeInfoParser(
            product=BinanceProduct.SPOT
        ).parse((FIXTURES / "spot_exchange_info.json").read_bytes())

        self.assertEqual(instrument.instrument_id.kind, InstrumentKind.SPOT)
        self.assertIsInstance(instrument.specification, SpotSpecification)
        self.assertEqual(instrument.status, InstrumentStatus.ACTIVE)
        self.assertEqual(str(instrument.price_increment), "0.01000000")
        self.assertEqual(str(instrument.quantity_increment), "0.00001000")
        self.assertEqual(str(instrument.min_notional), "5.00000000")

    def test_maps_usdm_as_linear_perpetual(self) -> None:
        (instrument,) = BinanceExchangeInfoParser(
            product=BinanceProduct.USD_M_FUTURES
        ).parse((FIXTURES / "usdm_exchange_info.json").read_bytes())

        self.assertEqual(instrument.instrument_id.kind, InstrumentKind.PERPETUAL)
        specification = instrument.specification
        self.assertIsInstance(specification, PerpetualSpecification)
        assert isinstance(specification, PerpetualSpecification)
        self.assertEqual(specification.value_type, ContractValueType.LINEAR)
        self.assertEqual(specification.contract_size_asset, AssetId("BTC"))
        self.assertEqual(specification.margin_asset, AssetId("USDT"))

    def test_maps_coinm_as_inverse_dated_future(self) -> None:
        (instrument,) = BinanceExchangeInfoParser(
            product=BinanceProduct.COIN_M_FUTURES
        ).parse((FIXTURES / "coinm_exchange_info.json").read_bytes())

        self.assertEqual(instrument.instrument_id.kind, InstrumentKind.FUTURE)
        specification = instrument.specification
        self.assertIsInstance(specification, FutureSpecification)
        assert isinstance(specification, FutureSpecification)
        self.assertEqual(specification.value_type, ContractValueType.INVERSE)
        self.assertEqual(str(specification.contract_size), "100")
        self.assertEqual(specification.contract_size_asset, AssetId("USD"))
        self.assertEqual(specification.margin_asset, AssetId("BTC"))
        self.assertEqual(
            specification.expiry_time_ns,
            1_790_294_400_000_000_000,
        )

    def test_missing_tick_filter_is_typed_error(self) -> None:
        payload = b"""
        {
          "symbols": [{
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [{
              "filterType": "LOT_SIZE",
              "minQty": "1",
              "stepSize": "1"
            }]
          }]
        }
        """

        with self.assertRaises(InstrumentMappingError) as raised:
            BinanceExchangeInfoParser(product=BinanceProduct.SPOT).parse(payload)

        self.assertEqual(
            raised.exception.code,
            InstrumentMappingErrorCode.MISSING_FILTER,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
