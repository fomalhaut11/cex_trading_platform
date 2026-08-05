"""Concrete adapters that bind domain services to runtime pipeline ports."""

from .execution import (
    AsyncExecutionPortBridge,
    ExecutionBridgeError,
    ExecutionBridgeQueryError,
    ExecutionBridgeStateError,
    ExecutionBridgeUnknownError,
)
from .execution_routing import (
    MAX_CONFIGURED_EXECUTION_ROUTES,
    ExactExecutionGatewayRouter,
    ExactExecutionRoute,
    ExecutionRoutingError,
    RoutedExecutionGateway,
)
from .features import FeatureEngineAdapter
from .market_state import MarketStateGateAdapter, MarketStateUpdater
from .oms import (
    AccountPolicy,
    CanonicalOmsApplicationService,
    OmsIdentityPolicy,
    OmsInvariantError,
    OmsPersistenceError,
    OmsRecoveryError,
    OrderParameters,
    OrderPolicy,
)

__all__ = [
    "MAX_CONFIGURED_EXECUTION_ROUTES",
    "AccountPolicy",
    "AsyncExecutionPortBridge",
    "CanonicalOmsApplicationService",
    "ExactExecutionGatewayRouter",
    "ExactExecutionRoute",
    "ExecutionBridgeError",
    "ExecutionBridgeQueryError",
    "ExecutionBridgeStateError",
    "ExecutionBridgeUnknownError",
    "ExecutionRoutingError",
    "FeatureEngineAdapter",
    "MarketStateGateAdapter",
    "MarketStateUpdater",
    "OmsIdentityPolicy",
    "OmsInvariantError",
    "OmsPersistenceError",
    "OmsRecoveryError",
    "OrderParameters",
    "OrderPolicy",
    "RoutedExecutionGateway",
]
