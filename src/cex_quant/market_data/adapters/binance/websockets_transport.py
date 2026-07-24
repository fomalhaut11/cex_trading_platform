"""Thin production transport based on the `websockets` asyncio client."""

from __future__ import annotations

from typing import Any, cast

from cex_quant.market_data.adapters.binance.stream import (
    WebSocketConnection,
    WebSocketTransport,
)


class WebsocketsTransport(WebSocketTransport):
    """Create bounded websocket connections without exposing library types."""

    def __init__(
        self,
        *,
        open_timeout_seconds: float = 10.0,
        close_timeout_seconds: float = 10.0,
        max_message_bytes: int = 4 * 1024 * 1024,
        max_queue_messages: int = 16,
    ) -> None:
        if open_timeout_seconds <= 0 or close_timeout_seconds <= 0:
            raise ValueError("WebSocket timeouts must be positive")
        if max_message_bytes <= 0 or max_queue_messages <= 0:
            raise ValueError("WebSocket bounds must be positive")
        self._open_timeout_seconds = open_timeout_seconds
        self._close_timeout_seconds = close_timeout_seconds
        self._max_message_bytes = max_message_bytes
        self._max_queue_messages = max_queue_messages

    def connect(self, uri: str) -> Any:
        """Return the library's async context manager.

        `ping_interval=None` disables unsolicited client pings. The library still
        responds automatically to server ping frames, matching Binance's
        server-driven heartbeat contract.
        """

        try:
            from websockets.asyncio.client import connect
        except ImportError as error:
            raise RuntimeError(
                "websockets 16.x is required; install the project dependencies"
            ) from error
        connection = connect(
            uri,
            open_timeout=self._open_timeout_seconds,
            close_timeout=self._close_timeout_seconds,
            ping_interval=None,
            max_size=self._max_message_bytes,
            max_queue=self._max_queue_messages,
        )
        return cast(WebSocketConnection, connection)


__all__ = ["WebsocketsTransport"]
