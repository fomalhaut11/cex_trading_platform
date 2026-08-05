"""Checksummed append-only journal for ADR-012 authorization state."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Protocol, TypeAlias, cast

from cex_quant.core import UnixNanos

RISK_JOURNAL_FORMAT = "cex_quant.portfolio_risk_journal"
RISK_JOURNAL_VERSION = 1
DEFAULT_MAX_RISK_RECORD_BYTES = 262_144
DEFAULT_MAX_RISK_RECORDS = 100_000

RiskScalar: TypeAlias = bool | int | str | None
RiskPayload: TypeAlias = dict[str, RiskScalar]


class PortfolioRiskJournalEntryKind(StrEnum):
    APPROVAL_RESERVED = "approval_reserved"
    RESERVATION_CHANGED = "reservation_changed"
    PERMIT_ISSUED = "permit_issued"
    PERMIT_CONSUMED = "permit_consumed"
    STAGE_PERMIT_ISSUED = "stage_permit_issued"
    STAGE_PERMIT_CONSUMED = "stage_permit_consumed"
    AUTHORIZATION_GENERATION_CHANGED = "authorization_generation_changed"
    DIRECTIVE_ISSUED = "directive_issued"
    RECOVERY_AUTHORIZED = "recovery_authorized"
    TARGET_CONFIRMED = "target_confirmed"


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskJournalEntry:
    kind: PortfolioRiskJournalEntryKind
    at_ns: UnixNanos
    payload: RiskPayload

    def __post_init__(self) -> None:
        if self.at_ns < 0:
            raise ValueError("Risk journal time cannot be negative")
        if not self.payload:
            raise ValueError("Risk journal payload cannot be empty")
        for key, value in self.payload.items():
            if not key or key != key.strip() or len(key) > 128:
                raise ValueError("Risk journal payload key is invalid")
            if isinstance(value, str) and len(value) > 196_608:
                raise ValueError("Risk journal string value exceeds hard bound")


class PortfolioRiskJournal(Protocol):
    def read(self) -> Iterator[PortfolioRiskJournalEntry]:
        """Yield durable entries in accepted order."""

    def append(self, entry: PortfolioRiskJournalEntry) -> None:
        """Durably append one entry or raise."""


class PortfolioRiskJournalError(RuntimeError):
    pass


class PortfolioRiskJournalIntegrityError(PortfolioRiskJournalError):
    pass


class PortfolioRiskJournalIoError(PortfolioRiskJournalError):
    pass


class JsonLinesPortfolioRiskJournal:
    """Bounded JSONL journal with sequence, checksum, flush and optional fsync."""

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_RISK_RECORD_BYTES,
        max_records: int = DEFAULT_MAX_RISK_RECORDS,
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
        if not isinstance(sync_on_append, bool):
            raise ValueError("sync_on_append must be a bool")
        self._path = path
        self._max_record_bytes = max_record_bytes
        self._max_records = max_records
        self._sync_on_append = sync_on_append
        count = sum(1 for _ in self._read_file())
        self._next_sequence = count + 1
        try:
            self._file: BinaryIO = path.open("ab")
        except OSError:
            raise PortfolioRiskJournalIoError(
                "Portfolio Risk journal could not be opened"
            ) from None

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[PortfolioRiskJournalEntry]:
        yield from self._read_file()

    def append(self, entry: PortfolioRiskJournalEntry) -> None:
        if not isinstance(entry, PortfolioRiskJournalEntry):
            raise ValueError("entry must be a PortfolioRiskJournalEntry")
        if self._next_sequence > self._max_records:
            raise PortfolioRiskJournalIntegrityError(
                "Portfolio Risk journal record limit reached"
            )
        body: dict[str, object] = {
            "format": RISK_JOURNAL_FORMAT,
            "version": RISK_JOURNAL_VERSION,
            "sequence": self._next_sequence,
            "kind": entry.kind.value,
            "at_ns": int(entry.at_ns),
            "payload": entry.payload,
        }
        body["checksum"] = hashlib.sha256(_canonical(body)).hexdigest()
        encoded = _canonical(body) + b"\n"
        if len(encoded) > self._max_record_bytes:
            raise PortfolioRiskJournalIntegrityError(
                "Portfolio Risk journal record exceeds configured limit"
            )
        try:
            written = self._file.write(encoded)
            if written != len(encoded):
                raise PortfolioRiskJournalIoError(
                    "Portfolio Risk journal append was incomplete"
                )
            self._file.flush()
            if self._sync_on_append:
                os.fsync(self._file.fileno())
        except PortfolioRiskJournalError:
            raise
        except OSError:
            raise PortfolioRiskJournalIoError(
                "Portfolio Risk journal append failed"
            ) from None
        self._next_sequence += 1

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            self._file.close()
        except OSError:
            raise PortfolioRiskJournalIoError(
                "Portfolio Risk journal close failed"
            ) from None

    def __enter__(self) -> JsonLinesPortfolioRiskJournal:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _read_file(self) -> Iterator[PortfolioRiskJournalEntry]:
        if not self._path.exists():
            return
        try:
            file = self._path.open("rb")
        except OSError:
            raise PortfolioRiskJournalIoError(
                "Portfolio Risk journal could not be read"
            ) from None
        with file:
            expected_sequence = 1
            while True:
                try:
                    raw = file.readline(self._max_record_bytes + 1)
                except OSError:
                    raise PortfolioRiskJournalIoError(
                        "Portfolio Risk journal read failed"
                    ) from None
                if not raw:
                    return
                if expected_sequence > self._max_records:
                    raise PortfolioRiskJournalIntegrityError(
                        "Portfolio Risk journal record limit exceeded"
                    )
                if len(raw) > self._max_record_bytes:
                    raise PortfolioRiskJournalIntegrityError(
                        "Portfolio Risk journal record exceeds configured limit"
                    )
                if not raw.endswith(b"\n"):
                    raise PortfolioRiskJournalIntegrityError(
                        "Portfolio Risk journal record is truncated"
                    )
                sequence, entry = _decode(raw[:-1])
                if sequence != expected_sequence:
                    raise PortfolioRiskJournalIntegrityError(
                        "Portfolio Risk journal sequence is invalid"
                    )
                yield entry
                expected_sequence += 1


def _decode(raw: bytes) -> tuple[int, PortfolioRiskJournalEntry]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal record is not valid JSON"
        ) from None
    if not isinstance(value, dict):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal record must be an object"
        )
    body = cast(dict[str, object], value)
    checksum = body.get("checksum")
    if not isinstance(checksum, str):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal checksum is missing"
        )
    unsigned = dict(body)
    del unsigned["checksum"]
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != checksum:
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal checksum mismatch"
        )
    if (
        body.get("format") != RISK_JOURNAL_FORMAT
        or body.get("version") != RISK_JOURNAL_VERSION
    ):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal format is unsupported"
        )
    sequence = _integer(body, "sequence", positive=True)
    at_ns = UnixNanos(_integer(body, "at_ns", positive=False))
    kind_raw = body.get("kind")
    payload_raw = body.get("payload")
    if not isinstance(kind_raw, str) or not isinstance(payload_raw, dict):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal body is malformed"
        )
    payload: RiskPayload = {}
    for key, item in payload_raw.items():
        if not isinstance(key, str) or not (
            item is None
            or (isinstance(item, (bool, int, str))
            and not isinstance(item, float))
        ):
            raise PortfolioRiskJournalIntegrityError(
                "Portfolio Risk journal payload is malformed"
            )
        payload[key] = item
    try:
        entry = PortfolioRiskJournalEntry(
            kind=PortfolioRiskJournalEntryKind(kind_raw),
            at_ns=at_ns,
            payload=payload,
        )
    except (TypeError, ValueError):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal entry is invalid"
        ) from None
    return sequence, entry


def _integer(
    body: dict[str, object],
    key: str,
    *,
    positive: bool,
) -> int:
    value = body.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise PortfolioRiskJournalIntegrityError(
            f"Portfolio Risk journal {key} must be an integer"
        )
    if (positive and value <= 0) or (not positive and value < 0):
        raise PortfolioRiskJournalIntegrityError(
            f"Portfolio Risk journal {key} is outside bounds"
        )
    return value


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise PortfolioRiskJournalIntegrityError(
            "Portfolio Risk journal value is not canonical JSON"
        ) from None


__all__ = [
    "DEFAULT_MAX_RISK_RECORDS",
    "DEFAULT_MAX_RISK_RECORD_BYTES",
    "RISK_JOURNAL_FORMAT",
    "RISK_JOURNAL_VERSION",
    "JsonLinesPortfolioRiskJournal",
    "PortfolioRiskJournal",
    "PortfolioRiskJournalEntry",
    "PortfolioRiskJournalEntryKind",
    "PortfolioRiskJournalError",
    "PortfolioRiskJournalIntegrityError",
    "PortfolioRiskJournalIoError",
]
