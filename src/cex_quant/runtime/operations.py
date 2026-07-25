"""Protocol-neutral runtime health queries and operator trading controls."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from typing import Protocol

from cex_quant.core import UnixNanos
from cex_quant.observability import (
    Clock,
    HealthCheck,
    HealthIssue,
    HealthReport,
    HealthStatus,
    aggregate_health,
)
from cex_quant.risk import (
    RiskContext,
    RiskDecision,
    RiskDecisionStatus,
    RiskRejectReason,
)
from cex_quant.strategy import PositionTargetIntent


class OperatorMode(StrEnum):
    """Trading authority ordered from least to most restrictive."""

    ACTIVE = "active"
    REDUCE_ONLY = "reduce_only"
    HALTED = "halted"


class OperatorAction(StrEnum):
    ACTIVATE = "activate"
    ENABLE_REDUCE_ONLY = "enable_reduce_only"
    HALT = "halt"


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorCommand:
    """One authenticated command after a transport adapter validates identity."""

    command_id: str
    action: OperatorAction
    actor: str
    reason: str

    def __post_init__(self) -> None:
        _validate_text("command_id", self.command_id, maximum=128)
        _validate_text("actor", self.actor, maximum=128)
        _validate_text("reason", self.reason, maximum=512)
        if not isinstance(self.action, OperatorAction):
            raise ValueError("action must be an OperatorAction")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorControlSnapshot:
    mode: OperatorMode
    generation: int
    changed_at_ns: UnixNanos
    command_id: str
    actor: str
    reason: str


class OperatorCommandConflictError(RuntimeError):
    """Raised when one idempotency key is reused for a different command."""


class OperatorControlDurabilityError(RuntimeError):
    """Raised after a journal failure has latched trading halted."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorCommandRecord:
    command: OperatorCommand
    snapshot: OperatorControlSnapshot


class OperatorCommandJournal(Protocol):
    def read(self) -> Iterator[OperatorCommandRecord]: ...

    def append(self, record: OperatorCommandRecord) -> None: ...


class OperatorController:
    """Thread-safe, bounded and idempotent in-process trading authority."""

    component = "operator-control"

    def __init__(
        self,
        *,
        clock: Clock,
        command_history_size: int = 256,
        journal: OperatorCommandJournal | None = None,
    ) -> None:
        if (
            not isinstance(command_history_size, int)
            or isinstance(command_history_size, bool)
            or command_history_size < 1
        ):
            raise ValueError("command_history_size must be a positive int")
        self._clock = clock
        self._history_size = command_history_size
        self._journal = journal
        self._journal_failed = False
        self._lock = Lock()
        self._history: OrderedDict[
            str, tuple[OperatorCommand, OperatorControlSnapshot]
        ] = OrderedDict()
        self._snapshot = OperatorControlSnapshot(
            mode=OperatorMode.HALTED,
            generation=0,
            changed_at_ns=clock.wall_time_ns(),
            command_id="",
            actor="",
            reason="explicit operator activation is required",
        )
        if journal is not None:
            self._restore(journal)

    @property
    def snapshot(self) -> OperatorControlSnapshot:
        with self._lock:
            return self._snapshot

    def apply(self, command: OperatorCommand) -> OperatorControlSnapshot:
        if not isinstance(command, OperatorCommand):
            raise ValueError("command must be an OperatorCommand")
        with self._lock:
            if self._journal_failed:
                raise OperatorControlDurabilityError(
                    "operator command journal is unavailable"
                )
            if self._journal is not None:
                previous = self._find_durable(command.command_id)
                if previous is not None:
                    previous_command, previous_snapshot = previous
                    if previous_command != command:
                        raise OperatorCommandConflictError(
                            "operator command id was reused with "
                            "different content"
                        )
                    return previous_snapshot
            else:
                previous = self._history.get(command.command_id)
                if previous is not None:
                    previous_command, previous_snapshot = previous
                    if previous_command != command:
                        raise OperatorCommandConflictError(
                            "operator command id was reused with "
                            "different content"
                        )
                    self._history.move_to_end(command.command_id)
                    return previous_snapshot

            mode = {
                OperatorAction.ACTIVATE: OperatorMode.ACTIVE,
                OperatorAction.ENABLE_REDUCE_ONLY: OperatorMode.REDUCE_ONLY,
                OperatorAction.HALT: OperatorMode.HALTED,
            }[command.action]
            snapshot = OperatorControlSnapshot(
                mode=mode,
                generation=self._snapshot.generation + 1,
                changed_at_ns=self._clock.wall_time_ns(),
                command_id=command.command_id,
                actor=command.actor,
                reason=command.reason,
            )
            if self._journal is not None:
                try:
                    self._journal.append(
                        OperatorCommandRecord(
                            command=command,
                            snapshot=snapshot,
                        )
                    )
                except Exception:
                    self._latch_journal_failure()
                    raise OperatorControlDurabilityError(
                        "operator command journal append failed"
                    ) from None
            self._snapshot = snapshot
            self._remember(command, snapshot)
            return snapshot

    def health(self) -> HealthReport:
        snapshot = self.snapshot
        if self._journal_failed:
            status = HealthStatus.UNHEALTHY
            issues: tuple[HealthIssue, ...] = (
                HealthIssue(
                    code="JOURNAL_FAILED",
                    message="operator command journal is unavailable",
                ),
            )
        elif snapshot.mode is OperatorMode.ACTIVE:
            status = HealthStatus.HEALTHY
            issues = ()
        elif snapshot.mode is OperatorMode.REDUCE_ONLY:
            status = HealthStatus.DEGRADED
            issues = (
                HealthIssue(
                    code="REDUCE_ONLY",
                    message="operator restricted trading to exposure reduction",
                ),
            )
        else:
            status = HealthStatus.UNHEALTHY
            issues = (
                HealthIssue(
                    code="HALTED",
                    message="operator halted all new trading intents",
                ),
            )
        return HealthReport(
            component=self.component,
            status=status,
            observed_at_ns=self._clock.wall_time_ns(),
            issues=issues,
        )

    def _restore(self, journal: OperatorCommandJournal) -> None:
        seen: set[str] = set()
        expected_generation = 1
        try:
            for record in journal.read():
                self._validate_record(
                    record,
                    expected_generation=expected_generation,
                    seen=seen,
                )
                command = record.command
                snapshot = record.snapshot
                seen.add(command.command_id)
                expected_generation += 1
                self._snapshot = snapshot
                self._remember(command, snapshot)
        except Exception:
            self._latch_journal_failure()
            raise OperatorControlDurabilityError(
                "operator command journal recovery failed"
            ) from None

    def _find_durable(
        self,
        command_id: str,
    ) -> tuple[OperatorCommand, OperatorControlSnapshot] | None:
        assert self._journal is not None
        found: tuple[OperatorCommand, OperatorControlSnapshot] | None = None
        final_snapshot: OperatorControlSnapshot | None = None
        seen: set[str] = set()
        expected_generation = 1
        try:
            for record in self._journal.read():
                self._validate_record(
                    record,
                    expected_generation=expected_generation,
                    seen=seen,
                )
                seen.add(record.command.command_id)
                expected_generation += 1
                final_snapshot = record.snapshot
                if record.command.command_id == command_id:
                    found = record.command, record.snapshot
            if (
                final_snapshot is None
                and self._snapshot.generation != 0
            ) or (
                final_snapshot is not None
                and final_snapshot != self._snapshot
            ):
                raise ValueError("operator journal changed outside controller")
        except Exception:
            self._latch_journal_failure()
            raise OperatorControlDurabilityError(
                "operator command journal read failed"
            ) from None
        return found

    @staticmethod
    def _validate_record(
        record: OperatorCommandRecord,
        *,
        expected_generation: int,
        seen: set[str],
    ) -> None:
        if not isinstance(record, OperatorCommandRecord):
            raise ValueError("invalid operator journal record")
        command = record.command
        snapshot = record.snapshot
        expected_mode = {
            OperatorAction.ACTIVATE: OperatorMode.ACTIVE,
            OperatorAction.ENABLE_REDUCE_ONLY: OperatorMode.REDUCE_ONLY,
            OperatorAction.HALT: OperatorMode.HALTED,
        }[command.action]
        if (
            command.command_id in seen
            or snapshot.generation != expected_generation
            or snapshot.mode is not expected_mode
            or snapshot.command_id != command.command_id
            or snapshot.actor != command.actor
            or snapshot.reason != command.reason
        ):
            raise ValueError("inconsistent operator journal record")

    def _remember(
        self,
        command: OperatorCommand,
        snapshot: OperatorControlSnapshot,
    ) -> None:
        self._history[command.command_id] = (command, snapshot)
        while len(self._history) > self._history_size:
            self._history.popitem(last=False)

    def _latch_journal_failure(self) -> None:
        self._journal_failed = True
        self._snapshot = OperatorControlSnapshot(
            mode=OperatorMode.HALTED,
            generation=self._snapshot.generation,
            changed_at_ns=self._clock.wall_time_ns(),
            command_id="",
            actor="",
            reason="operator command journal failure",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeHealthSnapshot:
    aggregate: HealthReport
    reports: tuple[HealthReport, ...]


class RuntimeHealthService:
    """Evaluate registered checks in stable order and sanitize failures."""

    def __init__(
        self,
        *,
        component: str,
        clock: Clock,
        checks: tuple[HealthCheck, ...],
    ) -> None:
        _validate_text("component", component, maximum=128)
        if not isinstance(checks, tuple):
            raise ValueError("checks must be a tuple")
        names: list[str] = []
        for check in checks:
            try:
                name = check.component
            except Exception:
                raise ValueError(
                    "health check component must be readable"
                ) from None
            _validate_text("health check component", name, maximum=128)
            names.append(name)
        if len(names) != len(set(names)):
            raise ValueError("health check components must be unique")
        self._component = component
        self._clock = clock
        self._checks = tuple(zip(names, checks, strict=True))

    @property
    def component(self) -> str:
        return self._component

    def snapshot(self) -> RuntimeHealthSnapshot:
        observed_at_ns = self._clock.wall_time_ns()
        reports = tuple(
            self._safe_report(name, check, observed_at_ns)
            for name, check in self._checks
        )
        return RuntimeHealthSnapshot(
            aggregate=aggregate_health(
                self._component,
                observed_at_ns,
                reports,
            ),
            reports=reports,
        )

    def health(self) -> HealthReport:
        return self.snapshot().aggregate

    @staticmethod
    def _safe_report(
        component: str,
        check: HealthCheck,
        observed_at_ns: UnixNanos,
    ) -> HealthReport:
        try:
            report = check.health()
        except Exception as error:
            return HealthReport(
                component=component,
                status=HealthStatus.UNHEALTHY,
                observed_at_ns=observed_at_ns,
                issues=(
                    HealthIssue(
                        code="CHECK_FAILED",
                        message=(
                            "health check failed: "
                            f"{type(error).__name__}"
                        ),
                    ),
                ),
            )
        if (
            not isinstance(report, HealthReport)
            or report.component != component
            or not isinstance(report.status, HealthStatus)
        ):
            return HealthReport(
                component=component,
                status=HealthStatus.UNHEALTHY,
                observed_at_ns=observed_at_ns,
                issues=(
                    HealthIssue(
                        code="INVALID_REPORT",
                        message="health check returned an invalid report",
                    ),
                ),
            )
        return report


class RiskEvaluator(Protocol):
    def evaluate(
        self,
        intent: PositionTargetIntent,
        context: RiskContext,
    ) -> RiskDecision: ...


_MODE_SEVERITY = {
    OperatorMode.ACTIVE: 0,
    OperatorMode.REDUCE_ONLY: 1,
    OperatorMode.HALTED: 2,
}


class OperatorRiskGate:
    """Apply halt/reduce-only authority after normal deterministic risk."""

    def __init__(
        self,
        *,
        delegate: RiskEvaluator,
        controller: OperatorController,
    ) -> None:
        self._delegate = delegate
        self._controller = controller

    def evaluate(
        self,
        intent: PositionTargetIntent,
        context: RiskContext,
    ) -> RiskDecision:
        before = self._controller.snapshot.mode
        decision = self._delegate.evaluate(intent, context)
        after = self._controller.snapshot.mode
        mode = max((before, after), key=_MODE_SEVERITY.__getitem__)
        if mode is OperatorMode.ACTIVE:
            return decision
        if mode is OperatorMode.HALTED:
            return _reject(decision, RiskRejectReason.OPERATOR_HALTED)
        if not (
            _reduces_exposure(
                context.current_strategy_position.as_decimal(),
                decision.projected_strategy_position.as_decimal(),
            )
            and _reduces_exposure(
                context.current_global_position.as_decimal(),
                decision.projected_global_position.as_decimal(),
            )
        ):
            return _reject(
                decision,
                RiskRejectReason.REDUCE_ONLY_VIOLATION,
            )
        return decision


def _reject(
    decision: RiskDecision,
    reason: RiskRejectReason,
) -> RiskDecision:
    reasons = (
        decision.reasons
        if reason in decision.reasons
        else (*decision.reasons, reason)
    )
    return replace(
        decision,
        status=RiskDecisionStatus.REJECT,
        reasons=reasons,
    )


def _reduces_exposure(current: Decimal, projected: Decimal) -> bool:
    if projected == 0:
        return True
    if current == 0 or (current > 0) != (projected > 0):
        return False
    return abs(projected) <= abs(current)


def _validate_text(name: str, value: str, *, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(
            f"{name} must be non-empty, trimmed and at most {maximum} characters"
        )


__all__ = [
    "OperatorAction",
    "OperatorCommand",
    "OperatorCommandConflictError",
    "OperatorCommandJournal",
    "OperatorCommandRecord",
    "OperatorControlDurabilityError",
    "OperatorControlSnapshot",
    "OperatorController",
    "OperatorMode",
    "OperatorRiskGate",
    "RiskEvaluator",
    "RuntimeHealthService",
    "RuntimeHealthSnapshot",
]
