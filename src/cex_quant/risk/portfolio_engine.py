"""Pure deterministic ADR-012 Portfolio Risk projection and decisions."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from cex_quant.core import (
    AccountId,
    ExecutionPermitId,
    FixedPoint,
    MarginScopeId,
    Money,
    PortfolioApprovalId,
    RiskDirectiveId,
    RiskFactorId,
    UnixNanos,
)
from cex_quant.instruments import (
    ContractValueType,
    FutureSpecification,
    Instrument,
    InstrumentId,
    InstrumentStatus,
    OptionSpecification,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.observability import HealthStatus
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionPermit,
    OrderGroupStatus,
    OrderGroupView,
    OrderSide,
    execution_action_checksum,
)
from cex_quant.portfolio import PositionRiskReadiness
from cex_quant.snapshots import DecisionSnapshotPublication
from cex_quant.strategy import BasketTargetIntent, basket_target_intent_checksum

from .portfolio_model import (
    BasketPortfolioRiskDecision,
    ExecutionActionRiskDecision,
    MarginScopeExposure,
    PortfolioApprovalEvidence,
    PortfolioExposure,
    PortfolioRiskDecisionStatus,
    PortfolioRiskDirective,
    PortfolioRiskDirectiveKind,
    PortfolioRiskPolicy,
    PortfolioRiskRejectReason,
    PortfolioRiskReservationView,
    PortfolioRiskSnapshot,
    RiskFactorExposure,
)

ScopeKey = tuple[AccountId, InstrumentId]


class PortfolioRiskEngine:
    """Stateless whole-Basket and exact-action Risk engine."""

    def assess_basket(
        self,
        basket: BasketTargetIntent,
        risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
        policy: PortfolioRiskPolicy,
        *,
        now_ns: UnixNanos,
    ) -> BasketPortfolioRiskDecision:
        value = risk_snapshot.value
        reasons = self._validate_snapshot(
            risk_snapshot,
            policy,
            now_ns=now_ns,
            enforce_reservation_capacity=True,
        )
        if basket.decision_time_ns > now_ns:
            reasons.append(PortfolioRiskRejectReason.BASKET_FROM_FUTURE)
        if now_ns > basket.valid_until_ns:
            reasons.append(PortfolioRiskRejectReason.BASKET_EXPIRED)
        if (
            basket.decision_snapshot_id
            not in value.original_decision_snapshot_ids
        ):
            reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)

        current = _position_quantities(value)
        reserved, reservation_reasons = _apply_reservations(
            current,
            value.active_reservations,
            incoming_basket=basket,
        )
        reasons.extend(reservation_reasons)
        projected = dict(reserved)
        for leg in basket.legs:
            projected[(leg.account_id, leg.instrument_id)] = (
                leg.target_quantity.as_decimal()
            )

        current_exposure, current_reasons = _calculate_exposure(
            current,
            value,
            policy,
        )
        projected_exposure, projected_reasons = _calculate_exposure(
            projected,
            value,
            policy,
            current_exposure=current_exposure,
        )
        conservative_quantities = _apply_working_envelope(
            projected,
            value,
        )
        conservative_exposure, conservative_reasons = _calculate_exposure(
            conservative_quantities,
            value,
            policy,
            current_exposure=current_exposure,
        )
        reasons.extend(current_reasons)
        reasons.extend(projected_reasons)
        reasons.extend(conservative_reasons)
        reasons.extend(_limit_reasons(conservative_exposure, value, policy))
        reasons = _deduplicate_reasons(reasons)

        approval: PortfolioApprovalEvidence | None = None
        if not reasons:
            assessment_checksum = _assessment_checksum(
                basket=basket,
                snapshot_id=risk_snapshot.metadata.snapshot_id,
                policy_version=policy.version,
                current=current_exposure,
                projected=projected_exposure,
                conservative=conservative_exposure,
            )
            valid_until_ns = UnixNanos(
                min(
                    int(basket.valid_until_ns),
                    int(now_ns) + policy.approval_lifetime_ns,
                    _source_valid_until(value),
                )
            )
            content = {
                "assessment_checksum": assessment_checksum,
                "basket_checksum": basket_target_intent_checksum(basket),
                "basket_intent_id": str(basket.intent_id),
                "risk_policy_version": policy.version,
                "risk_snapshot_id": str(risk_snapshot.metadata.snapshot_id),
                "valid_until_ns": int(valid_until_ns),
            }
            approval = PortfolioApprovalEvidence(
                approval_id=PortfolioApprovalId(_sha256(content)),
                basket_intent_id=basket.intent_id,
                basket_checksum=basket_target_intent_checksum(basket),
                risk_snapshot_id=risk_snapshot.metadata.snapshot_id,
                assessment_checksum=assessment_checksum,
                approved_at_ns=now_ns,
                valid_until_ns=valid_until_ns,
                risk_policy_version=policy.version,
            )

        return BasketPortfolioRiskDecision(
            status=(
                PortfolioRiskDecisionStatus.ALLOW
                if approval is not None
                else PortfolioRiskDecisionStatus.REJECT
            ),
            basket=basket,
            risk_snapshot_id=risk_snapshot.metadata.snapshot_id,
            risk_policy_version=policy.version,
            reasons=tuple(reasons),
            current_exposure=current_exposure,
            projected_exposure=projected_exposure,
            conservative_exposure=conservative_exposure,
            approval=approval,
        )

    def authorize_action(
        self,
        group: OrderGroupView,
        action: ExecutionAction,
        risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
        policy: PortfolioRiskPolicy,
        *,
        now_ns: UnixNanos,
    ) -> ExecutionActionRiskDecision:
        value = risk_snapshot.value
        reasons = self._validate_snapshot(
            risk_snapshot,
            policy,
            now_ns=now_ns,
            enforce_reservation_capacity=False,
        )
        if group.order_group_id != action.group_id:
            reasons.append(PortfolioRiskRejectReason.GROUP_IDENTITY_MISMATCH)
        if group.status is not OrderGroupStatus.ACTIVE:
            reasons.append(PortfolioRiskRejectReason.GROUP_NOT_ACTIONABLE)
        if group.revision != action.expected_group_revision:
            reasons.append(PortfolioRiskRejectReason.GROUP_REVISION_MISMATCH)

        matching_legs = tuple(
            leg
            for leg in group.legs
            if leg.basket_leg_id == action.basket_leg_id
        )
        if (
            len(matching_legs) != 1
            or matching_legs[0].account_id != action.account_id
            or matching_legs[0].instrument_id != action.instrument_id
        ):
            reasons.append(PortfolioRiskRejectReason.ACTION_IDENTITY_MISMATCH)

        reservations = tuple(
            item
            for item in value.active_reservations
            if item.approval_id == group.approval_id
        )
        if (
            len(reservations) != 1
            or not reservations[0].active
            or reservations[0].group_id != group.order_group_id
            or now_ns > reservations[0].valid_until_ns
        ):
            reasons.append(PortfolioRiskRejectReason.RESERVATION_NOT_ACTIVE)

        current = _position_quantities(value)
        projected = _apply_other_reservations(
            current,
            value.active_reservations,
            excluded_approval_id=group.approval_id,
        )
        key = (action.account_id, action.instrument_id)
        before = projected.get(key, Decimal(0))
        signed_quantity = action.quantity.as_decimal()
        if action.side is OrderSide.SELL:
            signed_quantity = -signed_quantity
        after = before + signed_quantity
        projected[key] = after
        if action.reduce_only and abs(after) >= abs(before):
            reasons.append(PortfolioRiskRejectReason.REDUCE_ONLY_VIOLATION)

        current_exposure, current_reasons = _calculate_exposure(
            current,
            value,
            policy,
        )
        projected_exposure, projected_reasons = _calculate_exposure(
            projected,
            value,
            policy,
            current_exposure=current_exposure,
        )
        conservative = _apply_working_envelope(projected, value)
        conservative_exposure, conservative_reasons = _calculate_exposure(
            conservative,
            value,
            policy,
            current_exposure=current_exposure,
        )
        reasons.extend(current_reasons)
        reasons.extend(projected_reasons)
        reasons.extend(conservative_reasons)
        reasons.extend(_limit_reasons(conservative_exposure, value, policy))
        reasons = _deduplicate_reasons(reasons)

        permit: ExecutionActionPermit | None = None
        if not reasons:
            valid_until = UnixNanos(
                min(
                    int(now_ns) + policy.permit_lifetime_ns,
                    _source_valid_until(value),
                    int(reservations[0].valid_until_ns),
                )
            )
            checksum = execution_action_checksum(action)
            permit_id = ExecutionPermitId(
                _sha256(
                    {
                        "action_checksum": checksum,
                        "action_id": str(action.action_id),
                        "group_id": str(action.group_id),
                        "group_revision": action.expected_group_revision,
                        "risk_policy_version": policy.version,
                        "risk_snapshot_id": str(
                            risk_snapshot.metadata.snapshot_id
                        ),
                        "valid_until_ns": int(valid_until),
                    }
                )
            )
            permit = ExecutionActionPermit(
                permit_id=permit_id,
                group_id=action.group_id,
                expected_group_revision=action.expected_group_revision,
                action_id=action.action_id,
                action_checksum=checksum,
                risk_snapshot_id=risk_snapshot.metadata.snapshot_id,
                issued_at_ns=now_ns,
                valid_until_ns=valid_until,
                risk_policy_version=policy.version,
            )

        return ExecutionActionRiskDecision(
            status=(
                PortfolioRiskDecisionStatus.ALLOW
                if permit is not None
                else PortfolioRiskDecisionStatus.REJECT
            ),
            group_id=action.group_id,
            action_id=action.action_id,
            risk_snapshot_id=risk_snapshot.metadata.snapshot_id,
            reasons=tuple(reasons),
            current_exposure=current_exposure,
            projected_exposure=projected_exposure,
            conservative_exposure=conservative_exposure,
            permit=permit,
        )

    def supervise_group(
        self,
        group: OrderGroupView,
        risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
        policy: PortfolioRiskPolicy,
        *,
        now_ns: UnixNanos,
    ) -> PortfolioRiskDirective:
        """Assess current group safety without mutating OMS or Execution."""

        value = risk_snapshot.value
        reasons = self._validate_snapshot(
            risk_snapshot,
            policy,
            now_ns=now_ns,
            enforce_reservation_capacity=False,
        )
        current = _position_quantities(value)
        current_exposure, exposure_reasons = _calculate_exposure(
            current,
            value,
            policy,
        )
        conservative_quantities = _apply_working_envelope(current, value)
        conservative, conservative_reasons = _calculate_exposure(
            conservative_quantities,
            value,
            policy,
            current_exposure=current_exposure,
        )
        reasons.extend(exposure_reasons)
        reasons.extend(conservative_reasons)
        reasons.extend(_limit_reasons(conservative, value, policy))
        reasons = _deduplicate_reasons(reasons)
        if any(
            item
            in {
                PortfolioRiskRejectReason.POSITION_NOT_READY,
                PortfolioRiskRejectReason.SCOPE_INCOMPLETE,
            }
            for item in reasons
        ):
            kind = PortfolioRiskDirectiveKind.RECONCILIATION_REQUIRED
        elif group.status is OrderGroupStatus.RECOVERY_REQUIRED:
            kind = PortfolioRiskDirectiveKind.RECOVERY_ACTION_REQUIRED
            if not reasons:
                reasons.append(PortfolioRiskRejectReason.RECOVERY_REQUIRED)
        elif PortfolioRiskRejectReason.HEALTH_NOT_READY in reasons:
            kind = PortfolioRiskDirectiveKind.OPERATOR_REVIEW_REQUIRED
        elif reasons:
            kind = PortfolioRiskDirectiveKind.BLOCK_NEW_ACTIONS
        else:
            kind = PortfolioRiskDirectiveKind.CLEAR
        directive_id = RiskDirectiveId(
            _sha256(
                {
                    "group_id": str(group.order_group_id),
                    "group_revision": group.revision,
                    "issued_at_ns": int(now_ns),
                    "kind": kind.value,
                    "policy_version": policy.version,
                    "reasons": [item.value for item in reasons],
                    "risk_snapshot_id": str(
                        risk_snapshot.metadata.snapshot_id
                    ),
                }
            )
        )
        return PortfolioRiskDirective(
            directive_id=directive_id,
            group_id=group.order_group_id,
            expected_group_revision=group.revision,
            risk_snapshot_id=risk_snapshot.metadata.snapshot_id,
            kind=kind,
            reasons=tuple(reasons),
            issued_at_ns=now_ns,
            risk_policy_version=policy.version,
        )

    @staticmethod
    def _validate_snapshot(
        publication: DecisionSnapshotPublication[PortfolioRiskSnapshot],
        policy: PortfolioRiskPolicy,
        *,
        now_ns: UnixNanos,
        enforce_reservation_capacity: bool,
    ) -> list[PortfolioRiskRejectReason]:
        value = publication.value
        reasons: list[PortfolioRiskRejectReason] = []
        assembled_at = publication.metadata.assembled_at_ns
        if assembled_at > now_ns:
            reasons.append(PortfolioRiskRejectReason.SNAPSHOT_FROM_FUTURE)
        elif now_ns - assembled_at > policy.max_snapshot_age_ns:
            reasons.append(PortfolioRiskRejectReason.SNAPSHOT_EXPIRED)
        if value.health.status is not HealthStatus.HEALTHY:
            reasons.append(PortfolioRiskRejectReason.HEALTH_NOT_READY)
        if any(
            item.readiness is not PositionRiskReadiness.READY
            for item in value.positions
        ):
            reasons.append(PortfolioRiskRejectReason.POSITION_NOT_READY)
        account_ids = {item.account_id for item in value.positions}
        if not set(policy.required_account_ids).issubset(account_ids):
            reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
        instrument_ids = {item.instrument_id for item in value.instruments}
        if not set(policy.required_instrument_ids).issubset(instrument_ids):
            reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
        active_reservations = sum(
            item.active for item in value.active_reservations
        )
        if (
            enforce_reservation_capacity
            and active_reservations >= policy.max_active_reservations
        ):
            reasons.append(PortfolioRiskRejectReason.ACTIVE_RESERVATION_LIMIT)
        if any(
            item.reporting_asset != policy.reporting_asset
            for item in value.margins
        ):
            reasons.append(PortfolioRiskRejectReason.REPORTING_ASSET_MISMATCH)
        margin_by_id = {item.scope_id: item for item in value.margins}
        if not set(policy.required_margin_scope_ids).issubset(margin_by_id):
            reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
        for scope_id in policy.required_margin_scope_ids:
            margin = margin_by_id.get(scope_id)
            if margin is not None and (
                margin.as_of_ns > now_ns
                or now_ns - margin.as_of_ns > policy.max_margin_age_ns
            ):
                reasons.append(PortfolioRiskRejectReason.SNAPSHOT_EXPIRED)
        liquidation_by_scope = {
            (item.account_id, item.instrument_id): item
            for item in value.liquidation_references
        }
        mark_by_instrument = {
            item.instrument_id: item for item in value.marks
        }
        for requirement in policy.required_liquidation_references:
            reference = liquidation_by_scope.get(
                (requirement.account_id, requirement.instrument_id)
            )
            if reference is None or reference.liquidation_price is None:
                reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
            elif (
                reference.as_of_ns > now_ns
                or now_ns - reference.as_of_ns
                > policy.max_liquidation_age_ns
            ):
                reasons.append(PortfolioRiskRejectReason.SNAPSHOT_EXPIRED)
            else:
                mark = mark_by_instrument.get(requirement.instrument_id)
                if mark is None:
                    reasons.append(PortfolioRiskRejectReason.MARK_MISSING)
                else:
                    mark_value = mark.price.value.as_decimal()
                    liquidation_value = reference.liquidation_price.as_decimal()
                    buffer = abs(mark_value - liquidation_value) / mark_value
                    if buffer < policy.min_liquidation_buffer.as_decimal():
                        reasons.append(
                            PortfolioRiskRejectReason.LIQUIDATION_BUFFER_LIMIT
                        )
        for mark in value.marks:
            if mark.price.as_of_ns > now_ns:
                reasons.append(PortfolioRiskRejectReason.SNAPSHOT_FROM_FUTURE)
            elif (
                now_ns - mark.price.as_of_ns > policy.max_mark_age_ns
                or now_ns > mark.price.valid_until_ns
            ):
                reasons.append(PortfolioRiskRejectReason.MARK_STALE)
        for sensitivity in value.sensitivities:
            sources = (
                sensitivity.delta_per_quantity,
                sensitivity.initial_margin_per_quantity,
                sensitivity.gamma_per_quantity,
                sensitivity.vega_per_quantity,
            )
            if any(
                item is not None and item.as_of_ns > now_ns
                for item in sources
            ):
                reasons.append(PortfolioRiskRejectReason.SNAPSHOT_FROM_FUTURE)
            elif any(
                item is not None
                and (
                    now_ns - item.as_of_ns > policy.max_sensitivity_age_ns
                    or now_ns > item.valid_until_ns
                )
                for item in sources
            ):
                reasons.append(PortfolioRiskRejectReason.SENSITIVITY_STALE)
        return reasons


def _position_quantities(
    snapshot: PortfolioRiskSnapshot,
) -> dict[ScopeKey, Decimal]:
    quantities: dict[ScopeKey, Decimal] = {}
    for account in snapshot.positions:
        for position in account.positions:
            quantities[(account.account_id, position.instrument_id)] = (
                position.effective_quantity.as_decimal()
            )
    return quantities


def _apply_reservations(
    current: dict[ScopeKey, Decimal],
    reservations: tuple[PortfolioRiskReservationView, ...],
    *,
    incoming_basket: BasketTargetIntent,
) -> tuple[dict[ScopeKey, Decimal], list[PortfolioRiskRejectReason]]:
    result = dict(current)
    reasons: list[PortfolioRiskRejectReason] = []
    incoming_scope = {
        (leg.account_id, leg.instrument_id) for leg in incoming_basket.legs
    }
    for reservation in reservations:
        if not reservation.active:
            continue
        reserved_scope = {
            (leg.account_id, leg.instrument_id) for leg in reservation.basket.legs
        }
        if incoming_scope & reserved_scope:
            reasons.append(PortfolioRiskRejectReason.RESERVATION_CONFLICT)
        for leg in reservation.basket.legs:
            key = (leg.account_id, leg.instrument_id)
            transition = (
                leg.target_quantity.as_decimal()
                - current.get(key, Decimal(0))
            )
            result[key] = result.get(key, Decimal(0)) + transition
    return result, reasons


def _apply_working_envelope(
    quantities: dict[ScopeKey, Decimal],
    snapshot: PortfolioRiskSnapshot,
) -> dict[ScopeKey, Decimal]:
    result = dict(quantities)
    for order in snapshot.working_orders:
        key = (order.account_id, order.instrument_id)
        before = result.get(key, Decimal(0))
        after = before + order.signed_remaining_quantity.as_decimal()
        if abs(after) > abs(before):
            result[key] = after
    return result


def _apply_other_reservations(
    current: dict[ScopeKey, Decimal],
    reservations: tuple[PortfolioRiskReservationView, ...],
    *,
    excluded_approval_id: PortfolioApprovalId,
) -> dict[ScopeKey, Decimal]:
    result = dict(current)
    for reservation in reservations:
        if (
            not reservation.active
            or reservation.approval_id == excluded_approval_id
        ):
            continue
        for leg in reservation.basket.legs:
            key = (leg.account_id, leg.instrument_id)
            result[key] = result.get(key, Decimal(0)) + (
                leg.target_quantity.as_decimal()
                - current.get(key, Decimal(0))
            )
    return result


def _calculate_exposure(
    quantities: dict[ScopeKey, Decimal],
    snapshot: PortfolioRiskSnapshot,
    policy: PortfolioRiskPolicy,
    *,
    current_exposure: PortfolioExposure | None = None,
) -> tuple[PortfolioExposure, list[PortfolioRiskRejectReason]]:
    reasons: list[PortfolioRiskRejectReason] = []
    instruments = {item.instrument_id: item for item in snapshot.instruments}
    marks = {item.instrument_id: item for item in snapshot.marks}
    sensitivities = {
        item.instrument_id: item for item in snapshot.sensitivities
    }
    model_policies = {
        item.instrument_id: item for item in policy.instrument_models
    }
    factor_net: defaultdict[RiskFactorId, Decimal] = defaultdict(Decimal)
    factor_gross: defaultdict[RiskFactorId, Decimal] = defaultdict(Decimal)
    factor_gamma: defaultdict[RiskFactorId, Decimal] = defaultdict(Decimal)
    factor_vega: defaultdict[RiskFactorId, Decimal] = defaultdict(Decimal)
    margin_by_scope = {item.scope_id: item for item in snapshot.margins}
    initial_by_scope: defaultdict[MarginScopeId, Decimal] = defaultdict(
        Decimal
    )
    gross_notional = Decimal(0)
    initial_margin = Decimal(0)

    for (_, instrument_id), quantity in quantities.items():
        if quantity == 0:
            continue
        instrument = instruments.get(instrument_id)
        mark = marks.get(instrument_id)
        sensitivity = sensitivities.get(instrument_id)
        model_policy = model_policies.get(instrument_id)
        if instrument is None:
            reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
            continue
        if instrument.status is not InstrumentStatus.ACTIVE:
            reasons.append(PortfolioRiskRejectReason.INSTRUMENT_NOT_ACTIVE)
        if mark is None:
            reasons.append(PortfolioRiskRejectReason.MARK_MISSING)
            continue
        if sensitivity is None:
            reasons.append(PortfolioRiskRejectReason.SENSITIVITY_MISSING)
            continue
        if (
            model_policy is None
            or sensitivity.model_version not in policy.supported_model_versions
            or sensitivity.model_version != model_policy.model_version
        ):
            reasons.append(
                PortfolioRiskRejectReason.UNSUPPORTED_INSTRUMENT_MODEL
            )
            continue
        if (
            sensitivity.delta_per_quantity.unit != model_policy.delta_unit
            or sensitivity.initial_margin_per_quantity.unit
            != model_policy.initial_margin_unit
            or (
                model_policy.gamma_unit is None
                and sensitivity.gamma_per_quantity is not None
            )
            or (
                model_policy.gamma_unit is not None
                and (
                    sensitivity.gamma_per_quantity is None
                    or sensitivity.gamma_per_quantity.unit
                    != model_policy.gamma_unit
                )
            )
            or (
                model_policy.vega_unit is None
                and sensitivity.vega_per_quantity is not None
            )
            or (
                model_policy.vega_unit is not None
                and (
                    sensitivity.vega_per_quantity is None
                    or sensitivity.vega_per_quantity.unit
                    != model_policy.vega_unit
                )
            )
        ):
            reasons.append(
                PortfolioRiskRejectReason.SENSITIVITY_UNIT_MISMATCH
            )
            continue
        if (
            mark.price.asset != policy.reporting_asset
            or sensitivity.initial_margin_per_quantity.asset
            != policy.reporting_asset
        ):
            reasons.append(PortfolioRiskRejectReason.REPORTING_ASSET_MISMATCH)
            continue
        try:
            notional = _notional(
                instrument,
                quantity,
                mark.price.value.as_decimal(),
            )
        except UnsupportedPortfolioRiskModelError:
            reasons.append(
                PortfolioRiskRejectReason.UNSUPPORTED_INSTRUMENT_MODEL
            )
            continue
        delta = (
            quantity
            * sensitivity.delta_per_quantity.value.as_decimal()
        )
        factor = sensitivity.risk_factor_id
        factor_net[factor] += delta
        factor_gross[factor] += abs(delta)
        if sensitivity.gamma_per_quantity is not None:
            factor_gamma[factor] += (
                quantity
                * sensitivity.gamma_per_quantity.value.as_decimal()
            )
        if sensitivity.vega_per_quantity is not None:
            factor_vega[factor] += (
                quantity
                * sensitivity.vega_per_quantity.value.as_decimal()
            )
        gross_notional += notional
        initial_margin += (
            abs(quantity)
            * sensitivity.initial_margin_per_quantity.value.as_decimal()
        )
        margin_amount = (
            abs(quantity)
            * sensitivity.initial_margin_per_quantity.value.as_decimal()
        )
        if margin_amount != 0:
            if sensitivity.margin_scope_id is None:
                reasons.append(
                    PortfolioRiskRejectReason.UNSUPPORTED_INSTRUMENT_MODEL
                )
            elif sensitivity.margin_scope_id not in margin_by_scope:
                reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
            else:
                initial_by_scope[sensitivity.margin_scope_id] += margin_amount

    current_margin_scopes = (
        {}
        if current_exposure is None
        else {item.scope_id: item for item in current_exposure.margin_scopes}
    )
    margin_scope_exposures: list[MarginScopeExposure] = []
    for scope_id in sorted(margin_by_scope, key=str):
        margin = margin_by_scope[scope_id]
        initial = initial_by_scope[scope_id]
        current_scope = current_margin_scopes.get(scope_id)
        available = margin.available_margin.as_decimal()
        if current_scope is not None:
            available += (
                current_scope.initial_margin.as_decimal() - initial
            )
        margin_scope_exposures.append(
            MarginScopeExposure(
                scope_id=scope_id,
                reporting_asset=margin.reporting_asset,
                initial_margin=_money(initial),
                available_margin=_money(available),
            )
        )
    margin_available = sum(
        (
            item.available_margin.as_decimal()
            for item in margin_scope_exposures
        ),
        Decimal(0),
    )
    factors = tuple(
        RiskFactorExposure(
            risk_factor_id=factor,
            net_delta=_fixed(factor_net[factor]),
            gross_delta=_fixed(factor_gross[factor]),
            gamma=_fixed(factor_gamma[factor]),
            vega=_fixed(factor_vega[factor]),
        )
        for factor in sorted(
            set(factor_net)
            | set(factor_gross)
            | set(factor_gamma)
            | set(factor_vega),
            key=str,
        )
    )
    return (
        PortfolioExposure(
            reporting_asset=policy.reporting_asset,
            gross_notional=_money(gross_notional),
            initial_margin=_money(initial_margin),
            available_margin=_money(margin_available),
            factors=factors,
            margin_scopes=tuple(margin_scope_exposures),
        ),
        _deduplicate_reasons(reasons),
    )


def _limit_reasons(
    exposure: PortfolioExposure,
    snapshot: PortfolioRiskSnapshot,
    policy: PortfolioRiskPolicy,
) -> list[PortfolioRiskRejectReason]:
    reasons: list[PortfolioRiskRejectReason] = []
    if exposure.gross_notional.as_decimal() > policy.max_gross_notional.as_decimal():
        reasons.append(PortfolioRiskRejectReason.GROSS_NOTIONAL_LIMIT)
    if exposure.initial_margin.as_decimal() > policy.max_initial_margin.as_decimal():
        reasons.append(PortfolioRiskRejectReason.INITIAL_MARGIN_LIMIT)
    if (
        exposure.available_margin.as_decimal()
        < policy.min_available_margin.as_decimal()
        or any(
            item.available_margin.as_decimal()
            < policy.min_available_margin.as_decimal()
            for item in exposure.margin_scopes
        )
    ):
        reasons.append(PortfolioRiskRejectReason.AVAILABLE_MARGIN_LIMIT)
    by_factor = {item.risk_factor_id: item for item in exposure.factors}
    for limit in policy.factor_limits:
        measured = by_factor.get(limit.risk_factor_id)
        if measured is None:
            continue
        if (
            abs(measured.net_delta.as_decimal())
            > limit.max_abs_net_delta.as_decimal()
            or measured.gross_delta.as_decimal()
            > limit.max_gross_delta.as_decimal()
            or (
                limit.max_abs_gamma is not None
                and abs(measured.gamma.as_decimal())
                > limit.max_abs_gamma.as_decimal()
            )
            or (
                limit.max_abs_vega is not None
                and abs(measured.vega.as_decimal())
                > limit.max_abs_vega.as_decimal()
            )
        ):
            reasons.append(PortfolioRiskRejectReason.RISK_FACTOR_LIMIT)
    spreads = {item.spread_id: item.value for item in snapshot.spread_inputs}
    for spread_limit in policy.spread_limits:
        value = spreads.get(spread_limit.spread_id)
        if value is None:
            reasons.append(PortfolioRiskRejectReason.SCOPE_INCOMPLETE)
        elif (
            abs(value.value.as_decimal())
            > spread_limit.max_abs_value.as_decimal()
        ):
            reasons.append(PortfolioRiskRejectReason.SPREAD_LIMIT)
    return reasons


def _notional(
    instrument: Instrument,
    signed_quantity: Decimal,
    mark_price: Decimal,
) -> Decimal:
    quantity = abs(signed_quantity)
    specification = instrument.specification
    if isinstance(specification, SpotSpecification):
        return quantity * mark_price
    if isinstance(specification, (PerpetualSpecification, FutureSpecification)):
        size = specification.contract_size.as_decimal()
        if specification.value_type is ContractValueType.LINEAR:
            return quantity * size * mark_price
        if specification.value_type is ContractValueType.INVERSE:
            return quantity * size
        raise UnsupportedPortfolioRiskModelError
    if isinstance(specification, OptionSpecification):
        return quantity * specification.contract_size.as_decimal() * mark_price
    raise UnsupportedPortfolioRiskModelError


class UnsupportedPortfolioRiskModelError(ValueError):
    """Instrument valuation model is intentionally unsupported."""


def _source_valid_until(snapshot: PortfolioRiskSnapshot) -> int:
    deadlines = [
        int(item.price.valid_until_ns) for item in snapshot.marks
    ]
    for item in snapshot.sensitivities:
        deadlines.extend(
            int(value.valid_until_ns)
            for value in (
                item.delta_per_quantity,
                item.initial_margin_per_quantity,
                item.gamma_per_quantity,
                item.vega_per_quantity,
            )
            if value is not None
        )
    return min(deadlines) if deadlines else 0


def _assessment_checksum(
    *,
    basket: BasketTargetIntent,
    snapshot_id: object,
    policy_version: int,
    current: PortfolioExposure,
    projected: PortfolioExposure,
    conservative: PortfolioExposure,
) -> str:
    return _sha256(
        {
            "basket_checksum": basket_target_intent_checksum(basket),
            "conservative": _exposure_payload(conservative),
            "current": _exposure_payload(current),
            "policy_version": policy_version,
            "projected": _exposure_payload(projected),
            "snapshot_id": str(snapshot_id),
        }
    )


def _exposure_payload(exposure: PortfolioExposure) -> object:
    return {
        "available_margin": _fixed_payload(exposure.available_margin),
        "factors": [
            {
                "gamma": _fixed_payload(item.gamma),
                "gross_delta": _fixed_payload(item.gross_delta),
                "net_delta": _fixed_payload(item.net_delta),
                "risk_factor_id": str(item.risk_factor_id),
                "vega": _fixed_payload(item.vega),
            }
            for item in exposure.factors
        ],
        "gross_notional": _fixed_payload(exposure.gross_notional),
        "initial_margin": _fixed_payload(exposure.initial_margin),
        "margin_scopes": [
            {
                "available_margin": _fixed_payload(item.available_margin),
                "initial_margin": _fixed_payload(item.initial_margin),
                "reporting_asset": str(item.reporting_asset),
                "scope_id": str(item.scope_id),
            }
            for item in exposure.margin_scopes
        ],
        "reporting_asset": str(exposure.reporting_asset),
    }


def _fixed_payload(value: FixedPoint) -> dict[str, int]:
    return {"raw": value.raw, "scale": value.scale}


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fixed(value: Decimal) -> FixedPoint:
    return FixedPoint.from_str(format(value, "f"))


def _money(value: Decimal) -> Money:
    return Money.from_str(format(value, "f"))


def _deduplicate_reasons(
    reasons: list[PortfolioRiskRejectReason],
) -> list[PortfolioRiskRejectReason]:
    return list(dict.fromkeys(reasons))


__all__ = ["PortfolioRiskEngine", "UnsupportedPortfolioRiskModelError"]
