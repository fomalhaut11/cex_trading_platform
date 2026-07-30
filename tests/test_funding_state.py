from unittest import TestCase

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    Rate,
    SchemaVersion,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    FundingRateState,
    FundingRateUpdate,
    InstrumentMismatchError,
    MarketStateStatus,
    UpdateDisposition,
)

PERPETUAL = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)


def update(
    sequence: int | None,
    *,
    event_time_ns: int = 1_000,
    rate: str = "0.0001",
    instrument_id: InstrumentId = PERPETUAL,
) -> FundingRateUpdate:
    return FundingRateUpdate(
        metadata=EventMetadata(
            event_id=EventId(f"funding-{event_time_ns}-{sequence}"),
            event_time_ns=UnixNanos(event_time_ns),
            receive_time_ns=UnixNanos(event_time_ns + 2),
            source=EventSource(
                venue=VenueId("BINANCE"),
                channel="markPrice",
            ),
            schema_version=SchemaVersion(1),
            source_time_precision=TimePrecision.NANOSECOND,
            sequence=sequence,
        ),
        instrument_id=instrument_id,
        funding_rate=Rate.from_str(rate),
        next_funding_time_ns=UnixNanos(event_time_ns + 100),
    )


class FundingRateStateTests(TestCase):
    def test_publishes_latest_immutable_snapshot_source_view(self) -> None:
        state = FundingRateState(instrument_id=PERPETUAL)

        result = state.apply(update(1))
        view = state.view()

        self.assertEqual(result.disposition, UpdateDisposition.INITIALIZED)
        self.assertEqual(state.status, MarketStateStatus.LIVE)
        assert view is not None
        self.assertEqual(view.instrument_id, PERPETUAL)
        self.assertEqual(view.funding_rate, Rate.from_str("0.0001"))
        self.assertEqual(view.event_id, EventId("funding-1000-1"))
        self.assertEqual(view.as_of_ns, UnixNanos(1_000))
        self.assertEqual(view.source_sequence, 1)

    def test_ignores_stale_sequence_without_replacing_last_good_view(self) -> None:
        state = FundingRateState(instrument_id=PERPETUAL)
        state.apply(update(2, rate="0.0002"))

        result = state.apply(update(1, event_time_ns=1_001, rate="0.9"))

        self.assertEqual(result.disposition, UpdateDisposition.IGNORED_STALE)
        assert state.view() is not None
        self.assertEqual(state.view().funding_rate, Rate.from_str("0.0002"))

    def test_time_orders_sources_without_sequence(self) -> None:
        state = FundingRateState(instrument_id=PERPETUAL)
        state.apply(update(None, event_time_ns=1_000))

        self.assertEqual(
            state.apply(update(None, event_time_ns=999)).disposition,
            UpdateDisposition.IGNORED_STALE,
        )
        self.assertEqual(
            state.apply(update(None, event_time_ns=1_001)).disposition,
            UpdateDisposition.APPLIED,
        )

    def test_rejects_wrong_instrument_product_and_invalid_funding_time(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "perpetual"):
            FundingRateState(
                instrument_id=InstrumentId(
                    venue=VenueId("BINANCE"),
                    kind=InstrumentKind.SPOT,
                    symbol="BTCUSDT",
                )
            )
        state = FundingRateState(instrument_id=PERPETUAL)
        with self.assertRaises(InstrumentMismatchError):
            state.apply(
                update(
                    1,
                    instrument_id=InstrumentId(
                        venue=VenueId("BINANCE"),
                        kind=InstrumentKind.PERPETUAL,
                        symbol="ETHUSDT",
                    ),
                )
            )
        invalid = update(1)
        invalid = FundingRateUpdate(
            metadata=invalid.metadata,
            instrument_id=invalid.instrument_id,
            funding_rate=invalid.funding_rate,
            next_funding_time_ns=UnixNanos(999),
        )
        with self.assertRaisesRegex(ValueError, "precedes"):
            state.apply(invalid)


if __name__ == "__main__":
    import unittest

    unittest.main()
