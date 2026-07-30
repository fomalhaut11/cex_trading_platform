"""Carry economic recovery proposals, never execution instructions."""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import UnixNanos
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import BasketTargetIntent

from .identifiers import ApplicationPositionId
from .model import MAX_CARRY_REASON_LENGTH


class CarryRecoveryKind(StrEnum):
    WAIT_FOR_FACT_RECONCILIATION = "wait_for_fact_reconciliation"
    RESTORE_CARRY_TARGET = "restore_carry_target"
    REDUCE_TO_SAFE_HEDGE = "reduce_to_safe_hedge"
    FLATTEN_TO_BASELINE = "flatten_to_baseline"
    HALT_FOR_OPERATOR = "halt_for_operator"


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryRecoveryProposal:
    """A fresh economic preference with no OMS or Risk authority."""

    application_position_id: ApplicationPositionId
    kind: CarryRecoveryKind
    source_snapshot_id: DecisionSnapshotId
    proposed_target: BasketTargetIntent | None
    proposed_at_ns: UnixNanos
    policy_version: int
    reason: str

    def __post_init__(self) -> None:
        if not self.application_position_id:
            raise ValueError("recovery application_position_id cannot be empty")
        if not self.source_snapshot_id:
            raise ValueError("recovery source_snapshot_id cannot be empty")
        if self.proposed_at_ns < 0:
            raise ValueError("recovery proposal time cannot be negative")
        if self.policy_version <= 0:
            raise ValueError("recovery policy version must be positive")
        if (
            not self.reason
            or self.reason != self.reason.strip()
            or len(self.reason) > MAX_CARRY_REASON_LENGTH
        ):
            raise ValueError("recovery reason must be non-empty and bounded")
        target_required = self.kind in {
            CarryRecoveryKind.RESTORE_CARRY_TARGET,
            CarryRecoveryKind.REDUCE_TO_SAFE_HEDGE,
            CarryRecoveryKind.FLATTEN_TO_BASELINE,
        }
        if target_required != (self.proposed_target is not None):
            raise ValueError(
                "exposure-changing recovery requires exactly one Basket target"
            )
        if (
            self.proposed_target is not None
            and self.proposed_target.decision_snapshot_id
            != self.source_snapshot_id
        ):
            raise ValueError(
                "recovery Basket must reference the proposal Snapshot"
            )


__all__ = [
    "CarryRecoveryKind",
    "CarryRecoveryProposal",
]
