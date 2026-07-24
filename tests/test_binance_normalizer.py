from pathlib import Path
from unittest import TestCase

from cex_quant.core import (
    EventSource,
    EventTimeSource,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    AggressorSide,
    BestBidAsk,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    NormalizationError,
    NormalizationErrorCode,
    OrderBookDelta,
    PartialBookFrame,
    RawMarketMessage,
)
from cex_quant.market_data.adapters.binance import (
    BinanceMarketDataNormalizer,
    BinanceProduct,
    StaticInstrumentResolver,
)

FIXTURES = Path(__file__).parent / "fixtures" / "binance"
BINANCE = VenueId("BINANCE")
SPOT_ID = InstrumentId(
    venue=BINANCE,
    kind=InstrumentKind.SPOT,
    symbol="BTCUSDT",
)
PERPETUAL_ID = InstrumentId(
    venue=BINANCE,
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)


def raw(name: str, channel: str) -> RawMarketMessage:
    return RawMarketMessage(
        payload=(FIXTURES / name).read_bytes(),
        source=EventSource(venue=BINANCE, channel=channel),
        receive_time_ns=UnixNanos(1_700_000_000_000_000_000),
    )


def normalizer(product: BinanceProduct) -> BinanceMarketDataNormalizer:
    return BinanceMarketDataNormalizer(
        product=product,
        instruments=StaticInstrumentResolver(
            {
                (BinanceProduct.SPOT, "BTCUSDT"): SPOT_ID,
                (BinanceProduct.USD_M_FUTURES, "BTCUSDT"): PERPETUAL_ID,
            }
        ),
    )


class BinanceNormalizerTest(TestCase):
    def test_normalizes_spot_trade_and_aggressor(self) -> None:
        (event,) = normalizer(BinanceProduct.SPOT).normalize(
            raw("spot_trade.json", "btcusdt@trade")
        )

        self.assertIsInstance(event, MarketTrade)
        assert isinstance(event, MarketTrade)
        self.assertEqual(event.instrument_id, SPOT_ID)
        self.assertEqual(event.aggressor_side, AggressorSide.SELL)
        self.assertEqual(event.metadata.event_time_ns, 1_672_515_782_136_000_000)
        self.assertEqual(event.metadata.event_time_source, EventTimeSource.VENUE)
        self.assertEqual(
            event.metadata.source_time_precision,
            TimePrecision.MILLISECOND,
        )

    def test_spot_book_ticker_uses_receive_clock_fallback(self) -> None:
        message = raw("spot_combined_book_ticker.json", "btcusdt@bookTicker")

        (event,) = normalizer(BinanceProduct.SPOT).normalize(message)

        self.assertIsInstance(event, BestBidAsk)
        assert isinstance(event, BestBidAsk)
        self.assertEqual(event.metadata.event_time_ns, message.receive_time_ns)
        self.assertEqual(
            event.metadata.event_time_source,
            EventTimeSource.RECEIVE_CLOCK,
        )
        self.assertEqual(event.metadata.sequence, 400900217)

    def test_partial_book_infers_symbol_and_sorts_canonical_sides(self) -> None:
        (event,) = normalizer(BinanceProduct.SPOT).normalize(
            raw("spot_combined_partial_depth.json", "combined")
        )

        self.assertIsInstance(event, PartialBookFrame)
        assert isinstance(event, PartialBookFrame)
        self.assertEqual(
            [str(level.price) for level in event.bids],
            ["16700.20", "16700.10"],
        )
        self.assertEqual(
            [str(level.price) for level in event.asks],
            ["16700.30", "16700.40"],
        )

    def test_usdm_depth_preserves_sequence_range_and_previous(self) -> None:
        (event,) = normalizer(BinanceProduct.USD_M_FUTURES).normalize(
            raw("usdm_diff_depth.json", "btcusdt@depth@100ms")
        )

        self.assertIsInstance(event, OrderBookDelta)
        assert isinstance(event, OrderBookDelta)
        self.assertEqual((event.first_sequence, event.last_sequence), (157, 160))
        self.assertEqual(event.previous_sequence, 149)
        self.assertEqual(event.bids[-1].quantity.raw, 0)

    def test_mark_price_payload_emits_three_distinct_facts(self) -> None:
        events = normalizer(BinanceProduct.USD_M_FUTURES).normalize(
            raw("usdm_mark_price.json", "btcusdt@markPrice")
        )

        self.assertEqual(len(events), 3)
        self.assertIsInstance(events[0], MarkPriceUpdate)
        self.assertIsInstance(events[1], IndexPriceUpdate)
        self.assertIsInstance(events[2], FundingRateUpdate)
        self.assertEqual(len({event.metadata.event_id for event in events}), 3)
        funding = events[2]
        assert isinstance(funding, FundingRateUpdate)
        self.assertEqual(str(funding.funding_rate), "0.00038167")
        self.assertEqual(
            funding.next_funding_time_ns,
            1_596_096_000_000_000_000,
        )

    def test_normalizes_spot_kline(self) -> None:
        (event,) = normalizer(BinanceProduct.SPOT).normalize(
            raw("spot_kline.json", "btcusdt@kline_1m")
        )

        self.assertIsInstance(event, KlineUpdate)
        assert isinstance(event, KlineUpdate)
        self.assertEqual(event.interval, "1m")
        self.assertFalse(event.is_closed)
        self.assertEqual(str(event.high_price), "16710.00")

    def test_unknown_symbol_is_typed_error(self) -> None:
        message = RawMarketMessage(
            payload=b'{"e":"trade","s":"UNKNOWN","t":1,"p":"1","q":"1","T":1,"m":false}',
            source=EventSource(venue=BINANCE, channel="unknown@trade"),
            receive_time_ns=UnixNanos(2_000_000),
        )

        with self.assertRaises(NormalizationError) as raised:
            normalizer(BinanceProduct.SPOT).normalize(message)

        self.assertEqual(
            raised.exception.code,
            NormalizationErrorCode.UNKNOWN_INSTRUMENT,
        )

    def test_malformed_json_is_typed_error(self) -> None:
        message = RawMarketMessage(
            payload=b"{not-json",
            source=EventSource(venue=BINANCE, channel="btcusdt@trade"),
            receive_time_ns=UnixNanos(2_000_000),
        )

        with self.assertRaises(NormalizationError) as raised:
            normalizer(BinanceProduct.SPOT).normalize(message)

        self.assertEqual(
            raised.exception.code,
            NormalizationErrorCode.MALFORMED_PAYLOAD,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
