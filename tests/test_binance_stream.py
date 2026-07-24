from __future__ import annotations

from pathlib import Path
from types import TracebackType
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import MonotonicNanos, TimePrecision, UnixNanos, VenueId
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import MarketDataValidator, MarketEvent, ValidationResult
from cex_quant.market_data.adapters.binance import (
    BinanceMarketDataNormalizer,
    BinanceProduct,
    BinanceStreamSession,
    CombinedStreamRequest,
    ConnectionState,
    StaticInstrumentResolver,
)

FIXTURES = Path(__file__).parent / "fixtures" / "binance"


class FixedClock:
    def unix_ns(self) -> UnixNanos:
        return UnixNanos(1_700_000_000_000_000_000)

    def monotonic_ns(self) -> MonotonicNanos:
        return MonotonicNanos(100)


class FakeConnection:
    def __init__(self, messages: list[bytes]) -> None:
        self._messages = messages
        self.closed = False

    def __aiter__(self) -> FakeConnection:
        self._index = 0
        return self

    async def __anext__(self) -> bytes:
        if self._index >= len(self._messages):
            raise StopAsyncIteration
        message = self._messages[self._index]
        self._index += 1
        return message

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.connection.close()


class FakeTransport:
    def __init__(self, messages: list[bytes]) -> None:
        self.connection = FakeConnection(messages)
        self.uri: str | None = None

    def connect(self, uri: str) -> FakeContext:
        self.uri = uri
        return FakeContext(self.connection)


class CombinedStreamRequestTest(TestCase):
    def test_builds_microsecond_combined_stream_uri(self) -> None:
        request = CombinedStreamRequest(
            base_url="wss://stream.binance.com:9443/stream",
            streams=("btcusdt@trade", "btcusdt@depth@100ms"),
            timestamp_precision=TimePrecision.MICROSECOND,
        )

        self.assertEqual(
            request.uri(),
            "wss://stream.binance.com:9443/stream"
            "?streams=btcusdt@trade/btcusdt@depth@100ms"
            "&timeUnit=MICROSECOND",
        )

    def test_rejects_duplicate_or_uppercase_streams(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            CombinedStreamRequest(
                base_url="wss://example.test/stream",
                streams=("btcusdt@trade", "btcusdt@trade"),
            )
        with self.assertRaisesRegex(ValueError, "lowercase"):
            CombinedStreamRequest(
                base_url="wss://example.test/stream",
                streams=("BTCUSDT@trade",),
            )


class BinanceStreamSessionTest(IsolatedAsyncioTestCase):
    async def test_session_applies_sequential_validation_backpressure(self) -> None:
        instrument_id = InstrumentId(
            venue=VenueId("BINANCE"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSDT",
        )
        normalizer = BinanceMarketDataNormalizer(
            product=BinanceProduct.SPOT,
            instruments=StaticInstrumentResolver(
                {(BinanceProduct.SPOT, "BTCUSDT"): instrument_id}
            ),
        )
        events: list[MarketEvent] = []
        validations: list[ValidationResult] = []

        async def on_event(event: MarketEvent) -> None:
            events.append(event)

        async def on_validation(result: ValidationResult) -> None:
            validations.append(result)

        session = BinanceStreamSession(
            request=CombinedStreamRequest(
                base_url="wss://example.test/stream",
                streams=("btcusdt@bookticker",),
            ),
            normalizer=normalizer,
            validator=MarketDataValidator(),
            clock=FixedClock(),
            on_event=on_event,
            on_validation=on_validation,
            connection_id="market-1",
        )
        transport = FakeTransport(
            [(FIXTURES / "spot_combined_book_ticker.json").read_bytes()]
        )

        await session.run_once(transport)

        self.assertEqual(len(validations), 1)
        self.assertEqual(len(events), 1)
        self.assertTrue(validations[0].is_valid)
        self.assertEqual(session.lifecycle.state, ConnectionState.RECONNECT_WAIT)
        self.assertTrue(transport.connection.closed)
        self.assertEqual(
            transport.uri,
            "wss://example.test/stream?streams=btcusdt@bookticker",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
