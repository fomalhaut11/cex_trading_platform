"""Caller-driven ADR-011 Order Group runtime with external submit blocked."""

from __future__ import annotations

from collections.abc import Callable

from cex_quant.core import (
    ClientOrderId,
    ExecutionPermitId,
    GroupActionId,
    IntentId,
    OrderGroupId,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionActionState,
    ExecutionPlanRef,
    GroupActionPreparedEntry,
    GroupActionStateChangedEntry,
    GroupControlChangedEntry,
    GroupCreatedEntry,
    OmsJournal,
    OmsJournalEntry,
    OrderEvent,
    OrderGroupAdmission,
    OrderGroupCloseOutcome,
    OrderGroupLimits,
    OrderGroupStateError,
    OrderGroupStateMachine,
    OrderGroupStatus,
    OrderGroupView,
    OrderRequest,
    OrderStatus,
    VenueEventEntry,
    child_order_id_for_action,
    deterministic_order_group_id,
)


class OrderGroupRuntimeError(RuntimeError):
    pass


class OrderGroupPersistenceError(OrderGroupRuntimeError):
    """Group runtime is latched fail-closed after journal failure."""


class OrderGroupRecoveryError(OrderGroupRuntimeError):
    pass


class GroupedExecutionBlockedError(OrderGroupRuntimeError):
    """ADR-012 has not authorized grouped external execution."""


class OrderGroupRuntime:
    """Own durable groups and child facts without owning Portfolio Risk."""

    def __init__(
        self,
        *,
        now_ns: Callable[[], UnixNanos],
        journal: OmsJournal | None = None,
        limits: OrderGroupLimits | None = None,
    ) -> None:
        self._now_ns = now_ns
        self._journal = journal
        self._limits = limits or OrderGroupLimits()
        self._persistence_failure: Exception | None = None
        self._groups: dict[OrderGroupId, OrderGroupStateMachine] = {}
        self._intent_to_group: dict[IntentId, OrderGroupId] = {}
        self._child_to_group: dict[ClientOrderId, OrderGroupId] = {}
        self._permit_to_action: dict[
            ExecutionPermitId,
            tuple[OrderGroupId, GroupActionId],
        ] = {}
        self._creation: dict[
            OrderGroupId,
            tuple[OrderGroupAdmission, ExecutionPlanRef],
        ] = {}
        self._recover()

    def create_group(
        self,
        admission: OrderGroupAdmission,
        execution_plan: ExecutionPlanRef,
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        group_id = deterministic_order_group_id(admission)
        existing_group_id = self._intent_to_group.get(admission.basket.intent_id)
        if existing_group_id is not None:
            existing = self._creation[existing_group_id]
            if existing_group_id == group_id and existing == (
                admission,
                execution_plan,
            ):
                return self._group(existing_group_id).view()
            raise OrderGroupRuntimeError(
                "Basket intent is already owned by another group admission"
            )
        created_at_ns = self._now_ns()
        if len(self._groups) >= self._limits.max_retained_groups:
            raise OrderGroupRuntimeError("retained Order Group capacity reached")
        machine = OrderGroupStateMachine(
            admission=admission,
            execution_plan=execution_plan,
            group_id=group_id,
            created_at_ns=created_at_ns,
            limits=self._limits,
        )
        self._persist(
            GroupCreatedEntry(
                group_id=group_id,
                admission=admission,
                execution_plan=execution_plan,
                created_at_ns=created_at_ns,
            )
        )
        self._register_group(machine, admission, execution_plan)
        return machine.view()

    def group(self, group_id: OrderGroupId) -> OrderGroupView:
        return self._group(group_id).view()

    def groups(self) -> tuple[OrderGroupView, ...]:
        return tuple(
            self._groups[group_id].view() for group_id in sorted(self._groups, key=str)
        )

    def child(self, client_order_id: ClientOrderId) -> object:
        group_id = self._child_to_group[client_order_id]
        return self._group(group_id).child(client_order_id)

    def recovery_candidates(self) -> tuple[object, ...]:
        return tuple(
            child
            for group_id in sorted(self._groups, key=str)
            for child in self._groups[group_id].recovery_candidates()
        )

    def activate_group(self, group_id: OrderGroupId) -> OrderGroupView:
        return self._change_control(
            group_id,
            OrderGroupStatus.ACTIVE,
            at_ns=self._now_ns(),
        )

    def suspend_group(
        self,
        group_id: OrderGroupId,
        *,
        reason: str = "",
    ) -> OrderGroupView:
        return self._change_control(
            group_id,
            OrderGroupStatus.SUSPENDED,
            at_ns=self._now_ns(),
            reason=reason,
        )

    def require_recovery(
        self,
        group_id: OrderGroupId,
        *,
        reason: str,
    ) -> OrderGroupView:
        return self._change_control(
            group_id,
            OrderGroupStatus.RECOVERY_REQUIRED,
            at_ns=self._now_ns(),
            reason=reason,
        )

    def resume_group(
        self,
        group_id: OrderGroupId,
        *,
        recovery_authorization_id: str,
    ) -> OrderGroupView:
        return self._change_control(
            group_id,
            OrderGroupStatus.ACTIVE,
            at_ns=self._now_ns(),
            recovery_authorization_id=recovery_authorization_id,
        )

    def begin_closing(self, group_id: OrderGroupId) -> OrderGroupView:
        return self._change_control(
            group_id,
            OrderGroupStatus.CLOSING,
            at_ns=self._now_ns(),
        )

    def close_group(
        self,
        group_id: OrderGroupId,
        *,
        outcome: OrderGroupCloseOutcome,
        portfolio_confirmation_id: str = "",
    ) -> OrderGroupView:
        return self._change_control(
            group_id,
            OrderGroupStatus.CLOSED,
            at_ns=self._now_ns(),
            close_outcome=outcome,
            portfolio_confirmation_id=portfolio_confirmation_id,
        )

    def prepare_child_submit(
        self,
        *,
        action: ExecutionAction,
        permit: ExecutionActionPermit,
    ) -> OrderRequest:
        """Durably create one SUBMITTING child; performs no external I/O."""

        self._assert_persistence_healthy()
        machine = self._group(action.group_id)
        permit_owner = self._permit_to_action.get(permit.permit_id)
        if permit_owner is not None and permit_owner != (
            action.group_id,
            action.action_id,
        ):
            raise OrderGroupRuntimeError(
                "ExecutionPermitId is already bound to another action"
            )
        at_ns = self._now_ns()
        request = OrderRequest(
            client_order_id=child_order_id_for_action(action.action_id),
            approval_id=str(permit.permit_id),
            intent_id=IntentId(machine.source_intent_id),
            account_id=action.account_id,
            instrument_id=action.instrument_id,
            side=action.side,
            order_type=action.order_type,
            quantity=action.quantity,
            created_at_ns=at_ns,
            time_in_force=action.time_in_force,
            limit_price=action.limit_price,
            stop_price=action.stop_price,
            reduce_only=action.reduce_only,
            post_only=action.post_only,
            position_side=action.position_side,
        )
        machine.validate_action_preparation(
            action=action,
            permit=permit,
            request=request,
            at_ns=at_ns,
        )
        self._persist(
            GroupActionPreparedEntry(
                group_id=action.group_id,
                action=action,
                permit=permit,
                request=request,
                at_ns=at_ns,
            )
        )
        machine.prepare_action(
            action=action,
            permit=permit,
            request=request,
            at_ns=at_ns,
        )
        self._child_to_group[request.client_order_id] = action.group_id
        self._permit_to_action[permit.permit_id] = (
            action.group_id,
            action.action_id,
        )
        return request

    def submit_prepared_child(
        self,
        client_order_id: ClientOrderId,
    ) -> None:
        """Fail closed until ADR-012 supplies the real authorization boundary."""

        del client_order_id
        raise GroupedExecutionBlockedError(
            "grouped external execution is blocked until ADR-012 is accepted"
        )

    def mark_transmitting(
        self,
        group_id: OrderGroupId,
        action_id: GroupActionId,
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        at_ns = self._now_ns()
        view = self._group(group_id).mark_transmitting(
            action_id,
            at_ns=at_ns,
        )
        self._persist(
            GroupActionStateChangedEntry(
                group_id=group_id,
                action_id=action_id,
                state=ExecutionActionState.TRANSMITTING,
                at_ns=at_ns,
            )
        )
        return view

    def record_acknowledged(
        self,
        group_id: OrderGroupId,
        action_id: GroupActionId,
        *,
        venue_order_id: VenueOrderId | None = None,
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        at_ns = self._now_ns()
        view = self._group(group_id).record_acknowledged(
            action_id,
            at_ns=at_ns,
            venue_order_id=venue_order_id,
        )
        self._persist(
            GroupActionStateChangedEntry(
                group_id=group_id,
                action_id=action_id,
                state=ExecutionActionState.ACKNOWLEDGED,
                at_ns=at_ns,
                venue_order_id=venue_order_id,
            )
        )
        return view

    def record_rejected(
        self,
        group_id: OrderGroupId,
        action_id: GroupActionId,
        *,
        reason: str,
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        at_ns = self._now_ns()
        view = self._group(group_id).record_rejected(
            action_id,
            at_ns=at_ns,
            reason=reason,
        )
        self._persist(
            GroupActionStateChangedEntry(
                group_id=group_id,
                action_id=action_id,
                state=ExecutionActionState.REJECTED,
                at_ns=at_ns,
                child_terminal_status=OrderStatus.REJECTED,
                reason=reason,
            )
        )
        return view

    def record_definitely_not_sent(
        self,
        group_id: OrderGroupId,
        action_id: GroupActionId,
        *,
        reason: str,
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        at_ns = self._now_ns()
        machine = self._group(group_id)
        view = machine.record_definitely_not_sent(
            action_id,
            at_ns=at_ns,
            reason=reason,
        )
        state = next(
            item.state for item in view.actions if item.action.action_id == action_id
        )
        terminal = (
            OrderStatus.FAILED if state is ExecutionActionState.REJECTED else None
        )
        self._persist(
            GroupActionStateChangedEntry(
                group_id=group_id,
                action_id=action_id,
                state=state,
                at_ns=at_ns,
                child_terminal_status=terminal,
                reason=reason,
            )
        )
        return view

    def record_unknown(
        self,
        group_id: OrderGroupId,
        action_id: GroupActionId,
        *,
        reason: str,
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        at_ns = self._now_ns()
        view = self._group(group_id).record_unknown(
            action_id,
            at_ns=at_ns,
            reason=reason,
        )
        self._persist(
            GroupActionStateChangedEntry(
                group_id=group_id,
                action_id=action_id,
                state=ExecutionActionState.UNKNOWN,
                at_ns=at_ns,
                reason=reason,
            )
        )
        return view

    def apply_child_event(self, event: OrderEvent) -> OrderGroupView:
        self._assert_persistence_healthy()
        group_id = self._child_to_group[event.client_order_id]
        view = self._group(group_id).apply_child_event(event)
        self._persist(VenueEventEntry(event=event))
        return view

    def _change_control(
        self,
        group_id: OrderGroupId,
        status: OrderGroupStatus,
        *,
        at_ns: UnixNanos,
        reason: str = "",
        recovery_authorization_id: str = "",
        close_outcome: OrderGroupCloseOutcome | None = None,
        portfolio_confirmation_id: str = "",
    ) -> OrderGroupView:
        self._assert_persistence_healthy()
        view = self._group(group_id).transition_control(
            status,
            at_ns=at_ns,
            reason=reason,
            recovery_authorization_id=recovery_authorization_id,
            close_outcome=close_outcome,
            portfolio_confirmation_id=portfolio_confirmation_id,
        )
        self._persist(
            GroupControlChangedEntry(
                group_id=group_id,
                status=status,
                at_ns=at_ns,
                reason=reason,
                recovery_authorization_id=recovery_authorization_id,
                close_outcome=close_outcome,
                portfolio_confirmation_id=portfolio_confirmation_id,
            )
        )
        return view

    def _recover(self) -> None:
        if self._journal is None:
            return
        try:
            for entry in self._journal.read():
                if isinstance(entry, GroupCreatedEntry):
                    machine = OrderGroupStateMachine(
                        admission=entry.admission,
                        execution_plan=entry.execution_plan,
                        group_id=entry.group_id,
                        created_at_ns=entry.created_at_ns,
                        limits=self._limits,
                    )
                    self._register_group(
                        machine,
                        entry.admission,
                        entry.execution_plan,
                    )
                elif isinstance(entry, GroupControlChangedEntry):
                    self._group(entry.group_id).transition_control(
                        entry.status,
                        at_ns=entry.at_ns,
                        reason=entry.reason,
                        recovery_authorization_id=(entry.recovery_authorization_id),
                        close_outcome=entry.close_outcome,
                        portfolio_confirmation_id=(entry.portfolio_confirmation_id),
                    )
                elif isinstance(entry, GroupActionPreparedEntry):
                    machine = self._group(entry.group_id)
                    machine.prepare_action(
                        action=entry.action,
                        permit=entry.permit,
                        request=entry.request,
                        at_ns=entry.at_ns,
                    )
                    self._child_to_group[entry.request.client_order_id] = entry.group_id
                    permit_owner = self._permit_to_action.get(entry.permit.permit_id)
                    current_owner = (entry.group_id, entry.action.action_id)
                    if permit_owner is not None and permit_owner != current_owner:
                        raise OrderGroupRecoveryError(
                            "recovered ExecutionPermitId has multiple owners"
                        )
                    self._permit_to_action[entry.permit.permit_id] = current_owner
                elif isinstance(entry, GroupActionStateChangedEntry):
                    self._recover_action_state(entry)
                elif (
                    isinstance(entry, VenueEventEntry)
                    and entry.event.client_order_id in self._child_to_group
                ):
                    group_id = self._child_to_group[entry.event.client_order_id]
                    self._group(group_id).apply_child_event(entry.event)
        except OrderGroupRecoveryError:
            raise
        except (
            KeyError,
            OrderGroupStateError,
            ValueError,
        ) as error:
            raise OrderGroupRecoveryError(
                f"invalid Order Group recovery history: {error}"
            ) from error

    def _recover_action_state(
        self,
        entry: GroupActionStateChangedEntry,
    ) -> None:
        machine = self._group(entry.group_id)
        if entry.state is ExecutionActionState.TRANSMITTING:
            machine.mark_transmitting(entry.action_id, at_ns=entry.at_ns)
        elif entry.state is ExecutionActionState.ACKNOWLEDGED:
            machine.record_acknowledged(
                entry.action_id,
                at_ns=entry.at_ns,
                venue_order_id=entry.venue_order_id,
            )
        elif entry.state is ExecutionActionState.RETRY_ELIGIBLE:
            machine.record_definitely_not_sent(
                entry.action_id,
                at_ns=entry.at_ns,
                reason=entry.reason,
            )
        elif entry.state is ExecutionActionState.UNKNOWN:
            machine.record_unknown(
                entry.action_id,
                at_ns=entry.at_ns,
                reason=entry.reason,
            )
        elif entry.state is ExecutionActionState.REJECTED:
            if entry.child_terminal_status is OrderStatus.FAILED:
                machine.record_definitely_not_sent(
                    entry.action_id,
                    at_ns=entry.at_ns,
                    reason=entry.reason,
                )
            else:
                machine.record_rejected(
                    entry.action_id,
                    at_ns=entry.at_ns,
                    reason=entry.reason,
                )
        else:
            raise OrderGroupRecoveryError(
                f"unexpected recovered action state: {entry.state.value}"
            )

    def _register_group(
        self,
        machine: OrderGroupStateMachine,
        admission: OrderGroupAdmission,
        execution_plan: ExecutionPlanRef,
    ) -> None:
        group_id = machine.group_id
        intent_id = admission.basket.intent_id
        if group_id in self._groups or intent_id in self._intent_to_group:
            raise OrderGroupRecoveryError("duplicate group or Basket intent")
        if len(self._groups) >= self._limits.max_retained_groups:
            raise OrderGroupRecoveryError("retained Order Group capacity reached")
        self._groups[group_id] = machine
        self._intent_to_group[intent_id] = group_id
        self._creation[group_id] = (admission, execution_plan)

    def _group(self, group_id: OrderGroupId) -> OrderGroupStateMachine:
        try:
            return self._groups[group_id]
        except KeyError as error:
            raise KeyError(f"unknown Order Group: {group_id}") from error

    def _persist(self, entry: OmsJournalEntry) -> None:
        if self._journal is None:
            return
        try:
            self._journal.append(entry)
        except Exception as error:
            self._persistence_failure = error
            raise OrderGroupPersistenceError(
                "Order Group journal failed; runtime is latched fail-closed"
            ) from error

    def _assert_persistence_healthy(self) -> None:
        if self._persistence_failure is not None:
            raise OrderGroupPersistenceError(
                "Order Group persistence is unhealthy; restart required"
            ) from self._persistence_failure


__all__ = [
    "GroupedExecutionBlockedError",
    "OrderGroupPersistenceError",
    "OrderGroupRecoveryError",
    "OrderGroupRuntime",
    "OrderGroupRuntimeError",
]
