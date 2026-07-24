"""Bounded append-only JSON Lines storage adapter."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from cex_quant.market_data import MarketEvent

from .codec import decode_event, encode_event
from .contracts import AppendResult, RecorderError, RecorderErrorCode

DEFAULT_MAX_RECORD_BYTES = 1_048_576


class JsonLinesRecorder:
    """Synchronous append-only writer.

    Callers must keep blocking filesystem I/O outside latency-sensitive state
    transitions. ``sync_on_flush`` adds an fsync durability boundary to flush.
    """

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
        sync_on_flush: bool = False,
    ) -> None:
        if max_record_bytes <= 0:
            raise ValueError("max_record_bytes must be positive")
        if not path.parent.is_dir():
            raise ValueError("recorder parent directory must already exist")
        self._path = path
        self._max_record_bytes = max_record_bytes
        self._sync_on_flush = sync_on_flush
        try:
            self._file: BinaryIO = path.open("ab")
        except OSError as error:
            raise RecorderError(
                code=RecorderErrorCode.IO_FAILURE,
                reason=str(error),
                path=path,
            ) from error

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: MarketEvent) -> AppendResult:
        try:
            record = encode_event(event) + b"\n"
        except (AttributeError, TypeError, ValueError) as error:
            raise RecorderError(
                code=RecorderErrorCode.UNSUPPORTED_EVENT,
                reason=str(error),
                path=self._path,
            ) from error
        if len(record) > self._max_record_bytes:
            raise RecorderError(
                code=RecorderErrorCode.RECORD_TOO_LARGE,
                reason=(
                    f"encoded record has {len(record)} bytes; "
                    f"limit is {self._max_record_bytes}"
                ),
                path=self._path,
            )
        try:
            offset = self._file.tell()
            written = self._file.write(record)
        except OSError as error:
            raise RecorderError(
                code=RecorderErrorCode.IO_FAILURE,
                reason=str(error),
                path=self._path,
            ) from error
        if written != len(record):
            raise RecorderError(
                code=RecorderErrorCode.IO_FAILURE,
                reason=f"short append: wrote {written} of {len(record)} bytes",
                path=self._path,
            )
        return AppendResult(offset=offset, byte_length=written)

    def flush(self) -> None:
        try:
            self._file.flush()
            if self._sync_on_flush:
                os.fsync(self._file.fileno())
        except OSError as error:
            raise RecorderError(
                code=RecorderErrorCode.IO_FAILURE,
                reason=str(error),
                path=self._path,
            ) from error

    def close(self) -> None:
        if not self._file.closed:
            self.flush()
            self._file.close()

    def __enter__(self) -> JsonLinesRecorder:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class JsonLinesReader:
    """Strict sequential reader with a hard per-record memory bound."""

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    ) -> None:
        if max_record_bytes <= 0:
            raise ValueError("max_record_bytes must be positive")
        self._path = path
        self._max_record_bytes = max_record_bytes

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[MarketEvent]:
        try:
            file = self._path.open("rb")
        except OSError as error:
            raise RecorderError(
                code=RecorderErrorCode.IO_FAILURE,
                reason=str(error),
                path=self._path,
            ) from error
        with file:
            line_number = 0
            while True:
                try:
                    record = file.readline(self._max_record_bytes + 1)
                except OSError as error:
                    raise RecorderError(
                        code=RecorderErrorCode.IO_FAILURE,
                        reason=str(error),
                        path=self._path,
                        line_number=line_number + 1,
                    ) from error
                if not record:
                    return
                line_number += 1
                if len(record) > self._max_record_bytes:
                    raise RecorderError(
                        code=RecorderErrorCode.RECORD_TOO_LARGE,
                        reason=f"record exceeds {self._max_record_bytes} bytes",
                        path=self._path,
                        line_number=line_number,
                    )
                if not record.endswith(b"\n"):
                    raise RecorderError(
                        code=RecorderErrorCode.TRUNCATED_RECORD,
                        reason="record has no terminating newline",
                        path=self._path,
                        line_number=line_number,
                    )
                try:
                    yield decode_event(record[:-1])
                except ArithmeticError as error:
                    raise self._error(
                        RecorderErrorCode.CHECKSUM_MISMATCH, error, line_number
                    ) from error
                except LookupError as error:
                    raise self._error(
                        RecorderErrorCode.UNSUPPORTED_FORMAT, error, line_number
                    ) from error
                except TypeError as error:
                    raise self._error(
                        RecorderErrorCode.UNSUPPORTED_EVENT, error, line_number
                    ) from error
                except ValueError as error:
                    raise self._error(
                        RecorderErrorCode.MALFORMED_RECORD, error, line_number
                    ) from error

    def _error(
        self,
        code: RecorderErrorCode,
        error: Exception,
        line_number: int,
    ) -> RecorderError:
        return RecorderError(
            code=code,
            reason=str(error),
            path=self._path,
            line_number=line_number,
        )


__all__ = ["DEFAULT_MAX_RECORD_BYTES", "JsonLinesReader", "JsonLinesRecorder"]
