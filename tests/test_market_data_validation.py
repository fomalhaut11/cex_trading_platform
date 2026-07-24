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
    MarketDataValidator,
    PartialBookFrame,
    ValidationCode,
    ValidationSeverity,
    VenueOptionAnalyticsUpdate,
)


def metadata(
    *,
    venue: str = "BINANCE",
    event_time_ns: int = 1_000,
    version: int = 1,
) -> EventMetadata:
    return EventMetadata(
        event_id=EventId("event-1"),
        event_time_ns=UnixNanos(event_time_ns),
        receive_time_ns=UnixNanos(1_100),
        source=EventSource(venue=VenueId(venue), channel="depth"),
        schema_version=SchemaVersion(version),
        source_time_precision=TimePrecision.MILLISECOND,
    )


def instrument_id(*, kind: InstrumentKind = InstrumentKind.PERPETUAL) -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=kind,
        symbol="BTCUSDT",
    )


def level(price: str, quantity: str = "1") -> BookLevel:
    return BookLevel(
        price=Price.from_str(price),
        quantity=Quantity.from_str(quantity),
    )


class MarketDataValidationTest(TestCase):
    def setUp(self) -> None:
        self.validator = MarketDataValidator()

    def test_valid_top_of_book_has_no_issues(self) -> None:
        event = BestBidAsk(
            metadata=metadata(),
            instrument_id=instrument_id(),
            bid=level("67000"),
            ask=level("67001"),
        )

        result = self.validator.validate(event)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues, ())

    def test_locked_book_is_warning_but_remains_valid(self) -> None:
        event = BestBidAsk(
            metadata=metadata(),
            instrument_id=instrument_id(),
            bid=level("67000"),
            ask=level("67000"),
        )

        result = self.validator.validate(event)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues[0].code, ValidationCode.LOCKED_BOOK)
        self.assertEqual(result.issues[0].severity, ValidationSeverity.WARNING)

    def test_crossed_and_unsorted_book_is_invalid(self) -> None:
        event = PartialBookFrame(
            metadata=metadata(),
            instrument_id=instrument_id(),
            bids=(level("67000"), level("67002")),
            asks=(level("67001"), level("67003")),
            sequence=1,
        )

        result = self.validator.validate(event)

        self.assertFalse(result.is_valid)
        self.assertEqual(
            {issue.code for issue in result.issues},
            {ValidationCode.UNSORTED_BOOK},
        )

    def test_source_venue_and_future_time_are_checked(self) -> None:
        event = BestBidAsk(
            metadata=metadata(venue="OTHER", event_time_ns=3_000_000_000),
            instrument_id=instrument_id(),
            bid=level("67000"),
            ask=level("67001"),
        )

        result = self.validator.validate(event, now_ns=UnixNanos(1_000))

        self.assertFalse(result.is_valid)
        self.assertEqual(
            {issue.code for issue in result.issues},
            {
                ValidationCode.EVENT_FROM_FUTURE,
                ValidationCode.SOURCE_VENUE_MISMATCH,
            },
        )

    def test_non_finite_venue_analytics_is_invalid(self) -> None:
        event = VenueOptionAnalyticsUpdate(
            metadata=metadata(),
            instrument_id=instrument_id(kind=InstrumentKind.OPTION),
            implied_volatility=float("nan"),
        )

        result = self.validator.validate(event)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.issues[0].code, ValidationCode.NON_FINITE_ANALYTIC)


if __name__ == "__main__":
    import unittest

    unittest.main()
