"""Checksummed append-only Carry application fact journal."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from .codec import (
    JsonObject,
    JsonValue,
    decode_carry_application_fact,
    encode_carry_application_fact,
)
from .facts import CarryApplicationFact

CARRY_JOURNAL_FORMAT = "cex_quant.carry_application_journal"
CARRY_JOURNAL_VERSION = 1
DEFAULT_MAX_CARRY_RECORD_BYTES = 262_144
DEFAULT_MAX_CARRY_RECORDS = 250_000


class CarryJournal(Protocol):
    def read(self) -> Iterator[CarryApplicationFact]: ...

    def append(self, fact: CarryApplicationFact) -> None: ...


class CarryJournalError(RuntimeError):
    pass


class CarryJournalIntegrityError(CarryJournalError):
    pass


class CarryJournalIoError(CarryJournalError):
    pass


class JsonLinesCarryJournal:
    """Bounded JSONL journal with sequence, checksum, flush and optional fsync."""

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_CARRY_RECORD_BYTES,
        max_records: int = DEFAULT_MAX_CARRY_RECORDS,
        sync_on_append: bool = True,
    ) -> None:
        if not isinstance(path, Path):
            raise ValueError("path must be a Path")
        if not path.parent.is_dir():
            raise ValueError("journal parent directory must already exist")
        if (
            not isinstance(max_record_bytes, int)
            or isinstance(max_record_bytes, bool)
            or max_record_bytes <= 0
        ):
            raise ValueError("max_record_bytes must be a positive int")
        if (
            not isinstance(max_records, int)
            or isinstance(max_records, bool)
            or max_records <= 0
        ):
            raise ValueError("max_records must be a positive int")
        self._path = path
        self._max_record_bytes = max_record_bytes
        self._max_records = max_records
        self._sync_on_append = sync_on_append
        count = sum(1 for _ in self._read_file())
        self._next_sequence = count + 1
        try:
            self._file: BinaryIO = path.open("ab")
        except OSError:
            raise CarryJournalIoError(
                "Carry journal could not be opened"
            ) from None

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[CarryApplicationFact]:
        yield from self._read_file()

    def append(self, fact: CarryApplicationFact) -> None:
        if not isinstance(fact, CarryApplicationFact):
            raise ValueError("fact must be a CarryApplicationFact")
        if self._next_sequence > self._max_records:
            raise CarryJournalIntegrityError(
                "Carry journal record limit reached"
            )
        body: JsonObject = {
            "format": CARRY_JOURNAL_FORMAT,
            "version": CARRY_JOURNAL_VERSION,
            "sequence": self._next_sequence,
            "fact": encode_carry_application_fact(fact),
        }
        body["checksum"] = hashlib.sha256(_canonical_json(body)).hexdigest()
        encoded = _canonical_json(body) + b"\n"
        if len(encoded) > self._max_record_bytes:
            raise CarryJournalIntegrityError(
                "Carry journal record exceeds configured limit"
            )
        try:
            written = self._file.write(encoded)
            if written != len(encoded):
                raise CarryJournalIoError("Carry journal append was incomplete")
            self._file.flush()
            if self._sync_on_append:
                os.fsync(self._file.fileno())
        except CarryJournalError:
            raise
        except OSError:
            raise CarryJournalIoError(
                "Carry journal append failed"
            ) from None
        self._next_sequence += 1

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            self._file.close()
        except OSError:
            raise CarryJournalIoError(
                "Carry journal close failed"
            ) from None

    def __enter__(self) -> JsonLinesCarryJournal:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _read_file(self) -> Iterator[CarryApplicationFact]:
        if not self._path.exists():
            return
        try:
            file = self._path.open("rb")
        except OSError:
            raise CarryJournalIoError(
                "Carry journal could not be read"
            ) from None
        with file:
            expected_sequence = 1
            while True:
                try:
                    raw = file.readline(self._max_record_bytes + 1)
                except OSError:
                    raise CarryJournalIoError(
                        "Carry journal read failed"
                    ) from None
                if not raw:
                    return
                if expected_sequence > self._max_records:
                    raise CarryJournalIntegrityError(
                        "Carry journal record limit exceeded"
                    )
                if len(raw) > self._max_record_bytes:
                    raise CarryJournalIntegrityError(
                        "Carry journal record exceeds configured limit"
                    )
                if not raw.endswith(b"\n"):
                    raise CarryJournalIntegrityError(
                        "Carry journal record is truncated"
                    )
                sequence, fact = _decode_record(raw[:-1])
                if sequence != expected_sequence:
                    raise CarryJournalIntegrityError(
                        "Carry journal sequence is invalid"
                    )
                yield fact
                expected_sequence += 1


def _decode_record(raw: bytes) -> tuple[int, CarryApplicationFact]:
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CarryJournalIntegrityError(
            "Carry journal record is not valid JSON"
        ) from None
    if not isinstance(decoded, dict):
        raise CarryJournalIntegrityError(
            "Carry journal record must be an object"
        )
    body = cast(JsonObject, decoded)
    checksum = body.get("checksum")
    if not isinstance(checksum, str):
        raise CarryJournalIntegrityError(
            "Carry journal checksum is missing"
        )
    unsigned = dict(body)
    del unsigned["checksum"]
    if hashlib.sha256(_canonical_json(unsigned)).hexdigest() != checksum:
        raise CarryJournalIntegrityError(
            "Carry journal checksum mismatch"
        )
    if (
        body.get("format") != CARRY_JOURNAL_FORMAT
        or body.get("version") != CARRY_JOURNAL_VERSION
    ):
        raise CarryJournalIntegrityError(
            "Carry journal format is unsupported"
        )
    sequence = _positive_integer(body.get("sequence"), "sequence")
    fact_raw = body.get("fact")
    if not isinstance(fact_raw, dict):
        raise CarryJournalIntegrityError(
            "Carry journal fact must be an object"
        )
    try:
        fact = decode_carry_application_fact(fact_raw)
    except ValueError:
        raise CarryJournalIntegrityError(
            "Carry journal fact is invalid"
        ) from None
    return sequence, fact


def _positive_integer(value: JsonValue | None, name: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise CarryJournalIntegrityError(
            f"Carry journal {name} must be a positive integer"
        )
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


__all__ = [
    "CARRY_JOURNAL_FORMAT",
    "CARRY_JOURNAL_VERSION",
    "DEFAULT_MAX_CARRY_RECORDS",
    "DEFAULT_MAX_CARRY_RECORD_BYTES",
    "CarryJournal",
    "CarryJournalError",
    "CarryJournalIntegrityError",
    "CarryJournalIoError",
    "JsonLinesCarryJournal",
]
