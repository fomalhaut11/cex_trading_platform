from unittest import TestCase

from cex_quant.core import EventSource, UnixNanos, VenueId
from cex_quant.market_data import (
    NormalizationError,
    NormalizationErrorCode,
    RawMarketMessage,
)


class MarketDataNormalizationTest(TestCase):
    def test_raw_message_preserves_boundary_bytes(self) -> None:
        message = RawMarketMessage(
            payload=b'{"e":"trade"}',
            source=EventSource(venue=VenueId("BINANCE"), channel="trade"),
            receive_time_ns=UnixNanos(42),
        )

        self.assertEqual(message.payload, b'{"e":"trade"}')

    def test_raw_message_rejects_empty_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            RawMarketMessage(
                payload=b"",
                source=EventSource(venue=VenueId("BINANCE"), channel="trade"),
                receive_time_ns=UnixNanos(42),
            )

    def test_normalization_error_exposes_stable_fields(self) -> None:
        error = NormalizationError(
            code=NormalizationErrorCode.MISSING_FIELD,
            source=EventSource(venue=VenueId("BINANCE"), channel="trade"),
            reason="required field is absent",
            field="price",
        )

        self.assertEqual(error.code, NormalizationErrorCode.MISSING_FIELD)
        self.assertEqual(error.field, "price")
        self.assertNotIn("payload", str(error))


if __name__ == "__main__":
    import unittest

    unittest.main()
