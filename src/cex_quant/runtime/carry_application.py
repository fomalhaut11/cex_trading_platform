"""Offline Carry Snapshot/strategy composition with external execution absent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Never, Protocol

from cex_quant.applications.carry.funding_arbitrage import (
    FundingCarryDecisionSnapshot,
)
from cex_quant.core import MonotonicNanos, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.snapshots import (
    DecisionSnapshotPublication,
    SnapshotAssessment,
    SnapshotReadiness,
    SourceObservation,
)
from cex_quant.strategy import (
    BasketTargetIntent,
    StrategyDecision,
    StrategyRuntime,
)

from .snapshot_coordinator import (
    ObservationDisposition,
    SnapshotCoordinator,
)


class CarryApplicationRuntimeStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class CarryRuntimeDisposition(StrEnum):
    NOT_READY = "not_ready"
    NO_NEW_SNAPSHOT = "no_new_snapshot"
    NO_ECONOMIC_INTENT = "no_economic_intent"
    BASKET_RECORDED_EXTERNAL_BLOCKED = "basket_recorded_external_blocked"


@dataclass(frozen=True, slots=True, kw_only=True)
class CarryRuntimeResult:
    disposition: CarryRuntimeDisposition
    assessment: SnapshotAssessment
    publication: (
        DecisionSnapshotPublication[FundingCarryDecisionSnapshot] | None
    )
    decision: StrategyDecision | None
    baskets: tuple[BasketTargetIntent, ...]
    external_execution_blocked: bool = True

    def __post_init__(self) -> None:
        if not self.external_execution_blocked:
            raise ValueError("offline Carry Runtime cannot enable execution")
        if (
            self.disposition
            is CarryRuntimeDisposition.BASKET_RECORDED_EXTERNAL_BLOCKED
        ):
            if not self.baskets or self.decision is None:
                raise ValueError("blocked Basket result requires decision evidence")
        elif self.baskets:
            raise ValueError("only blocked Basket result may contain Baskets")


class CarryBasketEvidencePort(Protocol):
    """Durable/offline evidence sink; it has no Risk, OMS or venue method."""

    def record(
        self,
        publication: DecisionSnapshotPublication[
            FundingCarryDecisionSnapshot
        ],
        decision: StrategyDecision,
    ) -> None: ...


class CarryApplicationRuntimeError(RuntimeError):
    pass


class CarryApplicationRuntimeStateError(CarryApplicationRuntimeError):
    pass


class CarryApplicationRuntime:
    """Compose ADR-009 and pure Carry policy, stopping before Risk/OMS."""

    def __init__(
        self,
        *,
        snapshots: SnapshotCoordinator[FundingCarryDecisionSnapshot],
        strategy: StrategyRuntime,
        evidence: CarryBasketEvidencePort | None = None,
    ) -> None:
        self._snapshots = snapshots
        self._strategy = strategy
        self._evidence = evidence
        self._status = CarryApplicationRuntimeStatus.CREATED
        self._failure: BaseException | None = None

    @property
    def status(self) -> CarryApplicationRuntimeStatus:
        return self._status

    @property
    def failure(self) -> BaseException | None:
        return self._failure

    def start(self) -> None:
        if self._status is not CarryApplicationRuntimeStatus.CREATED:
            raise CarryApplicationRuntimeStateError(
                f"cannot start Carry Runtime in {self._status.value} state"
            )
        try:
            self._strategy.start()
        except Exception as error:
            self._fail(error)
        self._status = CarryApplicationRuntimeStatus.RUNNING

    def accept(
        self,
        observation: SourceObservation[object],
    ) -> ObservationDisposition:
        self._require_running()
        try:
            return self._snapshots.accept(observation)
        except Exception as error:
            self._fail(error)

    def evaluate(
        self,
        *,
        now_ns: UnixNanos,
        now_monotonic_ns: MonotonicNanos,
        clock_status: HealthStatus,
    ) -> CarryRuntimeResult:
        self._require_running()
        try:
            result = self._snapshots.evaluate(
                now_ns=now_ns,
                now_monotonic_ns=now_monotonic_ns,
                clock_status=clock_status,
            )
            publication = result.publication
            if publication is None:
                disposition = (
                    CarryRuntimeDisposition.NOT_READY
                    if result.assessment.readiness
                    is SnapshotReadiness.NOT_READY
                    else CarryRuntimeDisposition.NO_NEW_SNAPSHOT
                )
                return CarryRuntimeResult(
                    disposition=disposition,
                    assessment=result.assessment,
                    publication=None,
                    decision=None,
                    baskets=(),
                )
            decision = self._strategy.on_input(publication)
            if any(
                not isinstance(item, BasketTargetIntent)
                for item in decision.intents
            ):
                raise CarryApplicationRuntimeError(
                    "Carry Runtime accepts only generic Basket targets"
                )
            baskets = tuple(
                item
                for item in decision.intents
                if isinstance(item, BasketTargetIntent)
            )
            if not baskets:
                return CarryRuntimeResult(
                    disposition=CarryRuntimeDisposition.NO_ECONOMIC_INTENT,
                    assessment=result.assessment,
                    publication=publication,
                    decision=decision,
                    baskets=(),
                )
            if self._evidence is not None:
                self._evidence.record(publication, decision)
            return CarryRuntimeResult(
                disposition=(
                    CarryRuntimeDisposition.BASKET_RECORDED_EXTERNAL_BLOCKED
                ),
                assessment=result.assessment,
                publication=publication,
                decision=decision,
                baskets=baskets,
            )
        except Exception as error:
            self._fail(error)

    def stop(self) -> None:
        self._require_running()
        try:
            self._strategy.stop()
        except Exception as error:
            self._fail(error)
        self._status = CarryApplicationRuntimeStatus.STOPPED

    def _require_running(self) -> None:
        if self._status is not CarryApplicationRuntimeStatus.RUNNING:
            raise CarryApplicationRuntimeStateError(
                f"Carry Runtime is {self._status.value}, not running"
            )

    def _fail(self, error: BaseException) -> Never:
        self._failure = error
        self._status = CarryApplicationRuntimeStatus.FAILED
        raise CarryApplicationRuntimeError(
            f"Carry Runtime failed with {type(error).__name__}: {error}"
        ) from error


__all__ = [
    "CarryApplicationRuntime",
    "CarryApplicationRuntimeError",
    "CarryApplicationRuntimeStateError",
    "CarryApplicationRuntimeStatus",
    "CarryBasketEvidencePort",
    "CarryRuntimeDisposition",
    "CarryRuntimeResult",
]
