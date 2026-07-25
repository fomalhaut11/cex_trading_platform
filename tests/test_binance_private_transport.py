from __future__ import annotations

import asyncio
import json
from types import TracebackType
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import AccountId
from cex_quant.execution.adapters.binance import BinanceProduct
from cex_quant.execution.adapters.binance_authenticated import (
    BinanceCredentials,
)
from cex_quant.execution.adapters.binance_private_transport import (
    BinanceFuturesPrivateStreamTransport,
    BinanceSpotPrivateStreamTransport,
)
from cex_quant.execution.gateway import ExecutionTransportError


class Credentials:
    def __init__(self, value: BinanceCredentials) -> None:
        self.value = value

    def credentials_for(self, account_id: AccountId) -> BinanceCredentials:
        del account_id
        return self.value


class FailingCredentials:
    def credentials_for(self, account_id: AccountId) -> BinanceCredentials:
        del account_id
        raise RuntimeError("sensitive-api-key sensitive-secret")


class Connection:
    def __init__(
        self,
        messages: list[bytes],
        *,
        send_error: Exception | None = None,
    ) -> None:
        self.messages = messages
        self.send_error = send_error
        self.sent: list[bytes | str] = []
        self.closed = False
        self.block = asyncio.Event()

    def __aiter__(self) -> Connection:
        return self

    async def __anext__(self) -> bytes:
        if self.messages:
            return self.messages.pop(0)
        await self.block.wait()
        raise StopAsyncIteration

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)
        if self.send_error is not None:
            raise self.send_error

    async def close(self) -> None:
        self.closed = True


class Context:
    def __init__(
        self,
        connection: Connection,
        *,
        enter_error: Exception | None = None,
    ) -> None:
        self.connection = connection
        self.enter_error = enter_error

    async def __aenter__(self) -> Connection:
        if self.enter_error is not None:
            raise self.enter_error
        return self.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        await self.connection.close()


class Connector:
    def __init__(
        self,
        connection: Connection,
        *,
        enter_error: Exception | None = None,
    ) -> None:
        self.connection = connection
        self.enter_error = enter_error
        self.uris: list[str] = []

    def connect(self, uri: str) -> Context:
        self.uris.append(uri)
        return Context(self.connection, enter_error=self.enter_error)


class Control:
    def __init__(
        self,
        product: BinanceProduct,
        *,
        keepalive_error: Exception | None = None,
    ) -> None:
        self.product = product
        self.keepalive_error = keepalive_error
        self.calls: list[str] = []
        self.listen_key = "secret-listen-key"

    async def open(self, account_id: AccountId) -> object:
        from cex_quant.execution.adapters.binance_private_stream import (
            BinanceFuturesUserStreamLease,
        )

        del account_id
        self.calls.append("open")
        return BinanceFuturesUserStreamLease(
            product=self.product,
            listen_key=self.listen_key,
        )

    async def keepalive(self, account_id: AccountId, lease: object) -> None:
        del account_id, lease
        self.calls.append("keepalive")
        if self.keepalive_error is not None:
            raise self.keepalive_error

    async def close(self, account_id: AccountId, lease: object) -> None:
        del account_id, lease
        self.calls.append("close")


def spot_transport(
    connection: Connection,
    *,
    timeout: float = 0.1,
) -> BinanceSpotPrivateStreamTransport:
    return BinanceSpotPrivateStreamTransport(
        product=BinanceProduct.SPOT,
        account_id=AccountId("testnet"),
        base_url="wss://ws-api.test",
        credential_provider=Credentials(
            BinanceCredentials(
                api_key="sensitive-api-key",
                secret="sensitive-secret",
            )
        ),
        connector=Connector(connection),
        timestamp_ms=lambda: 1_700_000_000_000,
        request_id_factory=lambda: "request-1",
        operation_timeout_seconds=timeout,
    )


class SpotPrivateTransportTests(IsolatedAsyncioTestCase):
    async def test_handshake_is_consumed_before_events_are_exposed(self) -> None:
        connection = Connection(
            [
                b'{"id":"request-1","status":200,'
                b'"result":{"subscriptionId":7}}',
                b'{"event":{"e":"executionReport"}}',
            ]
        )
        transport = spot_transport(connection)

        async with transport.connect() as stream:
            event = await anext(stream)

        request = json.loads(connection.sent[0])
        self.assertEqual(
            request["method"],
            "userDataStream.subscribe.signature",
        )
        self.assertEqual(event, b'{"event":{"e":"executionReport"}}')
        self.assertTrue(connection.closed)

    async def test_invalid_response_and_sensitive_send_error_are_redacted(
        self,
    ) -> None:
        for connection in (
            Connection([b'{"id":"wrong","status":200,"result":{}}']),
            Connection(
                [],
                send_error=RuntimeError(
                    "sensitive-api-key sensitive-secret signature-value"
                ),
            ),
        ):
            with self.subTest(send_error=connection.send_error):
                transport = spot_transport(connection)
                with self.assertRaises(ExecutionTransportError) as caught:
                    async with transport.connect():
                        self.fail("handshake must fail")
                rendered = str(caught.exception)
                self.assertNotIn("sensitive-api-key", rendered)
                self.assertNotIn("sensitive-secret", rendered)
                self.assertNotIn("signature-value", rendered)
                self.assertTrue(connection.closed)

    async def test_subscription_timeout_closes_connection(self) -> None:
        connection = Connection([])
        transport = spot_transport(connection, timeout=0.01)

        with self.assertRaisesRegex(ExecutionTransportError, "timed out"):
            async with transport.connect():
                self.fail("handshake must time out")

        self.assertTrue(connection.closed)

    async def test_credential_provider_error_is_redacted(self) -> None:
        transport = BinanceSpotPrivateStreamTransport(
            product=BinanceProduct.SPOT,
            account_id=AccountId("testnet"),
            base_url="wss://ws-api.test",
            credential_provider=FailingCredentials(),
            connector=Connector(Connection([])),
            timestamp_ms=lambda: 1,
        )

        with self.assertRaises(ExecutionTransportError) as caught:
            async with transport.connect():
                self.fail("authorization must fail")

        rendered = str(caught.exception)
        self.assertNotIn("sensitive-api-key", rendered)
        self.assertNotIn("sensitive-secret", rendered)


class FuturesPrivateTransportTests(IsolatedAsyncioTestCase):
    async def test_owns_lease_uri_connection_renewal_and_close(self) -> None:
        connection = Connection([b'{"e":"ORDER_TRADE_UPDATE"}'])
        connector = Connector(connection)
        control = Control(BinanceProduct.USD_M)

        async def immediate_sleep(_: float) -> None:
            await asyncio.sleep(0)

        transport = BinanceFuturesPrivateStreamTransport(
            product=BinanceProduct.USD_M,
            account_id=AccountId("testnet"),
            base_url="wss://fstream.test",
            control=control,  # type: ignore[arg-type]
            connector=connector,
            keepalive_interval_seconds=1,
            operation_timeout_seconds=0.1,
            sleep=immediate_sleep,
        )

        async with transport.connect() as stream:
            self.assertEqual(
                await anext(stream),
                b'{"e":"ORDER_TRADE_UPDATE"}',
            )
            await asyncio.sleep(0)

        self.assertEqual(control.calls[0], "open")
        self.assertIn("keepalive", control.calls)
        self.assertEqual(control.calls[-1], "close")
        self.assertEqual(
            connector.uris,
            ["wss://fstream.test/ws/secret-listen-key"],
        )
        self.assertTrue(connection.closed)
        rendered = repr(transport)
        self.assertNotIn("secret-listen-key", rendered)

    async def test_renewal_failure_interrupts_receive_and_cleans_up(self) -> None:
        secret = "secret-listen-key"
        connection = Connection([])
        control = Control(
            BinanceProduct.COIN_M,
            keepalive_error=RuntimeError(secret),
        )

        async def immediate_sleep(_: float) -> None:
            await asyncio.sleep(0)

        transport = BinanceFuturesPrivateStreamTransport(
            product=BinanceProduct.COIN_M,
            account_id=AccountId("testnet"),
            base_url="wss://dstream.test",
            control=control,  # type: ignore[arg-type]
            connector=Connector(connection),
            keepalive_interval_seconds=1,
            operation_timeout_seconds=0.1,
            sleep=immediate_sleep,
        )

        with self.assertRaises(ExecutionTransportError) as caught:
            async with transport.connect() as stream:
                await anext(stream)

        self.assertNotIn(secret, str(caught.exception))
        self.assertTrue(connection.closed)
        self.assertEqual(control.calls[-1], "close")

    async def test_cancellation_closes_connection_and_lease(self) -> None:
        connection = Connection([])
        control = Control(BinanceProduct.USD_M)
        transport = BinanceFuturesPrivateStreamTransport(
            product=BinanceProduct.USD_M,
            account_id=AccountId("testnet"),
            base_url="wss://fstream.test",
            control=control,  # type: ignore[arg-type]
            connector=Connector(connection),
            operation_timeout_seconds=0.1,
        )

        entered = asyncio.Event()

        async def consume() -> None:
            async with transport.connect() as stream:
                entered.set()
                await anext(stream)

        task = asyncio.create_task(consume())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(connection.closed)
        self.assertEqual(control.calls[-1], "close")

    async def test_connection_failure_closes_lease_without_leaking_key(
        self,
    ) -> None:
        secret = "secret-listen-key"
        control = Control(BinanceProduct.USD_M)
        transport = BinanceFuturesPrivateStreamTransport(
            product=BinanceProduct.USD_M,
            account_id=AccountId("testnet"),
            base_url="wss://fstream.test",
            control=control,  # type: ignore[arg-type]
            connector=Connector(
                Connection([]),
                enter_error=RuntimeError(secret),
            ),
            operation_timeout_seconds=0.1,
        )

        with self.assertRaises(ExecutionTransportError) as caught:
            async with transport.connect():
                self.fail("connection must fail")

        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(control.calls, ["open", "close"])


class PrivateTransportValidationTests(TestCase):
    def test_products_urls_and_timeouts_are_strict(self) -> None:
        connection = Connection([])
        credentials = Credentials(
            BinanceCredentials(api_key="key", secret="secret")
        )
        with self.assertRaisesRegex(ValueError, "Spot"):
            BinanceSpotPrivateStreamTransport(
                product=BinanceProduct.USD_M,
                account_id=AccountId("test"),
                base_url="wss://spot.test",
                credential_provider=credentials,
                connector=Connector(connection),
                timestamp_ms=lambda: 1,
            )
        with self.assertRaisesRegex(ValueError, "wss"):
            BinanceSpotPrivateStreamTransport(
                product=BinanceProduct.SPOT,
                account_id=AccountId("test"),
                base_url="https://spot.test",
                credential_provider=credentials,
                connector=Connector(connection),
                timestamp_ms=lambda: 1,
            )
        with self.assertRaisesRegex(ValueError, "timeout"):
            spot_transport(connection, timeout=0)
        with self.assertRaisesRegex(ValueError, "finite"):
            spot_transport(connection, timeout=float("nan"))
        with self.assertRaisesRegex(ValueError, "finite"):
            spot_transport(connection, timeout=True)
        with self.assertRaisesRegex(ValueError, "credential-free"):
            BinanceSpotPrivateStreamTransport(
                product=BinanceProduct.SPOT,
                account_id=AccountId("test"),
                base_url="wss://key@spot.test",
                credential_provider=credentials,
                connector=Connector(connection),
                timestamp_ms=lambda: 1,
            )
        with self.assertRaisesRegex(ValueError, "recv_window"):
            BinanceSpotPrivateStreamTransport(
                product=BinanceProduct.SPOT,
                account_id=AccountId("test"),
                base_url="wss://spot.test",
                credential_provider=credentials,
                connector=Connector(connection),
                timestamp_ms=lambda: 1,
                recv_window_ms=True,
            )
        with self.assertRaisesRegex(ValueError, "products must match"):
            BinanceFuturesPrivateStreamTransport(
                product=BinanceProduct.COIN_M,
                account_id=AccountId("test"),
                base_url="wss://dstream.test",
                control=Control(BinanceProduct.USD_M),  # type: ignore[arg-type]
                connector=Connector(connection),
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
