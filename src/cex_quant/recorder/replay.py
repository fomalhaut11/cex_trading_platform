"""Deterministic synchronous replay orchestration."""

from dataclasses import dataclass
from itertools import islice

from .contracts import EventReader, ReplaySink


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplayResult:
    event_count: int

    def __post_init__(self) -> None:
        if self.event_count < 0:
            raise ValueError("event_count must be non-negative")


def replay(
    reader: EventReader,
    sink: ReplaySink,
    *,
    max_events: int | None = None,
) -> ReplayResult:
    """Replay in recorded order; sink or reader failures propagate immediately."""

    if max_events is not None and max_events < 0:
        raise ValueError("max_events must be non-negative")
    count = 0
    events = reader.read()
    selected = events if max_events is None else islice(events, max_events)
    for event in selected:
        sink.on_event(event)
        count += 1
    return ReplayResult(event_count=count)


__all__ = ["ReplayResult", "replay"]
