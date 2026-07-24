"""Append-only canonical-event recording and deterministic replay.

The package owns persistence contracts and a synchronous JSON Lines adapter.
Runtime assembly must place blocking storage I/O behind a bounded handoff.
"""

from .codec import FORMAT_NAME, FORMAT_VERSION, decode_event, encode_event
from .contracts import (
    AppendResult,
    EventReader,
    EventRecorder,
    RecorderError,
    RecorderErrorCode,
    ReplaySink,
)
from .jsonl import DEFAULT_MAX_RECORD_BYTES, JsonLinesReader, JsonLinesRecorder
from .replay import ReplayResult, replay

__all__ = [
    "DEFAULT_MAX_RECORD_BYTES",
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "AppendResult",
    "EventReader",
    "EventRecorder",
    "JsonLinesReader",
    "JsonLinesRecorder",
    "RecorderError",
    "RecorderErrorCode",
    "ReplayResult",
    "ReplaySink",
    "decode_event",
    "encode_event",
    "replay",
]
