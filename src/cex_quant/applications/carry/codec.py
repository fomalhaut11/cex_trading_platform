"""Strict JSON-compatible codec for Carry application facts."""

from __future__ import annotations

from typing import TypeAlias, cast

from cex_quant.core import (
    AccountId,
    IntentId,
    OrderGroupId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.snapshots import DecisionSnapshotId

from .facts import (
    CarryApplicationFact,
    CarryApplicationFactKind,
    CarryFactPayload,
    CarryIntentLinked,
    CarryOrderGroupLinked,
    CarryOwnershipRegistered,
    CarryPositionCreated,
    CarryRecoveryRequired,
    CarryStateChanged,
    encode_carry_fact_payload,
)
from .identifiers import (
    ApplicationPositionId,
    CarryApplicationFactId,
    CarryOwnershipId,
    CarryPairId,
)
from .model import CarryFinancialState, CarryHedgeState, CarryLifecycle
from .ownership import CarryLegOwnership

JsonScalar: TypeAlias = bool | int | str | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class CarryCodecError(ValueError):
    pass


def encode_carry_application_fact(
    fact: CarryApplicationFact,
) -> JsonObject:
    return {
        "fact_id": str(fact.fact_id),
        "application_position_id": str(fact.application_position_id),
        "expected_revision": fact.expected_revision,
        "new_revision": fact.new_revision,
        "occurred_at_ns": int(fact.occurred_at_ns),
        "recorded_at_ns": int(fact.recorded_at_ns),
        "policy_version": fact.policy_version,
        "schema_version": fact.schema_version,
        "payload": cast(JsonObject, encode_carry_fact_payload(fact.payload)),
    }


def decode_carry_application_fact(
    value: JsonObject,
) -> CarryApplicationFact:
    try:
        payload = _decode_payload(_object(value, "payload"))
        return CarryApplicationFact(
            fact_id=CarryApplicationFactId(_string(value, "fact_id")),
            application_position_id=ApplicationPositionId(
                _string(value, "application_position_id")
            ),
            expected_revision=_integer(value, "expected_revision"),
            new_revision=_integer(value, "new_revision"),
            occurred_at_ns=UnixNanos(_integer(value, "occurred_at_ns")),
            recorded_at_ns=UnixNanos(_integer(value, "recorded_at_ns")),
            policy_version=_integer(value, "policy_version"),
            schema_version=_integer(value, "schema_version"),
            payload=payload,
        )
    except (KeyError, TypeError, ValueError):
        raise CarryCodecError("Carry application fact is invalid") from None


def _decode_payload(value: JsonObject) -> CarryFactPayload:
    kind = CarryApplicationFactKind(_string(value, "kind"))
    body = _object(value, "body")
    if kind is CarryApplicationFactKind.POSITION_CREATED:
        return CarryPositionCreated(
            strategy_id=StrategyId(_string(body, "strategy_id")),
            pair_id=CarryPairId(_string(body, "pair_id")),
            opening_snapshot_id=DecisionSnapshotId(
                _string(body, "opening_snapshot_id")
            ),
            ownership=tuple(
                _decode_ownership(item)
                for item in _object_list(body, "ownership")
            ),
        )
    if kind is CarryApplicationFactKind.INTENT_LINKED:
        return CarryIntentLinked(
            intent_id=IntentId(_string(body, "intent_id")),
            source_snapshot_id=DecisionSnapshotId(
                _string(body, "source_snapshot_id")
            ),
        )
    if kind is CarryApplicationFactKind.ORDER_GROUP_LINKED:
        return CarryOrderGroupLinked(
            order_group_id=OrderGroupId(_string(body, "order_group_id")),
            source_snapshot_id=DecisionSnapshotId(
                _string(body, "source_snapshot_id")
            ),
        )
    if kind is CarryApplicationFactKind.OWNERSHIP_REGISTERED:
        return CarryOwnershipRegistered(
            ownership=_decode_ownership(_object(body, "ownership"))
        )
    if kind is CarryApplicationFactKind.STATE_CHANGED:
        return CarryStateChanged(
            lifecycle=CarryLifecycle(_string(body, "lifecycle")),
            hedge_state=CarryHedgeState(_string(body, "hedge_state")),
            financial_state=CarryFinancialState(
                _string(body, "financial_state")
            ),
            source_snapshot_id=DecisionSnapshotId(
                _string(body, "source_snapshot_id")
            ),
            reason=_string(body, "reason", allow_empty=True),
        )
    return CarryRecoveryRequired(
        source_snapshot_id=DecisionSnapshotId(
            _string(body, "source_snapshot_id")
        ),
        reason=_string(body, "reason"),
    )


def _decode_ownership(value: JsonObject) -> CarryLegOwnership:
    instrument = _object(value, "instrument_id")
    return CarryLegOwnership(
        ownership_id=CarryOwnershipId(_string(value, "ownership_id")),
        application_position_id=ApplicationPositionId(
            _string(value, "application_position_id")
        ),
        account_id=AccountId(_string(value, "account_id")),
        instrument_id=InstrumentId(
            venue=VenueId(_string(instrument, "venue")),
            kind=InstrumentKind(_string(instrument, "kind")),
            symbol=_string(instrument, "symbol"),
        ),
        baseline_quantity=_quantity(value, "baseline_quantity"),
        intended_owned_delta=_quantity(value, "intended_owned_delta"),
        effective_from_ns=UnixNanos(_integer(value, "effective_from_ns")),
        source_snapshot_id=DecisionSnapshotId(
            _string(value, "source_snapshot_id")
        ),
        policy_version=_integer(value, "policy_version"),
    )


def _quantity(value: JsonObject, name: str) -> Quantity:
    body = _object(value, name)
    return Quantity(
        raw=_integer(body, "raw"),
        scale=_integer(body, "scale"),
    )


def _object(value: JsonObject, name: str) -> JsonObject:
    item = value[name]
    if not isinstance(item, dict):
        raise CarryCodecError(f"{name} must be an object")
    return item


def _object_list(value: JsonObject, name: str) -> tuple[JsonObject, ...]:
    items = value[name]
    if not isinstance(items, list) or any(
        not isinstance(item, dict) for item in items
    ):
        raise CarryCodecError(f"{name} must be an object list")
    return tuple(cast(JsonObject, item) for item in items)


def _string(
    value: JsonObject,
    name: str,
    *,
    allow_empty: bool = False,
) -> str:
    item = value[name]
    if (
        not isinstance(item, str)
        or (not allow_empty and not item)
        or item != item.strip()
    ):
        raise CarryCodecError(f"{name} must be a trimmed string")
    return item


def _integer(value: JsonObject, name: str) -> int:
    item = value[name]
    if not isinstance(item, int) or isinstance(item, bool):
        raise CarryCodecError(f"{name} must be an integer")
    return item


__all__ = [
    "CarryCodecError",
    "JsonObject",
    "JsonValue",
    "decode_carry_application_fact",
    "encode_carry_application_fact",
]
