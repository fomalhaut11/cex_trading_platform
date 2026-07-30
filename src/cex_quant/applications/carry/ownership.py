"""Immutable Carry ownership declarations and Accounting owner mapping."""

from __future__ import annotations

from dataclasses import dataclass

from cex_quant.accounting import EconomicOwnerRef, EconomicOwnerTypeRef
from cex_quant.core import AccountId, Quantity, UnixNanos
from cex_quant.instruments import InstrumentId
from cex_quant.snapshots import DecisionSnapshotId

from .identifiers import (
    ApplicationPositionId,
    CarryOwnershipId,
    deterministic_carry_ownership_id,
)

APPLICATION_POSITION_OWNER_TYPE = EconomicOwnerTypeRef(
    name="application.position",
    version=1,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryLegOwnership:
    """One immutable application claim over an account/instrument delta."""

    ownership_id: CarryOwnershipId
    application_position_id: ApplicationPositionId
    account_id: AccountId
    instrument_id: InstrumentId
    baseline_quantity: Quantity
    intended_owned_delta: Quantity
    effective_from_ns: UnixNanos
    source_snapshot_id: DecisionSnapshotId
    policy_version: int

    def __post_init__(self) -> None:
        for name, value in (
            ("ownership_id", self.ownership_id),
            ("application_position_id", self.application_position_id),
            ("account_id", self.account_id),
            ("source_snapshot_id", self.source_snapshot_id),
        ):
            _require_id(value, name=name)
        if self.intended_owned_delta.raw == 0:
            raise ValueError("Carry owned delta cannot be zero")
        if self.effective_from_ns < 0:
            raise ValueError("ownership effective time cannot be negative")
        if self.policy_version <= 0:
            raise ValueError("ownership policy version must be positive")

    @property
    def absolute_target(self) -> Quantity:
        return _add_quantity(
            self.baseline_quantity,
            self.intended_owned_delta,
        )


def create_carry_leg_ownership(
    *,
    application_position_id: ApplicationPositionId,
    account_id: AccountId,
    instrument_id: InstrumentId,
    baseline_quantity: Quantity,
    intended_owned_delta: Quantity,
    effective_from_ns: UnixNanos,
    source_snapshot_id: DecisionSnapshotId,
    policy_version: int,
) -> CarryLegOwnership:
    payload = {
        "account_id": str(account_id),
        "application_position_id": str(application_position_id),
        "baseline_quantity": _fixed(baseline_quantity),
        "effective_from_ns": int(effective_from_ns),
        "instrument": {
            "kind": instrument_id.kind.value,
            "symbol": instrument_id.symbol,
            "venue": str(instrument_id.venue),
        },
        "intended_owned_delta": _fixed(intended_owned_delta),
        "policy_version": policy_version,
        "source_snapshot_id": str(source_snapshot_id),
    }
    return CarryLegOwnership(
        ownership_id=deterministic_carry_ownership_id(payload),
        application_position_id=application_position_id,
        account_id=account_id,
        instrument_id=instrument_id,
        baseline_quantity=baseline_quantity,
        intended_owned_delta=intended_owned_delta,
        effective_from_ns=effective_from_ns,
        source_snapshot_id=source_snapshot_id,
        policy_version=policy_version,
    )


def accounting_owner_for_position(
    application_position_id: ApplicationPositionId,
) -> EconomicOwnerRef:
    _require_id(
        application_position_id,
        name="application_position_id",
    )
    return EconomicOwnerRef(
        owner_type=APPLICATION_POSITION_OWNER_TYPE,
        owner_id=str(application_position_id),
    )


def _add_quantity(first: Quantity, second: Quantity) -> Quantity:
    scale = max(first.scale, second.scale)
    return Quantity(
        raw=(
            first.raw * 10 ** (scale - first.scale)
            + second.raw * 10 ** (scale - second.scale)
        ),
        scale=scale,
    )


def _fixed(value: Quantity) -> dict[str, int]:
    return {"raw": value.raw, "scale": value.scale}


def _require_id(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")
    if len(value) > 128:
        raise ValueError(f"{name} exceeds maximum length 128")


__all__ = [
    "APPLICATION_POSITION_OWNER_TYPE",
    "CarryLegOwnership",
    "accounting_owner_for_position",
    "create_carry_leg_ownership",
]
