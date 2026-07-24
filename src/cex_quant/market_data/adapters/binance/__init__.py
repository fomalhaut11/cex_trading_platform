"""Binance market-data adapter public API.

The normalizer is pure and network-free. WebSocket lifecycle and REST
instrument discovery are separate adapter components.
"""

from .connection import (
    ConnectionLifecycle,
    ConnectionPolicy,
    ConnectionState,
    ConnectionTransitionError,
    ReconnectPolicy,
)
from .exchange_info import (
    BinanceExchangeInfoParser,
    InstrumentMappingError,
    InstrumentMappingErrorCode,
)
from .normalizer import (
    BINANCE_VENUE,
    BinanceMarketDataNormalizer,
    BinanceProduct,
    InstrumentResolver,
    StaticInstrumentResolver,
)
from .stream import (
    BinanceStreamSession,
    Clock,
    CombinedStreamRequest,
    EventHandler,
    ValidationHandler,
    WebSocketConnection,
    WebSocketTransport,
)
from .websockets_transport import WebsocketsTransport

__all__ = [
    "BINANCE_VENUE",
    "BinanceExchangeInfoParser",
    "BinanceMarketDataNormalizer",
    "BinanceProduct",
    "BinanceStreamSession",
    "Clock",
    "CombinedStreamRequest",
    "ConnectionLifecycle",
    "ConnectionPolicy",
    "ConnectionState",
    "ConnectionTransitionError",
    "EventHandler",
    "InstrumentMappingError",
    "InstrumentMappingErrorCode",
    "InstrumentResolver",
    "ReconnectPolicy",
    "StaticInstrumentResolver",
    "ValidationHandler",
    "WebSocketConnection",
    "WebSocketTransport",
    "WebsocketsTransport",
]
