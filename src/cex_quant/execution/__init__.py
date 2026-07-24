"""Venue execution adapters and canonical execution reports.

This domain translates OMS commands but does not own canonical order state.
"""

from .adapters.binance_authenticated import (
    AuthenticatedBinanceExecutionAdapter,
    BinanceCredentialProvider,
    BinanceCredentials,
    BinanceHttpRequest,
    BinanceHttpResponse,
    BinanceHttpTransport,
    BinanceHttpTransportFailure,
    canonical_query,
    hmac_sha256_hex,
)
from .adapters.binance_reconciliation import (
    BinanceOrderNormalizationError,
    BinanceOrderNormalizationErrorCode,
    normalize_binance_order_query,
    normalize_binance_user_order_update,
)
from .contracts import (
    CancelOrder,
    CancelResult,
    ExecutionOutcome,
    QueryOrder,
    SubmitResult,
)
from .gateway import (
    ExecutionGateway,
    ExecutionGatewayError,
    ExecutionQueryError,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    InvalidExecutionRequestError,
    OrderReconciliationGateway,
    UnsupportedExecutionFeatureError,
)

__all__ = [
    "AuthenticatedBinanceExecutionAdapter",
    "BinanceCredentialProvider",
    "BinanceCredentials",
    "BinanceHttpRequest",
    "BinanceHttpResponse",
    "BinanceHttpTransport",
    "BinanceHttpTransportFailure",
    "BinanceOrderNormalizationError",
    "BinanceOrderNormalizationErrorCode",
    "CancelOrder",
    "CancelResult",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "ExecutionOutcome",
    "ExecutionQueryError",
    "ExecutionStateUnknownError",
    "ExecutionTransportError",
    "InvalidExecutionRequestError",
    "OrderReconciliationGateway",
    "QueryOrder",
    "SubmitResult",
    "UnsupportedExecutionFeatureError",
    "canonical_query",
    "hmac_sha256_hex",
    "normalize_binance_order_query",
    "normalize_binance_user_order_update",
]
