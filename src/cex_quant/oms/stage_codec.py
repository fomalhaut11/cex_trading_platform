"""Canonical checksummed codec for ADR-015 Execution Stage evidence."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import TypeAlias, cast

from cex_quant.core import (
    ExecutionStageId,
    ExecutionStagePermitId,
    OrderGroupId,
    UnixNanos,
)
from cex_quant.snapshots import DecisionSnapshotId

from .group_codec import (
    decode_execution_action,
    decode_execution_action_permit,
    decode_execution_plan_ref,
    encode_execution_action,
    encode_execution_action_permit,
    encode_execution_plan_ref,
)
from .stage_model import ExecutionStage, ExecutionStagePermit

STAGE_CONTRACT_FORMAT = "cex_quant.execution_stage"
STAGE_CONTRACT_VERSION = 1
MAX_STAGE_CONTRACT_BYTES = 262_144

JsonValue: TypeAlias = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)
JsonObject: TypeAlias = dict[str, JsonValue]


def encode_execution_stage(value: ExecutionStage) -> bytes:
    return _encode(
        "execution_stage",
        {
            "stage_id": str(value.stage_id),
            "group_id": str(value.group_id),
            "base_group_revision": value.base_group_revision,
            "execution_plan": _blob(encode_execution_plan_ref(value.execution_plan)),
            "actions": [_blob(encode_execution_action(item)) for item in value.actions],
            "dispatch_width": value.dispatch_width,
            "created_at_ns": int(value.created_at_ns),
        },
    )


def decode_execution_stage(encoded: bytes) -> ExecutionStage:
    raw = _decode(encoded, "execution_stage")
    actions = _list(raw, "actions")
    return ExecutionStage(
        stage_id=ExecutionStageId(_string(raw, "stage_id")),
        group_id=OrderGroupId(_string(raw, "group_id")),
        base_group_revision=_integer(raw, "base_group_revision"),
        execution_plan=decode_execution_plan_ref(
            _unblob(_string(raw, "execution_plan"), name="execution_plan")
        ),
        actions=tuple(
            decode_execution_action(
                _unblob(_list_string(item, name="actions"), name="actions")
            )
            for item in actions
        ),
        dispatch_width=_integer(raw, "dispatch_width"),
        created_at_ns=UnixNanos(_integer(raw, "created_at_ns")),
    )


def encode_execution_stage_permit(value: ExecutionStagePermit) -> bytes:
    return _encode(
        "execution_stage_permit",
        {
            "permit_id": str(value.permit_id),
            "stage_id": str(value.stage_id),
            "stage_checksum": value.stage_checksum,
            "group_id": str(value.group_id),
            "base_group_revision": value.base_group_revision,
            "action_permits": [
                _blob(encode_execution_action_permit(item))
                for item in value.action_permits
            ],
            "partial_execution_envelope_checksum": (
                value.partial_execution_envelope_checksum
            ),
            "risk_snapshot_id": str(value.risk_snapshot_id),
            "issued_at_ns": int(value.issued_at_ns),
            "valid_until_ns": int(value.valid_until_ns),
            "risk_policy_version": value.risk_policy_version,
        },
    )


def decode_execution_stage_permit(encoded: bytes) -> ExecutionStagePermit:
    raw = _decode(encoded, "execution_stage_permit")
    action_permits = _list(raw, "action_permits")
    return ExecutionStagePermit(
        permit_id=ExecutionStagePermitId(_string(raw, "permit_id")),
        stage_id=ExecutionStageId(_string(raw, "stage_id")),
        stage_checksum=_string(raw, "stage_checksum"),
        group_id=OrderGroupId(_string(raw, "group_id")),
        base_group_revision=_integer(raw, "base_group_revision"),
        action_permits=tuple(
            decode_execution_action_permit(
                _unblob(
                    _list_string(item, name="action_permits"),
                    name="action_permits",
                )
            )
            for item in action_permits
        ),
        partial_execution_envelope_checksum=_string(
            raw,
            "partial_execution_envelope_checksum",
        ),
        risk_snapshot_id=DecisionSnapshotId(_string(raw, "risk_snapshot_id")),
        issued_at_ns=UnixNanos(_integer(raw, "issued_at_ns")),
        valid_until_ns=UnixNanos(_integer(raw, "valid_until_ns")),
        risk_policy_version=_integer(raw, "risk_policy_version"),
    )


def _encode(kind: str, payload: JsonObject) -> bytes:
    body: JsonObject = {
        "format": STAGE_CONTRACT_FORMAT,
        "version": STAGE_CONTRACT_VERSION,
        "kind": kind,
        "payload": payload,
    }
    canonical = _canonical(body)
    envelope = dict(body)
    envelope["checksum"] = hashlib.sha256(canonical).hexdigest()
    encoded = _canonical(envelope)
    if len(encoded) > MAX_STAGE_CONTRACT_BYTES:
        raise ValueError("Execution Stage contract exceeds hard byte bound")
    return encoded


def _decode(encoded: bytes, expected_kind: str) -> JsonObject:
    if not encoded or len(encoded) > MAX_STAGE_CONTRACT_BYTES:
        raise ValueError("Execution Stage contract size is invalid")
    try:
        decoded = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Execution Stage contract is not valid JSON") from error
    raw = _object(decoded, "contract")
    checksum = _string(raw, "checksum")
    body = dict(raw)
    del body["checksum"]
    if hashlib.sha256(_canonical(body)).hexdigest() != checksum:
        raise ValueError("Execution Stage contract checksum mismatch")
    if _string(raw, "format") != STAGE_CONTRACT_FORMAT:
        raise ValueError("unsupported Execution Stage contract format")
    if _integer(raw, "version") != STAGE_CONTRACT_VERSION:
        raise ValueError("unsupported Execution Stage contract version")
    if _string(raw, "kind") != expected_kind:
        raise ValueError("Execution Stage contract kind mismatch")
    return _object(raw.get("payload"), "payload")


def _blob(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unblob(value: str, *, name: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError(f"{name} is not valid base64") from error


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return cast(JsonObject, value)


def _list(raw: JsonObject, key: str) -> list[JsonValue]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return value


def _list_string(value: JsonValue, *, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must contain strings")
    return value


def _string(raw: JsonObject, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _integer(raw: JsonObject, key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an int")
    return value


__all__ = [
    "MAX_STAGE_CONTRACT_BYTES",
    "STAGE_CONTRACT_FORMAT",
    "STAGE_CONTRACT_VERSION",
    "decode_execution_stage",
    "decode_execution_stage_permit",
    "encode_execution_stage",
    "encode_execution_stage_permit",
]
