"""Deterministic single-writer Parent Order Group state."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import get_ident

from cex_quant.core import (
    ClientOrderId,
    ExecutionStageId,
    GroupActionId,
    IntentId,
    OrderGroupId,
    Quantity,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.strategy import BasketTargetLeg

from .group_model import (
    MAX_TECHNICAL_RETRANSMISSIONS,
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionActionState,
    ExecutionActionView,
    ExecutionPlanRef,
    OrderGroupAdmission,
    OrderGroupCloseOutcome,
    OrderGroupLegView,
    OrderGroupLimits,
    OrderGroupStatus,
    OrderGroupView,
    child_order_id_for_action,
    deterministic_order_group_id,
    execution_action_checksum,
)
from .model import (
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderView,
)
from .stage_model import (
    ExecutionStage,
    ExecutionStagePermit,
    ExecutionStageState,
    ExecutionStageView,
    validate_execution_stage_permit,
)
from .state import OrderStateMachine, UpdateDisposition


class OrderGroupStateError(RuntimeError):
    """Base class for rejected group mutations."""


class OrderGroupWriterViolationError(OrderGroupStateError):
    pass


class OrderGroupIdentityError(OrderGroupStateError):
    pass


class OrderGroupTransitionError(OrderGroupStateError):
    pass


class OrderGroupAuthorizationError(OrderGroupStateError):
    pass


class OrderGroupCapacityError(OrderGroupStateError):
    pass


@dataclass(slots=True)
class _ActionRecord:
    action: ExecutionAction
    permit: ExecutionActionPermit
    child: OrderStateMachine
    state: ExecutionActionState
    transport_attempts: int
    last_transition_ns: UnixNanos
    venue_order_id: VenueOrderId | None = None
    reason: str = ""


@dataclass(slots=True)
class _StageRecord:
    stage: ExecutionStage
    permit: ExecutionStagePermit
    action_ids: tuple[GroupActionId, ...]


_CONTROL_TRANSITIONS = {
    OrderGroupStatus.CREATED: frozenset(
        {
            OrderGroupStatus.ACTIVE,
            OrderGroupStatus.SUSPENDED,
        }
    ),
    OrderGroupStatus.ACTIVE: frozenset(
        {
            OrderGroupStatus.SUSPENDED,
            OrderGroupStatus.RECOVERY_REQUIRED,
            OrderGroupStatus.CLOSING,
        }
    ),
    OrderGroupStatus.SUSPENDED: frozenset(
        {
            OrderGroupStatus.ACTIVE,
            OrderGroupStatus.RECOVERY_REQUIRED,
            OrderGroupStatus.CLOSING,
        }
    ),
    OrderGroupStatus.RECOVERY_REQUIRED: frozenset(
        {OrderGroupStatus.ACTIVE, OrderGroupStatus.CLOSING}
    ),
    OrderGroupStatus.CLOSING: frozenset({OrderGroupStatus.CLOSED}),
    OrderGroupStatus.CLOSED: frozenset(),
}


class OrderGroupStateMachine:
    """Own one generic Order Group and its canonical child state machines."""

    def __init__(
        self,
        *,
        admission: OrderGroupAdmission,
        execution_plan: ExecutionPlanRef,
        group_id: OrderGroupId,
        created_at_ns: UnixNanos,
        limits: OrderGroupLimits | None = None,
    ) -> None:
        expected = deterministic_order_group_id(admission)
        if group_id != expected:
            raise OrderGroupIdentityError(
                "group_id does not match deterministic admission identity"
            )
        if created_at_ns < admission.approved_at_ns:
            raise ValueError("group creation cannot precede admission")
        if created_at_ns > admission.valid_until_ns:
            raise ValueError("group admission has expired")
        self._writer_thread_id = get_ident()
        self._admission = admission
        self._execution_plan = execution_plan
        self._limits = limits or OrderGroupLimits()
        self._group_id = group_id
        self._created_at_ns = created_at_ns
        self._last_transition_ns = created_at_ns
        self._revision = 1
        self._status = OrderGroupStatus.CREATED
        self._recovery_reason = ""
        self._close_outcome: OrderGroupCloseOutcome | None = None
        self._portfolio_confirmation_id = ""
        self._recovery_authorization_id = ""
        self._actions: dict[GroupActionId, _ActionRecord] = {}
        self._stages: dict[ExecutionStageId, _StageRecord] = {}
        self._action_to_stage: dict[GroupActionId, ExecutionStageId] = {}
        self._permit_to_action: dict[str, GroupActionId] = {}
        self._child_to_action: dict[ClientOrderId, GroupActionId] = {}
        self._leg_action_ids: dict[str, list[GroupActionId]] = {
            str(leg.leg_id): [] for leg in admission.basket.legs
        }

    @property
    def group_id(self) -> OrderGroupId:
        return self._group_id

    @property
    def source_intent_id(self) -> IntentId:
        return self._admission.basket.intent_id

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def status(self) -> OrderGroupStatus:
        return self._status

    def view(self) -> OrderGroupView:
        action_views = tuple(
            self._action_view(record) for record in self._actions.values()
        )
        legs = tuple(self._leg_view(leg.leg_id) for leg in self._admission.basket.legs)
        return OrderGroupView(
            order_group_id=self._group_id,
            source_intent_id=self.source_intent_id,
            approval_id=self._admission.approval_id,
            execution_plan=self._execution_plan,
            revision=self._revision,
            status=self._status,
            legs=legs,
            actions=action_views,
            created_at_ns=self._created_at_ns,
            last_transition_ns=self._last_transition_ns,
            recovery_reason=self._recovery_reason,
            close_outcome=self._close_outcome,
            portfolio_confirmation_id=self._portfolio_confirmation_id,
            stages=tuple(
                self._stage_view(record) for record in self._stages.values()
            ),
        )

    def child(self, client_order_id: ClientOrderId) -> OrderView:
        return self._record_for_child(client_order_id).child.view()

    def children(self) -> tuple[OrderView, ...]:
        return tuple(record.child.view() for record in self._actions.values())

    def recovery_candidates(self) -> tuple[OrderView, ...]:
        statuses = {
            OrderStatus.SUBMITTING,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }
        return tuple(
            record.child.view()
            for record in self._actions.values()
            if (
                record.state is ExecutionActionState.UNKNOWN
                or record.child.view().status in statuses
            )
        )

    def validate_action_preparation(
        self,
        *,
        action: ExecutionAction,
        permit: ExecutionActionPermit,
        request: OrderRequest,
        at_ns: UnixNanos,
    ) -> None:
        self._assert_writer()
        self._assert_time(at_ns)
        if self._status is not OrderGroupStatus.ACTIVE:
            raise OrderGroupTransitionError(
                "new child preparation requires ACTIVE group"
            )
        if at_ns > self._admission.valid_until_ns:
            raise OrderGroupAuthorizationError("group admission has expired")
        if action.group_id != self._group_id:
            raise OrderGroupIdentityError("action belongs to another group")
        if action.expected_group_revision != self._revision:
            raise OrderGroupAuthorizationError("action group revision is stale")
        if action.execution_plan != self._execution_plan:
            raise OrderGroupIdentityError("action execution plan mismatch")
        if action.created_at_ns > at_ns:
            raise ValueError("action creation cannot be in the future")
        if action.action_id in self._actions:
            raise OrderGroupIdentityError("action_id is already owned")
        if permit.group_id != self._group_id:
            raise OrderGroupIdentityError("permit belongs to another group")
        if permit.action_id != action.action_id:
            raise OrderGroupIdentityError("permit action identity mismatch")
        existing_permit_action = self._permit_to_action.get(str(permit.permit_id))
        if (
            existing_permit_action is not None
            and existing_permit_action != action.action_id
        ):
            raise OrderGroupIdentityError(
                "execution permit is already bound to another action"
            )
        if permit.expected_group_revision != self._revision:
            raise OrderGroupAuthorizationError("permit group revision is stale")
        if permit.action_checksum != execution_action_checksum(action):
            raise OrderGroupAuthorizationError("permit action checksum mismatch")
        if at_ns < permit.issued_at_ns or at_ns > permit.valid_until_ns:
            raise OrderGroupAuthorizationError("permit is not currently valid")
        if permit.valid_until_ns > self._admission.valid_until_ns:
            raise OrderGroupAuthorizationError("permit outlives group admission")
        leg = self._leg(action.basket_leg_id)
        if (
            leg.account_id != action.account_id
            or leg.instrument_id != action.instrument_id
        ):
            raise OrderGroupIdentityError("action does not match admitted leg")
        leg_actions = self._leg_action_ids[str(action.basket_leg_id)]
        if len(leg_actions) >= self._limits.max_child_attempts_per_leg:
            raise OrderGroupCapacityError("leg child-attempt hard cap reached")
        if len(self._actions) >= self._limits.max_children_per_group:
            raise OrderGroupCapacityError("group child hard cap reached")
        if self._unresolved_action_ids():
            raise OrderGroupCapacityError(
                "V1 permits only one unresolved exposure-changing action"
            )
        expected_child_id = child_order_id_for_action(action.action_id)
        if request.client_order_id != expected_child_id:
            raise OrderGroupIdentityError("child identity does not match action")
        if request.client_order_id in self._child_to_action:
            raise OrderGroupIdentityError("child_order_id is already owned")
        if (
            request.approval_id != str(permit.permit_id)
            or request.intent_id != self._admission.basket.intent_id
            or request.account_id != action.account_id
            or request.instrument_id != action.instrument_id
            or request.side is not action.side
            or request.order_type is not action.order_type
            or request.quantity != action.quantity
            or request.time_in_force is not action.time_in_force
            or request.limit_price != action.limit_price
            or request.stop_price != action.stop_price
            or request.reduce_only != action.reduce_only
            or request.post_only != action.post_only
            or request.position_side is not action.position_side
            or request.created_at_ns != at_ns
        ):
            raise OrderGroupIdentityError(
                "child request content does not match permitted action"
            )

    def validate_stage_preparation(
        self,
        *,
        stage: ExecutionStage,
        permit: ExecutionStagePermit,
        requests: tuple[OrderRequest, ...],
        at_ns: UnixNanos,
    ) -> None:
        """Validate one complete Stage before its single journal mutation."""

        self._assert_writer()
        self._assert_time(at_ns)
        if self._status is not OrderGroupStatus.ACTIVE:
            raise OrderGroupTransitionError(
                "new Stage preparation requires ACTIVE group"
            )
        if at_ns > self._admission.valid_until_ns:
            raise OrderGroupAuthorizationError("group admission has expired")
        if stage.group_id != self._group_id:
            raise OrderGroupIdentityError("Stage belongs to another group")
        if stage.base_group_revision != self._revision:
            raise OrderGroupAuthorizationError("Stage group revision is stale")
        if stage.execution_plan != self._execution_plan:
            raise OrderGroupIdentityError("Stage execution plan mismatch")
        if stage.created_at_ns > at_ns:
            raise ValueError("Stage creation cannot be in the future")
        if stage.stage_id in self._stages:
            raise OrderGroupIdentityError("stage_id is already owned")
        try:
            validate_execution_stage_permit(stage, permit)
        except ValueError as error:
            raise OrderGroupAuthorizationError(str(error)) from error
        if at_ns < permit.issued_at_ns or at_ns > permit.valid_until_ns:
            raise OrderGroupAuthorizationError("Stage permit is not currently valid")
        if permit.valid_until_ns > self._admission.valid_until_ns:
            raise OrderGroupAuthorizationError("Stage permit outlives admission")
        if len(requests) != len(stage.actions):
            raise OrderGroupIdentityError("Stage request vector width mismatch")
        if self._unresolved_action_ids():
            raise OrderGroupCapacityError(
                "current host permits no overlapping unresolved Stage"
            )
        if (
            len(self._actions) + len(stage.actions)
            > self._limits.max_children_per_group
        ):
            raise OrderGroupCapacityError("group child hard cap reached")

        pending_per_leg: dict[str, int] = {}
        for action, action_permit, request in zip(
            stage.actions,
            permit.action_permits,
            requests,
            strict=True,
        ):
            if (
                action.action_id in self._actions
                or action.action_id in self._action_to_stage
            ):
                raise OrderGroupIdentityError("Stage action_id is already owned")
            existing_permit_action = self._permit_to_action.get(
                str(action_permit.permit_id)
            )
            if existing_permit_action is not None:
                raise OrderGroupIdentityError(
                    "Stage Action permit is already bound to an Action"
                )
            leg = self._leg(action.basket_leg_id)
            if (
                leg.account_id != action.account_id
                or leg.instrument_id != action.instrument_id
            ):
                raise OrderGroupIdentityError(
                    "Stage Action does not match admitted leg"
                )
            leg_key = str(action.basket_leg_id)
            pending_per_leg[leg_key] = pending_per_leg.get(leg_key, 0) + 1
            if (
                len(self._leg_action_ids[leg_key]) + pending_per_leg[leg_key]
                > self._limits.max_child_attempts_per_leg
            ):
                raise OrderGroupCapacityError("leg child-attempt hard cap reached")
            expected_child_id = child_order_id_for_action(action.action_id)
            if request.client_order_id != expected_child_id:
                raise OrderGroupIdentityError("Stage Child identity mismatch")
            if request.client_order_id in self._child_to_action:
                raise OrderGroupIdentityError("Stage Child is already owned")
            if (
                request.approval_id != str(action_permit.permit_id)
                or request.intent_id != self._admission.basket.intent_id
                or request.account_id != action.account_id
                or request.instrument_id != action.instrument_id
                or request.side is not action.side
                or request.order_type is not action.order_type
                or request.quantity != action.quantity
                or request.time_in_force is not action.time_in_force
                or request.limit_price != action.limit_price
                or request.stop_price != action.stop_price
                or request.reduce_only != action.reduce_only
                or request.post_only != action.post_only
                or request.position_side is not action.position_side
                or request.created_at_ns != at_ns
            ):
                raise OrderGroupIdentityError(
                    "Stage Child request does not match permitted Action"
                )

    def prepare_stage(
        self,
        *,
        stage: ExecutionStage,
        permit: ExecutionStagePermit,
        requests: tuple[OrderRequest, ...],
        at_ns: UnixNanos,
    ) -> OrderGroupView:
        """Atomically install a complete already-durable Stage in memory."""

        self.validate_stage_preparation(
            stage=stage,
            permit=permit,
            requests=requests,
            at_ns=at_ns,
        )
        for action, action_permit, request in zip(
            stage.actions,
            permit.action_permits,
            requests,
            strict=True,
        ):
            child = OrderStateMachine(request)
            child.mark_submitting(at_ns=at_ns)
            self._actions[action.action_id] = _ActionRecord(
                action=action,
                permit=action_permit,
                child=child,
                state=ExecutionActionState.PREPARED,
                transport_attempts=0,
                last_transition_ns=at_ns,
            )
            self._permit_to_action[str(action_permit.permit_id)] = action.action_id
            self._child_to_action[request.client_order_id] = action.action_id
            self._leg_action_ids[str(action.basket_leg_id)].append(action.action_id)
            self._action_to_stage[action.action_id] = stage.stage_id
        self._stages[stage.stage_id] = _StageRecord(
            stage=stage,
            permit=permit,
            action_ids=tuple(item.action_id for item in stage.actions),
        )
        self._advance(at_ns)
        return self.view()

    def prepare_action(
        self,
        *,
        action: ExecutionAction,
        permit: ExecutionActionPermit,
        request: OrderRequest,
        at_ns: UnixNanos,
    ) -> OrderGroupView:
        self.validate_action_preparation(
            action=action,
            permit=permit,
            request=request,
            at_ns=at_ns,
        )
        child = OrderStateMachine(request)
        child.mark_submitting(at_ns=at_ns)
        self._actions[action.action_id] = _ActionRecord(
            action=action,
            permit=permit,
            child=child,
            state=ExecutionActionState.PREPARED,
            transport_attempts=0,
            last_transition_ns=at_ns,
        )
        self._permit_to_action[str(permit.permit_id)] = action.action_id
        self._child_to_action[request.client_order_id] = action.action_id
        self._leg_action_ids[str(action.basket_leg_id)].append(action.action_id)
        self._advance(at_ns)
        return self.view()

    def mark_transmitting(
        self,
        action_id: GroupActionId,
        *,
        at_ns: UnixNanos,
    ) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(at_ns)
        if self._status is not OrderGroupStatus.ACTIVE:
            raise OrderGroupTransitionError(
                "transmission requires ACTIVE group"
            )
        record = self._record(action_id)
        if record.state not in {
            ExecutionActionState.PREPARED,
            ExecutionActionState.RETRY_ELIGIBLE,
        }:
            raise OrderGroupTransitionError(
                f"cannot transmit action from {record.state.value}"
            )
        if record.state is ExecutionActionState.RETRY_ELIGIBLE:
            if record.transport_attempts > MAX_TECHNICAL_RETRANSMISSIONS:
                raise OrderGroupCapacityError(
                    "technical retransmission hard cap reached"
                )
            self._validate_retry_authority(record, at_ns=at_ns)
        record.transport_attempts += 1
        record.state = ExecutionActionState.TRANSMITTING
        record.last_transition_ns = at_ns
        record.reason = ""
        self._advance(at_ns)
        return self.view()

    def record_acknowledged(
        self,
        action_id: GroupActionId,
        *,
        at_ns: UnixNanos,
        venue_order_id: VenueOrderId | None = None,
    ) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(at_ns)
        record = self._require_transmitting(action_id)
        record.state = ExecutionActionState.ACKNOWLEDGED
        record.venue_order_id = venue_order_id
        record.last_transition_ns = at_ns
        record.reason = ""
        self._advance(at_ns)
        return self.view()

    def record_rejected(
        self,
        action_id: GroupActionId,
        *,
        at_ns: UnixNanos,
        reason: str,
    ) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(at_ns)
        _require_reason(reason)
        record = self._require_transmitting(action_id)
        record.child.apply_venue_update(
            self._local_terminal_event(
                record,
                status=OrderStatus.REJECTED,
                at_ns=at_ns,
                reason=reason,
            )
        )
        record.state = ExecutionActionState.REJECTED
        record.last_transition_ns = at_ns
        record.reason = reason
        self._advance(at_ns)
        return self.view()

    def record_definitely_not_sent(
        self,
        action_id: GroupActionId,
        *,
        at_ns: UnixNanos,
        reason: str,
    ) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(at_ns)
        _require_reason(reason)
        record = self._require_transmitting(action_id)
        if record.transport_attempts <= MAX_TECHNICAL_RETRANSMISSIONS:
            record.state = ExecutionActionState.RETRY_ELIGIBLE
        else:
            record.child.apply_venue_update(
                self._local_terminal_event(
                    record,
                    status=OrderStatus.FAILED,
                    at_ns=at_ns,
                    reason=reason,
                )
            )
            record.state = ExecutionActionState.REJECTED
        record.last_transition_ns = at_ns
        record.reason = reason
        self._advance(at_ns)
        return self.view()

    def record_unknown(
        self,
        action_id: GroupActionId,
        *,
        at_ns: UnixNanos,
        reason: str,
    ) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(at_ns)
        _require_reason(reason)
        record = self._require_transmitting(action_id)
        record.state = ExecutionActionState.UNKNOWN
        record.last_transition_ns = at_ns
        record.reason = reason
        self._status = OrderGroupStatus.RECOVERY_REQUIRED
        self._recovery_reason = reason
        self._advance(at_ns)
        return self.view()

    def apply_child_event(self, event: OrderEvent) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(event.event_time_ns)
        record = self._record_for_child(event.client_order_id)
        update = record.child.apply_venue_update(event)
        if update.disposition is UpdateDisposition.DUPLICATE:
            return self.view()
        if record.state is ExecutionActionState.UNKNOWN:
            record.state = (
                ExecutionActionState.REJECTED
                if event.status is OrderStatus.REJECTED
                else ExecutionActionState.ACKNOWLEDGED
            )
            record.venue_order_id = event.venue_order_id
            record.last_transition_ns = event.event_time_ns
        self._advance(event.event_time_ns)
        return self.view()

    def transition_control(
        self,
        status: OrderGroupStatus,
        *,
        at_ns: UnixNanos,
        reason: str = "",
        recovery_authorization_id: str = "",
        close_outcome: OrderGroupCloseOutcome | None = None,
        portfolio_confirmation_id: str = "",
    ) -> OrderGroupView:
        self._assert_writer()
        self._assert_time(at_ns)
        _validate_evidence(reason, name="reason", required=False)
        _validate_evidence(
            recovery_authorization_id,
            name="recovery_authorization_id",
            required=False,
        )
        _validate_evidence(
            portfolio_confirmation_id,
            name="portfolio_confirmation_id",
            required=False,
        )
        if status not in _CONTROL_TRANSITIONS[self._status]:
            raise OrderGroupTransitionError(
                f"illegal group transition {self._status.value} -> {status.value}"
            )
        if self._status is OrderGroupStatus.RECOVERY_REQUIRED and (
            status is OrderGroupStatus.ACTIVE
        ):
            if not recovery_authorization_id.strip():
                raise OrderGroupAuthorizationError(
                    "recovery resume requires explicit authorization evidence"
                )
            if any(
                record.state is ExecutionActionState.UNKNOWN
                for record in self._actions.values()
            ):
                raise OrderGroupTransitionError(
                    "cannot resume while an action remains unknown"
                )
        if status is OrderGroupStatus.RECOVERY_REQUIRED and not reason.strip():
            raise ValueError("recovery transition requires a reason")
        if status is OrderGroupStatus.CLOSED:
            if close_outcome is None:
                raise ValueError("closed transition requires an outcome")
            if self._unresolved_action_ids():
                raise OrderGroupTransitionError(
                    "cannot close while child actions remain unresolved"
                )
            if (
                close_outcome is OrderGroupCloseOutcome.TARGET_CONFIRMED
                and not portfolio_confirmation_id.strip()
            ):
                raise OrderGroupAuthorizationError(
                    "TARGET_CONFIRMED requires Portfolio/Risk evidence"
                )
        elif close_outcome is not None or portfolio_confirmation_id:
            raise ValueError("close evidence is only valid for CLOSED")

        self._status = status
        self._recovery_reason = (
            reason if status is OrderGroupStatus.RECOVERY_REQUIRED else ""
        )
        self._recovery_authorization_id = recovery_authorization_id
        self._close_outcome = close_outcome
        self._portfolio_confirmation_id = portfolio_confirmation_id
        self._advance(at_ns)
        return self.view()

    def _action_view(self, record: _ActionRecord) -> ExecutionActionView:
        return ExecutionActionView(
            action=record.action,
            permit_id=record.permit.permit_id,
            child_order_id=record.child.client_order_id,
            state=record.state,
            transport_attempts=record.transport_attempts,
            last_transition_ns=record.last_transition_ns,
            venue_order_id=record.venue_order_id,
            reason=record.reason,
        )

    def _stage_view(self, stage_record: _StageRecord) -> ExecutionStageView:
        records = tuple(self._record(item) for item in stage_record.action_ids)
        if any(item.state is ExecutionActionState.UNKNOWN for item in records):
            state = ExecutionStageState.RECOVERY_REQUIRED
        elif all(not self._record_is_unresolved(item) for item in records):
            state = ExecutionStageState.COMPLETED
        elif all(item.state is ExecutionActionState.PREPARED for item in records):
            state = ExecutionStageState.PREPARED
        else:
            state = ExecutionStageState.ACTIVE
        return ExecutionStageView(
            stage=stage_record.stage,
            permit_id=stage_record.permit.permit_id,
            child_order_ids=tuple(
                item.child.view().request.client_order_id for item in records
            ),
            state=state,
            last_transition_ns=max(item.last_transition_ns for item in records),
        )

    def _leg_view(self, basket_leg_id: object) -> OrderGroupLegView:
        leg = self._leg(basket_leg_id)
        action_ids = self._leg_action_ids[str(leg.leg_id)]
        records = tuple(self._actions[action_id] for action_id in action_ids)
        filled = Decimal(0)
        working = Decimal(0)
        unresolved: list[GroupActionId] = []
        child_ids: list[ClientOrderId] = []
        for record in records:
            child = record.child.view()
            sign = Decimal(1) if child.request.side is OrderSide.BUY else Decimal(-1)
            filled += sign * child.cumulative_filled_quantity.as_decimal()
            if not child.is_terminal:
                working += sign * child.remaining_quantity.as_decimal()
            if self._record_is_unresolved(record):
                unresolved.append(record.action.action_id)
            child_ids.append(child.request.client_order_id)
        return OrderGroupLegView(
            basket_leg_id=leg.leg_id,
            account_id=leg.account_id,
            instrument_id=leg.instrument_id,
            target_quantity=leg.target_quantity,
            child_order_ids=tuple(child_ids),
            signed_cumulative_filled_delta=_quantity_from_decimal(filled),
            signed_working_quantity=_quantity_from_decimal(working),
            unresolved_action_ids=tuple(unresolved),
        )

    def _unresolved_action_ids(self) -> tuple[GroupActionId, ...]:
        return tuple(
            action_id
            for action_id, record in self._actions.items()
            if self._record_is_unresolved(record)
        )

    @staticmethod
    def _record_is_unresolved(record: _ActionRecord) -> bool:
        if record.state in {
            ExecutionActionState.PREPARED,
            ExecutionActionState.TRANSMITTING,
            ExecutionActionState.RETRY_ELIGIBLE,
            ExecutionActionState.UNKNOWN,
        }:
            return True
        return not record.child.view().is_terminal

    def _validate_retry_authority(
        self,
        record: _ActionRecord,
        *,
        at_ns: UnixNanos,
    ) -> None:
        if at_ns > record.permit.valid_until_ns:
            raise OrderGroupAuthorizationError("permit expired before retry")
        if at_ns > self._admission.valid_until_ns:
            raise OrderGroupAuthorizationError("group expired before retry")
        if self._status is not OrderGroupStatus.ACTIVE:
            raise OrderGroupTransitionError("retry requires ACTIVE group")

    def _require_transmitting(self, action_id: GroupActionId) -> _ActionRecord:
        record = self._record(action_id)
        if record.state is not ExecutionActionState.TRANSMITTING:
            raise OrderGroupTransitionError(
                f"action is not transmitting: {record.state.value}"
            )
        return record

    def _record(self, action_id: GroupActionId) -> _ActionRecord:
        try:
            return self._actions[action_id]
        except KeyError as error:
            raise KeyError(f"unknown group action: {action_id}") from error

    def _record_for_child(self, client_order_id: ClientOrderId) -> _ActionRecord:
        try:
            action_id = self._child_to_action[client_order_id]
        except KeyError as error:
            raise KeyError(f"unknown group child: {client_order_id}") from error
        return self._record(action_id)

    def _leg(self, basket_leg_id: object) -> BasketTargetLeg:
        for leg in self._admission.basket.legs:
            if leg.leg_id == basket_leg_id:
                return leg
        raise OrderGroupIdentityError("unknown Basket leg")

    def _local_terminal_event(
        self,
        record: _ActionRecord,
        *,
        status: OrderStatus,
        at_ns: UnixNanos,
        reason: str,
    ) -> OrderEvent:
        return OrderEvent(
            venue_update_id=(f"group-submit-{status.value}:{record.action.action_id}"),
            client_order_id=record.child.client_order_id,
            status=status,
            cumulative_filled_quantity=Quantity(raw=0, scale=0),
            event_time_ns=at_ns,
            reason=reason,
        )

    def _advance(self, at_ns: UnixNanos) -> None:
        self._revision += 1
        self._last_transition_ns = UnixNanos(max(self._last_transition_ns, at_ns))

    def _assert_time(self, at_ns: UnixNanos) -> None:
        if at_ns < self._created_at_ns:
            raise ValueError("group mutation cannot precede creation")

    def _assert_writer(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise OrderGroupWriterViolationError(
                "Order Group state may only be mutated by its owner thread"
            )


def _quantity_from_decimal(value: Decimal) -> Quantity:
    return Quantity.from_str(format(value, "f"))


def _require_reason(value: str) -> None:
    _validate_evidence(value, name="reason", required=True)


def _validate_evidence(
    value: str,
    *,
    name: str,
    required: bool,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if required and not value:
        raise ValueError(f"{name} must be non-empty")
    if value and value != value.strip():
        raise ValueError(f"{name} must be trimmed")
    if len(value) > 512:
        raise ValueError(f"{name} exceeds maximum length")


__all__ = [
    "OrderGroupAuthorizationError",
    "OrderGroupCapacityError",
    "OrderGroupIdentityError",
    "OrderGroupStateError",
    "OrderGroupStateMachine",
    "OrderGroupTransitionError",
    "OrderGroupWriterViolationError",
]
