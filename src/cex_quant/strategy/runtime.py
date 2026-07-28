"""Synchronous single-writer strategy lifecycle and scheduling."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Never, Protocol, runtime_checkable

from cex_quant.core import IntentId, StrategyId
from cex_quant.features import FeatureSnapshot
from cex_quant.market_data import (
    AggregateTrade,
    BestBidAsk,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    OpenInterestUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)
from cex_quant.snapshots import DecisionSnapshotPublication

from .basket import (
    BasketIntentPolicy,
    BasketTargetIntent,
    ObjectiveTypeRegistry,
)
from .model import (
    DecisionIntent,
    PositionTargetIntent,
    StrategyContext,
    StrategyInput,
)

_CANONICAL_EVENT_TYPES = (
    AggregateTrade,
    BestBidAsk,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    OpenInterestUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)


class StrategyStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class StrategyPhase(StrEnum):
    START = "start"
    INPUT = "input"
    STOP = "stop"


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyFailure:
    """Stable diagnostic captured when strategy code raises."""

    phase: StrategyPhase
    input_sequence: int
    exception_type: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyDecision:
    """The complete output for exactly one accepted input."""

    strategy_id: StrategyId
    input_sequence: int
    intents: tuple[DecisionIntent, ...]


@runtime_checkable
class Strategy(Protocol):
    """Pure synchronous strategy callbacks.

    Implementations must not perform I/O. Lifecycle hooks receive no clock or
    service handles, keeping replay behavior controlled by explicit inputs.
    """

    @property
    def strategy_id(self) -> StrategyId:
        """Stable identity owned by the strategy instance."""

    def on_start(self) -> None:
        """Initialize deterministic in-memory state."""

    def on_input(
        self, context: StrategyContext
    ) -> tuple[DecisionIntent, ...]:
        """Transform one input into zero or more decision intents."""

    def on_stop(self) -> None:
        """Release deterministic in-memory state without performing I/O."""


class StrategyRuntimeError(RuntimeError):
    """Base error for invalid runtime usage or strategy execution."""


class StrategyLifecycleError(StrategyRuntimeError):
    """Raised when an operation is invalid for the current lifecycle state."""


class InvalidStrategyInputError(StrategyRuntimeError):
    """Raised when input is neither canonical nor an immutable snapshot."""


class StrategyScopeError(InvalidStrategyInputError):
    """Raised when an input is outside the runtime's stable scope set."""


class InvalidStrategyOutputError(StrategyRuntimeError):
    """Raised when strategy output violates the decision contract."""


class StrategyExecutionError(StrategyRuntimeError):
    """Raised after an exception is latched and the runtime enters FAILED."""


class StrategyRuntime:
    """Runs one strategy serially in caller-provided input order.

    The caller is the sole writer and must not invoke this object concurrently.
    No queue, task, clock or I/O capability exists inside this runtime.
    """

    def __init__(
        self,
        *,
        strategy: Strategy,
        accepted_scopes: frozenset[str] | None = None,
        basket_policy: BasketIntentPolicy | None = None,
        objective_registry: ObjectiveTypeRegistry | None = None,
    ) -> None:
        if not strategy.strategy_id:
            raise ValueError("strategy_id cannot be empty")
        if accepted_scopes is not None and (
            not accepted_scopes
            or any(
                not scope or scope.strip() != scope
                for scope in accepted_scopes
            )
        ):
            raise ValueError(
                "accepted_scopes must contain non-empty trimmed scopes"
            )
        if (basket_policy is None) != (objective_registry is None):
            raise ValueError(
                "basket_policy and objective_registry must be configured "
                "together"
            )
        self._strategy = strategy
        self._strategy_id = strategy.strategy_id
        self._accepted_scopes = accepted_scopes
        self._basket_policy = basket_policy
        self._objective_registry = objective_registry
        self._observed_scope: str | None = None
        self._status = StrategyStatus.CREATED
        self._input_sequence = 0
        self._failure: StrategyFailure | None = None
        self._callback_active = False

    @property
    def strategy_id(self) -> StrategyId:
        return self._strategy_id

    @property
    def status(self) -> StrategyStatus:
        return self._status

    @property
    def input_sequence(self) -> int:
        return self._input_sequence

    @property
    def failure(self) -> StrategyFailure | None:
        return self._failure

    def start(self) -> None:
        self._reject_reentrancy("start")
        if self._status is not StrategyStatus.CREATED:
            self._raise_lifecycle("start")
        self._callback_active = True
        try:
            self._strategy.on_start()
        except Exception as error:
            self._fail(StrategyPhase.START, error)
        finally:
            self._callback_active = False
        self._status = StrategyStatus.RUNNING

    def on_input(self, input: StrategyInput) -> StrategyDecision:
        self._reject_reentrancy("accept input")
        if self._status is not StrategyStatus.RUNNING:
            self._raise_lifecycle("accept input")
        if not isinstance(
            input,
            (
                *_CANONICAL_EVENT_TYPES,
                FeatureSnapshot,
                DecisionSnapshotPublication,
            ),
        ):
            raise InvalidStrategyInputError(
                "strategy input must be a canonical market event "
                "or immutable snapshot publication"
            )
        if isinstance(input, DecisionSnapshotPublication):
            input_scope = input.metadata.scope
        elif isinstance(input, FeatureSnapshot):
            input_scope = input.scope
        else:
            input_scope = str(input.instrument_id)
        self._validate_scope(input_scope)

        next_sequence = self._input_sequence + 1
        context = StrategyContext(
            strategy_id=self.strategy_id,
            input_scope=input_scope,
            input_sequence=next_sequence,
            input=input,
        )
        self._callback_active = True
        try:
            intents = self._strategy.on_input(context)
            self._validate_intents(intents, input)
        except Exception as error:
            self._fail(StrategyPhase.INPUT, error, next_sequence)
        finally:
            self._callback_active = False

        self._input_sequence = next_sequence
        return StrategyDecision(
            strategy_id=self.strategy_id,
            input_sequence=next_sequence,
            intents=intents,
        )

    def stop(self) -> None:
        self._reject_reentrancy("stop")
        if self._status is not StrategyStatus.RUNNING:
            self._raise_lifecycle("stop")
        self._callback_active = True
        try:
            self._strategy.on_stop()
        except Exception as error:
            self._fail(StrategyPhase.STOP, error, self._input_sequence)
        finally:
            self._callback_active = False
        self._status = StrategyStatus.STOPPED

    def _validate_scope(self, input_scope: str) -> None:
        if not input_scope or input_scope.strip() != input_scope:
            raise StrategyScopeError(
                "strategy input scope must be non-empty and trimmed"
            )
        if self._accepted_scopes is not None:
            if input_scope not in self._accepted_scopes:
                raise StrategyScopeError(
                    f"input scope {input_scope!r} is not accepted"
                )
            return
        if self._observed_scope is None:
            self._observed_scope = input_scope
        elif input_scope != self._observed_scope:
            raise StrategyScopeError(
                f"input scope {input_scope!r} does not match locked "
                f"scope {self._observed_scope!r}"
            )

    def _validate_intents(
        self,
        intents: tuple[DecisionIntent, ...],
        input: StrategyInput,
    ) -> None:
        if not isinstance(intents, tuple):
            raise InvalidStrategyOutputError(
                "strategy output must be a tuple of decision intents"
            )
        ids: set[IntentId] = set()
        for intent in intents:
            if not isinstance(
                intent,
                (PositionTargetIntent, BasketTargetIntent),
            ):
                raise InvalidStrategyOutputError(
                    "strategy returned an unsupported decision intent"
                )
            if intent.strategy_id != self.strategy_id:
                raise InvalidStrategyOutputError(
                    "intent strategy_id does not match runtime strategy"
                )
            if intent.intent_id in ids:
                raise InvalidStrategyOutputError(
                    "intent_id must be unique within one decision"
                )
            ids.add(intent.intent_id)
            if isinstance(intent, BasketTargetIntent):
                if not isinstance(input, DecisionSnapshotPublication):
                    raise InvalidStrategyOutputError(
                        "Basket intent requires a decision snapshot input"
                    )
                if (
                    intent.decision_snapshot_id
                    != input.metadata.snapshot_id
                ):
                    raise InvalidStrategyOutputError(
                        "Basket decision_snapshot_id does not match input"
                    )
                if (
                    intent.decision_time_ns
                    < input.metadata.assembled_at_ns
                ):
                    raise InvalidStrategyOutputError(
                        "Basket decision time precedes snapshot assembly"
                    )
                if (
                    self._basket_policy is None
                    or self._objective_registry is None
                ):
                    raise InvalidStrategyOutputError(
                        "Basket output is not enabled for this runtime"
                    )
                self._basket_policy.validate(
                    intent,
                    registry=self._objective_registry,
                )

    def _fail(
        self,
        phase: StrategyPhase,
        error: Exception,
        input_sequence: int = 0,
    ) -> Never:
        self._failure = StrategyFailure(
            phase=phase,
            input_sequence=input_sequence,
            exception_type=type(error).__name__,
            message=str(error),
        )
        self._status = StrategyStatus.FAILED
        raise StrategyExecutionError(
            f"strategy {phase.value} failed: {type(error).__name__}: {error}"
        ) from error

    def _raise_lifecycle(self, operation: str) -> Never:
        raise StrategyLifecycleError(
            f"cannot {operation} strategy in {self._status.value} state"
        )

    def _reject_reentrancy(self, operation: str) -> None:
        if self._callback_active:
            raise StrategyLifecycleError(
                f"cannot {operation} strategy during a strategy callback"
            )


__all__ = [
    "InvalidStrategyInputError",
    "InvalidStrategyOutputError",
    "Strategy",
    "StrategyDecision",
    "StrategyExecutionError",
    "StrategyFailure",
    "StrategyLifecycleError",
    "StrategyPhase",
    "StrategyRuntime",
    "StrategyRuntimeError",
    "StrategyScopeError",
    "StrategyStatus",
]
