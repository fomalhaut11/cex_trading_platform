"""Immutable generic Carry position contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import IntentId, OrderGroupId, Quantity, StrategyId, UnixNanos
from cex_quant.snapshots import DecisionSnapshotId

from .identifiers import ApplicationPositionId, CarryPairId
from .ownership import CarryLegOwnership

MAX_CARRY_REFERENCES = 64
MAX_CARRY_OWNERSHIP_LEGS = 16
MAX_CARRY_REASON_LENGTH = 512


class CarryLifecycle(StrEnum):
    PROPOSED = "proposed"
    OPENING = "opening"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    RECOVERY_REQUIRED = "recovery_required"
    HALTED = "halted"


class CarryHedgeState(StrEnum):
    UNKNOWN = "unknown"
    UNHEDGED = "unhedged"
    PARTIALLY_HEDGED = "partially_hedged"
    HEDGED = "hedged"


class CarryFinancialState(StrEnum):
    NOT_READY = "not_ready"
    PROVISIONAL = "provisional"
    RECONCILED = "reconciled"


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryHedgeAssessment:
    state: CarryHedgeState
    signed_residual_base_quantity: Quantity | None
    assessed_at_ns: UnixNanos
    policy_version: int
    reason: str = ""

    def __post_init__(self) -> None:
        if self.assessed_at_ns < 0:
            raise ValueError("hedge assessment time cannot be negative")
        if self.policy_version <= 0:
            raise ValueError("hedge policy version must be positive")
        _require_reason(self.reason)
        if self.state is CarryHedgeState.UNKNOWN:
            if self.signed_residual_base_quantity is not None:
                raise ValueError("UNKNOWN hedge cannot carry a residual")
            if not self.reason:
                raise ValueError("UNKNOWN hedge requires a reason")
        elif self.signed_residual_base_quantity is None:
            raise ValueError("known hedge state requires a residual")


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryPositionView:
    application_position_id: ApplicationPositionId
    strategy_id: StrategyId
    pair_id: CarryPairId
    revision: int
    lifecycle: CarryLifecycle
    hedge_state: CarryHedgeState
    financial_state: CarryFinancialState
    opening_snapshot_id: DecisionSnapshotId
    latest_snapshot_id: DecisionSnapshotId
    intent_ids: tuple[IntentId, ...]
    order_group_ids: tuple[OrderGroupId, ...]
    leg_ownership: tuple[CarryLegOwnership, ...]
    last_transition_ns: UnixNanos
    recovery_reason: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("application_position_id", self.application_position_id),
            ("strategy_id", self.strategy_id),
            ("pair_id", self.pair_id),
            ("opening_snapshot_id", self.opening_snapshot_id),
            ("latest_snapshot_id", self.latest_snapshot_id),
        ):
            _require_id(value, name=name)
        if self.revision <= 0:
            raise ValueError("Carry position revision must be positive")
        if self.last_transition_ns < 0:
            raise ValueError("Carry transition time cannot be negative")
        _require_bounded_unique(
            self.intent_ids,
            name="intent_ids",
            maximum=MAX_CARRY_REFERENCES,
        )
        _require_bounded_unique(
            self.order_group_ids,
            name="order_group_ids",
            maximum=MAX_CARRY_REFERENCES,
        )
        if not 1 <= len(self.leg_ownership) <= MAX_CARRY_OWNERSHIP_LEGS:
            raise ValueError("Carry ownership leg count is outside bounds")
        ownership_ids = tuple(item.ownership_id for item in self.leg_ownership)
        if len(set(ownership_ids)) != len(ownership_ids):
            raise ValueError("Carry ownership IDs must be unique")
        scopes = tuple(
            (item.account_id, item.instrument_id)
            for item in self.leg_ownership
        )
        if len(set(scopes)) != len(scopes):
            raise ValueError("Carry ownership scopes must be unique")
        if any(
            item.application_position_id != self.application_position_id
            for item in self.leg_ownership
        ):
            raise ValueError("Carry ownership belongs to another position")
        _require_reason(self.recovery_reason)
        if self.lifecycle in {
            CarryLifecycle.RECOVERY_REQUIRED,
            CarryLifecycle.HALTED,
        }:
            if not self.recovery_reason:
                raise ValueError(
                    "recovery-required or halted Carry needs a reason"
                )
        elif self.recovery_reason:
            raise ValueError(
                "recovery reason is only valid for recovery or halted state"
            )
        if (
            self.lifecycle in {CarryLifecycle.ACTIVE, CarryLifecycle.CLOSED}
            and self.hedge_state is not CarryHedgeState.HEDGED
        ):
            raise ValueError("active or closed Carry must be HEDGED")


def _require_bounded_unique(
    values: tuple[object, ...],
    *,
    name: str,
    maximum: int,
) -> None:
    if len(values) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _require_id(value, name=name)


def _require_id(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")
    if len(value) > 128:
        raise ValueError(f"{name} exceeds maximum length 128")


def _require_reason(value: str) -> None:
    if value and value != value.strip():
        raise ValueError("Carry reason must be trimmed")
    if len(value) > MAX_CARRY_REASON_LENGTH:
        raise ValueError(
            f"Carry reason exceeds maximum length {MAX_CARRY_REASON_LENGTH}"
        )


__all__ = [
    "MAX_CARRY_OWNERSHIP_LEGS",
    "MAX_CARRY_REASON_LENGTH",
    "MAX_CARRY_REFERENCES",
    "CarryFinancialState",
    "CarryHedgeAssessment",
    "CarryHedgeState",
    "CarryLifecycle",
    "CarryPositionView",
]
