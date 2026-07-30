"""Single-writer durable Carry economic-position aggregate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from threading import get_ident

from cex_quant.core import IntentId, OrderGroupId, StrategyId, UnixNanos
from cex_quant.snapshots import DecisionSnapshotId

from .facts import (
    CarryApplicationFact,
    CarryFactPayload,
    CarryIntentLinked,
    CarryOrderGroupLinked,
    CarryOwnershipRegistered,
    CarryPositionCreated,
    CarryRecoveryRequired,
    CarryStateChanged,
    create_carry_application_fact,
)
from .identifiers import (
    ApplicationPositionId,
    CarryApplicationFactId,
    CarryPairId,
    deterministic_application_position_id,
)
from .journal import CarryJournal, CarryJournalError
from .model import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
    CarryPositionView,
)
from .ownership import CarryLegOwnership

MAX_RETAINED_CARRY_POSITIONS = 4_096

_LIFECYCLE_TRANSITIONS: dict[CarryLifecycle, frozenset[CarryLifecycle]] = {
    CarryLifecycle.PROPOSED: frozenset(
        {
            CarryLifecycle.OPENING,
            CarryLifecycle.RECOVERY_REQUIRED,
            CarryLifecycle.HALTED,
        }
    ),
    CarryLifecycle.OPENING: frozenset(
        {
            CarryLifecycle.ACTIVE,
            CarryLifecycle.CLOSING,
            CarryLifecycle.RECOVERY_REQUIRED,
            CarryLifecycle.HALTED,
        }
    ),
    CarryLifecycle.ACTIVE: frozenset(
        {
            CarryLifecycle.CLOSING,
            CarryLifecycle.RECOVERY_REQUIRED,
            CarryLifecycle.HALTED,
        }
    ),
    CarryLifecycle.CLOSING: frozenset(
        {
            CarryLifecycle.CLOSED,
            CarryLifecycle.RECOVERY_REQUIRED,
            CarryLifecycle.HALTED,
        }
    ),
    CarryLifecycle.RECOVERY_REQUIRED: frozenset(
        {
            CarryLifecycle.OPENING,
            CarryLifecycle.CLOSING,
            CarryLifecycle.HALTED,
        }
    ),
    CarryLifecycle.HALTED: frozenset(
        {
            CarryLifecycle.RECOVERY_REQUIRED,
            CarryLifecycle.CLOSING,
        }
    ),
    CarryLifecycle.CLOSED: frozenset(),
}


class CarryStateError(RuntimeError):
    pass


class CarryPersistenceError(CarryStateError):
    pass


class CarryRecoveryError(CarryStateError):
    pass


class CarryWriterViolationError(CarryStateError):
    pass


class CarryPositionBook:
    """Publish application state only after durable fact append."""

    def __init__(
        self,
        journal: CarryJournal,
        *,
        now_ns: Callable[[], UnixNanos],
        max_retained_positions: int = MAX_RETAINED_CARRY_POSITIONS,
    ) -> None:
        if not 0 < max_retained_positions <= MAX_RETAINED_CARRY_POSITIONS:
            raise ValueError("Carry retained-position limit is outside bounds")
        self._journal = journal
        self._now_ns = now_ns
        self._max_retained_positions = max_retained_positions
        self._writer_thread_id = get_ident()
        self._failure: BaseException | None = None
        self._positions: dict[ApplicationPositionId, CarryPositionView] = {}
        self._facts: dict[CarryApplicationFactId, CarryApplicationFact] = {}
        try:
            for fact in journal.read():
                self._apply(fact, replay=True)
        except (CarryJournalError, CarryStateError, ValueError) as error:
            self._failure = error
            raise CarryRecoveryError(
                f"Carry journal replay failed: {error}"
            ) from error

    def create_position(
        self,
        *,
        strategy_id: StrategyId,
        pair_id: CarryPairId,
        opening_snapshot_id: DecisionSnapshotId,
        ownership: tuple[CarryLegOwnership, ...],
        occurred_at_ns: UnixNanos,
        policy_version: int,
    ) -> CarryPositionView:
        self._assert_mutation_allowed()
        position_id = deterministic_application_position_id(
            strategy_id=strategy_id,
            pair_id=pair_id,
            opening_snapshot_id=opening_snapshot_id,
        )
        existing = self._positions.get(position_id)
        if existing is not None:
            if (
                existing.strategy_id,
                existing.pair_id,
                existing.opening_snapshot_id,
                existing.leg_ownership,
            ) == (
                strategy_id,
                pair_id,
                opening_snapshot_id,
                ownership,
            ):
                return existing
            raise CarryStateError(
                "Carry position identity has conflicting creation content"
            )
        if len(self._positions) >= self._max_retained_positions:
            raise CarryStateError("retained Carry position limit reached")
        if len(ownership) < 2:
            raise ValueError("Carry position requires at least two owned legs")
        fact = self._fact(
            position_id=position_id,
            expected_revision=0,
            occurred_at_ns=occurred_at_ns,
            policy_version=policy_version,
            payload=CarryPositionCreated(
                strategy_id=strategy_id,
                pair_id=pair_id,
                opening_snapshot_id=opening_snapshot_id,
                ownership=ownership,
            ),
        )
        return self._commit(fact)

    def link_intent(
        self,
        position_id: ApplicationPositionId,
        *,
        intent_id: IntentId,
        source_snapshot_id: DecisionSnapshotId,
        occurred_at_ns: UnixNanos,
        policy_version: int,
    ) -> CarryPositionView:
        current = self._current_for_mutation(position_id)
        if intent_id in current.intent_ids:
            return current
        return self._commit(
            self._fact(
                position_id=position_id,
                expected_revision=current.revision,
                occurred_at_ns=occurred_at_ns,
                policy_version=policy_version,
                payload=CarryIntentLinked(
                    intent_id=intent_id,
                    source_snapshot_id=source_snapshot_id,
                ),
            )
        )

    def link_order_group(
        self,
        position_id: ApplicationPositionId,
        *,
        order_group_id: OrderGroupId,
        source_snapshot_id: DecisionSnapshotId,
        occurred_at_ns: UnixNanos,
        policy_version: int,
    ) -> CarryPositionView:
        current = self._current_for_mutation(position_id)
        if order_group_id in current.order_group_ids:
            return current
        return self._commit(
            self._fact(
                position_id=position_id,
                expected_revision=current.revision,
                occurred_at_ns=occurred_at_ns,
                policy_version=policy_version,
                payload=CarryOrderGroupLinked(
                    order_group_id=order_group_id,
                    source_snapshot_id=source_snapshot_id,
                ),
            )
        )

    def register_ownership(
        self,
        position_id: ApplicationPositionId,
        *,
        ownership: CarryLegOwnership,
        occurred_at_ns: UnixNanos,
        policy_version: int,
    ) -> CarryPositionView:
        current = self._current_for_mutation(position_id)
        prior = next(
            (
                item
                for item in current.leg_ownership
                if item.ownership_id == ownership.ownership_id
            ),
            None,
        )
        if prior is not None:
            if prior == ownership:
                return current
            raise CarryStateError("Carry ownership identity has changed content")
        return self._commit(
            self._fact(
                position_id=position_id,
                expected_revision=current.revision,
                occurred_at_ns=occurred_at_ns,
                policy_version=policy_version,
                payload=CarryOwnershipRegistered(ownership=ownership),
            )
        )

    def transition(
        self,
        position_id: ApplicationPositionId,
        *,
        lifecycle: CarryLifecycle,
        hedge_state: CarryHedgeState,
        financial_state: CarryFinancialState,
        source_snapshot_id: DecisionSnapshotId,
        occurred_at_ns: UnixNanos,
        policy_version: int,
        reason: str = "",
    ) -> CarryPositionView:
        current = self._current_for_mutation(position_id)
        if (
            current.lifecycle,
            current.hedge_state,
            current.financial_state,
            current.latest_snapshot_id,
            current.recovery_reason,
        ) == (
            lifecycle,
            hedge_state,
            financial_state,
            source_snapshot_id,
            reason,
        ):
            return current
        if (
            lifecycle is not current.lifecycle
            and lifecycle not in _LIFECYCLE_TRANSITIONS[current.lifecycle]
        ):
            raise CarryStateError(
                f"invalid Carry lifecycle transition "
                f"{current.lifecycle.value}->{lifecycle.value}"
            )
        return self._commit(
            self._fact(
                position_id=position_id,
                expected_revision=current.revision,
                occurred_at_ns=occurred_at_ns,
                policy_version=policy_version,
                payload=CarryStateChanged(
                    lifecycle=lifecycle,
                    hedge_state=hedge_state,
                    financial_state=financial_state,
                    source_snapshot_id=source_snapshot_id,
                    reason=reason,
                ),
            )
        )

    def require_recovery(
        self,
        position_id: ApplicationPositionId,
        *,
        source_snapshot_id: DecisionSnapshotId,
        occurred_at_ns: UnixNanos,
        policy_version: int,
        reason: str,
    ) -> CarryPositionView:
        current = self._current_for_mutation(position_id)
        if (
            current.lifecycle is CarryLifecycle.RECOVERY_REQUIRED
            and current.latest_snapshot_id == source_snapshot_id
            and current.recovery_reason == reason
        ):
            return current
        return self._commit(
            self._fact(
                position_id=position_id,
                expected_revision=current.revision,
                occurred_at_ns=occurred_at_ns,
                policy_version=policy_version,
                payload=CarryRecoveryRequired(
                    source_snapshot_id=source_snapshot_id,
                    reason=reason,
                ),
            )
        )

    def position(
        self,
        position_id: ApplicationPositionId,
    ) -> CarryPositionView:
        try:
            return self._positions[position_id]
        except KeyError:
            raise KeyError(f"unknown Carry position: {position_id}") from None

    def positions(self) -> tuple[CarryPositionView, ...]:
        return tuple(
            self._positions[item]
            for item in sorted(self._positions, key=str)
        )

    def _fact(
        self,
        *,
        position_id: ApplicationPositionId,
        expected_revision: int,
        occurred_at_ns: UnixNanos,
        policy_version: int,
        payload: CarryFactPayload,
    ) -> CarryApplicationFact:
        return create_carry_application_fact(
            application_position_id=position_id,
            expected_revision=expected_revision,
            occurred_at_ns=occurred_at_ns,
            recorded_at_ns=self._now_ns(),
            policy_version=policy_version,
            payload=payload,
        )

    def _current_for_mutation(
        self,
        position_id: ApplicationPositionId,
    ) -> CarryPositionView:
        self._assert_mutation_allowed()
        return self.position(position_id)

    def _commit(self, fact: CarryApplicationFact) -> CarryPositionView:
        projected = _project(self._positions.get(fact.application_position_id), fact)
        try:
            self._journal.append(fact)
        except Exception as error:
            self._failure = error
            raise CarryPersistenceError(
                "Carry fact could not be durably appended"
            ) from error
        self._positions[fact.application_position_id] = projected
        self._facts[fact.fact_id] = fact
        return projected

    def _apply(self, fact: CarryApplicationFact, *, replay: bool) -> None:
        prior = self._facts.get(fact.fact_id)
        if prior is not None:
            if prior != fact:
                raise CarryStateError(
                    "Carry fact identity has changed content"
                )
            if replay:
                raise CarryStateError("Carry journal contains duplicate fact")
            return
        projected = _project(self._positions.get(fact.application_position_id), fact)
        self._positions[fact.application_position_id] = projected
        self._facts[fact.fact_id] = fact

    def _assert_mutation_allowed(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise CarryWriterViolationError(
                "Carry position book may only be mutated by its owner thread"
            )
        if self._failure is not None:
            raise CarryPersistenceError(
                "Carry position book is latched after persistence failure"
            ) from self._failure


def _project(
    current: CarryPositionView | None,
    fact: CarryApplicationFact,
) -> CarryPositionView:
    payload = fact.payload
    if isinstance(payload, CarryPositionCreated):
        if current is not None or fact.expected_revision != 0:
            raise CarryStateError("Carry position creation revision is invalid")
        return CarryPositionView(
            application_position_id=fact.application_position_id,
            strategy_id=payload.strategy_id,
            pair_id=payload.pair_id,
            revision=fact.new_revision,
            lifecycle=CarryLifecycle.PROPOSED,
            hedge_state=CarryHedgeState.UNKNOWN,
            financial_state=CarryFinancialState.NOT_READY,
            opening_snapshot_id=payload.opening_snapshot_id,
            latest_snapshot_id=payload.opening_snapshot_id,
            intent_ids=(),
            order_group_ids=(),
            leg_ownership=payload.ownership,
            last_transition_ns=fact.occurred_at_ns,
        )
    if current is None:
        raise CarryStateError("Carry fact precedes position creation")
    if current.revision != fact.expected_revision:
        raise CarryStateError("Carry fact revision does not match aggregate")
    if isinstance(payload, CarryIntentLinked):
        return replace(
            current,
            revision=fact.new_revision,
            last_transition_ns=fact.occurred_at_ns,
            intent_ids=(*current.intent_ids, payload.intent_id),
            latest_snapshot_id=payload.source_snapshot_id,
        )
    if isinstance(payload, CarryOrderGroupLinked):
        return replace(
            current,
            revision=fact.new_revision,
            last_transition_ns=fact.occurred_at_ns,
            order_group_ids=(
                *current.order_group_ids,
                payload.order_group_id,
            ),
            latest_snapshot_id=payload.source_snapshot_id,
        )
    if isinstance(payload, CarryOwnershipRegistered):
        return replace(
            current,
            revision=fact.new_revision,
            last_transition_ns=fact.occurred_at_ns,
            leg_ownership=(*current.leg_ownership, payload.ownership),
        )
    if isinstance(payload, CarryStateChanged):
        return replace(
            current,
            revision=fact.new_revision,
            last_transition_ns=fact.occurred_at_ns,
            lifecycle=payload.lifecycle,
            hedge_state=payload.hedge_state,
            financial_state=payload.financial_state,
            latest_snapshot_id=payload.source_snapshot_id,
            recovery_reason=payload.reason,
        )
    return replace(
        current,
        revision=fact.new_revision,
        last_transition_ns=fact.occurred_at_ns,
        lifecycle=CarryLifecycle.RECOVERY_REQUIRED,
        hedge_state=CarryHedgeState.UNKNOWN,
        latest_snapshot_id=payload.source_snapshot_id,
        recovery_reason=payload.reason,
    )


__all__ = [
    "MAX_RETAINED_CARRY_POSITIONS",
    "CarryPersistenceError",
    "CarryPositionBook",
    "CarryRecoveryError",
    "CarryStateError",
    "CarryWriterViolationError",
]
