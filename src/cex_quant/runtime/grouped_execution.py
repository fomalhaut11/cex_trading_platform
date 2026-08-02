"""Mode-neutral owner-thread composition for one grouped execution loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from threading import get_ident
from typing import Never, Protocol, cast

from cex_quant.core import ClientOrderId, OrderGroupId, Quantity, UnixNanos
from cex_quant.execution import (
    CancelOrder,
    CancelResult,
    ExecutionOutcome,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    SubmitResult,
)
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionState,
    ExecutionPlanRef,
    OrderEvent,
    OrderGroupAdmission,
    OrderGroupStatus,
    OrderGroupView,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderSubmitOutcome,
    OrderType,
    OrderView,
    PositionSide,
    TimeInForce,
    deterministic_group_action_id,
)
from cex_quant.risk import (
    BasketPortfolioRiskDecision,
    ExecutionActionRiskDecision,
    PortfolioRiskCoordinator,
    PortfolioRiskEngine,
    PortfolioRiskPolicy,
    PortfolioRiskReservationView,
    PortfolioRiskSnapshot,
)
from cex_quant.snapshots import DecisionSnapshotPublication
from cex_quant.strategy import (
    BasketTargetIntent,
    basket_target_intent_checksum,
)

from .execution_handoff import (
    DurableExecutionHandoff,
    ExternalSubmitBlockedError,
    ExternalSubmitGuardPort,
    SynchronousExecutionSubmitPort,
)
from .order_group_runtime import OrderGroupRuntime
from .portfolio_risk_guard import PortfolioRiskExecutionGuard


class GroupedExecutionRuntimeStatus(StrEnum):
    NEW = "new"
    RUNNING = "running"
    HALTED = "halted"
    RECOVERY_REQUIRED = "recovery_required"
    STOPPED = "stopped"
    FAILED = "failed"


class GroupedBootstrapStep(StrEnum):
    JOURNALS_REPLAYED = "journals_replayed"
    PORTFOLIO_RECONCILED = "portfolio_reconciled"
    ORDERS_RECONCILED = "orders_reconciled"
    OMS_EFFECTS_PROJECTED = "oms_effects_projected"
    ACCOUNTING_DRAINED = "accounting_drained"
    CARRY_PROJECTED = "carry_projected"


GROUPED_BOOTSTRAP_ORDER = (
    GroupedBootstrapStep.JOURNALS_REPLAYED,
    GroupedBootstrapStep.PORTFOLIO_RECONCILED,
    GroupedBootstrapStep.ORDERS_RECONCILED,
    GroupedBootstrapStep.OMS_EFFECTS_PROJECTED,
    GroupedBootstrapStep.ACCOUNTING_DRAINED,
    GroupedBootstrapStep.CARRY_PROJECTED,
)


class GroupedAdmissionDisposition(StrEnum):
    ADMITTED = "admitted"
    RISK_REJECTED = "risk_rejected"


class GroupedExecutionStepDisposition(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFINITELY_NOT_SENT = "definitely_not_sent"
    UNKNOWN = "unknown"
    RISK_REJECTED = "risk_rejected"
    NO_ACTION = "no_action"


class GroupedCancelDisposition(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFINITELY_NOT_SENT = "definitely_not_sent"
    UNKNOWN = "unknown"


class GroupedExecutionRuntimeError(RuntimeError):
    pass


class GroupedExecutionRuntimeStateError(GroupedExecutionRuntimeError):
    pass


class GroupedExecutionWriterViolationError(GroupedExecutionRuntimeError):
    pass


class SynchronousExecutionCancelPort(Protocol):
    def cancel(self, command: CancelOrder) -> CancelResult: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupedBootstrapEvidence:
    completed_steps: tuple[GroupedBootstrapStep, ...]
    external_io_disabled: bool
    healthy: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if self.completed_steps != GROUPED_BOOTSTRAP_ORDER[
            : len(self.completed_steps)
        ]:
            raise ValueError("grouped bootstrap steps are out of order")
        if self.reason.strip() != self.reason:
            raise ValueError("bootstrap reason must be trimmed")
        if not self.healthy and not self.reason:
            raise ValueError("unhealthy bootstrap evidence requires a reason")

    @property
    def ready(self) -> bool:
        return (
            self.completed_steps == GROUPED_BOOTSTRAP_ORDER
            and self.external_io_disabled
            and self.healthy
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupedAdmissionResult:
    disposition: GroupedAdmissionDisposition
    decision: BasketPortfolioRiskDecision
    group: OrderGroupView | None = None
    reservation: PortfolioRiskReservationView | None = None

    def __post_init__(self) -> None:
        admitted = self.disposition is GroupedAdmissionDisposition.ADMITTED
        if admitted != (self.group is not None and self.reservation is not None):
            raise ValueError("only admitted result contains group and reservation")


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupedExecutionStepResult:
    disposition: GroupedExecutionStepDisposition
    group: OrderGroupView
    action: ExecutionAction | None = None
    risk_decision: ExecutionActionRiskDecision | None = None
    submit_result: SubmitResult | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.reason and self.reason.strip() != self.reason:
            raise ValueError("step reason must be trimmed")
        if self.disposition is GroupedExecutionStepDisposition.NO_ACTION:
            if any(
                item is not None
                for item in (self.action, self.risk_decision, self.submit_result)
            ):
                raise ValueError("NO_ACTION cannot contain action evidence")
        elif self.action is None or self.risk_decision is None:
            raise ValueError("action step requires action and Risk decision")


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupedCancelResult:
    disposition: GroupedCancelDisposition
    group: OrderGroupView
    client_order_id: ClientOrderId
    cancel_result: CancelResult | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.reason.strip() != self.reason:
            raise ValueError("cancel reason must be trimmed")
        if self.disposition is GroupedCancelDisposition.ACCEPTED:
            if self.cancel_result is None:
                raise ValueError("accepted cancel requires immediate evidence")
        elif not self.reason:
            raise ValueError("non-accepted cancel requires a reason")


class GroupedExecutionRuntime:
    """Serialize Basket admission and one exact child action at a time."""

    def __init__(
        self,
        *,
        risk_engine: PortfolioRiskEngine,
        risk_coordinator: PortfolioRiskCoordinator,
        groups: OrderGroupRuntime,
        execution: SynchronousExecutionSubmitPort,
        cancel_execution: SynchronousExecutionCancelPort | None = None,
        platform_guard: ExternalSubmitGuardPort,
        execution_plan: ExecutionPlanRef,
        now_ns: Callable[[], UnixNanos],
    ) -> None:
        self._risk_engine = risk_engine
        self._risk_coordinator = risk_coordinator
        self._groups = groups
        self._execution = execution
        self._cancel_execution = cancel_execution
        self._platform_guard = platform_guard
        self._execution_plan = execution_plan
        self._now_ns = now_ns
        self._writer_thread_id = get_ident()
        self._status = GroupedExecutionRuntimeStatus.NEW
        self._failure: BaseException | None = None

    @property
    def status(self) -> GroupedExecutionRuntimeStatus:
        return self._status

    @property
    def failure(self) -> BaseException | None:
        return self._failure

    def start(self) -> None:
        self._assert_writer()
        if self._status is not GroupedExecutionRuntimeStatus.NEW:
            raise GroupedExecutionRuntimeStateError(
                f"cannot start grouped runtime from {self._status.value}"
            )
        recovered_groups = self._groups.groups()
        if not recovered_groups:
            self._status = GroupedExecutionRuntimeStatus.RUNNING
        elif self._groups.recovery_candidates() or any(
            item.status is OrderGroupStatus.RECOVERY_REQUIRED
            for item in recovered_groups
        ):
            self._status = GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED
        else:
            self._status = GroupedExecutionRuntimeStatus.HALTED

    def complete_bootstrap(
        self,
        evidence: GroupedBootstrapEvidence,
        *,
        recovery_authorization_id: str = "",
    ) -> None:
        self._assert_writer()
        if self._status not in {
            GroupedExecutionRuntimeStatus.HALTED,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        }:
            raise GroupedExecutionRuntimeStateError(
                "bootstrap completion requires a halted or recovery runtime"
            )
        if not evidence.ready:
            raise GroupedExecutionRuntimeStateError(
                "grouped bootstrap evidence is incomplete or unhealthy"
            )
        if self._groups.recovery_candidates():
            raise GroupedExecutionRuntimeStateError(
                "OMS recovery candidates remain unresolved"
            )
        recovery_groups = tuple(
            item
            for item in self._groups.groups()
            if item.status is OrderGroupStatus.RECOVERY_REQUIRED
        )
        non_runnable_groups = tuple(
            item
            for item in self._groups.groups()
            if item.status
            not in {
                OrderGroupStatus.ACTIVE,
                OrderGroupStatus.CLOSED,
                OrderGroupStatus.RECOVERY_REQUIRED,
            }
        )
        if non_runnable_groups:
            states = ",".join(
                sorted({item.status.value for item in non_runnable_groups})
            )
            raise GroupedExecutionRuntimeStateError(
                f"non-runnable Order Group state remains after bootstrap: {states}"
            )
        if recovery_groups and not recovery_authorization_id.strip():
            raise GroupedExecutionRuntimeStateError(
                "group recovery requires explicit authorization evidence"
            )
        for group in recovery_groups:
            self._groups.resume_group(
                group.order_group_id,
                recovery_authorization_id=recovery_authorization_id,
            )
        self._status = GroupedExecutionRuntimeStatus.RUNNING

    def stop(self) -> None:
        self._assert_writer()
        if self._status is GroupedExecutionRuntimeStatus.STOPPED:
            return
        if self._status not in {
            GroupedExecutionRuntimeStatus.NEW,
            GroupedExecutionRuntimeStatus.RUNNING,
            GroupedExecutionRuntimeStatus.HALTED,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        }:
            raise GroupedExecutionRuntimeStateError(
                f"cannot stop grouped runtime from {self._status.value}"
            )
        self._status = GroupedExecutionRuntimeStatus.STOPPED

    def admit(
        self,
        basket: BasketTargetIntent,
        risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
        policy: PortfolioRiskPolicy,
    ) -> GroupedAdmissionResult:
        self._require_running()
        now_ns = self._now_ns()
        try:
            decision = self._risk_engine.assess_basket(
                basket,
                risk_snapshot,
                policy,
                now_ns=now_ns,
            )
            if not decision.allowed:
                return GroupedAdmissionResult(
                    disposition=GroupedAdmissionDisposition.RISK_REJECTED,
                    decision=decision,
                )
            approval = self._risk_coordinator.reserve_approval(
                decision,
                now_ns=now_ns,
            )
            created = self._groups.create_group(
                OrderGroupAdmission(
                    approval_id=approval.approval_id,
                    basket=basket,
                    basket_checksum=basket_target_intent_checksum(basket),
                    approved_at_ns=approval.approved_at_ns,
                    valid_until_ns=approval.valid_until_ns,
                    risk_policy_version=approval.risk_policy_version,
                ),
                self._execution_plan,
            )
            reservation = self._risk_coordinator.attach_reservation(
                approval.approval_id,
                created.order_group_id,
                now_ns=self._now_ns(),
            )
            group = self._groups.activate_group(created.order_group_id)
            return GroupedAdmissionResult(
                disposition=GroupedAdmissionDisposition.ADMITTED,
                decision=decision,
                group=group,
                reservation=reservation,
            )
        except Exception as error:
            self._fail(error)

    def execute_next(
        self,
        group_id: OrderGroupId,
        risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
        policy: PortfolioRiskPolicy,
    ) -> GroupedExecutionStepResult:
        self._require_running()
        try:
            group = self._groups.group(group_id)
            action = _next_market_action(
                group,
                risk_snapshot.value,
                now_ns=self._now_ns(),
            )
            if action is None:
                return GroupedExecutionStepResult(
                    disposition=GroupedExecutionStepDisposition.NO_ACTION,
                    group=group,
                )
            risk_decision = self._risk_engine.authorize_action(
                group,
                action,
                risk_snapshot,
                policy,
                now_ns=self._now_ns(),
            )
            if not risk_decision.allowed:
                return GroupedExecutionStepResult(
                    disposition=GroupedExecutionStepDisposition.RISK_REJECTED,
                    group=group,
                    action=action,
                    risk_decision=risk_decision,
                    reason=",".join(item.value for item in risk_decision.reasons),
                )
            permit = self._risk_coordinator.issue_permit(
                risk_decision,
                now_ns=self._now_ns(),
            )
            request = self._groups.prepare_child_submit(
                action=action,
                permit=permit,
            )
            state = _GroupedSubmitStateAdapter(
                groups=self._groups,
                action=action,
                request=request,
            )
            risk_guard = PortfolioRiskExecutionGuard(
                coordinator=self._risk_coordinator,
                action=action,
                permit=permit,
                group_view=self._groups.group,
                now_ns=self._now_ns,
                platform_guard=self._platform_guard,
            )
            handoff = DurableExecutionHandoff(
                oms=state,
                execution=self._execution,
                guard=_PermitThenTransmitGuard(
                    risk_guard=risk_guard,
                    groups=self._groups,
                    action=action,
                ),
            )
            try:
                submit_result = handoff.submit(request)
            except ExternalSubmitBlockedError as error:
                self._status = GroupedExecutionRuntimeStatus.HALTED
                return self._step_failure(
                    GroupedExecutionStepDisposition.DEFINITELY_NOT_SENT,
                    group_id=group_id,
                    action=action,
                    risk_decision=risk_decision,
                    error=error,
                )
            except ExecutionTransportError as error:
                self._status = GroupedExecutionRuntimeStatus.HALTED
                return self._step_failure(
                    GroupedExecutionStepDisposition.DEFINITELY_NOT_SENT,
                    group_id=group_id,
                    action=action,
                    risk_decision=risk_decision,
                    error=error,
                )
            except ExecutionStateUnknownError as error:
                self._status = GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED
                return self._step_failure(
                    GroupedExecutionStepDisposition.UNKNOWN,
                    group_id=group_id,
                    action=action,
                    risk_decision=risk_decision,
                    error=error,
                )
            disposition = (
                GroupedExecutionStepDisposition.ACCEPTED
                if submit_result.outcome is ExecutionOutcome.ACCEPTED
                else GroupedExecutionStepDisposition.REJECTED
            )
            if disposition is GroupedExecutionStepDisposition.REJECTED:
                reason = (
                    submit_result.rejection_message
                    or submit_result.rejection_code
                    or "execution rejected"
                )
                self._groups.require_recovery(group_id, reason=reason)
                self._status = (
                    GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED
                )
            return GroupedExecutionStepResult(
                disposition=disposition,
                group=self._groups.group(group_id),
                action=action,
                risk_decision=risk_decision,
                submit_result=submit_result,
                reason=(submit_result.rejection_message or ""),
            )
        except Exception as error:
            self._fail(error)

    def apply_child_event(self, event: OrderEvent) -> OrderGroupView:
        self._require_running()
        try:
            group = self._groups.apply_child_event(event)
            if event.status in {
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
                OrderStatus.FAILED,
            }:
                reason = event.reason or (
                    f"child reached adverse terminal state {event.status.value}"
                )
                group = self._groups.require_recovery(
                    group.order_group_id,
                    reason=reason,
                )
                self._status = (
                    GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED
                )
            return group
        except Exception as error:
            self._fail(error)

    def cancel_child(
        self,
        group_id: OrderGroupId,
        client_order_id: ClientOrderId,
    ) -> GroupedCancelResult:
        self._require_running()
        if self._cancel_execution is None:
            raise GroupedExecutionRuntimeStateError(
                "grouped cancel execution port is unavailable"
            )
        try:
            group = self._groups.group(group_id)
            action_view = next(
                (
                    item
                    for item in group.actions
                    if item.child_order_id == client_order_id
                ),
                None,
            )
            if action_view is None:
                raise KeyError("child does not belong to Order Group")
            child = cast(OrderView, self._groups.child(client_order_id))
            if child.status not in {
                OrderStatus.OPEN,
                OrderStatus.PARTIALLY_FILLED,
            }:
                raise GroupedExecutionRuntimeStateError(
                    "only an open child can be canceled"
                )
            self._groups.suspend_group(
                group_id,
                reason=f"cancel pending for {client_order_id}",
            )
            command = CancelOrder(
                account_id=action_view.action.account_id,
                instrument_id=action_view.action.instrument_id,
                client_order_id=client_order_id,
            )
            try:
                result = self._cancel_execution.cancel(command)
            except ExecutionTransportError as error:
                return self._cancel_failure(
                    GroupedCancelDisposition.DEFINITELY_NOT_SENT,
                    group_id=group_id,
                    client_order_id=client_order_id,
                    error=error,
                )
            except ExecutionStateUnknownError as error:
                return self._cancel_failure(
                    GroupedCancelDisposition.UNKNOWN,
                    group_id=group_id,
                    client_order_id=client_order_id,
                    error=error,
                )
            if result.client_order_id != client_order_id:
                return self._cancel_failure(
                    GroupedCancelDisposition.UNKNOWN,
                    group_id=group_id,
                    client_order_id=client_order_id,
                    error=RuntimeError(
                        "cancel result belongs to another child"
                    ),
                )
            if result.outcome is ExecutionOutcome.REJECTED:
                reason = (
                    result.rejection_message
                    or result.rejection_code
                    or "cancel rejected"
                )
                return self._cancel_failure(
                    GroupedCancelDisposition.REJECTED,
                    group_id=group_id,
                    client_order_id=client_order_id,
                    error=RuntimeError(reason),
                    cancel_result=result,
                )
            self._status = GroupedExecutionRuntimeStatus.HALTED
            return GroupedCancelResult(
                disposition=GroupedCancelDisposition.ACCEPTED,
                group=self._groups.group(group_id),
                client_order_id=client_order_id,
                cancel_result=result,
            )
        except GroupedExecutionRuntimeStateError:
            raise
        except Exception as error:
            self._fail(error)

    def apply_recovery_child_event(self, event: OrderEvent) -> OrderGroupView:
        self._assert_writer()
        if self._status not in {
            GroupedExecutionRuntimeStatus.HALTED,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        }:
            raise GroupedExecutionRuntimeStateError(
                "recovery child events require a halted or recovery runtime"
            )
        try:
            return self._groups.apply_child_event(event)
        except Exception as error:
            self._fail(error)

    def group(self, group_id: OrderGroupId) -> OrderGroupView:
        return self._groups.group(group_id)

    def _step_failure(
        self,
        disposition: GroupedExecutionStepDisposition,
        *,
        group_id: OrderGroupId,
        action: ExecutionAction,
        risk_decision: ExecutionActionRiskDecision,
        error: Exception,
    ) -> GroupedExecutionStepResult:
        reason = str(error).strip() or type(error).__name__
        return GroupedExecutionStepResult(
            disposition=disposition,
            group=self._groups.group(group_id),
            action=action,
            risk_decision=risk_decision,
            reason=reason[:512],
        )

    def _cancel_failure(
        self,
        disposition: GroupedCancelDisposition,
        *,
        group_id: OrderGroupId,
        client_order_id: ClientOrderId,
        error: Exception,
        cancel_result: CancelResult | None = None,
    ) -> GroupedCancelResult:
        reason = str(error).strip() or type(error).__name__
        group = self._groups.require_recovery(
            group_id,
            reason=reason[:512],
        )
        self._status = GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED
        return GroupedCancelResult(
            disposition=disposition,
            group=group,
            client_order_id=client_order_id,
            cancel_result=cancel_result,
            reason=reason[:512],
        )

    def _require_running(self) -> None:
        self._assert_writer()
        if self._status is not GroupedExecutionRuntimeStatus.RUNNING:
            raise GroupedExecutionRuntimeStateError(
                f"grouped runtime is {self._status.value}, not running"
            )

    def _assert_writer(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise GroupedExecutionWriterViolationError(
                "grouped runtime may only be mutated by its owner thread"
            )

    def _fail(self, error: BaseException) -> Never:
        self._failure = error
        self._status = GroupedExecutionRuntimeStatus.FAILED
        raise GroupedExecutionRuntimeError(
            f"grouped runtime failed with {type(error).__name__}: {error}"
        ) from error


class _GroupedSubmitStateAdapter:
    def __init__(
        self,
        *,
        groups: OrderGroupRuntime,
        action: ExecutionAction,
        request: OrderRequest,
    ) -> None:
        self._groups = groups
        self._action = action
        self._request = request

    def prepare_submit(self, request: OrderRequest) -> object:
        if request != self._request:
            raise ValueError("durable handoff request changed after preparation")
        return self._groups.group(self._action.group_id)

    def record_submit_result(self, result: SubmitResult) -> object:
        if result.client_order_id != self._request.client_order_id:
            raise ValueError("submit result belongs to another child")
        if result.outcome is ExecutionOutcome.ACCEPTED:
            return self._groups.record_acknowledged(
                self._action.group_id,
                self._action.action_id,
                venue_order_id=result.venue_order_id,
            )
        return self._groups.record_rejected(
            self._action.group_id,
            self._action.action_id,
            reason=result.rejection_message or result.rejection_code or "rejected",
        )

    def record_submit_failure(
        self,
        client_order_id: ClientOrderId,
        *,
        outcome: OrderSubmitOutcome,
        reason: str,
    ) -> object:
        if client_order_id != self._request.client_order_id:
            raise ValueError("submit failure belongs to another child")
        current = self._groups.group(self._action.group_id)
        action_view = next(
            item
            for item in current.actions
            if item.action.action_id == self._action.action_id
        )
        if action_view.state is ExecutionActionState.PREPARED:
            self._groups.mark_transmitting(
                self._action.group_id,
                self._action.action_id,
            )
        if outcome is OrderSubmitOutcome.DEFINITELY_NOT_SENT:
            return self._groups.record_definitely_not_sent(
                self._action.group_id,
                self._action.action_id,
                reason=reason,
            )
        if outcome is OrderSubmitOutcome.UNKNOWN:
            return self._groups.record_unknown(
                self._action.group_id,
                self._action.action_id,
                reason=reason,
            )
        if outcome is OrderSubmitOutcome.REJECTED:
            return self._groups.record_rejected(
                self._action.group_id,
                self._action.action_id,
                reason=reason,
            )
        raise ValueError("accepted outcome cannot be recorded as failure")


class _PermitThenTransmitGuard:
    def __init__(
        self,
        *,
        risk_guard: PortfolioRiskExecutionGuard,
        groups: OrderGroupRuntime,
        action: ExecutionAction,
    ) -> None:
        self._risk_guard = risk_guard
        self._groups = groups
        self._action = action

    def assert_submit_allowed(self, request: OrderRequest) -> None:
        self._risk_guard.assert_submit_allowed(request)
        self._groups.mark_transmitting(
            self._action.group_id,
            self._action.action_id,
        )


def _next_market_action(
    group: OrderGroupView,
    snapshot: PortfolioRiskSnapshot,
    *,
    now_ns: UnixNanos,
) -> ExecutionAction | None:
    if any(leg.unresolved_action_ids for leg in group.legs):
        return None
    current = {
        (account.account_id, position.instrument_id): (
            position.effective_quantity.as_decimal()
        )
        for account in snapshot.positions
        for position in account.positions
    }
    for leg in group.legs:
        before = current.get((leg.account_id, leg.instrument_id), Decimal(0))
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
        return ExecutionAction(
            group_id=group.order_group_id,
            expected_group_revision=group.revision,
            action_id=action_id,
            basket_leg_id=leg.basket_leg_id,
            account_id=leg.account_id,
            instrument_id=leg.instrument_id,
            side=OrderSide.BUY if residual > 0 else OrderSide.SELL,
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
    return None


def _is_pure_reduction(before: Decimal, target: Decimal) -> bool:
    return (
        before != 0
        and before * target >= 0
        and abs(target) < abs(before)
    )


__all__ = [
    "GROUPED_BOOTSTRAP_ORDER",
    "GroupedAdmissionDisposition",
    "GroupedAdmissionResult",
    "GroupedBootstrapEvidence",
    "GroupedBootstrapStep",
    "GroupedCancelDisposition",
    "GroupedCancelResult",
    "GroupedExecutionRuntime",
    "GroupedExecutionRuntimeError",
    "GroupedExecutionRuntimeStateError",
    "GroupedExecutionRuntimeStatus",
    "GroupedExecutionStepDisposition",
    "GroupedExecutionStepResult",
    "GroupedExecutionWriterViolationError",
    "SynchronousExecutionCancelPort",
]
