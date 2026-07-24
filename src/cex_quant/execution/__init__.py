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
from .contracts import (
    CancelOrder,
    CancelResult,
    ExecutionOutcome,
    SubmitResult,
)
from .gateway import (
    ExecutionGateway,
    ExecutionGatewayError,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    InvalidExecutionRequestError,
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
    "CancelOrder",
    "CancelResult",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "ExecutionOutcome",
    "ExecutionStateUnknownError",
    "ExecutionTransportError",
    "InvalidExecutionRequestError",
    "SubmitResult",
    "UnsupportedExecutionFeatureError",
    "canonical_query",
    "hmac_sha256_hex",
]
