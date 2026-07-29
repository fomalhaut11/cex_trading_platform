"""Durable single-writer coordinator for Portfolio Risk authority."""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from threading import get_ident

from cex_quant.core import (
    ExecutionPermitId,
    GroupActionId,
    IntentId,
    OrderGroupId,
    PortfolioApprovalId,
    PortfolioConfirmationId,
    PortfolioReconciliationId,
    PortfolioReservationId,
    RecoveryAuthorizationId,
    UnixNanos,
)
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionActionState,
    OrderGroupStatus,
    OrderGroupView,
    decode_execution_action_permit,
    encode_execution_action_permit,
    execution_action_checksum,
)
from cex_quant.portfolio import AccountPositionRiskView, PositionRiskReadiness
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    BasketTargetIntent,
    decode_basket_target_intent,
    encode_basket_target_intent,
)

from .portfolio_journal import (
    PortfolioRiskJournal,
    PortfolioRiskJournalEntry,
    PortfolioRiskJournalEntryKind,
)
from .portfolio_model import (
    BasketPortfolioRiskDecision,
    ExecutionActionRiskDecision,
    GroupRecoveryAuthorization,
    PortfolioApprovalEvidence,
    PortfolioRiskDecisionStatus,
    PortfolioRiskDirective,
    PortfolioRiskDirectiveKind,
    PortfolioRiskReservationState,
    PortfolioRiskReservationView,
    PortfolioTargetConfirmation,
    RecoveryAuthorizationMode,
)


class PortfolioRiskCoordinatorError(RuntimeError):
    pass


class PortfolioRiskPersistenceError(PortfolioRiskCoordinatorError):
    """Coordinator is latched fail-closed after a journal failure."""


class PortfolioRiskAuthorizationError(PortfolioRiskCoordinatorError):
    pass


class PortfolioRiskIdentityConflictError(PortfolioRiskCoordinatorError):
    pass


class PortfolioRiskWriterViolationError(PortfolioRiskCoordinatorError):
    pass


class PortfolioRiskRecoveryError(PortfolioRiskCoordinatorError):
    pass


@dataclass(frozen=True, slots=True)
class _PermitRecord:
    permit: ExecutionActionPermit
    generation: int
    consumed: bool


class PortfolioRiskCoordinator:
    """Own reservations and the liveness of exact execution permits."""

    def __init__(
        self,
        *,
        journal: PortfolioRiskJournal,
        risk_policy_version: int,
        reservation_lifetime_ns: int,
        max_active_reservations: int,
        now_ns: UnixNanos,
    ) -> None:
        if risk_policy_version <= 0:
            raise ValueError("risk_policy_version must be positive")
        if reservation_lifetime_ns <= 0:
            raise ValueError("reservation_lifetime_ns must be positive")
        if max_active_reservations <= 0:
            raise ValueError("max_active_reservations must be positive")
        self._journal = journal
        self._risk_policy_version = risk_policy_version
        self._reservation_lifetime_ns = reservation_lifetime_ns
        self._max_active_reservations = max_active_reservations
        self._writer_thread_id = get_ident()
        self._persistence_failure: Exception | None = None
        self._generation = 1
        self._reservations: dict[
            PortfolioApprovalId, PortfolioRiskReservationView
        ] = {}
        self._approvals: dict[
            PortfolioApprovalId, PortfolioApprovalEvidence
        ] = {}
        self._permits: dict[ExecutionPermitId, _PermitRecord] = {}
        self._reserved_initial_margin: dict[PortfolioApprovalId, Decimal] = {}
        self._recovery_authorizations: dict[
            RecoveryAuthorizationId, GroupRecoveryAuthorization
        ] = {}
        self._confirmations: dict[
            PortfolioConfirmationId, PortfolioTargetConfirmation
        ] = {}
        entries = tuple(self._journal.read())
        try:
            for entry in entries:
                self._apply_replay(entry)
        except (KeyError, TypeError, ValueError) as error:
            raise PortfolioRiskRecoveryError(
                "Portfolio Risk journal semantic replay failed"
            ) from error
        if entries:
            self._append_generation_change(
                at_ns=now_ns,
                reason="process restart invalidates pre-restart permits",
            )

    @property
    def authorization_generation(self) -> int:
        return self._generation

    def reservations(self) -> tuple[PortfolioRiskReservationView, ...]:
        return tuple(
            self._reservations[key]
            for key in sorted(self._reservations, key=str)
        )

    def reserve_approval(
        self,
        decision: BasketPortfolioRiskDecision,
        *,
        now_ns: UnixNanos,
    ) -> PortfolioApprovalEvidence:
        """Persist reservation capacity before publishing ALLOW evidence."""

        self._assert_mutation_allowed()
        if (
            decision.status is not PortfolioRiskDecisionStatus.ALLOW
            or decision.approval is None
        ):
            raise PortfolioRiskAuthorizationError(
                "only an allowed Basket decision can be reserved"
            )
        approval = decision.approval
        if approval.risk_policy_version != self._risk_policy_version:
            raise PortfolioRiskAuthorizationError(
                "approval policy version is not current"
            )
        if now_ns > approval.valid_until_ns:
            raise PortfolioRiskAuthorizationError("approval is expired")
        existing = self._reservations.get(approval.approval_id)
        if existing is not None:
            if (
                self._approvals[approval.approval_id] == approval
                and existing.basket == decision.basket
            ):
                return approval
            raise PortfolioRiskIdentityConflictError(
                "PortfolioApprovalId content conflict"
            )
        active_count = sum(item.active for item in self._reservations.values())
        if active_count >= self._max_active_reservations:
            raise PortfolioRiskAuthorizationError(
                "active reservation capacity reached"
            )
        incoming_scope = {
            (leg.account_id, leg.instrument_id)
            for leg in decision.basket.legs
        }
        if any(
            incoming_scope
            & {
                (leg.account_id, leg.instrument_id)
                for leg in item.basket.legs
            }
            for item in self._reservations.values()
            if item.active
        ):
            raise PortfolioRiskAuthorizationError(
                "active reservation conflicts with Basket scope"
            )
        reserved_margin = sum(
            (
                self._reserved_initial_margin[approval_id]
                for approval_id, item in self._reservations.items()
                if item.active
            ),
            Decimal(0),
        )
        requested_margin = max(
            Decimal(0),
            (
                decision.conservative_exposure.initial_margin.as_decimal()
                - decision.current_exposure.initial_margin.as_decimal()
            ),
        )
        if (
            reserved_margin + requested_margin
            > decision.current_exposure.available_margin.as_decimal()
        ):
            raise PortfolioRiskAuthorizationError(
                "reservation would overspend available margin"
            )
        reservation_id = PortfolioReservationId(
            hashlib.sha256(
                f"reservation:{approval.approval_id}".encode()
            ).hexdigest()
        )
        valid_until_ns = UnixNanos(
            min(
                int(approval.valid_until_ns),
                int(now_ns) + self._reservation_lifetime_ns,
            )
        )
        reservation = PortfolioRiskReservationView(
            reservation_id=reservation_id,
            approval_id=approval.approval_id,
            strategy_id=decision.basket.strategy_id,
            basket=decision.basket,
            state=PortfolioRiskReservationState.ACTIVE,
            created_at_ns=now_ns,
            valid_until_ns=valid_until_ns,
        )
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.APPROVAL_RESERVED,
                at_ns=now_ns,
                payload=_approval_reservation_payload(
                    approval,
                    reservation,
                    reserved_initial_margin=requested_margin,
                ),
            )
        )
        self._append_generation_change(
            at_ns=now_ns,
            reason="Portfolio approval reservation created",
        )
        self._approvals[approval.approval_id] = approval
        self._reservations[approval.approval_id] = reservation
        self._reserved_initial_margin[approval.approval_id] = requested_margin
        return approval

    def attach_reservation(
        self,
        approval_id: PortfolioApprovalId,
        group_id: OrderGroupId,
        *,
        now_ns: UnixNanos,
    ) -> PortfolioRiskReservationView:
        self._assert_mutation_allowed()
        reservation = self._reservation(approval_id)
        if (
            reservation.state is PortfolioRiskReservationState.ATTACHED_TO_GROUP
            and reservation.group_id == group_id
        ):
            return reservation
        if reservation.state is not PortfolioRiskReservationState.ACTIVE:
            raise PortfolioRiskAuthorizationError(
                "only an active reservation can attach to a group"
            )
        changed = PortfolioRiskReservationView(
            reservation_id=reservation.reservation_id,
            approval_id=reservation.approval_id,
            strategy_id=reservation.strategy_id,
            basket=reservation.basket,
            state=PortfolioRiskReservationState.ATTACHED_TO_GROUP,
            created_at_ns=reservation.created_at_ns,
            valid_until_ns=reservation.valid_until_ns,
            group_id=group_id,
        )
        self._persist_reservation_change(changed, now_ns=now_ns)
        return changed

    def release_reservation(
        self,
        approval_id: PortfolioApprovalId,
        *,
        now_ns: UnixNanos,
        reason: str,
    ) -> PortfolioRiskReservationView:
        return self._finish_reservation(
            approval_id,
            state=PortfolioRiskReservationState.RELEASED,
            now_ns=now_ns,
            reason=reason,
        )

    def expire_due(
        self,
        *,
        now_ns: UnixNanos,
    ) -> tuple[PortfolioRiskReservationView, ...]:
        self._assert_mutation_allowed()
        expired: list[PortfolioRiskReservationView] = []
        for approval_id in sorted(self._reservations, key=str):
            reservation = self._reservations[approval_id]
            if reservation.active and now_ns > reservation.valid_until_ns:
                expired.append(
                    self._finish_reservation(
                        approval_id,
                        state=PortfolioRiskReservationState.EXPIRED,
                        now_ns=now_ns,
                        reason="reservation deadline elapsed",
                    )
                )
        return tuple(expired)

    def mark_reservation_recovery_required(
        self,
        approval_id: PortfolioApprovalId,
        *,
        now_ns: UnixNanos,
        reason: str,
    ) -> PortfolioRiskReservationView:
        return self._finish_reservation(
            approval_id,
            state=PortfolioRiskReservationState.RECOVERY_REQUIRED,
            now_ns=now_ns,
            reason=reason,
        )

    def issue_permit(
        self,
        decision: ExecutionActionRiskDecision,
        *,
        now_ns: UnixNanos,
    ) -> ExecutionActionPermit:
        """Persist issuance generation before publishing the permit."""

        self._assert_mutation_allowed()
        if (
            decision.status is not PortfolioRiskDecisionStatus.ALLOW
            or decision.permit is None
        ):
            raise PortfolioRiskAuthorizationError(
                "only an allowed action decision can issue a permit"
            )
        permit = decision.permit
        if permit.risk_policy_version != self._risk_policy_version:
            raise PortfolioRiskAuthorizationError(
                "permit policy version is not current"
            )
        if now_ns > permit.valid_until_ns:
            raise PortfolioRiskAuthorizationError("permit is already expired")
        existing = self._permits.get(permit.permit_id)
        if existing is not None:
            if existing.permit == permit:
                return permit
            raise PortfolioRiskIdentityConflictError(
                "ExecutionPermitId content conflict"
            )
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.PERMIT_ISSUED,
                at_ns=now_ns,
                payload={
                    "permit": base64.b64encode(
                        encode_execution_action_permit(permit)
                    ).decode("ascii"),
                    "generation": self._generation,
                },
            )
        )
        self._permits[permit.permit_id] = _PermitRecord(
            permit=permit,
            generation=self._generation,
            consumed=False,
        )
        return permit

    def validate_permit(
        self,
        *,
        permit: ExecutionActionPermit,
        action: ExecutionAction,
        group: OrderGroupView,
        now_ns: UnixNanos,
    ) -> None:
        """Immediate pre-I/O liveness check; performs no external action."""

        self._assert_healthy()
        record = self._permits.get(permit.permit_id)
        if record is None or record.permit != permit:
            raise PortfolioRiskAuthorizationError("permit is unknown or changed")
        if record.consumed:
            raise PortfolioRiskAuthorizationError("permit is already consumed")
        if record.generation != self._generation:
            raise PortfolioRiskAuthorizationError(
                "permit authorization generation is stale"
            )
        if now_ns > permit.valid_until_ns:
            raise PortfolioRiskAuthorizationError("permit is expired")
        prepared = tuple(
            item
            for item in group.actions
            if item.action.action_id == action.action_id
        )
        if (
            permit.group_id != group.order_group_id
            or permit.group_id != action.group_id
            or permit.expected_group_revision
            != action.expected_group_revision
            or permit.action_id != action.action_id
            or permit.action_checksum != execution_action_checksum(action)
            or group.revision != permit.expected_group_revision + 1
            or len(prepared) != 1
            or prepared[0].action != action
            or prepared[0].permit_id != permit.permit_id
            or prepared[0].state is not ExecutionActionState.PREPARED
        ):
            raise PortfolioRiskAuthorizationError(
                "permit does not match current group and action"
            )

    def consume_for_external_io(
        self,
        *,
        permit: ExecutionActionPermit,
        action: ExecutionAction,
        group: OrderGroupView,
        now_ns: UnixNanos,
    ) -> None:
        """Durably consume exact authority immediately before external I/O."""

        self._assert_mutation_allowed()
        self.validate_permit(
            permit=permit,
            action=action,
            group=group,
            now_ns=now_ns,
        )
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.PERMIT_CONSUMED,
                at_ns=now_ns,
                payload={"permit_id": str(permit.permit_id)},
            )
        )
        record = self._permits[permit.permit_id]
        self._permits[permit.permit_id] = _PermitRecord(
            permit=record.permit,
            generation=record.generation,
            consumed=True,
        )

    def record_material_change(
        self,
        *,
        now_ns: UnixNanos,
        reason: str,
    ) -> int:
        self._assert_mutation_allowed()
        self._append_generation_change(at_ns=now_ns, reason=reason)
        return self._generation

    def persist_directive(self, directive: PortfolioRiskDirective) -> None:
        """Durably publish a semantic instruction; never call OMS directly."""

        self._assert_mutation_allowed()
        if directive.risk_policy_version != self._risk_policy_version:
            raise PortfolioRiskAuthorizationError(
                "directive policy version is not current"
            )
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.DIRECTIVE_ISSUED,
                at_ns=directive.issued_at_ns,
                payload={
                    "directive_id": str(directive.directive_id),
                    "group_id": str(directive.group_id),
                    "group_revision": directive.expected_group_revision,
                    "kind": directive.kind.value,
                    "risk_snapshot_id": str(directive.risk_snapshot_id),
                },
            )
        )
        if directive.kind is not PortfolioRiskDirectiveKind.CLEAR:
            self._append_generation_change(
                at_ns=directive.issued_at_ns,
                reason=f"Risk directive: {directive.kind.value}",
            )

    def authorize_group_recovery(
        self,
        *,
        group: OrderGroupView,
        position_views: tuple[AccountPositionRiskView, ...],
        reconciliation_id: PortfolioReconciliationId,
        risk_snapshot_id: DecisionSnapshotId,
        mode: RecoveryAuthorizationMode,
        issued_at_ns: UnixNanos,
        valid_until_ns: UnixNanos,
        action_id: GroupActionId | None = None,
        permit_id: ExecutionPermitId | None = None,
    ) -> GroupRecoveryAuthorization:
        """Issue typed recovery evidence after reconciliation is complete."""

        self._assert_mutation_allowed()
        if valid_until_ns < issued_at_ns:
            raise PortfolioRiskAuthorizationError(
                "recovery authorization expiry is invalid"
            )
        if group.status is not OrderGroupStatus.RECOVERY_REQUIRED:
            raise PortfolioRiskAuthorizationError(
                "group is not awaiting recovery"
            )
        if not position_views or any(
            item.readiness is not PositionRiskReadiness.READY
            or item.reconciliation_id is None
            for item in position_views
        ):
            raise PortfolioRiskAuthorizationError(
                "recovery requires reconciled Portfolio positions"
            )
        if any(
            action.state is ExecutionActionState.UNKNOWN
            for action in group.actions
        ):
            raise PortfolioRiskAuthorizationError(
                "unknown child outcome blocks recovery authorization"
            )
        reservation = self._reservation(group.approval_id)
        if (
            not reservation.active
            or reservation.group_id != group.order_group_id
        ):
            raise PortfolioRiskAuthorizationError(
                "group reservation is not reconstructable"
            )
        authorization_id = RecoveryAuthorizationId(
            hashlib.sha256(
                (
                    f"{group.order_group_id}:{group.revision}:"
                    f"{mode.value}:{reconciliation_id}:{risk_snapshot_id}:"
                    f"{action_id}:{permit_id}:{valid_until_ns}"
                ).encode()
            ).hexdigest()
        )
        evidence = GroupRecoveryAuthorization(
            authorization_id=authorization_id,
            group_id=group.order_group_id,
            expected_group_revision=group.revision,
            mode=mode,
            reconciliation_id=reconciliation_id,
            risk_snapshot_id=risk_snapshot_id,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
            risk_policy_version=self._risk_policy_version,
            action_id=action_id,
            permit_id=permit_id,
        )
        existing = self._recovery_authorizations.get(authorization_id)
        if existing is not None:
            if existing == evidence:
                return evidence
            raise PortfolioRiskIdentityConflictError(
                "recovery authorization identity conflict"
            )
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.RECOVERY_AUTHORIZED,
                at_ns=issued_at_ns,
                payload=_recovery_payload(evidence),
            )
        )
        self._recovery_authorizations[authorization_id] = evidence
        return evidence

    def confirm_portfolio_target(
        self,
        *,
        group: OrderGroupView,
        basket: BasketTargetIntent,
        position_views: tuple[AccountPositionRiskView, ...],
        risk_snapshot_id: DecisionSnapshotId,
        confirmed_at_ns: UnixNanos,
    ) -> PortfolioTargetConfirmation:
        """Confirm economic target facts without creating application state."""

        self._assert_mutation_allowed()
        if group.source_intent_id != basket.intent_id:
            raise PortfolioRiskAuthorizationError(
                "group does not belong to Basket"
            )
        if group.status is not OrderGroupStatus.CLOSING:
            raise PortfolioRiskAuthorizationError(
                "target confirmation requires a closing group"
            )
        if any(
            leg.unresolved_action_ids
            or leg.signed_working_quantity.raw != 0
            for leg in group.legs
        ):
            raise PortfolioRiskAuthorizationError(
                "unresolved child execution blocks target confirmation"
            )
        if any(
            item.readiness is not PositionRiskReadiness.READY
            for item in position_views
        ):
            raise PortfolioRiskAuthorizationError(
                "target confirmation requires ready positions"
            )
        actual = {
            (account.account_id, position.instrument_id): (
                position.effective_quantity.as_decimal()
            )
            for account in position_views
            for position in account.positions
        }
        if any(
            actual.get((leg.account_id, leg.instrument_id), Decimal(0))
            != leg.target_quantity.as_decimal()
            for leg in basket.legs
        ):
            raise PortfolioRiskAuthorizationError(
                "effective positions do not match Basket targets"
            )
        target_scope = {
            (leg.account_id, leg.instrument_id) for leg in basket.legs
        }
        if any(
            {
                (leg.account_id, leg.instrument_id)
                for leg in item.basket.legs
            }
            & target_scope
            for item in self._reservations.values()
            if item.active and item.approval_id != group.approval_id
        ):
            raise PortfolioRiskAuthorizationError(
                "conflicting reservation blocks target confirmation"
            )
        confirmation_id = PortfolioConfirmationId(
            hashlib.sha256(
                (
                    f"{group.order_group_id}:{group.revision}:"
                    f"{basket.intent_id}:{risk_snapshot_id}:"
                    f"{confirmed_at_ns}"
                ).encode()
            ).hexdigest()
        )
        evidence = PortfolioTargetConfirmation(
            confirmation_id=confirmation_id,
            group_id=group.order_group_id,
            expected_group_revision=group.revision,
            basket_intent_id=IntentId(basket.intent_id),
            risk_snapshot_id=risk_snapshot_id,
            confirmed_at_ns=confirmed_at_ns,
            risk_policy_version=self._risk_policy_version,
        )
        existing_confirmation = self._confirmations.get(confirmation_id)
        if existing_confirmation is not None:
            if existing_confirmation == evidence:
                return evidence
            raise PortfolioRiskIdentityConflictError(
                "target confirmation identity conflict"
            )
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.TARGET_CONFIRMED,
                at_ns=confirmed_at_ns,
                payload=_confirmation_payload(evidence),
            )
        )
        self._confirmations[confirmation_id] = evidence
        return evidence

    def _finish_reservation(
        self,
        approval_id: PortfolioApprovalId,
        *,
        state: PortfolioRiskReservationState,
        now_ns: UnixNanos,
        reason: str,
    ) -> PortfolioRiskReservationView:
        self._assert_mutation_allowed()
        if state not in {
            PortfolioRiskReservationState.RELEASED,
            PortfolioRiskReservationState.EXPIRED,
            PortfolioRiskReservationState.RECOVERY_REQUIRED,
        }:
            raise ValueError("reservation terminal/control state is invalid")
        if not reason or reason != reason.strip():
            raise ValueError("reservation change reason must be non-empty and trimmed")
        reservation = self._reservation(approval_id)
        if reservation.state is state:
            return reservation
        if not reservation.active:
            raise PortfolioRiskAuthorizationError(
                "inactive reservation cannot change state"
            )
        changed = PortfolioRiskReservationView(
            reservation_id=reservation.reservation_id,
            approval_id=reservation.approval_id,
            strategy_id=reservation.strategy_id,
            basket=reservation.basket,
            state=state,
            created_at_ns=reservation.created_at_ns,
            valid_until_ns=reservation.valid_until_ns,
        )
        self._persist_reservation_change(
            changed,
            now_ns=now_ns,
            reason=reason,
        )
        return changed

    def _persist_reservation_change(
        self,
        changed: PortfolioRiskReservationView,
        *,
        now_ns: UnixNanos,
        reason: str = "reservation attached to Order Group",
    ) -> None:
        self._persist(
            PortfolioRiskJournalEntry(
                kind=PortfolioRiskJournalEntryKind.RESERVATION_CHANGED,
                at_ns=now_ns,
                payload={
                    "approval_id": str(changed.approval_id),
                    "state": changed.state.value,
                    "group_id": (
                        None if changed.group_id is None else str(changed.group_id)
                    ),
                    "reason": reason,
                },
            )
        )
        self._append_generation_change(
            at_ns=now_ns,
            reason=reason,
        )
        self._reservations[changed.approval_id] = changed

    def _append_generation_change(
        self,
        *,
        at_ns: UnixNanos,
        reason: str,
    ) -> None:
        if not reason or reason != reason.strip():
            raise ValueError("generation change reason must be non-empty and trimmed")
        generation = self._generation + 1
        self._persist(
            PortfolioRiskJournalEntry(
                kind=(
                    PortfolioRiskJournalEntryKind.AUTHORIZATION_GENERATION_CHANGED
                ),
                at_ns=at_ns,
                payload={"generation": generation, "reason": reason},
            )
        )
        self._generation = generation

    def _apply_replay(self, entry: PortfolioRiskJournalEntry) -> None:
        payload = entry.payload
        if entry.kind is PortfolioRiskJournalEntryKind.APPROVAL_RESERVED:
            approval, reservation, reserved_margin = (
                _decode_approval_reservation(payload)
            )
            existing = self._reservations.get(approval.approval_id)
            if existing is not None and (
                existing != reservation
                or self._approvals[approval.approval_id] != approval
            ):
                raise ValueError("approval reservation identity conflict")
            self._approvals[approval.approval_id] = approval
            self._reservations[approval.approval_id] = reservation
            self._reserved_initial_margin[approval.approval_id] = reserved_margin
        elif entry.kind is PortfolioRiskJournalEntryKind.RESERVATION_CHANGED:
            approval_id = PortfolioApprovalId(_string(payload, "approval_id"))
            current = self._reservation(approval_id)
            group_id_raw = payload.get("group_id")
            group_id = (
                None
                if group_id_raw is None
                else OrderGroupId(_required_string_value(group_id_raw, "group_id"))
            )
            self._reservations[approval_id] = PortfolioRiskReservationView(
                reservation_id=current.reservation_id,
                approval_id=current.approval_id,
                strategy_id=current.strategy_id,
                basket=current.basket,
                state=PortfolioRiskReservationState(
                    _string(payload, "state")
                ),
                created_at_ns=current.created_at_ns,
                valid_until_ns=current.valid_until_ns,
                group_id=group_id,
            )
        elif entry.kind is PortfolioRiskJournalEntryKind.PERMIT_ISSUED:
            permit = _decode_permit(_string(payload, "permit"))
            generation = _integer(payload, "generation")
            existing_permit = self._permits.get(permit.permit_id)
            record = _PermitRecord(
                permit=permit,
                generation=generation,
                consumed=False,
            )
            if existing_permit is not None and existing_permit != record:
                raise ValueError("permit identity conflict")
            self._permits[permit.permit_id] = record
        elif entry.kind is PortfolioRiskJournalEntryKind.PERMIT_CONSUMED:
            permit_id = ExecutionPermitId(_string(payload, "permit_id"))
            current_permit = self._permits[permit_id]
            self._permits[permit_id] = _PermitRecord(
                permit=current_permit.permit,
                generation=current_permit.generation,
                consumed=True,
            )
        elif (
            entry.kind
            is PortfolioRiskJournalEntryKind.AUTHORIZATION_GENERATION_CHANGED
        ):
            generation = _integer(payload, "generation")
            if generation != self._generation + 1:
                raise ValueError("authorization generation is not contiguous")
            self._generation = generation
        elif entry.kind is PortfolioRiskJournalEntryKind.RECOVERY_AUTHORIZED:
            recovery = _decode_recovery(payload)
            existing_recovery = self._recovery_authorizations.get(
                recovery.authorization_id
            )
            if existing_recovery is not None and existing_recovery != recovery:
                raise ValueError("recovery authorization identity conflict")
            self._recovery_authorizations[recovery.authorization_id] = recovery
        elif entry.kind is PortfolioRiskJournalEntryKind.TARGET_CONFIRMED:
            confirmation = _decode_confirmation(payload)
            existing_confirmation = self._confirmations.get(
                confirmation.confirmation_id
            )
            if (
                existing_confirmation is not None
                and existing_confirmation != confirmation
            ):
                raise ValueError("target confirmation identity conflict")
            self._confirmations[confirmation.confirmation_id] = confirmation
        else:
            _string(payload, "directive_id")
            _string(payload, "group_id")
            _integer(payload, "group_revision")
            _string(payload, "kind")
            _string(payload, "risk_snapshot_id")

    def _reservation(
        self,
        approval_id: PortfolioApprovalId,
    ) -> PortfolioRiskReservationView:
        try:
            return self._reservations[approval_id]
        except KeyError as error:
            raise PortfolioRiskAuthorizationError(
                "Portfolio approval reservation is unknown"
            ) from error

    def _persist(self, entry: PortfolioRiskJournalEntry) -> None:
        self._assert_healthy()
        try:
            self._journal.append(entry)
        except Exception as error:
            self._persistence_failure = error
            raise PortfolioRiskPersistenceError(
                "Portfolio Risk journal append failed; coordinator is fail-closed"
            ) from error

    def _assert_mutation_allowed(self) -> None:
        self._assert_healthy()
        if get_ident() != self._writer_thread_id:
            raise PortfolioRiskWriterViolationError(
                "Portfolio Risk coordinator has a different writer"
            )

    def _assert_healthy(self) -> None:
        if self._persistence_failure is not None:
            raise PortfolioRiskPersistenceError(
                "Portfolio Risk coordinator is latched fail-closed"
            )


def _approval_reservation_payload(
    approval: PortfolioApprovalEvidence,
    reservation: PortfolioRiskReservationView,
    *,
    reserved_initial_margin: Decimal,
) -> dict[str, bool | int | str | None]:
    return {
        "approval_id": str(approval.approval_id),
        "assessment_checksum": approval.assessment_checksum,
        "approved_at_ns": int(approval.approved_at_ns),
        "basket": base64.b64encode(
            encode_basket_target_intent(reservation.basket)
        ).decode("ascii"),
        "basket_checksum": approval.basket_checksum,
        "basket_intent_id": str(approval.basket_intent_id),
        "created_at_ns": int(reservation.created_at_ns),
        "reservation_id": str(reservation.reservation_id),
        "risk_policy_version": approval.risk_policy_version,
        "risk_snapshot_id": str(approval.risk_snapshot_id),
        "reserved_initial_margin": format(reserved_initial_margin, "f"),
        "strategy_id": str(reservation.strategy_id),
        "approval_valid_until_ns": int(approval.valid_until_ns),
        "reservation_valid_until_ns": int(reservation.valid_until_ns),
    }


def _decode_approval_reservation(
    payload: dict[str, bool | int | str | None],
) -> tuple[
    PortfolioApprovalEvidence,
    PortfolioRiskReservationView,
    Decimal,
]:
    basket = _decode_basket(_string(payload, "basket"))
    approval = PortfolioApprovalEvidence(
        approval_id=PortfolioApprovalId(_string(payload, "approval_id")),
        basket_intent_id=basket.intent_id,
        basket_checksum=_string(payload, "basket_checksum"),
        risk_snapshot_id=DecisionSnapshotId(
            _string(payload, "risk_snapshot_id")
        ),
        assessment_checksum=_string(payload, "assessment_checksum"),
        approved_at_ns=UnixNanos(_integer(payload, "approved_at_ns")),
        valid_until_ns=UnixNanos(
            _integer(payload, "approval_valid_until_ns")
        ),
        risk_policy_version=_integer(payload, "risk_policy_version"),
    )
    if _string(payload, "basket_intent_id") != str(basket.intent_id):
        raise ValueError("journal Basket intent identity mismatch")
    reservation = PortfolioRiskReservationView(
        reservation_id=PortfolioReservationId(
            _string(payload, "reservation_id")
        ),
        approval_id=approval.approval_id,
        strategy_id=basket.strategy_id,
        basket=basket,
        state=PortfolioRiskReservationState.ACTIVE,
        created_at_ns=UnixNanos(_integer(payload, "created_at_ns")),
        valid_until_ns=UnixNanos(
            _integer(payload, "reservation_valid_until_ns")
        ),
    )
    if _string(payload, "strategy_id") != str(basket.strategy_id):
        raise ValueError("journal Basket strategy identity mismatch")
    try:
        reserved_margin = Decimal(
            _string(payload, "reserved_initial_margin")
        )
    except Exception:
        raise ValueError("journal reserved margin is invalid") from None
    if not reserved_margin.is_finite() or reserved_margin < 0:
        raise ValueError("journal reserved margin is invalid")
    return approval, reservation, reserved_margin


def _decode_basket(encoded: str) -> BasketTargetIntent:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("journal Basket is not valid base64") from None
    return decode_basket_target_intent(raw)


def _decode_permit(encoded: str) -> ExecutionActionPermit:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("journal permit is not valid base64") from None
    return decode_execution_action_permit(raw)


def _recovery_payload(
    evidence: GroupRecoveryAuthorization,
) -> dict[str, bool | int | str | None]:
    return {
        "action_id": (
            None if evidence.action_id is None else str(evidence.action_id)
        ),
        "authorization_id": str(evidence.authorization_id),
        "group_id": str(evidence.group_id),
        "group_revision": evidence.expected_group_revision,
        "issued_at_ns": int(evidence.issued_at_ns),
        "mode": evidence.mode.value,
        "permit_id": (
            None if evidence.permit_id is None else str(evidence.permit_id)
        ),
        "reconciliation_id": str(evidence.reconciliation_id),
        "risk_policy_version": evidence.risk_policy_version,
        "risk_snapshot_id": str(evidence.risk_snapshot_id),
        "valid_until_ns": int(evidence.valid_until_ns),
    }


def _decode_recovery(
    payload: dict[str, bool | int | str | None],
) -> GroupRecoveryAuthorization:
    action_raw = payload.get("action_id")
    permit_raw = payload.get("permit_id")
    return GroupRecoveryAuthorization(
        authorization_id=RecoveryAuthorizationId(
            _string(payload, "authorization_id")
        ),
        group_id=OrderGroupId(_string(payload, "group_id")),
        expected_group_revision=_integer(payload, "group_revision"),
        mode=RecoveryAuthorizationMode(_string(payload, "mode")),
        reconciliation_id=PortfolioReconciliationId(
            _string(payload, "reconciliation_id")
        ),
        risk_snapshot_id=DecisionSnapshotId(
            _string(payload, "risk_snapshot_id")
        ),
        issued_at_ns=UnixNanos(_integer(payload, "issued_at_ns")),
        valid_until_ns=UnixNanos(_integer(payload, "valid_until_ns")),
        risk_policy_version=_integer(payload, "risk_policy_version"),
        action_id=(
            None
            if action_raw is None
            else GroupActionId(_required_string_value(action_raw, "action_id"))
        ),
        permit_id=(
            None
            if permit_raw is None
            else ExecutionPermitId(
                _required_string_value(permit_raw, "permit_id")
            )
        ),
    )


def _confirmation_payload(
    evidence: PortfolioTargetConfirmation,
) -> dict[str, bool | int | str | None]:
    return {
        "basket_intent_id": str(evidence.basket_intent_id),
        "confirmation_id": str(evidence.confirmation_id),
        "confirmed_at_ns": int(evidence.confirmed_at_ns),
        "group_id": str(evidence.group_id),
        "group_revision": evidence.expected_group_revision,
        "risk_policy_version": evidence.risk_policy_version,
        "risk_snapshot_id": str(evidence.risk_snapshot_id),
    }


def _decode_confirmation(
    payload: dict[str, bool | int | str | None],
) -> PortfolioTargetConfirmation:
    return PortfolioTargetConfirmation(
        confirmation_id=PortfolioConfirmationId(
            _string(payload, "confirmation_id")
        ),
        group_id=OrderGroupId(_string(payload, "group_id")),
        expected_group_revision=_integer(payload, "group_revision"),
        basket_intent_id=IntentId(_string(payload, "basket_intent_id")),
        risk_snapshot_id=DecisionSnapshotId(
            _string(payload, "risk_snapshot_id")
        ),
        confirmed_at_ns=UnixNanos(_integer(payload, "confirmed_at_ns")),
        risk_policy_version=_integer(payload, "risk_policy_version"),
    )


def _string(
    payload: dict[str, bool | int | str | None],
    key: str,
) -> str:
    return _required_string_value(payload.get(key), key)


def _required_string_value(value: object, key: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"journal {key} must be a non-empty string")
    return value


def _integer(
    payload: dict[str, bool | int | str | None],
    key: str,
) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"journal {key} must be a non-negative integer")
    return value


__all__ = [
    "PortfolioRiskAuthorizationError",
    "PortfolioRiskCoordinator",
    "PortfolioRiskCoordinatorError",
    "PortfolioRiskIdentityConflictError",
    "PortfolioRiskPersistenceError",
    "PortfolioRiskRecoveryError",
    "PortfolioRiskWriterViolationError",
]
