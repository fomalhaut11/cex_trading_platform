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
from cex_quant.market_data import (
    BestBidAsk,
    BookLevel,
    OrderBookDelta,
    PartialBookFrame,
)


def metadata() -> EventMetadata:
    return EventMetadata(
        event_id=EventId("event-1"),
        event_time_ns=UnixNanos(1),
        receive_time_ns=UnixNanos(2),
        source=EventSource(venue=VenueId("BINANCE"), channel="depth"),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.MILLISECOND,
    )


def instrument_id() -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=InstrumentKind.PERPETUAL,
        symbol="BTCUSDT",
    )


class MarketDataEventsTest(TestCase):
    def test_delta_allows_zero_quantity_deletion(self) -> None:
        delta = OrderBookDelta(
            metadata=metadata(),
            instrument_id=instrument_id(),
            bids=(
                BookLevel(
                    price=Price.from_str("67000"),
                    quantity=Quantity.from_str("0"),
                ),
            ),
            asks=(),
            first_sequence=10,
            last_sequence=12,
            previous_sequence=9,
        )

        self.assertEqual(delta.bids[0].quantity.raw, 0)

    def test_partial_frame_rejects_zero_quantity(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive quantity"):
            PartialBookFrame(
                metadata=metadata(),
                instrument_id=instrument_id(),
                bids=(
                    BookLevel(
                        price=Price.from_str("67000"),
                        quantity=Quantity.from_str("0"),
                    ),
                ),
                asks=(),
                sequence=10,
            )

    def test_rejects_invalid_delta_sequence_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "sequence range"):
            OrderBookDelta(
                metadata=metadata(),
                instrument_id=instrument_id(),
                bids=(),
                asks=(),
                first_sequence=12,
                last_sequence=10,
            )

    def test_best_bid_ask_requires_positive_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be positive"):
            BestBidAsk(
                metadata=metadata(),
                instrument_id=instrument_id(),
                bid=BookLevel(
                    price=Price.from_str("67000"),
                    quantity=Quantity.from_str("0"),
                ),
                ask=BookLevel(
                    price=Price.from_str("67001"),
                    quantity=Quantity.from_str("1"),
                ),
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
