"""Generic bounded portfolio-target intents and objective metadata."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cex_quant.core import (
    AccountId,
    BasketLegId,
    DurationNanos,
    IntentId,
    ObjectiveTypeId,
    Quantity,
    StrategyId,
    UnixNanos,
)
from cex_quant.instruments import InstrumentId
from cex_quant.snapshots import DecisionSnapshotId

MIN_BASKET_LEGS = 2
MAX_BASKET_LEGS = 16
MAX_BASKET_VALIDITY_NS = 7 * 24 * 60 * 60 * 1_000_000_000
MAX_ID_LENGTH = 128
MAX_OBJECTIVE_TYPE_ID_LENGTH = 96
MAX_OWNER_LENGTH = 96
MAX_REASON_LENGTH = 512
MAX_DESCRIPTION_LENGTH = 512

_OBJECTIVE_TYPE_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
)


def _require_text(value: str, *, name: str, maximum: int) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}")


def _require_optional_text(value: str, *, name: str, maximum: int) -> None:
    if value and value != value.strip():
        raise ValueError(f"{name} must be trimmed")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}")


@dataclass(frozen=True, slots=True, kw_only=True, order=True)
class ObjectiveTypeRef:
    """Stable versioned classification for one application objective."""

    objective_type_id: ObjectiveTypeId
    version: int

    def __post_init__(self) -> None:
        identifier = str(self.objective_type_id)
        _require_text(
            identifier,
            name="objective_type_id",
            maximum=MAX_OBJECTIVE_TYPE_ID_LENGTH,
        )
        if _OBJECTIVE_TYPE_PATTERN.fullmatch(identifier) is None:
            raise ValueError(
                "objective_type_id must use lowercase ASCII namespace segments"
            )
        if self.version <= 0:
            raise ValueError("objective type version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectiveTypeDefinition:
    """Metadata-only registry entry; no callback or import path is allowed."""

    ref: ObjectiveTypeRef
    owner: str
    description: str = ""
    deprecated: bool = False

    def __post_init__(self) -> None:
        _require_text(self.owner, name="owner", maximum=MAX_OWNER_LENGTH)
        _require_optional_text(
            self.description,
            name="description",
            maximum=MAX_DESCRIPTION_LENGTH,
        )


class ObjectiveTypeRegistrationError(ValueError):
    """An Objective Type registry is malformed or lacks a reference."""


@dataclass(frozen=True, slots=True, init=False)
class ObjectiveTypeRegistry:
    """Immutable deterministic registry of Objective Type metadata."""

    _definitions: tuple[ObjectiveTypeDefinition, ...]
    _by_ref: Mapping[ObjectiveTypeRef, ObjectiveTypeDefinition]

    def __init__(
        self,
        definitions: tuple[ObjectiveTypeDefinition, ...],
    ) -> None:
        refs = tuple(item.ref for item in definitions)
        if refs != tuple(sorted(refs)):
            raise ObjectiveTypeRegistrationError(
                "objective definitions must be sorted by reference"
            )
        if len(set(refs)) != len(refs):
            raise ObjectiveTypeRegistrationError(
                "objective type references must be unique"
            )
        object.__setattr__(self, "_definitions", definitions)
        object.__setattr__(
            self,
            "_by_ref",
            MappingProxyType({item.ref: item for item in definitions}),
        )

    @property
    def definitions(self) -> tuple[ObjectiveTypeDefinition, ...]:
        return self._definitions

    def contains(self, ref: ObjectiveTypeRef) -> bool:
        return ref in self._by_ref

    def require(self, ref: ObjectiveTypeRef) -> ObjectiveTypeDefinition:
        try:
            return self._by_ref[ref]
        except KeyError as error:
            raise ObjectiveTypeRegistrationError(
                f"objective type {ref.objective_type_id!s}@{ref.version} "
                "is not registered"
            ) from error


@dataclass(frozen=True, slots=True, kw_only=True)
class BasketTargetLeg:
    """One desired signed account/instrument position within a Basket."""

    leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    target_quantity: Quantity
    reason: str = ""

    def __post_init__(self) -> None:
        _require_text(
            str(self.leg_id),
            name="leg_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(
            str(self.account_id),
            name="account_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(
            str(self.instrument_id.venue),
            name="instrument venue",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(
            self.instrument_id.symbol,
            name="instrument symbol",
            maximum=MAX_ID_LENGTH,
        )
        _require_optional_text(
            self.reason,
            name="leg reason",
            maximum=MAX_REASON_LENGTH,
        )


def canonical_leg_key(
    leg: BasketTargetLeg,
) -> tuple[str, str, str, str]:
    """Return the accepted semantic-neutral canonical leg ordering key."""

    return (
        str(leg.account_id),
        str(leg.instrument_id.venue),
        leg.instrument_id.kind.value,
        leg.instrument_id.symbol,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class BasketTargetIntent:
    """One immutable bounded portfolio target, not an execution plan."""

    intent_id: IntentId
    strategy_id: StrategyId
    decision_snapshot_id: DecisionSnapshotId
    objective: ObjectiveTypeRef
    legs: tuple[BasketTargetLeg, ...]
    decision_time_ns: UnixNanos
    valid_until_ns: UnixNanos
    policy_version: int
    reason: str = ""

    def __post_init__(self) -> None:
        _require_text(
            str(self.intent_id),
            name="intent_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(
            str(self.strategy_id),
            name="strategy_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(
            str(self.decision_snapshot_id),
            name="decision_snapshot_id",
            maximum=MAX_ID_LENGTH,
        )
        if not MIN_BASKET_LEGS <= len(self.legs) <= MAX_BASKET_LEGS:
            raise ValueError(
                f"Basket requires {MIN_BASKET_LEGS} to "
                f"{MAX_BASKET_LEGS} legs"
            )
        leg_ids = tuple(item.leg_id for item in self.legs)
        if len(set(leg_ids)) != len(leg_ids):
            raise ValueError("Basket leg IDs must be unique")
        scope_keys = tuple(
            (item.account_id, item.instrument_id) for item in self.legs
        )
        if len(set(scope_keys)) != len(scope_keys):
            raise ValueError(
                "Basket account/instrument scopes must be unique"
            )
        if self.legs != tuple(sorted(self.legs, key=canonical_leg_key)):
            raise ValueError(
                "Basket legs must use canonical account/instrument order"
            )
        if self.decision_time_ns < 0:
            raise ValueError("decision_time_ns cannot be negative")
        if self.valid_until_ns < 0:
            raise ValueError("valid_until_ns cannot be negative")
        if self.valid_until_ns < self.decision_time_ns:
            raise ValueError(
                "valid_until_ns cannot precede decision_time_ns"
            )
        if (
            self.valid_until_ns - self.decision_time_ns
            > MAX_BASKET_VALIDITY_NS
        ):
            raise ValueError("Basket validity exceeds hard safety limit")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        _require_optional_text(
            self.reason,
            name="Basket reason",
            maximum=MAX_REASON_LENGTH,
        )


class BasketIntentPolicyError(ValueError):
    """A Basket violates deployment admission policy."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BasketIntentPolicy:
    """Deployment bounds below the immutable contract hard limits."""

    max_legs: int
    max_validity_ns: DurationNanos
    allowed_objectives: tuple[ObjectiveTypeRef, ...]

    def __post_init__(self) -> None:
        if not MIN_BASKET_LEGS <= self.max_legs <= MAX_BASKET_LEGS:
            raise ValueError(
                f"max_legs must be between {MIN_BASKET_LEGS} and "
                f"{MAX_BASKET_LEGS}"
            )
        if not 0 < self.max_validity_ns <= MAX_BASKET_VALIDITY_NS:
            raise ValueError("max_validity_ns is outside hard safety limits")
        if self.allowed_objectives != tuple(sorted(self.allowed_objectives)):
            raise ValueError("allowed_objectives must be sorted")
        if len(set(self.allowed_objectives)) != len(
            self.allowed_objectives
        ):
            raise ValueError("allowed_objectives must be unique")

    def validate(
        self,
        intent: BasketTargetIntent,
        *,
        registry: ObjectiveTypeRegistry,
    ) -> None:
        registry.require(intent.objective)
        if intent.objective not in self.allowed_objectives:
            raise BasketIntentPolicyError(
                "Basket objective is not allowed by policy"
            )
        if len(intent.legs) > self.max_legs:
            raise BasketIntentPolicyError(
                "Basket leg count exceeds deployment policy"
            )
        if (
            intent.valid_until_ns - intent.decision_time_ns
            > self.max_validity_ns
        ):
            raise BasketIntentPolicyError(
                "Basket validity exceeds deployment policy"
            )


def deterministic_basket_leg_id(
    *,
    decision_snapshot_id: DecisionSnapshotId,
    account_id: AccountId,
    instrument_id: InstrumentId,
) -> BasketLegId:
    """Derive one replay-stable leg identity from its canonical scope."""

    payload = {
        "account_id": str(account_id),
        "decision_snapshot_id": str(decision_snapshot_id),
        "instrument": {
            "kind": instrument_id.kind.value,
            "symbol": instrument_id.symbol,
            "venue": str(instrument_id.venue),
        },
    }
    return BasketLegId(_sha256_payload(payload))


def deterministic_basket_intent_id(
    *,
    strategy_id: StrategyId,
    decision_snapshot_id: DecisionSnapshotId,
    objective: ObjectiveTypeRef,
    legs: tuple[BasketTargetLeg, ...],
    decision_time_ns: UnixNanos,
    valid_until_ns: UnixNanos,
    policy_version: int,
    reason: str = "",
) -> IntentId:
    """Derive one replay-stable identity from the complete Basket content."""

    ordered = tuple(sorted(legs, key=canonical_leg_key))
    payload = {
        "decision_snapshot_id": str(decision_snapshot_id),
        "decision_time_ns": int(decision_time_ns),
        "legs": [
            {
                "account_id": str(item.account_id),
                "instrument": {
                    "kind": item.instrument_id.kind.value,
                    "symbol": item.instrument_id.symbol,
                    "venue": str(item.instrument_id.venue),
                },
                "leg_id": str(item.leg_id),
                "reason": item.reason,
                "target_quantity": {
                    "raw": item.target_quantity.raw,
                    "scale": item.target_quantity.scale,
                },
            }
            for item in ordered
        ],
        "objective": {
            "id": str(objective.objective_type_id),
            "version": objective.version,
        },
        "policy_version": policy_version,
        "reason": reason,
        "strategy_id": str(strategy_id),
        "valid_until_ns": int(valid_until_ns),
    }
    return IntentId(_sha256_payload(payload))


def create_basket_target_intent(
    *,
    strategy_id: StrategyId,
    decision_snapshot_id: DecisionSnapshotId,
    objective: ObjectiveTypeRef,
    legs: tuple[BasketTargetLeg, ...],
    decision_time_ns: UnixNanos,
    valid_until_ns: UnixNanos,
    policy_version: int,
    reason: str = "",
    intent_id: IntentId | None = None,
) -> BasketTargetIntent:
    """Sort candidates before constructing the immutable public contract."""

    ordered = tuple(sorted(legs, key=canonical_leg_key))
    resolved_intent_id = intent_id
    if resolved_intent_id is None:
        resolved_intent_id = deterministic_basket_intent_id(
            strategy_id=strategy_id,
            decision_snapshot_id=decision_snapshot_id,
            objective=objective,
            legs=ordered,
            decision_time_ns=decision_time_ns,
            valid_until_ns=valid_until_ns,
            policy_version=policy_version,
            reason=reason,
        )
    return BasketTargetIntent(
        intent_id=resolved_intent_id,
        strategy_id=strategy_id,
        decision_snapshot_id=decision_snapshot_id,
        objective=objective,
        legs=ordered,
        decision_time_ns=decision_time_ns,
        valid_until_ns=valid_until_ns,
        policy_version=policy_version,
        reason=reason,
    )


def _sha256_payload(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "MAX_BASKET_LEGS",
    "MAX_BASKET_VALIDITY_NS",
    "MIN_BASKET_LEGS",
    "BasketIntentPolicy",
    "BasketIntentPolicyError",
    "BasketTargetIntent",
    "BasketTargetLeg",
    "ObjectiveTypeDefinition",
    "ObjectiveTypeRef",
    "ObjectiveTypeRegistrationError",
    "ObjectiveTypeRegistry",
    "canonical_leg_key",
    "create_basket_target_intent",
    "deterministic_basket_intent_id",
    "deterministic_basket_leg_id",
]
