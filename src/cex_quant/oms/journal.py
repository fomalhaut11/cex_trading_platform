"""Durable append-only OMS recovery journal and deterministic codec."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Protocol, TypeAlias, cast

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind

from .model import (
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
)

FORMAT_NAME = "cex_quant.oms_journal"
FORMAT_VERSION = 1
DEFAULT_MAX_RECORD_BYTES = 65_536

JsonValue: TypeAlias = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)
JsonObject: TypeAlias = dict[str, JsonValue]


class OmsJournalError(RuntimeError):
    """Base class for journal I/O, integrity and recovery failures."""


class OmsJournalIntegrityError(OmsJournalError):
    """Raised when persistent records are malformed, truncated or reordered."""


class OmsJournalIoError(OmsJournalError):
    """Raised when a durable journal operation cannot complete."""


class OmsJournalEntryType(StrEnum):
    ORDER_CREATED = "order_created"
    ORDER_SUBMITTING = "order_submitting"
    CANCEL_REQUESTED = "cancel_requested"
    VENUE_EVENT = "venue_event"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCreatedEntry:
    request: OrderRequest

    @property
    def entry_type(self) -> OmsJournalEntryType:
        return OmsJournalEntryType.ORDER_CREATED


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderSubmittingEntry:
    client_order_id: ClientOrderId
    at_ns: UnixNanos

    @property
    def entry_type(self) -> OmsJournalEntryType:
        return OmsJournalEntryType.ORDER_SUBMITTING


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelRequestedEntry:
    client_order_id: ClientOrderId
    at_ns: UnixNanos

    @property
    def entry_type(self) -> OmsJournalEntryType:
        return OmsJournalEntryType.CANCEL_REQUESTED


@dataclass(frozen=True, slots=True, kw_only=True)
class VenueEventEntry:
    event: OrderEvent

    @property
    def entry_type(self) -> OmsJournalEntryType:
        return OmsJournalEntryType.VENUE_EVENT


OmsJournalEntry: TypeAlias = (
    OrderCreatedEntry
    | OrderSubmittingEntry
    | CancelRequestedEntry
    | VenueEventEntry
)


class OmsJournal(Protocol):
    """Durable ordered journal used by the single-writer OMS service."""

    def read(self) -> Iterator[OmsJournalEntry]: ...

    def append(self, entry: OmsJournalEntry) -> None: ...


class JsonLinesOmsJournal:
    """Strict checksummed JSONL journal with an fsync boundary per append."""

    def __init__(
        self,
        path: Path,
        *,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
        sync_on_append: bool = True,
    ) -> None:
        if max_record_bytes <= 0:
            raise ValueError("max_record_bytes must be positive")
        if not path.parent.is_dir():
            raise ValueError("journal parent directory must already exist")
        self._path = path
        self._max_record_bytes = max_record_bytes
        self._sync_on_append = sync_on_append
        self._next_sequence = sum(1 for _ in self._read_file()) + 1
        try:
            self._file: BinaryIO = path.open("ab")
        except OSError as error:
            raise OmsJournalIoError(str(error)) from error

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Iterator[OmsJournalEntry]:
        yield from self._read_file()

    def append(self, entry: OmsJournalEntry) -> None:
        record = encode_journal_record(entry, sequence=self._next_sequence) + b"\n"
        if len(record) > self._max_record_bytes:
            raise OmsJournalIntegrityError(
                f"encoded record exceeds {self._max_record_bytes} bytes"
            )
        try:
            written = self._file.write(record)
            if written != len(record):
                raise OmsJournalIoError(
                    f"short append: wrote {written} of {len(record)} bytes"
                )
            self._file.flush()
            if self._sync_on_append:
                os.fsync(self._file.fileno())
        except OmsJournalIoError:
            raise
        except OSError as error:
            raise OmsJournalIoError(str(error)) from error
        self._next_sequence += 1

    def close(self) -> None:
        if not self._file.closed:
            try:
                self._file.close()
            except OSError as error:
                raise OmsJournalIoError(str(error)) from error

    def __enter__(self) -> JsonLinesOmsJournal:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _read_file(self) -> Iterator[OmsJournalEntry]:
        if not self._path.exists():
            return
        try:
            file = self._path.open("rb")
        except OSError as error:
            raise OmsJournalIoError(str(error)) from error
        with file:
            expected_sequence = 1
            while True:
                try:
                    record = file.readline(self._max_record_bytes + 1)
                except OSError as error:
                    raise OmsJournalIoError(str(error)) from error
                if not record:
                    return
                if len(record) > self._max_record_bytes:
                    raise OmsJournalIntegrityError(
                        f"record {expected_sequence} exceeds "
                        f"{self._max_record_bytes} bytes"
                    )
                if not record.endswith(b"\n"):
                    raise OmsJournalIntegrityError(
                        f"record {expected_sequence} is truncated"
                    )
                sequence, entry = decode_journal_record(record[:-1])
                if sequence != expected_sequence:
                    raise OmsJournalIntegrityError(
                        f"expected sequence {expected_sequence}, got {sequence}"
                    )
                yield entry
                expected_sequence += 1


def encode_journal_record(
    entry: OmsJournalEntry,
    *,
    sequence: int,
) -> bytes:
    if sequence <= 0:
        raise ValueError("sequence must be positive")
    body: JsonObject = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "sequence": sequence,
        "entry": _encode_entry(entry),
    }
    canonical = _canonical_json(body)
    envelope = dict(body)
    envelope["checksum"] = hashlib.sha256(canonical).hexdigest()
    return _canonical_json(envelope)


def decode_journal_record(record: bytes) -> tuple[int, OmsJournalEntry]:
    try:
        raw_value = json.loads(record)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OmsJournalIntegrityError("record is not valid JSON") from error
    raw = _object(raw_value, "record")
    checksum = _string(raw, "checksum")
    body = dict(raw)
    del body["checksum"]
    expected = hashlib.sha256(_canonical_json(body)).hexdigest()
    if checksum != expected:
        raise OmsJournalIntegrityError("record checksum mismatch")
    if _string(raw, "format") != FORMAT_NAME:
        raise OmsJournalIntegrityError("unsupported journal format")
    if _integer(raw, "version") != FORMAT_VERSION:
        raise OmsJournalIntegrityError("unsupported journal version")
    sequence = _integer(raw, "sequence")
    if sequence <= 0:
        raise OmsJournalIntegrityError("sequence must be positive")
    return sequence, _decode_entry(_object(raw["entry"], "entry"))


def _encode_entry(entry: OmsJournalEntry) -> JsonObject:
    if isinstance(entry, OrderCreatedEntry):
        payload = _encode_request(entry.request)
    elif isinstance(entry, OrderSubmittingEntry | CancelRequestedEntry):
        payload = {
            "client_order_id": str(entry.client_order_id),
            "at_ns": int(entry.at_ns),
        }
    elif isinstance(entry, VenueEventEntry):
        payload = _encode_event(entry.event)
    else:
        raise TypeError(f"unsupported journal entry: {type(entry).__name__}")
    return {"type": entry.entry_type.value, "payload": payload}


def _decode_entry(raw: JsonObject) -> OmsJournalEntry:
    entry_type = OmsJournalEntryType(_string(raw, "type"))
    payload = _object(raw["payload"], "payload")
    if entry_type is OmsJournalEntryType.ORDER_CREATED:
        return OrderCreatedEntry(request=_decode_request(payload))
    if entry_type is OmsJournalEntryType.ORDER_SUBMITTING:
        return OrderSubmittingEntry(
            client_order_id=ClientOrderId(_string(payload, "client_order_id")),
            at_ns=UnixNanos(_integer(payload, "at_ns")),
        )
    if entry_type is OmsJournalEntryType.CANCEL_REQUESTED:
        return CancelRequestedEntry(
            client_order_id=ClientOrderId(_string(payload, "client_order_id")),
            at_ns=UnixNanos(_integer(payload, "at_ns")),
        )
    return VenueEventEntry(event=_decode_event(payload))


def _encode_request(request: OrderRequest) -> JsonObject:
    return {
        "client_order_id": str(request.client_order_id),
        "approval_id": request.approval_id,
        "intent_id": str(request.intent_id),
        "account_id": str(request.account_id),
        "instrument": _encode_instrument(request.instrument_id),
        "side": request.side.value,
        "order_type": request.order_type.value,
        "quantity": _encode_fixed(request.quantity),
        "created_at_ns": int(request.created_at_ns),
        "time_in_force": request.time_in_force.value,
        "limit_price": _encode_optional_fixed(request.limit_price),
        "stop_price": _encode_optional_fixed(request.stop_price),
        "reduce_only": request.reduce_only,
        "post_only": request.post_only,
        "position_side": request.position_side.value,
    }


def _decode_request(raw: JsonObject) -> OrderRequest:
    return OrderRequest(
        client_order_id=ClientOrderId(_string(raw, "client_order_id")),
        approval_id=_string(raw, "approval_id"),
        intent_id=IntentId(_string(raw, "intent_id")),
        account_id=AccountId(_string(raw, "account_id")),
        instrument_id=_decode_instrument(_object(raw["instrument"], "instrument")),
        side=OrderSide(_string(raw, "side")),
        order_type=OrderType(_string(raw, "order_type")),
        quantity=_quantity(raw["quantity"]),
        created_at_ns=UnixNanos(_integer(raw, "created_at_ns")),
        time_in_force=TimeInForce(_string(raw, "time_in_force")),
        limit_price=_optional_price(raw.get("limit_price")),
        stop_price=_optional_price(raw.get("stop_price")),
        reduce_only=_boolean(raw, "reduce_only"),
        post_only=_boolean(raw, "post_only"),
        position_side=PositionSide(_string(raw, "position_side")),
    )


def _encode_event(event: OrderEvent) -> JsonObject:
    return {
        "venue_update_id": event.venue_update_id,
        "client_order_id": str(event.client_order_id),
        "status": event.status.value,
        "cumulative_filled_quantity": _encode_fixed(
            event.cumulative_filled_quantity
        ),
        "event_time_ns": int(event.event_time_ns),
        "venue_order_id": (
            None if event.venue_order_id is None else str(event.venue_order_id)
        ),
        "average_fill_price": _encode_optional_fixed(event.average_fill_price),
        "reason": event.reason,
    }


def _decode_event(raw: JsonObject) -> OrderEvent:
    venue_order_id = _optional_string(raw, "venue_order_id")
    return OrderEvent(
        venue_update_id=_string(raw, "venue_update_id"),
        client_order_id=ClientOrderId(_string(raw, "client_order_id")),
        status=OrderStatus(_string(raw, "status")),
        cumulative_filled_quantity=_quantity(
            raw["cumulative_filled_quantity"]
        ),
        event_time_ns=UnixNanos(_integer(raw, "event_time_ns")),
        venue_order_id=(
            None if venue_order_id is None else VenueOrderId(venue_order_id)
        ),
        average_fill_price=_optional_price(raw.get("average_fill_price")),
        reason=_string(raw, "reason"),
    )


def _encode_instrument(instrument: InstrumentId) -> JsonObject:
    return {
        "venue": str(instrument.venue),
        "kind": instrument.kind.value,
        "symbol": instrument.symbol,
    }


def _decode_instrument(raw: JsonObject) -> InstrumentId:
    return InstrumentId(
        venue=VenueId(_string(raw, "venue")),
        kind=InstrumentKind(_string(raw, "kind")),
        symbol=_string(raw, "symbol"),
    )


def _encode_fixed(value: Price | Quantity) -> JsonObject:
    return {"raw": value.raw, "scale": value.scale}


def _encode_optional_fixed(value: Price | None) -> JsonObject | None:
    return None if value is None else _encode_fixed(value)


def _quantity(value: JsonValue) -> Quantity:
    raw = _object(value, "quantity")
    return Quantity(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _optional_price(value: JsonValue) -> Price | None:
    if value is None:
        return None
    raw = _object(value, "price")
    return Price(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _canonical_json(value: JsonObject) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise OmsJournalIntegrityError(f"{name} must be an object")
    return cast(JsonObject, value)


def _string(raw: JsonObject, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise OmsJournalIntegrityError(f"{key} must be a string")
    return value


def _optional_string(raw: JsonObject, key: str) -> str | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise OmsJournalIntegrityError(f"{key} must be a string or null")
    return value


def _integer(raw: JsonObject, key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise OmsJournalIntegrityError(f"{key} must be an integer")
    return value


def _boolean(raw: JsonObject, key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise OmsJournalIntegrityError(f"{key} must be a boolean")
    return value


__all__ = [
    "DEFAULT_MAX_RECORD_BYTES",
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "CancelRequestedEntry",
    "JsonLinesOmsJournal",
    "OmsJournal",
    "OmsJournalEntry",
    "OmsJournalEntryType",
    "OmsJournalError",
    "OmsJournalIntegrityError",
    "OmsJournalIoError",
    "OrderCreatedEntry",
    "OrderSubmittingEntry",
    "VenueEventEntry",
    "decode_journal_record",
    "encode_journal_record",
]
