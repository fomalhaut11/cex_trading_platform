"""Checksummed durable journal for operator command audit and recovery."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, cast

from cex_quant.core import UnixNanos

from .operations import (
    OperatorAction,
    OperatorCommand,
    OperatorCommandRecord,
    OperatorControlSnapshot,
    OperatorMode,
)

FORMAT_NAME = "cex_quant.operator_commands"
FORMAT_VERSION = 1
DEFAULT_MAX_RECORD_BYTES = 4_096
DEFAULT_MAX_RECORDS = 10_000


class OperatorJournalError(RuntimeError):
    """Sanitized base error for operator audit persistence."""


class OperatorJournalIntegrityError(OperatorJournalError):
    """Raised for malformed, truncated or inconsistent journal bytes."""


class OperatorJournalIoError(OperatorJournalError):
    """Raised when the durable audit boundary cannot complete."""


class JsonLinesOperatorCommandJournal:
    """Append-only JSONL journal with checksum, sequence and fsync."""

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
        max_records: int = DEFAULT_MAX_RECORDS,
        sync_on_append: bool = True,
    ) -> None:
        if not isinstance(path, Path):
            raise ValueError("path must be a Path")
        if (
            not isinstance(max_record_bytes, int)
            or isinstance(max_record_bytes, bool)
            or max_record_bytes < 1
        ):
            raise ValueError("max_record_bytes must be a positive int")
        if (
            not isinstance(max_records, int)
            or isinstance(max_records, bool)
            or max_records < 1
        ):
            raise ValueError("max_records must be a positive int")
        if not isinstance(sync_on_append, bool):
            raise ValueError("sync_on_append must be a bool")
        if not path.parent.is_dir():
            raise ValueError("journal parent directory must already exist")
        self._path = path
        self._max_record_bytes = max_record_bytes
        self._max_records = max_records
        self._sync_on_append = sync_on_append
        count = sum(1 for _ in self._read_file())
        self._next_sequence = count + 1
        try:
            self._file: BinaryIO = path.open("ab")
        except OSError:
            raise OperatorJournalIoError(
                "operator journal could not be opened"
            ) from None

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[OperatorCommandRecord]:
        yield from self._read_file()

    def append(self, record: OperatorCommandRecord) -> None:
        if not isinstance(record, OperatorCommandRecord):
            raise ValueError("record must be an OperatorCommandRecord")
        if self._next_sequence > self._max_records:
            raise OperatorJournalIntegrityError(
                "operator journal record limit reached"
            )
        encoded = _encode_record(
            record,
            sequence=self._next_sequence,
        ) + b"\n"
        if len(encoded) > self._max_record_bytes:
            raise OperatorJournalIntegrityError(
                "operator journal record exceeds configured limit"
            )
        try:
            written = self._file.write(encoded)
            if written != len(encoded):
                raise OperatorJournalIoError(
                    "operator journal append was incomplete"
                )
            self._file.flush()
            if self._sync_on_append:
                os.fsync(self._file.fileno())
        except OperatorJournalError:
            raise
        except OSError:
            raise OperatorJournalIoError(
                "operator journal append failed"
            ) from None
        self._next_sequence += 1

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            self._file.close()
        except OSError:
            raise OperatorJournalIoError(
                "operator journal close failed"
            ) from None

    def __enter__(self) -> JsonLinesOperatorCommandJournal:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _read_file(self) -> Iterator[OperatorCommandRecord]:
        if not self._path.exists():
            return
        try:
            file = self._path.open("rb")
        except OSError:
            raise OperatorJournalIoError(
                "operator journal could not be read"
            ) from None
        with file:
            expected_sequence = 1
            while True:
                try:
                    raw = file.readline(self._max_record_bytes + 1)
                except OSError:
                    raise OperatorJournalIoError(
                        "operator journal read failed"
                    ) from None
                if not raw:
                    return
                if expected_sequence > self._max_records:
                    raise OperatorJournalIntegrityError(
                        "operator journal record limit exceeded"
                    )
                if len(raw) > self._max_record_bytes:
                    raise OperatorJournalIntegrityError(
                        "operator journal record exceeds configured limit"
                    )
                if not raw.endswith(b"\n"):
                    raise OperatorJournalIntegrityError(
                        "operator journal record is truncated"
                    )
                sequence, record = _decode_record(raw[:-1])
                if sequence != expected_sequence:
                    raise OperatorJournalIntegrityError(
                        "operator journal sequence is invalid"
                    )
                yield record
                expected_sequence += 1


def _encode_record(
    record: OperatorCommandRecord,
    *,
    sequence: int,
) -> bytes:
    command = record.command
    snapshot = record.snapshot
    body: dict[str, object] = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "sequence": sequence,
        "command": {
            "command_id": command.command_id,
            "action": command.action.value,
            "actor": command.actor,
            "reason": command.reason,
        },
        "snapshot": {
            "mode": snapshot.mode.value,
            "generation": snapshot.generation,
            "changed_at_ns": int(snapshot.changed_at_ns),
            "command_id": snapshot.command_id,
            "actor": snapshot.actor,
            "reason": snapshot.reason,
        },
    }
    checksum = hashlib.sha256(_canonical(body)).hexdigest()
    body["checksum"] = checksum
    return _canonical(body)


def _decode_record(raw: bytes) -> tuple[int, OperatorCommandRecord]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OperatorJournalIntegrityError(
            "operator journal record is not valid JSON"
        ) from None
    if not isinstance(value, dict):
        raise OperatorJournalIntegrityError(
            "operator journal record must be an object"
        )
    body = cast(dict[str, object], value)
    checksum = _required_string(body, "checksum")
    unsigned = dict(body)
    del unsigned["checksum"]
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != checksum:
        raise OperatorJournalIntegrityError(
            "operator journal checksum mismatch"
        )
    if (
        body.get("format") != FORMAT_NAME
        or body.get("version") != FORMAT_VERSION
    ):
        raise OperatorJournalIntegrityError(
            "operator journal format is unsupported"
        )
    sequence = _required_int(body, "sequence", positive=True)
    command_raw = _required_object(body, "command")
    snapshot_raw = _required_object(body, "snapshot")
    try:
        command = OperatorCommand(
            command_id=_required_string(command_raw, "command_id"),
            action=OperatorAction(
                _required_string(command_raw, "action")
            ),
            actor=_required_string(command_raw, "actor"),
            reason=_required_string(command_raw, "reason"),
        )
        snapshot = OperatorControlSnapshot(
            mode=OperatorMode(_required_string(snapshot_raw, "mode")),
            generation=_required_int(
                snapshot_raw,
                "generation",
                positive=True,
            ),
            changed_at_ns=UnixNanos(
                _required_int(
                    snapshot_raw,
                    "changed_at_ns",
                    positive=False,
                )
            ),
            command_id=_required_string(snapshot_raw, "command_id"),
            actor=_required_string(snapshot_raw, "actor"),
            reason=_required_string(snapshot_raw, "reason"),
        )
    except (TypeError, ValueError):
        raise OperatorJournalIntegrityError(
            "operator journal record fields are invalid"
        ) from None
    return sequence, OperatorCommandRecord(
        command=command,
        snapshot=snapshot,
    )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _required_object(
    value: dict[str, object],
    key: str,
) -> dict[str, object]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise OperatorJournalIntegrityError(
            "operator journal object field is invalid"
        )
    return cast(dict[str, object], result)


def _required_string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise OperatorJournalIntegrityError(
            "operator journal string field is invalid"
        )
    return result


def _required_int(
    value: dict[str, object],
    key: str,
    *,
    positive: bool,
) -> int:
    result = value.get(key)
    if (
        not isinstance(result, int)
        or isinstance(result, bool)
        or (positive and result < 1)
        or (not positive and result < 0)
    ):
        raise OperatorJournalIntegrityError(
            "operator journal integer field is invalid"
        )
    return result


__all__ = [
    "JsonLinesOperatorCommandJournal",
    "OperatorJournalError",
    "OperatorJournalIntegrityError",
    "OperatorJournalIoError",
]
