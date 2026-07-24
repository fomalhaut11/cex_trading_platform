"""Stable contracts and failures for append-only event recording."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from cex_quant.market_data import MarketEvent


class RecorderErrorCode(StrEnum):
    RECORD_TOO_LARGE = "record_too_large"
    MALFORMED_RECORD = "malformed_record"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNSUPPORTED_EVENT = "unsupported_event"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    TRUNCATED_RECORD = "truncated_record"
    IO_FAILURE = "io_failure"


class RecorderError(RuntimeError):
    """Typed storage-boundary failure; corrupt data is never skipped silently."""

    def __init__(
        self,
        *,
        code: RecorderErrorCode,
        reason: str,
        path: Path | None = None,
        line_number: int | None = None,
    ) -> None:
        self.code = code
        self.reason = reason
        self.path = path
        self.line_number = line_number
        location = ""
        if path is not None:
            location = f" in {path}"
        if line_number is not None:
            location = f"{location} at line {line_number}"
        super().__init__(f"{code.value}{location}: {reason}")


@dataclass(frozen=True, slots=True, kw_only=True)
class AppendResult:
    """Location and size of one successfully appended record."""

    offset: int
    byte_length: int

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if self.byte_length <= 0:
            raise ValueError("byte_length must be positive")


@runtime_checkable
class EventRecorder(Protocol):
    def append(self, event: MarketEvent) -> AppendResult:
        """Append one event or fail explicitly without reporting success."""
        ...

    def flush(self) -> None:
        """Flush userspace buffers; durability policy belongs to the adapter."""
        ...


@runtime_checkable
class EventReader(Protocol):
    def read(self) -> Iterable[MarketEvent]:
        """Read records in append order, failing on the first invalid record."""
        ...


@runtime_checkable
class ReplaySink(Protocol):
    def on_event(self, event: MarketEvent) -> None:
        """Consume one event synchronously in recorded order."""
        ...


__all__ = [
    "AppendResult",
    "EventReader",
    "EventRecorder",
    "RecorderError",
    "RecorderErrorCode",
    "ReplaySink",
]
