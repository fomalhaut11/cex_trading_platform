from unittest import TestCase

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    Price,
    Quantity,
    SchemaVersion,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import KlineUpdate


def kline(**overrides: object) -> KlineUpdate:
    values: dict[str, object] = {
        "metadata": EventMetadata(
            event_id=EventId("kline-1"),
            event_time_ns=UnixNanos(2_000),
            receive_time_ns=UnixNanos(2_100),
            source=EventSource(venue=VenueId("BINANCE"), channel="kline"),
            schema_version=SchemaVersion(1),
            source_time_precision=TimePrecision.MILLISECOND,
        ),
        "instrument_id": InstrumentId(
            venue=VenueId("BINANCE"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSDT",
        ),
        "interval": "1m",
        "start_time_ns": UnixNanos(1_000),
        "end_time_ns": UnixNanos(2_000),
        "open_price": Price.from_str("100"),
        "high_price": Price.from_str("110"),
        "low_price": Price.from_str("90"),
        "close_price": Price.from_str("105"),
        "volume": Quantity.from_str("12.5"),
        "trade_count": 10,
        "is_closed": True,
    }
    values.update(overrides)
    return KlineUpdate(**values)  # type: ignore[arg-type]


class KlineEventTest(TestCase):
    def test_constructs_valid_kline(self) -> None:
        event = kline()

        self.assertTrue(event.is_closed)
        self.assertEqual(event.interval, "1m")

    def test_rejects_inconsistent_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "highest OHLC"):
            kline(high_price=Price.from_str("102"))


if __name__ == "__main__":
    import unittest

    unittest.main()

