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
from .adapters.binance_credentials import (
    BinanceCredentialBinding,
    BinanceCredentialError,
    EnvironmentBinanceCredentialProvider,
)
from .adapters.binance_http_transport import (
    AsyncioBinanceHttpTransport,
    BinanceHttpTimeouts,
    RestBaseUrlResolver,
    TlsConnectionOpener,
)
from .adapters.binance_private_stream import (
    BinanceFuturesUserStreamControlAdapter,
    BinanceFuturesUserStreamLease,
    BinancePrivateOrderStreamProcessor,
    BinancePrivateStreamDisposition,
    BinancePrivateStreamMessage,
    BinanceUserStreamLeaseExpiredError,
    build_spot_user_stream_subscription,
    parse_spot_user_stream_subscription,
)
from .adapters.binance_private_transport import (
    BinanceFuturesPrivateStreamTransport,
    BinancePrivateWebSocketConnection,
    BinancePrivateWebSocketConnector,
    BinanceSpotPrivateStreamTransport,
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
from .private_stream import (
    Keepalive,
    MonotonicNow,
    PrivateOrderStreamSession,
    PrivateOrderStreamSupervisor,
    PrivateStreamConnection,
    PrivateStreamTransport,
    Sleep,
    SnapshotHandler,
    TransportFactory,
)

__all__ = [
    "AsyncioBinanceHttpTransport",
    "AuthenticatedBinanceExecutionAdapter",
    "BinanceCredentialBinding",
    "BinanceCredentialError",
    "BinanceCredentialProvider",
    "BinanceCredentials",
    "BinanceFuturesPrivateStreamTransport",
    "BinanceFuturesUserStreamControlAdapter",
    "BinanceFuturesUserStreamLease",
    "BinanceHttpRequest",
    "BinanceHttpResponse",
    "BinanceHttpTimeouts",
    "BinanceHttpTransport",
    "BinanceHttpTransportFailure",
    "BinanceOrderNormalizationError",
    "BinanceOrderNormalizationErrorCode",
    "BinancePrivateOrderStreamProcessor",
    "BinancePrivateStreamDisposition",
    "BinancePrivateStreamMessage",
    "BinancePrivateWebSocketConnection",
    "BinancePrivateWebSocketConnector",
    "BinanceSpotPrivateStreamTransport",
    "BinanceUserStreamLeaseExpiredError",
    "CancelOrder",
    "CancelResult",
    "EnvironmentBinanceCredentialProvider",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "ExecutionOutcome",
    "ExecutionQueryError",
    "ExecutionStateUnknownError",
    "ExecutionTransportError",
    "InvalidExecutionRequestError",
    "Keepalive",
    "MonotonicNow",
    "OrderReconciliationGateway",
    "PrivateOrderStreamSession",
    "PrivateOrderStreamSupervisor",
    "PrivateStreamConnection",
    "PrivateStreamTransport",
    "QueryOrder",
    "RestBaseUrlResolver",
    "Sleep",
    "SnapshotHandler",
    "SubmitResult",
    "TlsConnectionOpener",
    "TransportFactory",
    "UnsupportedExecutionFeatureError",
    "build_spot_user_stream_subscription",
    "canonical_query",
    "hmac_sha256_hex",
    "normalize_binance_order_query",
    "normalize_binance_user_order_update",
    "parse_spot_user_stream_subscription",
]
