from unittest import TestCase

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    SchemaVersion,
    TimePrecision,
    UnixNanos,
    VenueId,
)


class EventMetadataTest(TestCase):
    def test_constructs_transport_neutral_metadata(self) -> None:
        metadata = EventMetadata(
            event_id=EventId("event-1"),
            event_time_ns=UnixNanos(1_000_000),
            receive_time_ns=UnixNanos(1_000_100),
            source=EventSource(venue=VenueId("BINANCE"), channel="trade"),
            schema_version=SchemaVersion(1),
            source_time_precision=TimePrecision.MILLISECOND,
            sequence=42,
        )

        self.assertEqual(metadata.sequence, 42)
        self.assertEqual(metadata.source.venue, "BINANCE")

    def test_rejects_invalid_version_and_sequence(self) -> None:
        base = {
            "event_id": EventId("event-1"),
            "event_time_ns": UnixNanos(1),
            "receive_time_ns": UnixNanos(2),
            "source": EventSource(venue=VenueId("BINANCE"), channel="trade"),
            "source_time_precision": TimePrecision.MILLISECOND,
        }
        with self.assertRaisesRegex(ValueError, "schema_version"):
            EventMetadata(**base, schema_version=SchemaVersion(0))
        with self.assertRaisesRegex(ValueError, "sequence"):
            EventMetadata(
                **base,
                schema_version=SchemaVersion(1),
                sequence=-1,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
