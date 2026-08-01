"""Runtime-owned projection of Portfolio and Accounting truth into Carry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cex_quant.accounting import (
    AccountingLedgerView,
    BalanceReconciliationProof,
    PnlAttributionView,
    SourceCompletenessProof,
)
from cex_quant.applications.carry import (
    ApplicationPositionId,
    CarryFinancialState,
    CarryHedgeAssessment,
    CarryHedgeState,
    CarryLifecycle,
    CarryPositionView,
    assess_carry_financial_state,
    assess_linear_funding_carry_hedge,
)
from cex_quant.applications.carry.funding_arbitrage import FundingCarryPair
from cex_quant.applications.carry.state import CarryPositionBook
from cex_quant.core import AttributionAllocationId, Quantity, UnixNanos
from cex_quant.oms import OrderGroupStatus, OrderGroupView
from cex_quant.portfolio import AccountPositionRiskView, PositionRiskReadiness
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import BasketTargetIntent


class CarryReadSideProjectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryFinancialEvidence:
    attribution: PnlAttributionView | None
    source_proofs: tuple[SourceCompletenessProof, ...]
    balance_proofs: tuple[BalanceReconciliationProof, ...]
    allocation_ids: tuple[AttributionAllocationId, ...]
    ledger: AccountingLedgerView


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryReadSideProjection:
    position: CarryPositionView
    hedge: CarryHedgeAssessment
    financial_state: CarryFinancialState


class CarryReadSideProjector:
    """Keep Carry lifecycle evidence separate from its source domains."""

    def __init__(
        self,
        book: CarryPositionBook,
        *,
        now_ns: Callable[[], UnixNanos],
    ) -> None:
        self._book = book
        self._now_ns = now_ns

    def link_opening_admission(
        self,
        position_id: ApplicationPositionId,
        *,
        basket: BasketTargetIntent,
        group: OrderGroupView,
    ) -> CarryPositionView:
        current = self._book.position(position_id)
        if current.strategy_id != basket.strategy_id:
            raise CarryReadSideProjectionError(
                "Basket strategy does not own the Carry position"
            )
        if current.opening_snapshot_id != basket.decision_snapshot_id:
            raise CarryReadSideProjectionError(
                "opening Basket snapshot does not match the Carry position"
            )
        if group.source_intent_id != basket.intent_id:
            raise CarryReadSideProjectionError(
                "Order Group is not caused by the supplied Basket"
            )
        if group.status is not OrderGroupStatus.ACTIVE:
            raise CarryReadSideProjectionError(
                "opening Order Group must be ACTIVE before Carry linking"
            )
        occurred_at_ns = self._now_ns()
        linked = self._book.link_intent(
            position_id,
            intent_id=basket.intent_id,
            source_snapshot_id=basket.decision_snapshot_id,
            occurred_at_ns=occurred_at_ns,
            policy_version=basket.policy_version,
        )
        linked = self._book.link_order_group(
            position_id,
            order_group_id=group.order_group_id,
            source_snapshot_id=basket.decision_snapshot_id,
            occurred_at_ns=occurred_at_ns,
            policy_version=basket.policy_version,
        )
        if linked.lifecycle is CarryLifecycle.PROPOSED:
            linked = self._book.transition(
                position_id,
                lifecycle=CarryLifecycle.OPENING,
                hedge_state=linked.hedge_state,
                financial_state=linked.financial_state,
                source_snapshot_id=basket.decision_snapshot_id,
                occurred_at_ns=occurred_at_ns,
                policy_version=basket.policy_version,
            )
        elif linked.lifecycle is not CarryLifecycle.OPENING:
            raise CarryReadSideProjectionError(
                "Carry position is not eligible for opening admission"
            )
        return linked

    def project(
        self,
        position_id: ApplicationPositionId,
        *,
        pair: FundingCarryPair,
        positions: tuple[AccountPositionRiskView, ...],
        tolerance_base_quantity: Quantity,
        financial: CarryFinancialEvidence,
        source_snapshot_id: DecisionSnapshotId,
        policy_version: int,
        execution_recovery_reason: str = "",
    ) -> CarryReadSideProjection:
        if execution_recovery_reason.strip() != execution_recovery_reason:
            raise ValueError("execution recovery reason must be trimmed")
        current = self._book.position(position_id)
        hedge = assess_linear_funding_carry_hedge(
            pair=pair,
            ownership=current.leg_ownership,
            positions=positions,
            tolerance_base_quantity=tolerance_base_quantity,
            assessed_at_ns=self._now_ns(),
            policy_version=policy_version,
        )
        financial_state = assess_carry_financial_state(
            attribution=financial.attribution,
            source_proofs=financial.source_proofs,
            balance_proofs=financial.balance_proofs,
            allocation_ids=financial.allocation_ids,
            ledger=financial.ledger,
        )
        lifecycle, reason = _next_lifecycle(
            current,
            hedge=hedge,
            execution_recovery_reason=execution_recovery_reason,
            opening_target_reached=_owned_quantities_match(
                current,
                positions,
                opening_target=True,
            ),
            closing_baseline_reached=_owned_quantities_match(
                current,
                positions,
                opening_target=False,
            ),
        )
        if (
            current.lifecycle is CarryLifecycle.RECOVERY_REQUIRED
            and lifecycle is CarryLifecycle.ACTIVE
        ):
            self._book.transition(
                position_id,
                lifecycle=CarryLifecycle.OPENING,
                hedge_state=hedge.state,
                financial_state=financial_state,
                source_snapshot_id=source_snapshot_id,
                occurred_at_ns=self._now_ns(),
                policy_version=policy_version,
            )
        projected = self._book.transition(
            position_id,
            lifecycle=lifecycle,
            hedge_state=hedge.state,
            financial_state=financial_state,
            source_snapshot_id=source_snapshot_id,
            occurred_at_ns=self._now_ns(),
            policy_version=policy_version,
            reason=reason,
        )
        return CarryReadSideProjection(
            position=projected,
            hedge=hedge,
            financial_state=financial_state,
        )


def _next_lifecycle(
    current: CarryPositionView,
    *,
    hedge: CarryHedgeAssessment,
    execution_recovery_reason: str,
    opening_target_reached: bool,
    closing_baseline_reached: bool,
) -> tuple[CarryLifecycle, str]:
    recovery_reason = execution_recovery_reason
    if hedge.state is CarryHedgeState.UNKNOWN:
        recovery_reason = recovery_reason or hedge.reason
    if recovery_reason:
        return CarryLifecycle.RECOVERY_REQUIRED, recovery_reason
    if current.lifecycle in {
        CarryLifecycle.OPENING,
        CarryLifecycle.RECOVERY_REQUIRED,
    }:
        if (
            hedge.state is CarryHedgeState.HEDGED
            and opening_target_reached
        ):
            return CarryLifecycle.ACTIVE, ""
        return CarryLifecycle.OPENING, ""
    if current.lifecycle is CarryLifecycle.ACTIVE:
        if (
            hedge.state is CarryHedgeState.HEDGED
            and opening_target_reached
        ):
            return CarryLifecycle.ACTIVE, ""
        return (
            CarryLifecycle.RECOVERY_REQUIRED,
            "active Carry position no longer matches its owned target",
        )
    if current.lifecycle is CarryLifecycle.CLOSING:
        if (
            hedge.state is CarryHedgeState.HEDGED
            and closing_baseline_reached
        ):
            return CarryLifecycle.CLOSED, ""
        return CarryLifecycle.CLOSING, ""
    if current.lifecycle is CarryLifecycle.HALTED:
        return CarryLifecycle.HALTED, current.recovery_reason
    return current.lifecycle, ""


def _owned_quantities_match(
    current: CarryPositionView,
    positions: tuple[AccountPositionRiskView, ...],
    *,
    opening_target: bool,
) -> bool:
    accounts = {item.account_id: item for item in positions}
    for ownership in current.leg_ownership:
        account = accounts.get(ownership.account_id)
        if (
            account is None
            or account.readiness is not PositionRiskReadiness.READY
        ):
            return False
        actual = next(
            (
                item.effective_quantity.as_decimal()
                for item in account.positions
                if item.instrument_id == ownership.instrument_id
            ),
            Quantity.from_str("0").as_decimal(),
        )
        expected = ownership.baseline_quantity.as_decimal()
        if opening_target:
            expected += ownership.intended_owned_delta.as_decimal()
        if actual != expected:
            return False
    return True


__all__ = [
    "CarryFinancialEvidence",
    "CarryReadSideProjection",
    "CarryReadSideProjectionError",
    "CarryReadSideProjector",
]
