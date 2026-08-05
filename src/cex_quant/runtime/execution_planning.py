"""Bounded Runtime registry for deterministic Order Group planners."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from itertools import islice
from types import MappingProxyType
from typing import Protocol, TypeVar

from cex_quant.core import Quantity, UnixNanos
from cex_quant.oms import (
    ExecutionAction,
    ExecutionPlanRef,
    ExecutionStage,
    OrderGroupView,
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
    create_execution_stage,
    deterministic_group_action_id,
)
from cex_quant.risk import PortfolioRiskSnapshot
from cex_quant.strategy import BasketTargetIntent, ObjectiveTypeRef

MAX_REGISTERED_EXECUTION_PLANS = 64
MAX_OBJECTIVE_EXECUTION_PLAN_BINDINGS = 256

_T = TypeVar("_T")


class ExecutionPlanningConfigurationError(ValueError):
    """Execution planning configuration is incomplete or ambiguous."""


class OrderGroupPlanner(Protocol):
    """Propose one bounded deterministic Stage without owning authority."""

    def propose(
        self,
        group: OrderGroupView,
        portfolio: PortfolioRiskSnapshot,
        now_ns: UnixNanos,
    ) -> ExecutionStage | None: ...


class ExecutionPlanResolver(Protocol):
    """Resolve immutable Basket metadata to one registered plan reference."""

    def resolve(self, basket: BasketTargetIntent) -> ExecutionPlanRef: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPlannerBinding:
    execution_plan: ExecutionPlanRef
    planner: OrderGroupPlanner

    def __post_init__(self) -> None:
        if not callable(getattr(self.planner, "propose", None)):
            raise ExecutionPlanningConfigurationError(
                "execution planner must provide propose"
            )


class ExecutionPlannerRegistry:
    """Immutable exact registry keyed by the full execution-plan reference."""

    def __init__(
        self,
        bindings: Iterable[ExecutionPlannerBinding],
        *,
        max_registered_plans: int = MAX_REGISTERED_EXECUTION_PLANS,
    ) -> None:
        configured = _bounded_values(
            bindings,
            maximum=max_registered_plans,
            label="execution planner registry",
        )
        by_plan: dict[ExecutionPlanRef, OrderGroupPlanner] = {}
        for binding in configured:
            if not isinstance(binding, ExecutionPlannerBinding):
                raise ExecutionPlanningConfigurationError(
                    "planner bindings must be ExecutionPlannerBinding values"
                )
            if binding.execution_plan in by_plan:
                raise ExecutionPlanningConfigurationError(
                    "execution planner registry contains a duplicate plan"
                )
            by_plan[binding.execution_plan] = binding.planner
        self._bindings = configured
        self._by_plan = MappingProxyType(by_plan)

    @property
    def bindings(self) -> tuple[ExecutionPlannerBinding, ...]:
        return self._bindings

    def require(self, execution_plan: ExecutionPlanRef) -> OrderGroupPlanner:
        try:
            return self._by_plan[execution_plan]
        except KeyError as error:
            raise ExecutionPlanningConfigurationError(
                "execution plan is not registered: "
                f"{execution_plan.execution_plan_id!s}@{execution_plan.version}"
            ) from error


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectiveExecutionPlanBinding:
    objective: ObjectiveTypeRef
    execution_plan: ExecutionPlanRef


class ObjectiveExecutionPlanResolver:
    """Fail closed on exact, versioned objective metadata."""

    def __init__(
        self,
        bindings: Iterable[ObjectiveExecutionPlanBinding],
        *,
        max_bindings: int = MAX_OBJECTIVE_EXECUTION_PLAN_BINDINGS,
    ) -> None:
        configured = _bounded_values(
            bindings,
            maximum=max_bindings,
            label="objective execution-plan resolver",
        )
        by_objective: dict[ObjectiveTypeRef, ExecutionPlanRef] = {}
        for binding in configured:
            if not isinstance(binding, ObjectiveExecutionPlanBinding):
                raise ExecutionPlanningConfigurationError(
                    "objective bindings must be ObjectiveExecutionPlanBinding values"
                )
            if binding.objective in by_objective:
                raise ExecutionPlanningConfigurationError(
                    "objective resolver contains a duplicate objective"
                )
            by_objective[binding.objective] = binding.execution_plan
        self._bindings = configured
        self._by_objective = MappingProxyType(by_objective)

    @property
    def bindings(self) -> tuple[ObjectiveExecutionPlanBinding, ...]:
        return self._bindings

    def resolve(self, basket: BasketTargetIntent) -> ExecutionPlanRef:
        try:
            return self._by_objective[basket.objective]
        except KeyError as error:
            raise ExecutionPlanningConfigurationError(
                "execution plan is not configured for objective "
                f"{basket.objective.objective_type_id!s}"
                f"@{basket.objective.version}"
            ) from error


@dataclass(frozen=True, slots=True, kw_only=True)
class StaticExecutionPlanResolver:
    """Compatibility resolver for one-plan deployments."""

    execution_plan: ExecutionPlanRef

    def resolve(self, basket: BasketTargetIntent) -> ExecutionPlanRef:
        del basket
        return self.execution_plan


class SequentialResidualExecutionPlanner:
    """Generic width-one market-residual reference Stage planner."""

    def propose(
        self,
        group: OrderGroupView,
        portfolio: PortfolioRiskSnapshot,
        now_ns: UnixNanos,
    ) -> ExecutionStage | None:
        if any(leg.unresolved_action_ids for leg in group.legs):
            return None
        current = {
            (account.account_id, position.instrument_id): (
                position.effective_quantity.as_decimal()
            )
            for account in portfolio.positions
            for position in account.positions
        }
        for leg in group.legs:
            before = current.get(
                (leg.account_id, leg.instrument_id),
                Decimal(0),
            )
            target = leg.target_quantity.as_decimal()
            residual = target - before - leg.signed_working_quantity.as_decimal()
            if residual == 0:
                continue
            attempt = len(leg.child_order_ids) + 1
            action_id = deterministic_group_action_id(
                group_id=group.order_group_id,
                expected_group_revision=group.revision,
                basket_leg_id=leg.basket_leg_id,
                execution_plan=group.execution_plan,
                action_kind="market_residual",
                leg_attempt_sequence=attempt,
            )
            action = ExecutionAction(
                group_id=group.order_group_id,
                expected_group_revision=group.revision,
                action_id=action_id,
                basket_leg_id=leg.basket_leg_id,
                account_id=leg.account_id,
                instrument_id=leg.instrument_id,
                side=(OrderSide.BUY if residual > 0 else OrderSide.SELL),
                order_type=OrderType.MARKET,
                quantity=Quantity.from_str(format(abs(residual), "f")),
                time_in_force=TimeInForce.GTC,
                limit_price=None,
                stop_price=None,
                reduce_only=_is_pure_reduction(before, target),
                post_only=False,
                position_side=PositionSide.NET,
                execution_plan=group.execution_plan,
                created_at_ns=now_ns,
            )
            return create_execution_stage(
                group_id=group.order_group_id,
                base_group_revision=group.revision,
                execution_plan=group.execution_plan,
                actions=(action,),
                dispatch_width=1,
                created_at_ns=now_ns,
            )
        return None


def default_execution_planning(
    execution_plan: ExecutionPlanRef,
) -> tuple[ExecutionPlanResolver, ExecutionPlannerRegistry]:
    """Build the backwards-compatible one-plan Runtime composition."""

    return (
        StaticExecutionPlanResolver(execution_plan=execution_plan),
        ExecutionPlannerRegistry(
            (
                ExecutionPlannerBinding(
                    execution_plan=execution_plan,
                    planner=SequentialResidualExecutionPlanner(),
                ),
            )
        ),
    )


def _bounded_values(
    values: Iterable[_T],
    *,
    maximum: int,
    label: str,
) -> tuple[_T, ...]:
    if maximum <= 0:
        raise ExecutionPlanningConfigurationError(f"{label} maximum must be positive")
    configured = tuple(islice(iter(values), maximum + 1))
    if not configured:
        raise ExecutionPlanningConfigurationError(
            f"{label} requires at least one binding"
        )
    if len(configured) > maximum:
        raise ExecutionPlanningConfigurationError(f"{label} exceeds configured maximum")
    return configured


def _is_pure_reduction(before: Decimal, target: Decimal) -> bool:
    return before != 0 and before * target >= 0 and abs(target) < abs(before)


__all__ = [
    "MAX_OBJECTIVE_EXECUTION_PLAN_BINDINGS",
    "MAX_REGISTERED_EXECUTION_PLANS",
    "ExecutionPlanResolver",
    "ExecutionPlannerBinding",
    "ExecutionPlannerRegistry",
    "ExecutionPlanningConfigurationError",
    "ObjectiveExecutionPlanBinding",
    "ObjectiveExecutionPlanResolver",
    "OrderGroupPlanner",
    "SequentialResidualExecutionPlanner",
    "StaticExecutionPlanResolver",
    "default_execution_planning",
]
