import json
import math
import unittest

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    EventTimeSource,
    Price,
    Quantity,
    Rate,
    SchemaVersion,
    TimePrecision,
    TradeId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    AggregateTrade,
    AggressorSide,
    BestBidAsk,
    BookLevel,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    OpenInterestUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)
from cex_quant.recorder import decode_event, encode_event


def metadata(*, event_id: str = "event-1") -> EventMetadata:
    return EventMetadata(
        event_id=EventId(event_id),
        event_time_ns=UnixNanos(1_700_000_000_123_456_789),
        receive_time_ns=UnixNanos(1_700_000_000_123_999_999),
        source=EventSource(
            venue=VenueId("BINANCE"),
            channel="depth@100ms",
            connection_id="connection-1",
        ),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.MICROSECOND,
        event_time_source=EventTimeSource.VENUE,
        sequence=42,
        correlation_id=None,
        causation_id=EventId("raw-1"),
    )


INSTRUMENT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)
BID = BookLevel(
    price=Price(raw=6_500_001, scale=2),
    quantity=Quantity(raw=125, scale=3),
)
ASK = BookLevel(
    price=Price(raw=6_500_002, scale=2),
    quantity=Quantity(raw=250, scale=3),
)


def canonical_events() -> tuple[object, ...]:
    common = {"metadata": metadata(), "instrument_id": INSTRUMENT}
    return (
        MarketTrade(
            **common,
            trade_id=TradeId("t-1"),
            price=BID.price,
            quantity=BID.quantity,
            aggressor_side=AggressorSide.BUY,
        ),
        AggregateTrade(
            **common,
            aggregate_trade_id=TradeId("a-1"),
            first_trade_id=TradeId("t-1"),
            last_trade_id=TradeId("t-3"),
            price=BID.price,
            quantity=BID.quantity,
            aggressor_side=None,
        ),
        BestBidAsk(**common, bid=BID, ask=ASK),
        OrderBookDelta(
            **common,
            bids=(BID,),
            asks=(ASK,),
            first_sequence=40,
            last_sequence=42,
            previous_sequence=39,
        ),
        PartialBookFrame(
            **common,
            bids=(BID,),
            asks=(ASK,),
            sequence=42,
        ),
        KlineUpdate(
            **common,
            interval="1m",
            start_time_ns=UnixNanos(1_700_000_000_000_000_000),
            end_time_ns=UnixNanos(1_700_000_059_999_999_999),
            open_price=Price(raw=65_000, scale=0),
            high_price=Price(raw=65_100, scale=0),
            low_price=Price(raw=64_900, scale=0),
            close_price=Price(raw=65_050, scale=0),
            volume=Quantity(raw=12345, scale=3),
            trade_count=27,
            is_closed=True,
        ),
        MarkPriceUpdate(**common, mark_price=BID.price),
        IndexPriceUpdate(**common, index_price=ASK.price),
        FundingRateUpdate(
            **common,
            funding_rate=Rate(raw=-125, scale=6),
            next_funding_time_ns=UnixNanos(1_700_028_800_000_000_000),
        ),
        OpenInterestUpdate(
            **common,
            open_interest=Quantity(raw=987654321, scale=3),
        ),
        VenueOptionAnalyticsUpdate(
            **common,
            implied_volatility=0.625,
            delta=-0.4,
            gamma=0.001,
            vega=12.5,
            theta=None,
        ),
    )


class RecorderCodecTests(unittest.TestCase):
    def test_all_canonical_market_events_round_trip_losslessly(self) -> None:
        for event in canonical_events():
            with self.subTest(event_type=type(event).__name__):
                encoded = encode_event(event)  # type: ignore[arg-type]
                self.assertEqual(decode_event(encoded), event)

    def test_encoding_is_deterministic_and_preserves_integer_nanoseconds(self) -> None:
        event = canonical_events()[0]
        first = encode_event(event)  # type: ignore[arg-type]
        second = encode_event(event)  # type: ignore[arg-type]
        self.assertEqual(first, second)
        raw = json.loads(first)
        self.assertEqual(
            raw["payload"]["metadata"]["event_time_ns"],
            1_700_000_000_123_456_789,
        )
        self.assertIsInstance(raw["payload"]["metadata"]["event_time_ns"], int)
        self.assertEqual(raw["payload"]["price"], {"raw": 6_500_001, "scale": 2})

    def test_non_finite_option_analytics_is_rejected_during_encoding(self) -> None:
        event = VenueOptionAnalyticsUpdate(
            metadata=metadata(),
            instrument_id=INSTRUMENT,
            implied_volatility=math.nan,
        )
        with self.assertRaises(ValueError):
            encode_event(event)

    def test_checksum_detects_payload_mutation(self) -> None:
        raw = json.loads(encode_event(canonical_events()[0]))  # type: ignore[arg-type]
        raw["payload"]["price"]["raw"] += 1
        mutated = json.dumps(raw, separators=(",", ":"), sort_keys=True).encode()
        with self.assertRaisesRegex(ArithmeticError, "checksum"):
            decode_event(mutated)


if __name__ == "__main__":
    unittest.main()
