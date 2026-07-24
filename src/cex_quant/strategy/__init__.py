"""Strategy runtime contracts that transform information into trade intents.

Strategies never construct venue orders or bypass risk and OMS ownership.
"""

from .model import (
    CanonicalMarketEvent,
    DecisionIntent,
    PositionTargetIntent,
    StrategyContext,
    StrategyInput,
)
from .runtime import (
    InvalidStrategyInputError,
    InvalidStrategyOutputError,
    Strategy,
    StrategyDecision,
    StrategyExecutionError,
    StrategyFailure,
    StrategyLifecycleError,
    StrategyPhase,
    StrategyRuntime,
    StrategyRuntimeError,
    StrategyScopeError,
    StrategyStatus,
)

__all__ = [
    "CanonicalMarketEvent",
    "DecisionIntent",
    "InvalidStrategyInputError",
    "InvalidStrategyOutputError",
    "PositionTargetIntent",
    "Strategy",
    "StrategyContext",
    "StrategyDecision",
    "StrategyExecutionError",
    "StrategyFailure",
    "StrategyInput",
    "StrategyLifecycleError",
    "StrategyPhase",
    "StrategyRuntime",
    "StrategyRuntimeError",
    "StrategyScopeError",
    "StrategyStatus",
]
