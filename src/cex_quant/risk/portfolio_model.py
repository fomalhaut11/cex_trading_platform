"""Immutable ADR-012 Portfolio Risk contracts.

These contracts contain economic evidence only.  They do not submit orders,
mutate OMS state, choose an execution sequence, or encode a strategy type.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from cex_quant.core import (
    AccountId,
    AssetId,
    ExecutionPermitId,
    FeatureId,
    FixedPoint,
    GroupActionId,
    IntentId,
    MarginScopeId,
    Money,
    OrderGroupId,
    PortfolioApprovalId,
    PortfolioConfirmationId,
    PortfolioReconciliationId,
    PortfolioReservationId,
    Rate,
    RecoveryAuthorizationId,
    RiskDirectiveId,
    RiskFactorId,
    SpreadRiskId,
    StrategyId,
    UnixNanos,
)
from cex_quant.instruments import Instrument, InstrumentId
from cex_quant.observability import HealthReport
from cex_quant.oms import ExecutionActionPermit, OrderGroupView
from cex_quant.portfolio import (
    AccountPositionRiskView,
    MarginScopeSnapshot,
    PositionLiquidationReference,
)
from cex_quant.snapshots import DecisionSnapshotId, ObservationId
from cex_quant.strategy import BasketTargetIntent

MAX_PORTFOLIO_SCOPE_ITEMS = 16_384
MAX_RISK_REASON_LENGTH = 512
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
T = TypeVar("T")


class PortfolioRiskDecisionStatus(StrEnum):
    ALLOW = "allow"
    REJECT = "reject"


class PortfolioRiskRejectReason(StrEnum):
    BASKET_EXPIRED = "basket_expired"
    BASKET_FROM_FUTURE = "basket_from_future"
    SNAPSHOT_EXPIRED = "snapshot_expired"
    SNAPSHOT_FROM_FUTURE = "snapshot_from_future"
    HEALTH_NOT_READY = "health_not_ready"
    POSITION_NOT_READY = "position_not_ready"
    SCOPE_INCOMPLETE = "scope_incomplete"
    INSTRUMENT_NOT_ACTIVE = "instrument_not_active"
    UNSUPPORTED_INSTRUMENT_MODEL = "unsupported_instrument_model"
    MARK_MISSING = "mark_missing"
    MARK_STALE = "mark_stale"
    SENSITIVITY_MISSING = "sensitivity_missing"
    SENSITIVITY_STALE = "sensitivity_stale"
    SENSITIVITY_UNIT_MISMATCH = "sensitivity_unit_mismatch"
    REPORTING_ASSET_MISMATCH = "reporting_asset_mismatch"
    RISK_FACTOR_LIMIT = "risk_factor_limit"
    GROSS_NOTIONAL_LIMIT = "gross_notional_limit"
    INITIAL_MARGIN_LIMIT = "initial_margin_limit"
    LIQUIDATION_BUFFER_LIMIT = "liquidation_buffer_limit"
    AVAILABLE_MARGIN_LIMIT = "available_margin_limit"
    ACTIVE_RESERVATION_LIMIT = "active_reservation_limit"
    RESERVATION_CONFLICT = "reservation_conflict"
    RESERVATION_NOT_ACTIVE = "reservation_not_active"
    GROUP_IDENTITY_MISMATCH = "group_identity_mismatch"
    GROUP_NOT_ACTIONABLE = "group_not_actionable"
    GROUP_REVISION_MISMATCH = "group_revision_mismatch"
    ACTION_IDENTITY_MISMATCH = "action_identity_mismatch"
    REDUCE_ONLY_VIOLATION = "reduce_only_violation"
    RECOVERY_REQUIRED = "recovery_required"
    SPREAD_LIMIT = "spread_limit"


@dataclass(frozen=True, slots=True, kw_only=True)
class ExactRiskValue:
    """Fixed-point Risk evidence with an explicit unit and provenance."""

    value: FixedPoint
    unit: str
    observation_id: ObservationId
    as_of_ns: UnixNanos
    valid_until_ns: UnixNanos
    asset: AssetId | None = None
    feature_id: FeatureId | None = None

    def __post_init__(self) -> None:
        _require_text(self.unit, name="unit")
        _require_id(self.observation_id, name="observation_id")
        if self.asset is not None:
            _require_id(self.asset, name="asset")
        if self.feature_id is not None:
            _require_id(self.feature_id, name="feature_id")
        if self.as_of_ns < 0:
            raise ValueError("risk value as_of_ns cannot be negative")
        if self.valid_until_ns < self.as_of_ns:
            raise ValueError("risk value expiry cannot precede as_of_ns")


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskMark:
    instrument_id: InstrumentId
    price: ExactRiskValue

    def __post_init__(self) -> None:
        if self.price.value.as_decimal() <= 0:
            raise ValueError("risk mark must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentSensitivity:
    """Registered model output consumed by Risk; Risk does not derive Greeks."""

    instrument_id: InstrumentId
    model_version: int
    risk_factor_id: RiskFactorId
    margin_scope_id: MarginScopeId | None
    delta_per_quantity: ExactRiskValue
    initial_margin_per_quantity: ExactRiskValue
    gamma_per_quantity: ExactRiskValue | None = None
    vega_per_quantity: ExactRiskValue | None = None

    def __post_init__(self) -> None:
        if self.model_version <= 0:
            raise ValueError("instrument Risk model version must be positive")
        _require_id(self.risk_factor_id, name="risk_factor_id")
        if self.margin_scope_id is not None:
            _require_id(self.margin_scope_id, name="margin_scope_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkingOrderRiskView:
    account_id: AccountId
    instrument_id: InstrumentId
    signed_remaining_quantity: FixedPoint
    group_id: OrderGroupId | None = None

    def __post_init__(self) -> None:
        _require_id(self.account_id, name="account_id")
        if self.group_id is not None:
            _require_id(self.group_id, name="group_id")
        if self.signed_remaining_quantity.raw == 0:
            raise ValueError("working order remaining quantity cannot be zero")


@dataclass(frozen=True, slots=True, kw_only=True)
class SpreadRiskInput:
    spread_id: SpreadRiskId
    value: ExactRiskValue

    def __post_init__(self) -> None:
        _require_id(self.spread_id, name="spread_id")


class PortfolioRiskReservationState(StrEnum):
    ACTIVE = "active"
    ATTACHED_TO_GROUP = "attached_to_group"
    RELEASED = "released"
    EXPIRED = "expired"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskReservationView:
    reservation_id: PortfolioReservationId
    approval_id: PortfolioApprovalId
    strategy_id: StrategyId
    basket: BasketTargetIntent
    state: PortfolioRiskReservationState
    created_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    group_id: OrderGroupId | None = None

    def __post_init__(self) -> None:
        _require_id(self.reservation_id, name="reservation_id")
        _require_id(self.approval_id, name="approval_id")
        _require_id(self.strategy_id, name="strategy_id")
        if self.strategy_id != self.basket.strategy_id:
            raise ValueError("reservation strategy does not match Basket")
        if self.valid_until_ns < self.created_at_ns:
            raise ValueError("reservation expiry cannot precede creation")
        if (
            self.state is PortfolioRiskReservationState.ATTACHED_TO_GROUP
            and self.group_id is None
        ):
            raise ValueError("attached reservation requires group_id")
        if (
            self.state is not PortfolioRiskReservationState.ATTACHED_TO_GROUP
            and self.group_id is not None
        ):
            raise ValueError("only an attached reservation may carry group_id")

    @property
    def active(self) -> bool:
        return self.state in {
            PortfolioRiskReservationState.ACTIVE,
            PortfolioRiskReservationState.ATTACHED_TO_GROUP,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskSnapshot:
    original_decision_snapshot_ids: tuple[DecisionSnapshotId, ...]
    positions: tuple[AccountPositionRiskView, ...]
    working_orders: tuple[WorkingOrderRiskView, ...]
    groups: tuple[OrderGroupView, ...]
    margins: tuple[MarginScopeSnapshot, ...]
    liquidation_references: tuple[PositionLiquidationReference, ...]
    instruments: tuple[Instrument, ...]
    marks: tuple[RiskMark, ...]
    sensitivities: tuple[InstrumentSensitivity, ...]
    spread_inputs: tuple[SpreadRiskInput, ...]
    active_reservations: tuple[PortfolioRiskReservationView, ...]
    health: HealthReport

    def __post_init__(self) -> None:
        collections = (
            self.original_decision_snapshot_ids,
            self.positions,
            self.working_orders,
            self.groups,
            self.margins,
            self.liquidation_references,
            self.instruments,
            self.marks,
            self.sensitivities,
            self.spread_inputs,
            self.active_reservations,
        )
        if any(len(items) > MAX_PORTFOLIO_SCOPE_ITEMS for items in collections):
            raise ValueError("Portfolio Risk snapshot exceeds hard scope bound")
        _require_sorted_unique_ids(
            self.original_decision_snapshot_ids,
            name="original decision snapshot IDs",
        )
        _require_unique(self.positions, key=lambda item: str(item.account_id))
        _require_unique(
            self.instruments, key=lambda item: str(item.instrument_id)
        )
        _require_unique(self.marks, key=lambda item: str(item.instrument_id))
        _require_unique(
            self.sensitivities, key=lambda item: str(item.instrument_id)
        )
        _require_unique(
            self.active_reservations, key=lambda item: str(item.approval_id)
        )
        _require_unique(self.margins, key=lambda item: str(item.scope_id))


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskFactorLimit:
    risk_factor_id: RiskFactorId
    max_abs_net_delta: FixedPoint
    max_gross_delta: FixedPoint
    max_abs_gamma: FixedPoint | None = None
    max_abs_vega: FixedPoint | None = None

    def __post_init__(self) -> None:
        _require_id(self.risk_factor_id, name="risk_factor_id")
        values = (
            self.max_abs_net_delta,
            self.max_gross_delta,
            self.max_abs_gamma,
            self.max_abs_vega,
        )
        if any(item is not None and item.as_decimal() < 0 for item in values):
            raise ValueError("Risk factor limits cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class SpreadRiskLimit:
    spread_id: SpreadRiskId
    max_abs_value: FixedPoint

    def __post_init__(self) -> None:
        _require_id(self.spread_id, name="spread_id")
        if self.max_abs_value.as_decimal() < 0:
            raise ValueError("spread Risk limit cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentRiskModelPolicy:
    instrument_id: InstrumentId
    model_version: int
    delta_unit: str
    initial_margin_unit: str
    gamma_unit: str | None = None
    vega_unit: str | None = None

    def __post_init__(self) -> None:
        if self.model_version <= 0:
            raise ValueError("instrument Risk model version must be positive")
        _require_text(self.delta_unit, name="delta_unit")
        _require_text(self.initial_margin_unit, name="initial_margin_unit")
        if self.gamma_unit is not None:
            _require_text(self.gamma_unit, name="gamma_unit")
        if self.vega_unit is not None:
            _require_text(self.vega_unit, name="vega_unit")


@dataclass(frozen=True, slots=True, kw_only=True)
class LiquidationRequirement:
    account_id: AccountId
    instrument_id: InstrumentId

    def __post_init__(self) -> None:
        _require_id(self.account_id, name="account_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskPolicy:
    """Versioned, data-only policy for admission and action authorization."""

    version: int
    reporting_asset: AssetId
    required_account_ids: tuple[AccountId, ...]
    required_instrument_ids: tuple[InstrumentId, ...]
    required_margin_scope_ids: tuple[MarginScopeId, ...]
    required_liquidation_references: tuple[LiquidationRequirement, ...]
    supported_model_versions: tuple[int, ...]
    instrument_models: tuple[InstrumentRiskModelPolicy, ...]
    factor_limits: tuple[RiskFactorLimit, ...]
    spread_limits: tuple[SpreadRiskLimit, ...]
    max_gross_notional: Money
    max_initial_margin: Money
    min_available_margin: Money
    min_liquidation_buffer: Rate
    max_snapshot_age_ns: int
    max_mark_age_ns: int
    max_sensitivity_age_ns: int
    max_margin_age_ns: int
    max_liquidation_age_ns: int
    approval_lifetime_ns: int
    permit_lifetime_ns: int
    reservation_lifetime_ns: int
    max_active_reservations: int

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("risk policy version must be positive")
        _require_id(self.reporting_asset, name="reporting_asset")
        _require_sorted_unique_ids(self.required_account_ids, name="accounts")
        instrument_keys = tuple(map(str, self.required_instrument_ids))
        if instrument_keys != tuple(sorted(instrument_keys)):
            raise ValueError("required instruments must be sorted")
        if len(set(instrument_keys)) != len(instrument_keys):
            raise ValueError("required instruments must be unique")
        _require_sorted_unique_ids(
            self.required_margin_scope_ids,
            name="required margin scopes",
        )
        liquidation_keys = tuple(
            (str(item.account_id), str(item.instrument_id))
            for item in self.required_liquidation_references
        )
        if liquidation_keys != tuple(sorted(liquidation_keys)) or len(
            set(liquidation_keys)
        ) != len(liquidation_keys):
            raise ValueError(
                "required liquidation references must be unique and sorted"
            )
        if (
            not self.supported_model_versions
            or self.supported_model_versions
            != tuple(sorted(set(self.supported_model_versions)))
            or any(item <= 0 for item in self.supported_model_versions)
        ):
            raise ValueError("supported model versions must be sorted and positive")
        model_keys = tuple(str(item.instrument_id) for item in self.instrument_models)
        if model_keys != tuple(sorted(model_keys)) or len(set(model_keys)) != len(
            model_keys
        ):
            raise ValueError("instrument Risk models must be unique and sorted")
        factor_ids = tuple(str(item.risk_factor_id) for item in self.factor_limits)
        if factor_ids != tuple(sorted(factor_ids)) or len(set(factor_ids)) != len(
            factor_ids
        ):
            raise ValueError("factor limits must be unique and sorted")
        spread_ids = tuple(str(item.spread_id) for item in self.spread_limits)
        if spread_ids != tuple(sorted(spread_ids)) or len(set(spread_ids)) != len(
            spread_ids
        ):
            raise ValueError("spread limits must be unique and sorted")
        if any(
            value.as_decimal() < 0
            for value in (
                self.max_gross_notional,
                self.max_initial_margin,
                self.min_available_margin,
                self.min_liquidation_buffer,
            )
        ):
            raise ValueError("portfolio money limits cannot be negative")
        durations = (
            self.max_snapshot_age_ns,
            self.max_mark_age_ns,
            self.max_sensitivity_age_ns,
            self.max_margin_age_ns,
            self.max_liquidation_age_ns,
            self.approval_lifetime_ns,
            self.permit_lifetime_ns,
            self.reservation_lifetime_ns,
        )
        if any(item <= 0 for item in durations):
            raise ValueError("Risk policy durations must be positive")
        if self.max_active_reservations <= 0:
            raise ValueError("active reservation bound must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskFactorExposure:
    risk_factor_id: RiskFactorId
    net_delta: FixedPoint
    gross_delta: FixedPoint
    gamma: FixedPoint
    vega: FixedPoint


@dataclass(frozen=True, slots=True, kw_only=True)
class MarginScopeExposure:
    scope_id: MarginScopeId
    reporting_asset: AssetId
    initial_margin: Money
    available_margin: Money

    def __post_init__(self) -> None:
        _require_id(self.scope_id, name="scope_id")
        _require_id(self.reporting_asset, name="reporting_asset")


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioExposure:
    reporting_asset: AssetId
    gross_notional: Money
    initial_margin: Money
    available_margin: Money
    factors: tuple[RiskFactorExposure, ...]
    margin_scopes: tuple[MarginScopeExposure, ...]

    def __post_init__(self) -> None:
        _require_id(self.reporting_asset, name="reporting_asset")
        factor_ids = tuple(str(item.risk_factor_id) for item in self.factors)
        if factor_ids != tuple(sorted(factor_ids)) or len(set(factor_ids)) != len(
            factor_ids
        ):
            raise ValueError("factor exposures must be unique and sorted")
        scope_ids = tuple(str(item.scope_id) for item in self.margin_scopes)
        if scope_ids != tuple(sorted(scope_ids)) or len(set(scope_ids)) != len(
            scope_ids
        ):
            raise ValueError("margin exposures must be unique and sorted")


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioApprovalEvidence:
    approval_id: PortfolioApprovalId
    basket_intent_id: IntentId
    basket_checksum: str
    risk_snapshot_id: DecisionSnapshotId
    assessment_checksum: str
    approved_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int

    def __post_init__(self) -> None:
        _require_id(self.approval_id, name="approval_id")
        _require_id(self.basket_intent_id, name="basket_intent_id")
        _require_checksum(self.basket_checksum, name="basket_checksum")
        _require_id(self.risk_snapshot_id, name="risk_snapshot_id")
        _require_checksum(self.assessment_checksum, name="assessment_checksum")
        if self.valid_until_ns < self.approved_at_ns:
            raise ValueError("approval expiry cannot precede issuance")
        if self.risk_policy_version <= 0:
            raise ValueError("risk policy version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class BasketPortfolioRiskDecision:
    status: PortfolioRiskDecisionStatus
    basket: BasketTargetIntent
    risk_snapshot_id: DecisionSnapshotId
    risk_policy_version: int
    reasons: tuple[PortfolioRiskRejectReason, ...]
    current_exposure: PortfolioExposure
    projected_exposure: PortfolioExposure
    conservative_exposure: PortfolioExposure
    approval: PortfolioApprovalEvidence | None

    def __post_init__(self) -> None:
        if self.status is PortfolioRiskDecisionStatus.ALLOW:
            if self.reasons or self.approval is None:
                raise ValueError("ALLOW requires approval and no rejection reasons")
        elif not self.reasons or self.approval is not None:
            raise ValueError("REJECT requires reasons and no approval")

    @property
    def allowed(self) -> bool:
        return self.status is PortfolioRiskDecisionStatus.ALLOW


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionActionRiskDecision:
    status: PortfolioRiskDecisionStatus
    group_id: OrderGroupId
    action_id: GroupActionId
    risk_snapshot_id: DecisionSnapshotId
    reasons: tuple[PortfolioRiskRejectReason, ...]
    current_exposure: PortfolioExposure
    projected_exposure: PortfolioExposure
    conservative_exposure: PortfolioExposure
    permit: ExecutionActionPermit | None

    def __post_init__(self) -> None:
        if self.status is PortfolioRiskDecisionStatus.ALLOW:
            if self.reasons or self.permit is None:
                raise ValueError("ALLOW requires permit and no rejection reasons")
        elif not self.reasons or self.permit is not None:
            raise ValueError("REJECT requires reasons and no permit")

    @property
    def allowed(self) -> bool:
        return self.status is PortfolioRiskDecisionStatus.ALLOW


class PortfolioRiskDirectiveKind(StrEnum):
    CLEAR = "clear"
    BLOCK_NEW_ACTIONS = "block_new_actions"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    RECOVERY_ACTION_REQUIRED = "recovery_action_required"
    OPERATOR_REVIEW_REQUIRED = "operator_review_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskDirective:
    directive_id: RiskDirectiveId
    group_id: OrderGroupId
    expected_group_revision: int
    risk_snapshot_id: DecisionSnapshotId
    kind: PortfolioRiskDirectiveKind
    reasons: tuple[PortfolioRiskRejectReason, ...]
    issued_at_ns: UnixNanos
    risk_policy_version: int

    def __post_init__(self) -> None:
        _require_id(self.directive_id, name="directive_id")
        if self.expected_group_revision <= 0:
            raise ValueError("directive group revision must be positive")
        if self.kind is PortfolioRiskDirectiveKind.CLEAR and self.reasons:
            raise ValueError("CLEAR directive cannot carry reasons")
        if self.kind is not PortfolioRiskDirectiveKind.CLEAR and not self.reasons:
            raise ValueError("blocking directive requires reasons")


class RecoveryAuthorizationMode(StrEnum):
    RESUME_GROUP = "resume_group"
    RETRANSMIT_DEFINITELY_NOT_SENT = "retransmit_definitely_not_sent"


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupRecoveryAuthorization:
    authorization_id: RecoveryAuthorizationId
    group_id: OrderGroupId
    expected_group_revision: int
    mode: RecoveryAuthorizationMode
    reconciliation_id: PortfolioReconciliationId
    risk_snapshot_id: DecisionSnapshotId
    issued_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int
    action_id: GroupActionId | None = None
    permit_id: ExecutionPermitId | None = None

    def __post_init__(self) -> None:
        _require_id(self.authorization_id, name="authorization_id")
        _require_id(self.group_id, name="group_id")
        _require_id(self.reconciliation_id, name="reconciliation_id")
        if self.expected_group_revision <= 0:
            raise ValueError("recovery group revision must be positive")
        if self.valid_until_ns < self.issued_at_ns:
            raise ValueError("recovery authorization expiry precedes issuance")
        if self.mode is RecoveryAuthorizationMode.RESUME_GROUP:
            if self.action_id is not None or self.permit_id is not None:
                raise ValueError("resume authorization carries no action authority")
        elif self.action_id is None or self.permit_id is None:
            raise ValueError("retransmission authorization requires action and permit")


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioTargetConfirmation:
    confirmation_id: PortfolioConfirmationId
    group_id: OrderGroupId
    expected_group_revision: int
    basket_intent_id: IntentId
    risk_snapshot_id: DecisionSnapshotId
    confirmed_at_ns: UnixNanos
    risk_policy_version: int

    def __post_init__(self) -> None:
        for name, value in (
            ("confirmation_id", self.confirmation_id),
            ("group_id", self.group_id),
            ("basket_intent_id", self.basket_intent_id),
            ("risk_snapshot_id", self.risk_snapshot_id),
        ):
            _require_id(value, name=name)
        if self.expected_group_revision <= 0:
            raise ValueError("confirmation group revision must be positive")


def _require_unique(
    items: tuple[T, ...],
    *,
    key: Callable[[T], str],
) -> None:
    values = tuple(key(item) for item in items)
    if len(set(values)) != len(values):
        raise ValueError("Portfolio Risk snapshot collection contains duplicates")


def _require_sorted_unique_ids(items: tuple[str, ...], *, name: str) -> None:
    values = tuple(str(item) for item in items)
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique and sorted")


def _require_id(value: object, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    _require_text(value, name=name)


def _require_text(value: str, *, name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > 128:
        raise ValueError(f"{name} exceeds maximum length 128")


def _require_checksum(value: str, *, name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


__all__ = [
    "BasketPortfolioRiskDecision",
    "ExactRiskValue",
    "ExecutionActionRiskDecision",
    "GroupRecoveryAuthorization",
    "InstrumentRiskModelPolicy",
    "InstrumentSensitivity",
    "LiquidationRequirement",
    "MarginScopeExposure",
    "PortfolioApprovalEvidence",
    "PortfolioExposure",
    "PortfolioRiskDecisionStatus",
    "PortfolioRiskDirective",
    "PortfolioRiskDirectiveKind",
    "PortfolioRiskPolicy",
    "PortfolioRiskRejectReason",
    "PortfolioRiskReservationState",
    "PortfolioRiskReservationView",
    "PortfolioRiskSnapshot",
    "PortfolioTargetConfirmation",
    "RecoveryAuthorizationMode",
    "RiskFactorExposure",
    "RiskFactorLimit",
    "RiskMark",
    "SpreadRiskInput",
    "SpreadRiskLimit",
    "WorkingOrderRiskView",
]
