"""Immutable append-only facts for the Carry economic aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from cex_quant.core import (
    IntentId,
    OrderGroupId,
    Quantity,
    StrategyId,
    UnixNanos,
)
from cex_quant.snapshots import DecisionSnapshotId

from .identifiers import (
    ApplicationPositionId,
    CarryApplicationFactId,
    CarryPairId,
    deterministic_carry_fact_id,
)
from .model import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
)
from .ownership import CarryLegOwnership


class CarryApplicationFactKind(StrEnum):
    POSITION_CREATED = "position_created"
    INTENT_LINKED = "intent_linked"
    ORDER_GROUP_LINKED = "order_group_linked"
    OWNERSHIP_REGISTERED = "ownership_registered"
    STATE_CHANGED = "state_changed"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryPositionCreated:
    strategy_id: StrategyId
    pair_id: CarryPairId
    opening_snapshot_id: DecisionSnapshotId
    ownership: tuple[CarryLegOwnership, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryIntentLinked:
    intent_id: IntentId
    source_snapshot_id: DecisionSnapshotId


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryOrderGroupLinked:
    order_group_id: OrderGroupId
    source_snapshot_id: DecisionSnapshotId


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryOwnershipRegistered:
    ownership: CarryLegOwnership


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryStateChanged:
    lifecycle: CarryLifecycle
    hedge_state: CarryHedgeState
    financial_state: CarryFinancialState
    source_snapshot_id: DecisionSnapshotId
    reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryRecoveryRequired:
    source_snapshot_id: DecisionSnapshotId
    reason: str


CarryFactPayload: TypeAlias = (
    CarryPositionCreated
    | CarryIntentLinked
    | CarryOrderGroupLinked
    | CarryOwnershipRegistered
    | CarryStateChanged
    | CarryRecoveryRequired
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryApplicationFact:
    fact_id: CarryApplicationFactId
    application_position_id: ApplicationPositionId
    expected_revision: int
    new_revision: int
    occurred_at_ns: UnixNanos
    recorded_at_ns: UnixNanos
    policy_version: int
    schema_version: int
    payload: CarryFactPayload

    def __post_init__(self) -> None:
        if not self.fact_id or not self.application_position_id:
            raise ValueError("Carry fact identities cannot be empty")
        if self.expected_revision < 0:
            raise ValueError("Carry expected revision cannot be negative")
        if self.new_revision != self.expected_revision + 1:
            raise ValueError("Carry fact must advance exactly one revision")
        if self.occurred_at_ns < 0 or self.recorded_at_ns < 0:
            raise ValueError("Carry fact times cannot be negative")
        if self.recorded_at_ns < self.occurred_at_ns:
            raise ValueError("Carry fact cannot be recorded before occurrence")
        if self.policy_version <= 0 or self.schema_version <= 0:
            raise ValueError("Carry fact versions must be positive")
        ownership = _payload_ownership(self.payload)
        if any(
            item.application_position_id != self.application_position_id
            for item in ownership
        ):
            raise ValueError("Carry fact ownership belongs to another position")

    @property
    def kind(self) -> CarryApplicationFactKind:
        return _kind(self.payload)


def create_carry_application_fact(
    *,
    application_position_id: ApplicationPositionId,
    expected_revision: int,
    occurred_at_ns: UnixNanos,
    recorded_at_ns: UnixNanos,
    policy_version: int,
    payload: CarryFactPayload,
    schema_version: int = 1,
) -> CarryApplicationFact:
    new_revision = expected_revision + 1
    identity_payload = {
        "application_position_id": str(application_position_id),
        "expected_revision": expected_revision,
        "new_revision": new_revision,
        "occurred_at_ns": int(occurred_at_ns),
        "payload": encode_carry_fact_payload(payload),
        "policy_version": policy_version,
        "recorded_at_ns": int(recorded_at_ns),
        "schema_version": schema_version,
    }
    return CarryApplicationFact(
        fact_id=deterministic_carry_fact_id(identity_payload),
        application_position_id=application_position_id,
        expected_revision=expected_revision,
        new_revision=new_revision,
        occurred_at_ns=occurred_at_ns,
        recorded_at_ns=recorded_at_ns,
        policy_version=policy_version,
        schema_version=schema_version,
        payload=payload,
    )


def encode_carry_fact_payload(payload: CarryFactPayload) -> dict[str, object]:
    if isinstance(payload, CarryPositionCreated):
        body: dict[str, object] = {
            "strategy_id": str(payload.strategy_id),
            "pair_id": str(payload.pair_id),
            "opening_snapshot_id": str(payload.opening_snapshot_id),
            "ownership": [_ownership(item) for item in payload.ownership],
        }
    elif isinstance(payload, CarryIntentLinked):
        body = {
            "intent_id": str(payload.intent_id),
            "source_snapshot_id": str(payload.source_snapshot_id),
        }
    elif isinstance(payload, CarryOrderGroupLinked):
        body = {
            "order_group_id": str(payload.order_group_id),
            "source_snapshot_id": str(payload.source_snapshot_id),
        }
    elif isinstance(payload, CarryOwnershipRegistered):
        body = {"ownership": _ownership(payload.ownership)}
    elif isinstance(payload, CarryStateChanged):
        body = {
            "lifecycle": payload.lifecycle.value,
            "hedge_state": payload.hedge_state.value,
            "financial_state": payload.financial_state.value,
            "source_snapshot_id": str(payload.source_snapshot_id),
            "reason": payload.reason,
        }
    else:
        body = {
            "source_snapshot_id": str(payload.source_snapshot_id),
            "reason": payload.reason,
        }
    return {"kind": _kind(payload).value, "body": body}


def _kind(payload: CarryFactPayload) -> CarryApplicationFactKind:
    if isinstance(payload, CarryPositionCreated):
        return CarryApplicationFactKind.POSITION_CREATED
    if isinstance(payload, CarryIntentLinked):
        return CarryApplicationFactKind.INTENT_LINKED
    if isinstance(payload, CarryOrderGroupLinked):
        return CarryApplicationFactKind.ORDER_GROUP_LINKED
    if isinstance(payload, CarryOwnershipRegistered):
        return CarryApplicationFactKind.OWNERSHIP_REGISTERED
    if isinstance(payload, CarryStateChanged):
        return CarryApplicationFactKind.STATE_CHANGED
    return CarryApplicationFactKind.RECOVERY_REQUIRED


def _payload_ownership(
    payload: CarryFactPayload,
) -> tuple[CarryLegOwnership, ...]:
    if isinstance(payload, CarryPositionCreated):
        return payload.ownership
    if isinstance(payload, CarryOwnershipRegistered):
        return (payload.ownership,)
    return ()


def _ownership(value: CarryLegOwnership) -> dict[str, object]:
    return {
        "ownership_id": str(value.ownership_id),
        "application_position_id": str(value.application_position_id),
        "account_id": str(value.account_id),
        "instrument_id": {
            "venue": str(value.instrument_id.venue),
            "kind": value.instrument_id.kind.value,
            "symbol": value.instrument_id.symbol,
        },
        "baseline_quantity": _quantity(value.baseline_quantity),
        "intended_owned_delta": _quantity(value.intended_owned_delta),
        "effective_from_ns": int(value.effective_from_ns),
        "source_snapshot_id": str(value.source_snapshot_id),
        "policy_version": value.policy_version,
    }


def _quantity(value: Quantity) -> dict[str, int]:
    return {"raw": value.raw, "scale": value.scale}


__all__ = [
    "CarryApplicationFact",
    "CarryApplicationFactKind",
    "CarryFactPayload",
    "CarryIntentLinked",
    "CarryOrderGroupLinked",
    "CarryOwnershipRegistered",
    "CarryPositionCreated",
    "CarryRecoveryRequired",
    "CarryStateChanged",
    "create_carry_application_fact",
    "encode_carry_fact_payload",
]
