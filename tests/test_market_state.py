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
    InstrumentMismatchError,
    L1State,
    MarketStateStatus,
    OrderBookDelta,
    PartialBookFrame,
    PartialBookState,
    ReconstructedOrderBook,
    StateBufferOverflowError,
    UpdateDisposition,
)

INSTRUMENT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)
OTHER_INSTRUMENT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="ETHUSDT",
)


def metadata(
    event_number: int,
    *,
    event_time_ns: int | None = None,
    sequence: int | None = None,
) -> EventMetadata:
    timestamp = event_number if event_time_ns is None else event_time_ns
    return EventMetadata(
        event_id=EventId(f"event-{event_number}"),
        event_time_ns=UnixNanos(timestamp),
        receive_time_ns=UnixNanos(timestamp + 1),
        source=EventSource(venue=VenueId("BINANCE"), channel="depth"),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.NANOSECOND,
        sequence=sequence,
    )


def level(price: str, quantity: str) -> BookLevel:
    return BookLevel(
        price=Price.from_str(price),
        quantity=Quantity.from_str(quantity),
    )


def snapshot(
    sequence: int | None = 100,
    *,
    bids: tuple[BookLevel, ...] | None = None,
    asks: tuple[BookLevel, ...] | None = None,
) -> PartialBookFrame:
    return PartialBookFrame(
        metadata=metadata(100),
        instrument_id=INSTRUMENT,
        bids=(level("100.0", "2"), level("99", "3"))
        if bids is None
        else bids,
        asks=(level("101", "4"), level("102", "5"))
        if asks is None
        else asks,
        sequence=sequence,
    )


def delta(
    first: int,
    last: int,
    *,
    previous: int | None = None,
    bids: tuple[BookLevel, ...] = (),
    asks: tuple[BookLevel, ...] = (),
    instrument_id: InstrumentId = INSTRUMENT,
) -> OrderBookDelta:
    return OrderBookDelta(
        metadata=metadata(last),
        instrument_id=instrument_id,
        bids=bids,
        asks=asks,
        first_sequence=first,
        last_sequence=last,
        previous_sequence=previous,
    )


class L1StateTest(TestCase):
    def test_initializes_and_ignores_stale_sequence(self) -> None:
        state = L1State(instrument_id=INSTRUMENT)
        first = BestBidAsk(
            metadata=metadata(1, sequence=10),
            instrument_id=INSTRUMENT,
            bid=level("100", "1"),
            ask=level("101", "1"),
        )
        stale = BestBidAsk(
            metadata=metadata(2, sequence=10),
            instrument_id=INSTRUMENT,
            bid=level("90", "1"),
            ask=level("91", "1"),
        )

        self.assertEqual(
            state.apply(first).disposition,
            UpdateDisposition.INITIALIZED,
        )
        self.assertEqual(
            state.apply(stale).disposition,
            UpdateDisposition.IGNORED_STALE,
        )
        self.assertEqual(state.view().bid.price.as_decimal(), 100)

    def test_rejects_another_instrument(self) -> None:
        state = L1State(instrument_id=INSTRUMENT)
        event = BestBidAsk(
            metadata=metadata(1),
            instrument_id=OTHER_INSTRUMENT,
            bid=level("100", "1"),
            ask=level("101", "1"),
        )
        with self.assertRaises(InstrumentMismatchError):
            state.apply(event)


class PartialBookStateTest(TestCase):
    def test_replaces_frame_atomically_and_uses_time_without_sequence(
        self,
    ) -> None:
        state = PartialBookState(instrument_id=INSTRUMENT)
        first = snapshot(None)
        stale = PartialBookFrame(
            metadata=metadata(99),
            instrument_id=INSTRUMENT,
            bids=(level("98", "1"),),
            asks=(level("103", "1"),),
            sequence=None,
        )

        state.apply(first)
        result = state.apply(stale)

        self.assertEqual(result.disposition, UpdateDisposition.IGNORED_STALE)
        self.assertEqual(len(state.view().bids), 2)


class ReconstructedOrderBookTest(TestCase):
    def test_buffers_then_aligns_snapshot_and_applies_deletions(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        self.assertEqual(
            state.apply(
                delta(
                    101,
                    102,
                    previous=100,
                    bids=(
                        level("100.00", "0"),
                        level("98", "7"),
                    ),
                    asks=(level("101", "6"),),
                )
            ).disposition,
            UpdateDisposition.BUFFERED,
        )

        result = state.load_snapshot(snapshot())
        view = state.view()

        self.assertEqual(result.disposition, UpdateDisposition.INITIALIZED)
        self.assertEqual(view.sequence, 102)
        self.assertEqual(view.status, MarketStateStatus.LIVE)
        self.assertEqual(
            [item.price.as_decimal() for item in view.bids],
            [99, 98],
        )
        self.assertEqual(view.asks[0].quantity.as_decimal(), 6)

    def test_discards_buffered_deltas_covered_by_snapshot(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        state.apply(delta(90, 99, bids=(level("100", "9"),)))

        result = state.load_snapshot(snapshot())

        self.assertEqual(result.sequence, 100)
        self.assertEqual(state.view().bids[0].quantity.as_decimal(), 2)

    def test_detects_sequence_gap_without_mutating_last_good_book(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        state.load_snapshot(snapshot())
        before = state.view()

        result = state.apply(
            delta(102, 102, previous=101, bids=(level("100", "9"),))
        )

        self.assertEqual(result.disposition, UpdateDisposition.GAP_DETECTED)
        self.assertEqual(state.status, MarketStateStatus.GAP)
        self.assertEqual(state.view().sequence, before.sequence)
        self.assertEqual(
            state.view().bids[0].quantity,
            before.bids[0].quantity,
        )

    def test_detects_previous_sequence_mismatch(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        state.load_snapshot(snapshot())

        result = state.apply(delta(101, 101, previous=99))

        self.assertEqual(result.disposition, UpdateDisposition.GAP_DETECTED)
        self.assertIn("previous sequence", result.reason)

    def test_ignores_duplicate_delta(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        state.load_snapshot(snapshot())
        event = delta(101, 101, previous=100, bids=(level("100", "8"),))
        state.apply(event)

        result = state.apply(event)

        self.assertEqual(result.disposition, UpdateDisposition.IGNORED_STALE)
        self.assertEqual(state.sequence, 101)

    def test_crossed_delta_is_atomic_and_requires_resync(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        state.load_snapshot(snapshot())

        result = state.apply(
            delta(101, 101, previous=100, bids=(level("103", "1"),))
        )

        self.assertEqual(result.disposition, UpdateDisposition.REJECTED)
        self.assertEqual(state.status, MarketStateStatus.INVALID)
        self.assertEqual(state.view().bids[0].price.as_decimal(), 100)
        self.assertEqual(
            state.apply(delta(101, 101)).disposition,
            UpdateDisposition.REJECTED,
        )

        state.begin_resync()
        self.assertEqual(state.status, MarketStateStatus.EMPTY)
        self.assertIsNone(state.view())
        self.assertEqual(
            state.apply(delta(201, 201)).disposition,
            UpdateDisposition.BUFFERED,
        )

    def test_buffer_limit_is_enforced(self) -> None:
        state = ReconstructedOrderBook(
            instrument_id=INSTRUMENT,
            max_buffered_deltas=1,
        )
        state.apply(delta(101, 101))

        with self.assertRaises(StateBufferOverflowError):
            state.apply(delta(102, 102))

    def test_rejects_snapshot_without_sequence_or_with_crossed_levels(
        self,
    ) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        with self.assertRaisesRegex(ValueError, "requires a sequence"):
            state.load_snapshot(snapshot(None))

        result = state.load_snapshot(
            snapshot(
                bids=(level("102", "1"),),
                asks=(level("101", "1"),),
            )
        )
        self.assertEqual(result.disposition, UpdateDisposition.REJECTED)
        self.assertEqual(state.status, MarketStateStatus.INVALID)

    def test_view_depth_is_sorted_and_bounded(self) -> None:
        state = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        state.load_snapshot(snapshot())

        view = state.view(depth=1)

        self.assertEqual(len(view.bids), 1)
        self.assertEqual(len(view.asks), 1)
        self.assertEqual(view.bids[0].price.as_decimal(), 100)
        self.assertEqual(view.asks[0].price.as_decimal(), 101)


if __name__ == "__main__":
    import unittest

    unittest.main()
