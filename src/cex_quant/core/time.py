"""Canonical time types and conversion constants.

Unix nanoseconds are comparable across processes. Monotonic nanoseconds are
only valid for local durations and timeouts and must never be persisted as
event time.
"""

from typing import NewType

UnixNanos = NewType("UnixNanos", int)
MonotonicNanos = NewType("MonotonicNanos", int)
DurationNanos = NewType("DurationNanos", int)

NANOS_PER_MICROSECOND = 1_000
NANOS_PER_MILLISECOND = 1_000_000
NANOS_PER_SECOND = 1_000_000_000


def milliseconds_to_nanos(value: int) -> UnixNanos:
    """Convert Unix milliseconds without pretending the source was precise."""

    return UnixNanos(value * NANOS_PER_MILLISECOND)


def microseconds_to_nanos(value: int) -> UnixNanos:
    """Convert Unix microseconds to the canonical unit."""

    return UnixNanos(value * NANOS_PER_MICROSECOND)


__all__ = [
    "NANOS_PER_MICROSECOND",
    "NANOS_PER_MILLISECOND",
    "NANOS_PER_SECOND",
    "DurationNanos",
    "MonotonicNanos",
    "UnixNanos",
    "microseconds_to_nanos",
    "milliseconds_to_nanos",
]

