"""Deterministic, fail-closed composition of the synchronous trading path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from cex_quant.execution import SubmitResult
from cex_quant.features import FeatureSnapshot
from cex_quant.market_data import MarketEvent, ValidationResult
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.oms import OrderRequest
from cex_quant.risk import RiskContext, RiskDecision
from cex_quant.strategy import (
    PositionTargetIntent,
    StrategyDecision,
    StrategyInput,
)


class PipelineStage(StrEnum):
    HEALTH = "health"
    VALIDATION = "validation"
    MARKET_STATE = "market_state"
    FEATURE = "feature"
    STRATEGY = "strategy"
    RISK = "risk"
    OMS = "oms"
    EXECUTION = "execution"
    RECORDER = "recorder"


class StageOutcome(StrEnum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class PipelineOutcome(StrEnum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class PipelineStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class StateGate:
    """Market-state admission result supplied by a state adapter."""

    accepted: bool
    reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class StageTrace:
    sequence: int
    stage: PipelineStage
    outcome: StageOutcome
    detail: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineFailure:
    stage: PipelineStage
    exception_type: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineResult:
    outcome: PipelineOutcome
    trace: tuple[StageTrace, ...]
    strategy_decision: StrategyDecision | None = None
    risk_decisions: tuple[RiskDecision, ...] = ()
    order_requests: tuple[OrderRequest, ...] = ()
    submit_results: tuple[SubmitResult, ...] = ()
    rejection_reason: str = ""
    failure: PipelineFailure | None = None


class HealthPort(Protocol):
    def health(self) -> HealthReport: ...


class ValidationPort(Protocol):
    def validate(self, event: MarketEvent) -> ValidationResult: ...


class MarketStatePort(Protocol):
    def apply(self, event: MarketEvent) -> StateGate: ...


class FeaturePort(Protocol):
    def on_event(self, event: MarketEvent) -> FeatureSnapshot | None: ...


class StrategyPort(Protocol):
    def on_input(self, input: StrategyInput) -> StrategyDecision: ...


class PortfolioReadPort(Protocol):
    """Minimum read-only portfolio surface needed by pre-trade risk."""

    def risk_context(self, intent: PositionTargetIntent) -> RiskContext: ...


class RiskPort(Protocol):
    def evaluate(
        self,
        intent: PositionTargetIntent,
        context: RiskContext,
    ) -> RiskDecision: ...


class OmsPort(Protocol):
    def create_order(
        self,
        intent: PositionTargetIntent,
        approval: RiskDecision,
    ) -> OrderRequest: ...


class ExecutionPort(Protocol):
    """Synchronous boundary used by replay and deterministic composition.

    A live application may bridge this port to an asynchronous gateway outside
    the single-writer pipeline.
    """

    def submit(self, request: OrderRequest) -> SubmitResult: ...


class PipelineRecorderPort(Protocol):
    def record(self, trace: StageTrace, value: object) -> None: ...


class PipelineStateError(RuntimeError):
    pass


class PipelineInvariantError(RuntimeError):
    pass


class TradingPipeline:
    """Run one market event through every mandatory stage in caller order."""

    def __init__(
        self,
        *,
        health: HealthPort,
        validator: ValidationPort,
        market_state: MarketStatePort,
        features: FeaturePort,
        strategy: StrategyPort,
        portfolio: PortfolioReadPort,
        risk: RiskPort,
        oms: OmsPort,
        execution: ExecutionPort,
        recorder: PipelineRecorderPort | None = None,
    ) -> None:
        self._health = health
        self._validator = validator
        self._market_state = market_state
        self._features = features
        self._strategy = strategy
        self._portfolio = portfolio
        self._risk = risk
        self._oms = oms
        self._execution = execution
        self._recorder = recorder
        self._status = PipelineStatus.RUNNING
        self._failure: PipelineFailure | None = None

    @property
    def status(self) -> PipelineStatus:
        return self._status

    @property
    def failure(self) -> PipelineFailure | None:
        return self._failure

    def stop(self) -> None:
        if self._status is PipelineStatus.FAILED:
            raise PipelineStateError("failed pipeline cannot be stopped")
        self._status = PipelineStatus.STOPPED

    def process(self, event: MarketEvent) -> PipelineResult:
        if self._status is not PipelineStatus.RUNNING:
            raise PipelineStateError(
                f"cannot process event while pipeline is {self._status.value}"
            )

        trace: list[StageTrace] = []
        try:
            health = self._health.health()
            if health.status is not HealthStatus.HEALTHY:
                return self._reject(
                    trace,
                    PipelineStage.HEALTH,
                    f"health status is {health.status.value}",
                    value=health,
                )
            self._append(trace, PipelineStage.HEALTH, StageOutcome.COMPLETED, health)

            validation = self._validator.validate(event)
            if not validation.is_valid:
                return self._reject(
                    trace,
                    PipelineStage.VALIDATION,
                    "market event validation failed",
                    value=validation,
                )
            self._append(
                trace,
                PipelineStage.VALIDATION,
                StageOutcome.COMPLETED,
                validation,
            )

            state_gate = self._market_state.apply(event)
            if not state_gate.accepted:
                return self._reject(
                    trace,
                    PipelineStage.MARKET_STATE,
                    state_gate.reason or "market state rejected event",
                    value=state_gate,
                )
            self._append(
                trace,
                PipelineStage.MARKET_STATE,
                StageOutcome.COMPLETED,
                state_gate,
            )

            snapshot = self._features.on_event(event)
            self._append(
                trace,
                PipelineStage.FEATURE,
                StageOutcome.COMPLETED,
                snapshot,
            )
            strategy_input: StrategyInput = (
                snapshot if snapshot is not None else event
            )
            strategy_decision = self._strategy.on_input(strategy_input)
            self._append(
                trace,
                PipelineStage.STRATEGY,
                StageOutcome.COMPLETED,
                strategy_decision,
            )

            risk_decisions: list[RiskDecision] = []
            requests: list[OrderRequest] = []
            submissions: list[SubmitResult] = []
            for intent in strategy_decision.intents:
                context = self._portfolio.risk_context(intent)
                approval = self._risk.evaluate(intent, context)
                self._validate_risk_identity(intent, approval)
                risk_decisions.append(approval)
                if not approval.allowed:
                    return self._reject(
                        trace,
                        PipelineStage.RISK,
                        "risk rejected intent",
                        value=approval,
                        strategy_decision=strategy_decision,
                        risk_decisions=tuple(risk_decisions),
                    )
                self._append(
                    trace,
                    PipelineStage.RISK,
                    StageOutcome.COMPLETED,
                    approval,
                )

                request = self._oms.create_order(intent, approval)
                self._validate_order_identity(intent, request)
                requests.append(request)
                self._append(
                    trace,
                    PipelineStage.OMS,
                    StageOutcome.COMPLETED,
                    request,
                )
                submission = self._execution.submit(request)
                submissions.append(submission)
                self._append(
                    trace,
                    PipelineStage.EXECUTION,
                    StageOutcome.COMPLETED,
                    submission,
                )

            return PipelineResult(
                outcome=PipelineOutcome.COMPLETED,
                trace=tuple(trace),
                strategy_decision=strategy_decision,
                risk_decisions=tuple(risk_decisions),
                order_requests=tuple(requests),
                submit_results=tuple(submissions),
            )
        except Exception as error:
            return self._fail(trace, error)

    def _append(
        self,
        trace: list[StageTrace],
        stage: PipelineStage,
        outcome: StageOutcome,
        value: object,
        detail: str = "",
    ) -> None:
        item = StageTrace(
            sequence=len(trace) + 1,
            stage=stage,
            outcome=outcome,
            detail=detail,
        )
        trace.append(item)
        if self._recorder is not None:
            try:
                self._recorder.record(item, value)
            except Exception as error:
                raise _RecorderFailure(error) from error

    def _reject(
        self,
        trace: list[StageTrace],
        stage: PipelineStage,
        reason: str,
        *,
        value: object,
        strategy_decision: StrategyDecision | None = None,
        risk_decisions: tuple[RiskDecision, ...] = (),
    ) -> PipelineResult:
        self._append(trace, stage, StageOutcome.REJECTED, value, reason)
        return PipelineResult(
            outcome=PipelineOutcome.REJECTED,
            trace=tuple(trace),
            strategy_decision=strategy_decision,
            risk_decisions=risk_decisions,
            rejection_reason=reason,
        )

    def _fail(
        self,
        trace: list[StageTrace],
        error: Exception,
    ) -> PipelineResult:
        if isinstance(error, _RecorderFailure):
            stage = PipelineStage.RECORDER
            actual = error.error
        else:
            stage = self._next_stage(trace)
            actual = error
        failure = PipelineFailure(
            stage=stage,
            exception_type=type(actual).__name__,
            message=str(actual),
        )
        self._failure = failure
        self._status = PipelineStatus.FAILED
        trace.append(
            StageTrace(
                sequence=len(trace) + 1,
                stage=stage,
                outcome=StageOutcome.FAILED,
                detail=f"{failure.exception_type}: {failure.message}",
            )
        )
        return PipelineResult(
            outcome=PipelineOutcome.FAILED,
            trace=tuple(trace),
            failure=failure,
        )

    @staticmethod
    def _next_stage(trace: list[StageTrace]) -> PipelineStage:
        order = (
            PipelineStage.HEALTH,
            PipelineStage.VALIDATION,
            PipelineStage.MARKET_STATE,
            PipelineStage.FEATURE,
            PipelineStage.STRATEGY,
            PipelineStage.RISK,
            PipelineStage.OMS,
            PipelineStage.EXECUTION,
        )
        completed = [
            item.stage
            for item in trace
            if item.outcome is StageOutcome.COMPLETED
        ]
        if not completed:
            return PipelineStage.HEALTH
        try:
            return order[order.index(completed[-1]) + 1]
        except (ValueError, IndexError):
            return completed[-1]

    @staticmethod
    def _validate_risk_identity(
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> None:
        if decision.intent != intent:
            raise PipelineInvariantError(
                "risk decision does not belong to the evaluated intent"
            )

    @staticmethod
    def _validate_order_identity(
        intent: PositionTargetIntent,
        request: OrderRequest,
    ) -> None:
        if (
            request.intent_id != intent.intent_id
            or request.instrument_id != intent.instrument_id
        ):
            raise PipelineInvariantError(
                "OMS request does not belong to the risk-approved intent"
            )


class _RecorderFailure(Exception):
    def __init__(self, error: Exception) -> None:
        self.error = error


__all__ = [
    "ExecutionPort",
    "FeaturePort",
    "HealthPort",
    "MarketStatePort",
    "OmsPort",
    "PipelineFailure",
    "PipelineInvariantError",
    "PipelineOutcome",
    "PipelineRecorderPort",
    "PipelineResult",
    "PipelineStage",
    "PipelineStateError",
    "PipelineStatus",
    "PortfolioReadPort",
    "RiskPort",
    "StageOutcome",
    "StageTrace",
    "StateGate",
    "StrategyPort",
    "TradingPipeline",
    "ValidationPort",
]
