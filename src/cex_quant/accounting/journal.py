"""Checksummed append-only Accounting journal."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from .codec import (
    JsonObject,
    JsonValue,
    canonical_json,
    decode_ledger_transaction,
    decode_observed_financial_fact,
    encode_ledger_transaction,
    encode_observed_financial_fact,
)
from .facts import ObservedFinancialFact
from .model import LedgerTransaction

ACCOUNTING_JOURNAL_FORMAT = "cex_quant.accounting_journal"
ACCOUNTING_JOURNAL_VERSION = 1
DEFAULT_MAX_ACCOUNTING_RECORD_BYTES = 1_048_576
DEFAULT_MAX_ACCOUNTING_RECORDS = 250_000


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountingJournalEntry:
    observed: ObservedFinancialFact
    transactions: tuple[LedgerTransaction, ...]

    def __post_init__(self) -> None:
        fact_id = self.observed.fact.metadata.fact_id
        if any(fact_id not in item.source_fact_ids for item in self.transactions):
            raise ValueError("journal transaction does not reference observed fact")


class AccountingJournal(Protocol):
    def read(self) -> Iterator[AccountingJournalEntry]:
        """Yield durable entries in append order."""

    def append(self, entry: AccountingJournalEntry) -> None:
        """Durably append one entry or raise."""


class AccountingJournalError(RuntimeError):
    pass


class AccountingJournalIntegrityError(AccountingJournalError):
    pass


class AccountingJournalIoError(AccountingJournalError):
    pass


class JsonLinesAccountingJournal:
    """Bounded JSONL journal with sequence, checksum, flush and optional fsync."""

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_ACCOUNTING_RECORD_BYTES,
        max_records: int = DEFAULT_MAX_ACCOUNTING_RECORDS,
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
            raise AccountingJournalIoError(
                "Accounting journal could not be opened"
            ) from None

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[AccountingJournalEntry]:
        yield from self._read_file()

    def append(self, entry: AccountingJournalEntry) -> None:
        if not isinstance(entry, AccountingJournalEntry):
            raise ValueError("entry must be an AccountingJournalEntry")
        if self._next_sequence > self._max_records:
            raise AccountingJournalIntegrityError(
                "Accounting journal record limit reached"
            )
        body: JsonObject = {
            "format": ACCOUNTING_JOURNAL_FORMAT,
            "version": ACCOUNTING_JOURNAL_VERSION,
            "sequence": self._next_sequence,
            "observed": encode_observed_financial_fact(entry.observed),
            "transactions": [
                encode_ledger_transaction(item) for item in entry.transactions
            ],
        }
        body["checksum"] = hashlib.sha256(canonical_json(body)).hexdigest()
        encoded = canonical_json(body) + b"\n"
        if len(encoded) > self._max_record_bytes:
            raise AccountingJournalIntegrityError(
                "Accounting journal record exceeds configured limit"
            )
        try:
            written = self._file.write(encoded)
            if written != len(encoded):
                raise AccountingJournalIoError(
                    "Accounting journal append was incomplete"
                )
            self._file.flush()
            if self._sync_on_append:
                os.fsync(self._file.fileno())
        except AccountingJournalError:
            raise
        except OSError:
            raise AccountingJournalIoError(
                "Accounting journal append failed"
            ) from None
        self._next_sequence += 1

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            self._file.close()
        except OSError:
            raise AccountingJournalIoError(
                "Accounting journal close failed"
            ) from None

    def __enter__(self) -> JsonLinesAccountingJournal:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _read_file(self) -> Iterator[AccountingJournalEntry]:
        if not self._path.exists():
            return
        try:
            file = self._path.open("rb")
        except OSError:
            raise AccountingJournalIoError(
                "Accounting journal could not be read"
            ) from None
        with file:
            expected_sequence = 1
            while True:
                try:
                    raw = file.readline(self._max_record_bytes + 1)
                except OSError:
                    raise AccountingJournalIoError(
                        "Accounting journal read failed"
                    ) from None
                if not raw:
                    return
                if expected_sequence > self._max_records:
                    raise AccountingJournalIntegrityError(
                        "Accounting journal record limit exceeded"
                    )
                if len(raw) > self._max_record_bytes:
                    raise AccountingJournalIntegrityError(
                        "Accounting journal record exceeds configured limit"
                    )
                if not raw.endswith(b"\n"):
                    raise AccountingJournalIntegrityError(
                        "Accounting journal record is truncated"
                    )
                sequence, entry = _decode_record(raw[:-1])
                if sequence != expected_sequence:
                    raise AccountingJournalIntegrityError(
                        "Accounting journal sequence is invalid"
                    )
                yield entry
                expected_sequence += 1


def _decode_record(raw: bytes) -> tuple[int, AccountingJournalEntry]:
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AccountingJournalIntegrityError(
            "Accounting journal record is not valid JSON"
        ) from None
    if not isinstance(decoded, dict):
        raise AccountingJournalIntegrityError(
            "Accounting journal record must be an object"
        )
    body = cast(JsonObject, decoded)
    checksum = body.get("checksum")
    if not isinstance(checksum, str):
        raise AccountingJournalIntegrityError(
            "Accounting journal checksum is missing"
        )
    unsigned = dict(body)
    del unsigned["checksum"]
    if hashlib.sha256(canonical_json(unsigned)).hexdigest() != checksum:
        raise AccountingJournalIntegrityError(
            "Accounting journal checksum mismatch"
        )
    if (
        body.get("format") != ACCOUNTING_JOURNAL_FORMAT
        or body.get("version") != ACCOUNTING_JOURNAL_VERSION
    ):
        raise AccountingJournalIntegrityError(
            "Accounting journal format is unsupported"
        )
    sequence = _positive_integer(body.get("sequence"), "sequence")
    observed_raw = _json_object(body.get("observed"), "observed")
    transactions_raw = body.get("transactions")
    if not isinstance(transactions_raw, list):
        raise AccountingJournalIntegrityError(
            "Accounting journal transactions must be a list"
        )
    try:
        entry = AccountingJournalEntry(
            observed=decode_observed_financial_fact(observed_raw),
            transactions=tuple(
                decode_ledger_transaction(
                    _json_object(item, "transaction"),
                )
                for item in transactions_raw
            ),
        )
    except (TypeError, ValueError):
        raise AccountingJournalIntegrityError(
            "Accounting journal entry is invalid"
        ) from None
    return sequence, entry


def _positive_integer(value: JsonValue | None, name: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AccountingJournalIntegrityError(
            f"Accounting journal {name} must be a positive integer"
        )
    return value


def _json_object(value: JsonValue | None, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise AccountingJournalIntegrityError(
            f"Accounting journal {name} must be an object"
        )
    return value


__all__ = [
    "ACCOUNTING_JOURNAL_FORMAT",
    "ACCOUNTING_JOURNAL_VERSION",
    "DEFAULT_MAX_ACCOUNTING_RECORDS",
    "DEFAULT_MAX_ACCOUNTING_RECORD_BYTES",
    "AccountingJournal",
    "AccountingJournalEntry",
    "AccountingJournalError",
    "AccountingJournalIntegrityError",
    "AccountingJournalIoError",
    "JsonLinesAccountingJournal",
]
