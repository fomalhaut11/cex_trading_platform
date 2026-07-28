"""Deterministic bounded codecs for ADR-011 immutable contracts."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any, TypeAlias, cast

from cex_quant.core import (
    AccountId,
    BasketLegId,
    ExecutionPermitId,
    ExecutionPlanId,
    GroupActionId,
    OrderGroupId,
    PortfolioApprovalId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    decode_basket_target_intent,
    encode_basket_target_intent,
)

from .group_model import (
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionPlanRef,
    OrderGroupAdmission,
)
from .model import OrderSide, OrderType, PositionSide, TimeInForce

GROUP_CONTRACT_FORMAT = "cex_quant.oms_group_contract"
GROUP_CONTRACT_VERSION = 1
MAX_GROUP_CONTRACT_BYTES = 131_072

JsonObject: TypeAlias = dict[str, Any]


def encode_order_group_admission(value: OrderGroupAdmission) -> bytes:
    return _encode("order_group_admission", _admission_to_dict(value))


def decode_order_group_admission(encoded: bytes) -> OrderGroupAdmission:
    return _admission_from_dict(_decode(encoded, "order_group_admission"))


def encode_execution_plan_ref(value: ExecutionPlanRef) -> bytes:
    return _encode("execution_plan_ref", _plan_to_dict(value))


def decode_execution_plan_ref(encoded: bytes) -> ExecutionPlanRef:
    return _plan_from_dict(_decode(encoded, "execution_plan_ref"))


def encode_execution_action(value: ExecutionAction) -> bytes:
    return _encode("execution_action", _action_to_dict(value))


def decode_execution_action(encoded: bytes) -> ExecutionAction:
    return _action_from_dict(_decode(encoded, "execution_action"))


def encode_execution_action_permit(value: ExecutionActionPermit) -> bytes:
    return _encode("execution_action_permit", _permit_to_dict(value))


def decode_execution_action_permit(encoded: bytes) -> ExecutionActionPermit:
    return _permit_from_dict(_decode(encoded, "execution_action_permit"))


def _admission_to_dict(value: OrderGroupAdmission) -> JsonObject:
    basket = base64.b64encode(encode_basket_target_intent(value.basket)).decode("ascii")
    return {
        "approval_id": str(value.approval_id),
        "approved_at_ns": int(value.approved_at_ns),
        "basket": basket,
        "basket_checksum": value.basket_checksum,
        "risk_policy_version": value.risk_policy_version,
        "valid_until_ns": int(value.valid_until_ns),
    }


def _admission_from_dict(raw: JsonObject) -> OrderGroupAdmission:
    _require_fields(
        raw,
        {
            "approval_id",
            "approved_at_ns",
            "basket",
            "basket_checksum",
            "risk_policy_version",
            "valid_until_ns",
        },
        "OrderGroupAdmission",
    )
    try:
        basket = base64.b64decode(
            _string(raw, "basket"),
            validate=True,
        )
    except (ValueError, binascii.Error) as error:
        raise ValueError("Basket evidence is not valid base64") from error
    return OrderGroupAdmission(
        approval_id=PortfolioApprovalId(_string(raw, "approval_id")),
        basket=decode_basket_target_intent(basket),
        basket_checksum=_string(raw, "basket_checksum"),
        approved_at_ns=UnixNanos(_integer(raw, "approved_at_ns")),
        valid_until_ns=UnixNanos(_integer(raw, "valid_until_ns")),
        risk_policy_version=_integer(raw, "risk_policy_version"),
    )


def _plan_to_dict(value: ExecutionPlanRef) -> JsonObject:
    return {
        "execution_plan_id": str(value.execution_plan_id),
        "parameters_checksum": value.parameters_checksum,
        "version": value.version,
    }


def _plan_from_dict(raw: JsonObject) -> ExecutionPlanRef:
    _require_fields(
        raw,
        {"execution_plan_id", "parameters_checksum", "version"},
        "ExecutionPlanRef",
    )
    return ExecutionPlanRef(
        execution_plan_id=ExecutionPlanId(_string(raw, "execution_plan_id")),
        version=_integer(raw, "version"),
        parameters_checksum=_string(raw, "parameters_checksum"),
    )


def _action_to_dict(value: ExecutionAction) -> JsonObject:
    return {
        "account_id": str(value.account_id),
        "action_id": str(value.action_id),
        "basket_leg_id": str(value.basket_leg_id),
        "created_at_ns": int(value.created_at_ns),
        "execution_plan": _plan_to_dict(value.execution_plan),
        "expected_group_revision": value.expected_group_revision,
        "group_id": str(value.group_id),
        "instrument": _instrument_to_dict(value.instrument_id),
        "limit_price": _optional_fixed(value.limit_price),
        "order_type": value.order_type.value,
        "position_side": value.position_side.value,
        "post_only": value.post_only,
        "quantity": _fixed(value.quantity),
        "reduce_only": value.reduce_only,
        "side": value.side.value,
        "stop_price": _optional_fixed(value.stop_price),
        "time_in_force": value.time_in_force.value,
    }


def _action_from_dict(raw: JsonObject) -> ExecutionAction:
    _require_fields(
        raw,
        {
            "account_id",
            "action_id",
            "basket_leg_id",
            "created_at_ns",
            "execution_plan",
            "expected_group_revision",
            "group_id",
            "instrument",
            "limit_price",
            "order_type",
            "position_side",
            "post_only",
            "quantity",
            "reduce_only",
            "side",
            "stop_price",
            "time_in_force",
        },
        "ExecutionAction",
    )
    return ExecutionAction(
        group_id=OrderGroupId(_string(raw, "group_id")),
        expected_group_revision=_integer(raw, "expected_group_revision"),
        action_id=GroupActionId(_string(raw, "action_id")),
        basket_leg_id=BasketLegId(_string(raw, "basket_leg_id")),
        account_id=AccountId(_string(raw, "account_id")),
        instrument_id=_instrument_from_dict(_object(raw["instrument"], "instrument")),
        side=OrderSide(_string(raw, "side")),
        order_type=OrderType(_string(raw, "order_type")),
        quantity=_quantity(raw["quantity"]),
        time_in_force=TimeInForce(_string(raw, "time_in_force")),
        limit_price=_optional_price(raw["limit_price"]),
        stop_price=_optional_price(raw["stop_price"]),
        reduce_only=_boolean(raw, "reduce_only"),
        post_only=_boolean(raw, "post_only"),
        position_side=PositionSide(_string(raw, "position_side")),
        execution_plan=_plan_from_dict(
            _object(raw["execution_plan"], "execution_plan")
        ),
        created_at_ns=UnixNanos(_integer(raw, "created_at_ns")),
    )


def _permit_to_dict(value: ExecutionActionPermit) -> JsonObject:
    return {
        "action_checksum": value.action_checksum,
        "action_id": str(value.action_id),
        "expected_group_revision": value.expected_group_revision,
        "group_id": str(value.group_id),
        "issued_at_ns": int(value.issued_at_ns),
        "permit_id": str(value.permit_id),
        "risk_policy_version": value.risk_policy_version,
        "risk_snapshot_id": str(value.risk_snapshot_id),
        "valid_until_ns": int(value.valid_until_ns),
    }


def _permit_from_dict(raw: JsonObject) -> ExecutionActionPermit:
    _require_fields(
        raw,
        {
            "action_checksum",
            "action_id",
            "expected_group_revision",
            "group_id",
            "issued_at_ns",
            "permit_id",
            "risk_policy_version",
            "risk_snapshot_id",
            "valid_until_ns",
        },
        "ExecutionActionPermit",
    )
    return ExecutionActionPermit(
        permit_id=ExecutionPermitId(_string(raw, "permit_id")),
        group_id=OrderGroupId(_string(raw, "group_id")),
        expected_group_revision=_integer(raw, "expected_group_revision"),
        action_id=GroupActionId(_string(raw, "action_id")),
        action_checksum=_string(raw, "action_checksum"),
        risk_snapshot_id=DecisionSnapshotId(_string(raw, "risk_snapshot_id")),
        issued_at_ns=UnixNanos(_integer(raw, "issued_at_ns")),
        valid_until_ns=UnixNanos(_integer(raw, "valid_until_ns")),
        risk_policy_version=_integer(raw, "risk_policy_version"),
    )


def _encode(kind: str, payload: JsonObject) -> bytes:
    body = {
        "format": GROUP_CONTRACT_FORMAT,
        "kind": kind,
        "payload": payload,
        "version": GROUP_CONTRACT_VERSION,
    }
    envelope = dict(body)
    envelope["checksum"] = hashlib.sha256(_json_bytes(body)).hexdigest()
    encoded = _json_bytes(envelope)
    if len(encoded) > MAX_GROUP_CONTRACT_BYTES:
        raise ValueError("encoded group contract exceeds maximum size")
    return encoded


def _decode(encoded: bytes, expected_kind: str) -> JsonObject:
    if not encoded or len(encoded) > MAX_GROUP_CONTRACT_BYTES:
        raise ValueError("encoded group contract size is outside limits")
    try:
        value = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("group contract is not valid UTF-8 JSON") from error
    envelope = _object(value, "group contract envelope")
    _require_fields(
        envelope,
        {"checksum", "format", "kind", "payload", "version"},
        "group contract envelope",
    )
    body = dict(envelope)
    checksum = _string(body, "checksum")
    del body["checksum"]
    if checksum != hashlib.sha256(_json_bytes(body)).hexdigest():
        raise ArithmeticError("group contract checksum mismatch")
    if _string(envelope, "format") != GROUP_CONTRACT_FORMAT:
        raise LookupError("unsupported group contract format")
    if _integer(envelope, "version") != GROUP_CONTRACT_VERSION:
        raise LookupError("unsupported group contract version")
    if _string(envelope, "kind") != expected_kind:
        raise TypeError("group contract kind mismatch")
    return _object(envelope["payload"], "group contract payload")


def _instrument_to_dict(value: InstrumentId) -> JsonObject:
    return {
        "kind": value.kind.value,
        "symbol": value.symbol,
        "venue": str(value.venue),
    }


def _instrument_from_dict(raw: JsonObject) -> InstrumentId:
    _require_fields(raw, {"kind", "symbol", "venue"}, "instrument")
    return InstrumentId(
        venue=VenueId(_string(raw, "venue")),
        kind=InstrumentKind(_string(raw, "kind")),
        symbol=_string(raw, "symbol"),
    )


def _fixed(value: Price | Quantity) -> JsonObject:
    return {"raw": value.raw, "scale": value.scale}


def _optional_fixed(value: Price | None) -> JsonObject | None:
    return None if value is None else _fixed(value)


def _quantity(value: object) -> Quantity:
    raw = _object(value, "quantity")
    _require_fields(raw, {"raw", "scale"}, "quantity")
    return Quantity(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _optional_price(value: object) -> Price | None:
    if value is None:
        return None
    raw = _object(value, "price")
    _require_fields(raw, {"raw", "scale"}, "price")
    return Price(raw=_integer(raw, "raw"), scale=_integer(raw, "scale"))


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
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


def _boolean(value: JsonObject, field: str) -> bool:
    item = value[field]
    if not isinstance(item, bool):
        raise TypeError(f"{field} must be a boolean")
    return item


__all__ = [
    "GROUP_CONTRACT_FORMAT",
    "GROUP_CONTRACT_VERSION",
    "MAX_GROUP_CONTRACT_BYTES",
    "decode_execution_action",
    "decode_execution_action_permit",
    "decode_execution_plan_ref",
    "decode_order_group_admission",
    "encode_execution_action",
    "encode_execution_action_permit",
    "encode_execution_plan_ref",
    "encode_order_group_admission",
]
