"""Strict deterministic serialization for Basket decision evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any, TypeAlias, cast

from cex_quant.core import (
    AccountId,
    BasketLegId,
    IntentId,
    ObjectiveTypeId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.snapshots import DecisionSnapshotId

from .basket import (
    BasketTargetIntent,
    BasketTargetLeg,
    ObjectiveTypeRef,
)

BASKET_FORMAT_NAME = "cex_quant.basket_target_intent"
BASKET_FORMAT_VERSION = 1
MAX_ENCODED_BASKET_BYTES = 65_536

JsonObject: TypeAlias = dict[str, Any]


def encode_basket_target_intent(intent: BasketTargetIntent) -> bytes:
    """Encode one immutable Basket as bounded canonical UTF-8 JSON."""

    payload = _intent_to_dict(intent)
    envelope = {
        "checksum": _payload_checksum(payload),
        "format": BASKET_FORMAT_NAME,
        "format_version": BASKET_FORMAT_VERSION,
        "payload": payload,
    }
    encoded = _json_bytes(envelope)
    if len(encoded) > MAX_ENCODED_BASKET_BYTES:
        raise ValueError("encoded Basket exceeds maximum size")
    return encoded


def decode_basket_target_intent(encoded: bytes) -> BasketTargetIntent:
    """Decode one complete Basket record and verify schema and checksum."""

    if not encoded or len(encoded) > MAX_ENCODED_BASKET_BYTES:
        raise ValueError("encoded Basket size is outside limits")
    try:
        decoded = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Basket record is not valid UTF-8 JSON") from error
    envelope = _object(decoded, "Basket envelope")
    _require_fields(
        envelope,
        {"checksum", "format", "format_version", "payload"},
        "Basket envelope",
    )
    if (
        _string(envelope, "format") != BASKET_FORMAT_NAME
        or _integer(envelope, "format_version")
        != BASKET_FORMAT_VERSION
    ):
        raise LookupError("unsupported Basket format or version")
    payload = _object(envelope["payload"], "Basket payload")
    checksum = _string(envelope, "checksum")
    if checksum != _payload_checksum(payload):
        raise ArithmeticError("Basket record checksum mismatch")
    try:
        return _intent_from_dict(payload)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid Basket payload") from error


def basket_target_intent_checksum(intent: BasketTargetIntent) -> str:
    """Return the canonical payload checksum used by evidence records."""

    return _payload_checksum(_intent_to_dict(intent))


def _intent_to_dict(intent: BasketTargetIntent) -> JsonObject:
    return {
        "decision_snapshot_id": str(intent.decision_snapshot_id),
        "decision_time_ns": int(intent.decision_time_ns),
        "intent_id": str(intent.intent_id),
        "legs": [
            {
                "account_id": str(leg.account_id),
                "instrument": {
                    "kind": leg.instrument_id.kind.value,
                    "symbol": leg.instrument_id.symbol,
                    "venue": str(leg.instrument_id.venue),
                },
                "leg_id": str(leg.leg_id),
                "reason": leg.reason,
                "target_quantity": {
                    "raw": leg.target_quantity.raw,
                    "scale": leg.target_quantity.scale,
                },
            }
            for leg in intent.legs
        ],
        "objective": {
            "id": str(intent.objective.objective_type_id),
            "version": intent.objective.version,
        },
        "policy_version": intent.policy_version,
        "reason": intent.reason,
        "strategy_id": str(intent.strategy_id),
        "valid_until_ns": int(intent.valid_until_ns),
    }


def _intent_from_dict(raw: JsonObject) -> BasketTargetIntent:
    _require_fields(
        raw,
        {
            "decision_snapshot_id",
            "decision_time_ns",
            "intent_id",
            "legs",
            "objective",
            "policy_version",
            "reason",
            "strategy_id",
            "valid_until_ns",
        },
        "Basket payload",
    )
    objective = _object(raw["objective"], "objective")
    _require_fields(objective, {"id", "version"}, "objective")
    encoded_legs = _list(raw, "legs")
    legs = tuple(_leg_from_dict(item) for item in encoded_legs)
    return BasketTargetIntent(
        intent_id=IntentId(_string(raw, "intent_id")),
        strategy_id=StrategyId(_string(raw, "strategy_id")),
        decision_snapshot_id=DecisionSnapshotId(
            _string(raw, "decision_snapshot_id")
        ),
        objective=ObjectiveTypeRef(
            objective_type_id=ObjectiveTypeId(_string(objective, "id")),
            version=_integer(objective, "version"),
        ),
        legs=legs,
        decision_time_ns=UnixNanos(_integer(raw, "decision_time_ns")),
        valid_until_ns=UnixNanos(_integer(raw, "valid_until_ns")),
        policy_version=_integer(raw, "policy_version"),
        reason=_string(raw, "reason"),
    )


def _leg_from_dict(value: object) -> BasketTargetLeg:
    raw = _object(value, "Basket leg")
    _require_fields(
        raw,
        {
            "account_id",
            "instrument",
            "leg_id",
            "reason",
            "target_quantity",
        },
        "Basket leg",
    )
    instrument = _object(raw["instrument"], "instrument")
    _require_fields(instrument, {"kind", "symbol", "venue"}, "instrument")
    target = _object(raw["target_quantity"], "target_quantity")
    _require_fields(target, {"raw", "scale"}, "target_quantity")
    return BasketTargetLeg(
        leg_id=BasketLegId(_string(raw, "leg_id")),
        account_id=AccountId(_string(raw, "account_id")),
        instrument_id=InstrumentId(
            venue=VenueId(_string(instrument, "venue")),
            kind=InstrumentKind(_string(instrument, "kind")),
            symbol=_string(instrument, "symbol"),
        ),
        target_quantity=Quantity(
            raw=_integer(target, "raw"),
            scale=_integer(target, "scale"),
        ),
        reason=_string(raw, "reason"),
    )


def _payload_checksum(payload: JsonObject) -> str:
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return cast(JsonObject, value)


def _require_fields(
    value: JsonObject,
    expected: set[str],
    name: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields do not match schema")


def _string(value: JsonObject, field: str) -> str:
    item = value[field]
    if not isinstance(item, str):
        raise TypeError(f"{field} must be a string")
    return item


def _integer(value: JsonObject, field: str) -> int:
    item = value[field]
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError(f"{field} must be an integer")
    return item


def _list(value: JsonObject, field: str) -> list[object]:
    item = value[field]
    if not isinstance(item, list):
        raise TypeError(f"{field} must be a list")
    return cast(list[object], item)


__all__ = [
    "BASKET_FORMAT_NAME",
    "BASKET_FORMAT_VERSION",
    "MAX_ENCODED_BASKET_BYTES",
    "basket_target_intent_checksum",
    "decode_basket_target_intent",
    "encode_basket_target_intent",
]
