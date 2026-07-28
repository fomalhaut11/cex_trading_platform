"""Immutable generic Order Group contracts accepted by ADR-011.

These contracts describe execution control only. They deliberately contain no
Delta, basis, margin, liquidation, hedging or application-specific state.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    BasketLegId,
    ClientOrderId,
    ExecutionPermitId,
    ExecutionPlanId,
    GroupActionId,
    IntentId,
    OrderGroupId,
    PortfolioApprovalId,
    Price,
    Quantity,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    BasketTargetIntent,
    basket_target_intent_checksum,
)

from .model import (
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
    _validate_order_fields,
)

MAX_GROUP_CHILDREN = 64
MAX_CHILD_ATTEMPTS_PER_LEG = 8
MAX_TECHNICAL_RETRANSMISSIONS = 1
MAX_RETAINED_ORDER_GROUPS = 4_096
MAX_ACTIVE_ORDER_GROUPS_PER_STRATEGY_ACCOUNT = 4_096
MAX_GROUP_REASON_LENGTH = 512
MAX_GROUP_ID_LENGTH = 128

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class OrderGroupStatus(StrEnum):
    """Durable execution-control state, not economic hedge state."""

    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RECOVERY_REQUIRED = "recovery_required"
    CLOSING = "closing"
    CLOSED = "closed"


class OrderGroupCloseOutcome(StrEnum):
    TARGET_CONFIRMED = "target_confirmed"
    ABORTED = "aborted"
    FAILED = "failed"


class ExecutionActionState(StrEnum):
    """Durable action/transmission state after a proposal is authorized."""

    PREPARED = "prepared"
    TRANSMITTING = "transmitting"
    RETRY_ELIGIBLE = "retry_eligible"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupLimits:
    """Deployment limits constrained by immutable ADR-011 hard caps."""

    max_child_attempts_per_leg: int = MAX_CHILD_ATTEMPTS_PER_LEG
    max_children_per_group: int = MAX_GROUP_CHILDREN
    max_retained_groups: int = MAX_RETAINED_ORDER_GROUPS
    max_active_groups_per_strategy_account: int = (
        MAX_ACTIVE_ORDER_GROUPS_PER_STRATEGY_ACCOUNT
    )

    def __post_init__(self) -> None:
        _require_bounded_positive_int(
            self.max_child_attempts_per_leg,
            name="max_child_attempts_per_leg",
            maximum=MAX_CHILD_ATTEMPTS_PER_LEG,
        )
        _require_bounded_positive_int(
            self.max_children_per_group,
            name="max_children_per_group",
            maximum=MAX_GROUP_CHILDREN,
        )
        _require_bounded_positive_int(
            self.max_retained_groups,
            name="max_retained_groups",
            maximum=MAX_RETAINED_ORDER_GROUPS,
        )
        _require_bounded_positive_int(
            self.max_active_groups_per_strategy_account,
            name="max_active_groups_per_strategy_account",
            maximum=MAX_ACTIVE_ORDER_GROUPS_PER_STRATEGY_ACCOUNT,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPlanRef:
    """Immutable reference to a registered execution plan and parameters."""

    execution_plan_id: ExecutionPlanId
    version: int
    parameters_checksum: str

    def __post_init__(self) -> None:
        _require_id(self.execution_plan_id, name="execution_plan_id")
        if self.version <= 0:
            raise ValueError("execution plan version must be positive")
        _require_checksum(
            self.parameters_checksum,
            name="parameters_checksum",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupAdmission:
    """Whole-Basket admission evidence; never a child submit permission."""

    approval_id: PortfolioApprovalId
    basket: BasketTargetIntent
    basket_checksum: str
    approved_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int

    def __post_init__(self) -> None:
        _require_id(self.approval_id, name="approval_id")
        _require_checksum(self.basket_checksum, name="basket_checksum")
        if self.basket_checksum != basket_target_intent_checksum(self.basket):
            raise ValueError("basket_checksum does not match Basket content")
        if self.approved_at_ns < self.basket.decision_time_ns:
            raise ValueError("admission cannot precede Basket decision")
        if self.valid_until_ns < self.approved_at_ns:
            raise ValueError("admission expiry cannot precede approval")
        if self.valid_until_ns > self.basket.valid_until_ns:
            raise ValueError("admission cannot outlive Basket")
        if self.risk_policy_version <= 0:
            raise ValueError("risk_policy_version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionAction:
    """One exact proposed child attempt; it contains no execution authority."""

    group_id: OrderGroupId
    expected_group_revision: int
    action_id: GroupActionId
    basket_leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    time_in_force: TimeInForce
    limit_price: Price | None
    stop_price: Price | None
    reduce_only: bool
    post_only: bool
    position_side: PositionSide
    execution_plan: ExecutionPlanRef
    created_at_ns: UnixNanos

    def __post_init__(self) -> None:
        _require_id(self.group_id, name="group_id")
        _require_checksum(str(self.action_id), name="action_id")
        _require_id(self.basket_leg_id, name="basket_leg_id")
        _require_id(self.account_id, name="account_id")
        if self.expected_group_revision <= 0:
            raise ValueError("expected_group_revision must be positive")
        if self.created_at_ns < 0:
            raise ValueError("created_at_ns cannot be negative")
        _validate_order_fields(
            instrument_id=self.instrument_id,
            order_type=self.order_type,
            quantity=self.quantity,
            time_in_force=self.time_in_force,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            reduce_only=self.reduce_only,
            post_only=self.post_only,
            position_side=self.position_side,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionActionPermit:
    """Finite ADR-012-facing evidence bound to one exact action."""

    permit_id: ExecutionPermitId
    group_id: OrderGroupId
    expected_group_revision: int
    action_id: GroupActionId
    action_checksum: str
    risk_snapshot_id: DecisionSnapshotId
    issued_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int

    def __post_init__(self) -> None:
        _require_id(self.permit_id, name="permit_id")
        _require_id(self.group_id, name="group_id")
        _require_checksum(str(self.action_id), name="action_id")
        _require_id(self.risk_snapshot_id, name="risk_snapshot_id")
        _require_checksum(self.action_checksum, name="action_checksum")
        if self.expected_group_revision <= 0:
            raise ValueError("expected_group_revision must be positive")
        if self.issued_at_ns < 0:
            raise ValueError("issued_at_ns cannot be negative")
        if self.valid_until_ns < self.issued_at_ns:
            raise ValueError("permit expiry cannot precede issuance")
        if self.risk_policy_version <= 0:
            raise ValueError("risk_policy_version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionActionView:
    action: ExecutionAction
    permit_id: ExecutionPermitId
    child_order_id: ClientOrderId
    state: ExecutionActionState
    transport_attempts: int
    last_transition_ns: UnixNanos
    venue_order_id: VenueOrderId | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        _require_id(self.permit_id, name="permit_id")
        _require_id(self.child_order_id, name="child_order_id")
        if self.transport_attempts < 0:
            raise ValueError("transport_attempts cannot be negative")
        _require_optional_reason(self.reason)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupLegView:
    basket_leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    target_quantity: Quantity
    child_order_ids: tuple[ClientOrderId, ...]
    signed_cumulative_filled_delta: Quantity
    signed_working_quantity: Quantity
    unresolved_action_ids: tuple[GroupActionId, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupView:
    order_group_id: OrderGroupId
    source_intent_id: IntentId
    approval_id: PortfolioApprovalId
    execution_plan: ExecutionPlanRef
    revision: int
    status: OrderGroupStatus
    legs: tuple[OrderGroupLegView, ...]
    actions: tuple[ExecutionActionView, ...]
    created_at_ns: UnixNanos
    last_transition_ns: UnixNanos
    recovery_reason: str = ""
    close_outcome: OrderGroupCloseOutcome | None = None
    portfolio_confirmation_id: str = ""

    def __post_init__(self) -> None:
        _require_id(self.order_group_id, name="order_group_id")
        _require_id(self.source_intent_id, name="source_intent_id")
        if self.revision <= 0:
            raise ValueError("revision must be positive")
        _require_optional_reason(self.recovery_reason)
        _require_optional_reason(self.portfolio_confirmation_id)
        if self.status is OrderGroupStatus.CLOSED:
            if self.close_outcome is None:
                raise ValueError("closed group requires close_outcome")
        elif self.close_outcome is not None:
            raise ValueError("only a closed group can have close_outcome")


def execution_plan_parameters_checksum(parameters: object) -> str:
    """Return a deterministic checksum for bounded JSON-like plan parameters."""

    try:
        encoded = json.dumps(
            parameters,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("execution plan parameters must be canonical JSON") from error
    if len(encoded) > 16_384:
        raise ValueError("execution plan parameters exceed 16384 bytes")
    return hashlib.sha256(encoded).hexdigest()


def execution_action_checksum(action: ExecutionAction) -> str:
    """Checksum every field that can alter one child order attempt."""

    payload = {
        "account_id": str(action.account_id),
        "action_id": str(action.action_id),
        "basket_leg_id": str(action.basket_leg_id),
        "created_at_ns": int(action.created_at_ns),
        "execution_plan": {
            "id": str(action.execution_plan.execution_plan_id),
            "parameters_checksum": action.execution_plan.parameters_checksum,
            "version": action.execution_plan.version,
        },
        "expected_group_revision": action.expected_group_revision,
        "group_id": str(action.group_id),
        "instrument": {
            "kind": action.instrument_id.kind.value,
            "symbol": action.instrument_id.symbol,
            "venue": str(action.instrument_id.venue),
        },
        "limit_price": _fixed_or_none(action.limit_price),
        "order_type": action.order_type.value,
        "position_side": action.position_side.value,
        "post_only": action.post_only,
        "quantity": _fixed(action.quantity),
        "reduce_only": action.reduce_only,
        "side": action.side.value,
        "stop_price": _fixed_or_none(action.stop_price),
        "time_in_force": action.time_in_force.value,
    }
    return _sha256(payload)


def deterministic_order_group_id(
    admission: OrderGroupAdmission,
) -> OrderGroupId:
    """Derive the replay-stable group identity from intent and approval."""

    return OrderGroupId(
        _sha256(
            {
                "intent_id": str(admission.basket.intent_id),
                "portfolio_approval_id": str(admission.approval_id),
            }
        )
    )


def deterministic_group_action_id(
    *,
    group_id: OrderGroupId,
    expected_group_revision: int,
    basket_leg_id: BasketLegId,
    execution_plan: ExecutionPlanRef,
    action_kind: str,
    leg_attempt_sequence: int,
) -> GroupActionId:
    """Derive one stable action identity before constructing its content."""

    _require_id(group_id, name="group_id")
    _require_id(basket_leg_id, name="basket_leg_id")
    _require_text(action_kind, name="action_kind")
    if expected_group_revision <= 0:
        raise ValueError("expected_group_revision must be positive")
    if not 1 <= leg_attempt_sequence <= MAX_CHILD_ATTEMPTS_PER_LEG:
        raise ValueError("leg_attempt_sequence is outside hard bounds")
    return GroupActionId(
        _sha256(
            {
                "action_kind": action_kind,
                "basket_leg_id": str(basket_leg_id),
                "execution_plan": {
                    "id": str(execution_plan.execution_plan_id),
                    "parameters_checksum": execution_plan.parameters_checksum,
                    "version": execution_plan.version,
                },
                "expected_group_revision": expected_group_revision,
                "group_id": str(group_id),
                "leg_attempt_sequence": leg_attempt_sequence,
            }
        )
    )


def child_order_id_for_action(action_id: GroupActionId) -> ClientOrderId:
    """Use the stable action hash as the venue idempotency key."""

    _require_id(action_id, name="action_id")
    return ClientOrderId(f"g-{str(action_id)[:32]}")


def _fixed(value: Price | Quantity) -> dict[str, int]:
    return {"raw": value.raw, "scale": value.scale}


def _fixed_or_none(value: Price | None) -> dict[str, int] | None:
    return None if value is None else _fixed(value)


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
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _require_id(value: object, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    _require_text(str(value), name=name)


def _require_text(value: str, *, name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > MAX_GROUP_ID_LENGTH:
        raise ValueError(f"{name} exceeds maximum length {MAX_GROUP_ID_LENGTH}")


def _require_optional_reason(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("reason/evidence text must be a string")
    if value and value != value.strip():
        raise ValueError("reason/evidence text must be trimmed")
    if len(value) > MAX_GROUP_REASON_LENGTH:
        raise ValueError("reason/evidence text exceeds maximum length")


def _require_bounded_positive_int(
    value: int,
    *,
    name: str,
    maximum: int,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")


__all__ = [
    "MAX_ACTIVE_ORDER_GROUPS_PER_STRATEGY_ACCOUNT",
    "MAX_CHILD_ATTEMPTS_PER_LEG",
    "MAX_GROUP_CHILDREN",
    "MAX_RETAINED_ORDER_GROUPS",
    "MAX_TECHNICAL_RETRANSMISSIONS",
    "ExecutionAction",
    "ExecutionActionPermit",
    "ExecutionActionState",
    "ExecutionActionView",
    "ExecutionPlanRef",
    "OrderGroupAdmission",
    "OrderGroupCloseOutcome",
    "OrderGroupLegView",
    "OrderGroupLimits",
    "OrderGroupStatus",
    "OrderGroupView",
    "child_order_id_for_action",
    "deterministic_group_action_id",
    "deterministic_order_group_id",
    "execution_action_checksum",
    "execution_plan_parameters_checksum",
]
