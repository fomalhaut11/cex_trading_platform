"""Metadata shared by immutable domain events."""

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

from .identifiers import CorrelationId, EventId, VenueId
from .time import UnixNanos

SchemaVersion = NewType("SchemaVersion", int)


class TimePrecision(StrEnum):
    """Precision supplied by an upstream source before nanosecond conversion."""

    MILLISECOND = "millisecond"
    MICROSECOND = "microsecond"
    NANOSECOND = "nanosecond"


class EventTimeSource(StrEnum):
    """Origin of `event_time_ns`, independent of its storage unit."""

    VENUE = "venue"
    RECEIVE_CLOCK = "receive_clock"


@dataclass(frozen=True, slots=True, kw_only=True)
class EventSource:
    """Origin of a canonical event."""

    venue: VenueId
    channel: str
    connection_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EventMetadata:
    """Transport-neutral metadata composed into strongly typed events."""

    event_id: EventId
    event_time_ns: UnixNanos
    receive_time_ns: UnixNanos
    source: EventSource
    schema_version: SchemaVersion
    source_time_precision: TimePrecision
    event_time_source: EventTimeSource = EventTimeSource.VENUE
    sequence: int | None = None
    correlation_id: CorrelationId | None = None
    causation_id: EventId | None = None

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence must be non-negative")


__all__ = [
    "EventMetadata",
    "EventSource",
    "EventTimeSource",
    "SchemaVersion",
    "TimePrecision",
]
