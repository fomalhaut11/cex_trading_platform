"""Immutable bounded Execution Stage contracts accepted by ADR-015."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    ClientOrderId,
    ExecutionStageId,
    ExecutionStagePermitId,
    OrderGroupId,
    UnixNanos,
)
from cex_quant.snapshots import DecisionSnapshotId

from .group_model import (
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionPlanRef,
    execution_action_checksum,
)

MAX_EXECUTION_STAGE_ACTIONS = 16
MAX_EXECUTION_STAGE_DISPATCH_WIDTH = 16

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ExecutionStageState(StrEnum):
    """Derived execution-control state; never economic hedge state."""

    PREPARED = "prepared"
    ACTIVE = "active"
    RECOVERY_REQUIRED = "recovery_required"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStage:
    """One exact bounded set of Actions proposed from one group revision."""

    stage_id: ExecutionStageId
    group_id: OrderGroupId
    base_group_revision: int
    execution_plan: ExecutionPlanRef
    actions: tuple[ExecutionAction, ...]
    dispatch_width: int
    created_at_ns: UnixNanos

    def __post_init__(self) -> None:
        _require_checksum(str(self.stage_id), name="stage_id")
        _require_text(str(self.group_id), name="group_id")
        if self.base_group_revision <= 0:
            raise ValueError("Stage base group revision must be positive")
        if not 1 <= len(self.actions) <= MAX_EXECUTION_STAGE_ACTIONS:
            raise ValueError("Stage action count is outside hard bounds")
        if not 1 <= self.dispatch_width <= len(self.actions):
            raise ValueError("Stage dispatch width must be within Stage width")
        if self.dispatch_width > MAX_EXECUTION_STAGE_DISPATCH_WIDTH:
            raise ValueError("Stage dispatch width exceeds hard bound")
        if self.created_at_ns < 0:
            raise ValueError("Stage creation time cannot be negative")
        action_ids = tuple(str(item.action_id) for item in self.actions)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("Stage Action identities must be unique")
        leg_ids = tuple(str(item.basket_leg_id) for item in self.actions)
        if len(set(leg_ids)) != len(leg_ids):
            raise ValueError("Stage may contain at most one Action per Basket leg")
        for action in self.actions:
            if (
                action.group_id != self.group_id
                or action.expected_group_revision != self.base_group_revision
                or action.execution_plan != self.execution_plan
            ):
                raise ValueError("Stage Action does not match Stage identity")
            if action.created_at_ns > self.created_at_ns:
                raise ValueError("Stage cannot precede one of its Actions")
        if self.stage_id != deterministic_execution_stage_id(
            group_id=self.group_id,
            base_group_revision=self.base_group_revision,
            execution_plan=self.execution_plan,
            actions=self.actions,
            dispatch_width=self.dispatch_width,
        ):
            raise ValueError("stage_id does not match Stage content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStagePermit:
    """Finite Portfolio Risk authority bound to one complete exact Stage."""

    permit_id: ExecutionStagePermitId
    stage_id: ExecutionStageId
    stage_checksum: str
    group_id: OrderGroupId
    base_group_revision: int
    action_permits: tuple[ExecutionActionPermit, ...]
    partial_execution_envelope_checksum: str
    risk_snapshot_id: DecisionSnapshotId
    issued_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int

    def __post_init__(self) -> None:
        _require_checksum(str(self.permit_id), name="stage_permit_id")
        _require_checksum(str(self.stage_id), name="stage_id")
        _require_checksum(self.stage_checksum, name="stage_checksum")
        _require_text(str(self.group_id), name="group_id")
        _require_checksum(
            self.partial_execution_envelope_checksum,
            name="partial_execution_envelope_checksum",
        )
        _require_text(str(self.risk_snapshot_id), name="risk_snapshot_id")
        if self.base_group_revision <= 0:
            raise ValueError("Stage permit base revision must be positive")
        if not 1 <= len(self.action_permits) <= MAX_EXECUTION_STAGE_ACTIONS:
            raise ValueError("Stage permit Action count is outside hard bounds")
        if self.issued_at_ns < 0 or self.valid_until_ns < self.issued_at_ns:
            raise ValueError("Stage permit validity interval is invalid")
        if self.risk_policy_version <= 0:
            raise ValueError("Stage permit Risk policy version must be positive")
        action_ids = tuple(str(item.action_id) for item in self.action_permits)
        permit_ids = tuple(str(item.permit_id) for item in self.action_permits)
        if len(set(action_ids)) != len(action_ids) or len(set(permit_ids)) != len(
            permit_ids
        ):
            raise ValueError("Stage Action permits must have unique identities")
        for permit in self.action_permits:
            if (
                permit.group_id != self.group_id
                or permit.expected_group_revision != self.base_group_revision
                or permit.risk_snapshot_id != self.risk_snapshot_id
                or permit.risk_policy_version != self.risk_policy_version
                or permit.issued_at_ns != self.issued_at_ns
                or permit.valid_until_ns != self.valid_until_ns
            ):
                raise ValueError("Action permit does not match Stage permit")
        expected = deterministic_execution_stage_permit_id(
            stage_id=self.stage_id,
            stage_checksum=self.stage_checksum,
            action_permits=self.action_permits,
            partial_execution_envelope_checksum=(
                self.partial_execution_envelope_checksum
            ),
            risk_snapshot_id=self.risk_snapshot_id,
            issued_at_ns=self.issued_at_ns,
            valid_until_ns=self.valid_until_ns,
            risk_policy_version=self.risk_policy_version,
        )
        if self.permit_id != expected:
            raise ValueError("Stage permit identity does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStageView:
    stage: ExecutionStage
    permit_id: ExecutionStagePermitId
    child_order_ids: tuple[ClientOrderId, ...]
    state: ExecutionStageState
    last_transition_ns: UnixNanos

    def __post_init__(self) -> None:
        _require_checksum(str(self.permit_id), name="stage_permit_id")
        if len(self.child_order_ids) != len(self.stage.actions):
            raise ValueError("Stage view Child vector width mismatch")
        if len(set(map(str, self.child_order_ids))) != len(self.child_order_ids):
            raise ValueError("Stage view Child identities must be unique")
        if self.last_transition_ns < self.stage.created_at_ns:
            raise ValueError("Stage view transition cannot precede creation")


def create_execution_stage(
    *,
    group_id: OrderGroupId,
    base_group_revision: int,
    execution_plan: ExecutionPlanRef,
    actions: tuple[ExecutionAction, ...],
    dispatch_width: int,
    created_at_ns: UnixNanos,
) -> ExecutionStage:
    """Construct a Stage with its deterministic identity."""

    return ExecutionStage(
        stage_id=deterministic_execution_stage_id(
            group_id=group_id,
            base_group_revision=base_group_revision,
            execution_plan=execution_plan,
            actions=actions,
            dispatch_width=dispatch_width,
        ),
        group_id=group_id,
        base_group_revision=base_group_revision,
        execution_plan=execution_plan,
        actions=actions,
        dispatch_width=dispatch_width,
        created_at_ns=created_at_ns,
    )


def deterministic_execution_stage_id(
    *,
    group_id: OrderGroupId,
    base_group_revision: int,
    execution_plan: ExecutionPlanRef,
    actions: tuple[ExecutionAction, ...],
    dispatch_width: int,
) -> ExecutionStageId:
    if base_group_revision <= 0:
        raise ValueError("Stage base group revision must be positive")
    return ExecutionStageId(
        _sha256(
            {
                "action_checksums": [
                    execution_action_checksum(item) for item in actions
                ],
                "base_group_revision": base_group_revision,
                "dispatch_width": dispatch_width,
                "execution_plan": _execution_plan_payload(execution_plan),
                "group_id": str(group_id),
            }
        )
    )


def execution_stage_checksum(stage: ExecutionStage) -> str:
    return _sha256(
        {
            "actions": [execution_action_checksum(item) for item in stage.actions],
            "base_group_revision": stage.base_group_revision,
            "created_at_ns": int(stage.created_at_ns),
            "dispatch_width": stage.dispatch_width,
            "execution_plan": _execution_plan_payload(stage.execution_plan),
            "group_id": str(stage.group_id),
            "stage_id": str(stage.stage_id),
        }
    )


def create_execution_stage_permit(
    *,
    stage: ExecutionStage,
    action_permits: tuple[ExecutionActionPermit, ...],
    partial_execution_envelope_checksum: str,
    risk_snapshot_id: DecisionSnapshotId,
    issued_at_ns: UnixNanos,
    valid_until_ns: UnixNanos,
    risk_policy_version: int,
) -> ExecutionStagePermit:
    stage_checksum = execution_stage_checksum(stage)
    return ExecutionStagePermit(
        permit_id=deterministic_execution_stage_permit_id(
            stage_id=stage.stage_id,
            stage_checksum=stage_checksum,
            action_permits=action_permits,
            partial_execution_envelope_checksum=(
                partial_execution_envelope_checksum
            ),
            risk_snapshot_id=risk_snapshot_id,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
            risk_policy_version=risk_policy_version,
        ),
        stage_id=stage.stage_id,
        stage_checksum=stage_checksum,
        group_id=stage.group_id,
        base_group_revision=stage.base_group_revision,
        action_permits=action_permits,
        partial_execution_envelope_checksum=partial_execution_envelope_checksum,
        risk_snapshot_id=risk_snapshot_id,
        issued_at_ns=issued_at_ns,
        valid_until_ns=valid_until_ns,
        risk_policy_version=risk_policy_version,
    )


def deterministic_execution_stage_permit_id(
    *,
    stage_id: ExecutionStageId,
    stage_checksum: str,
    action_permits: tuple[ExecutionActionPermit, ...],
    partial_execution_envelope_checksum: str,
    risk_snapshot_id: DecisionSnapshotId,
    issued_at_ns: UnixNanos,
    valid_until_ns: UnixNanos,
    risk_policy_version: int,
) -> ExecutionStagePermitId:
    return ExecutionStagePermitId(
        _sha256(
            {
                "action_permits": [
                    {
                        "action_checksum": item.action_checksum,
                        "action_id": str(item.action_id),
                        "permit_id": str(item.permit_id),
                    }
                    for item in action_permits
                ],
                "issued_at_ns": int(issued_at_ns),
                "partial_execution_envelope_checksum": (
                    partial_execution_envelope_checksum
                ),
                "risk_policy_version": risk_policy_version,
                "risk_snapshot_id": str(risk_snapshot_id),
                "stage_checksum": stage_checksum,
                "stage_id": str(stage_id),
                "valid_until_ns": int(valid_until_ns),
            }
        )
    )


def validate_execution_stage_permit(
    stage: ExecutionStage,
    permit: ExecutionStagePermit,
) -> None:
    if (
        permit.stage_id != stage.stage_id
        or permit.stage_checksum != execution_stage_checksum(stage)
        or permit.group_id != stage.group_id
        or permit.base_group_revision != stage.base_group_revision
        or len(permit.action_permits) != len(stage.actions)
    ):
        raise ValueError("Stage permit does not match Stage")
    for action, action_permit in zip(
        stage.actions,
        permit.action_permits,
        strict=True,
    ):
        if (
            action_permit.action_id != action.action_id
            or action_permit.action_checksum != execution_action_checksum(action)
        ):
            raise ValueError("Stage Action permit vector does not match Actions")


def _execution_plan_payload(plan: ExecutionPlanRef) -> object:
    return {
        "id": str(plan.execution_plan_id),
        "parameters_checksum": plan.parameters_checksum,
        "version": plan.version,
    }


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_checksum(value: str, *, name: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 checksum")


def _require_text(value: str, *, name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")


__all__ = [
    "MAX_EXECUTION_STAGE_ACTIONS",
    "MAX_EXECUTION_STAGE_DISPATCH_WIDTH",
    "ExecutionStage",
    "ExecutionStagePermit",
    "ExecutionStageState",
    "ExecutionStageView",
    "create_execution_stage",
    "create_execution_stage_permit",
    "deterministic_execution_stage_id",
    "deterministic_execution_stage_permit_id",
    "execution_stage_checksum",
    "validate_execution_stage_permit",
]
