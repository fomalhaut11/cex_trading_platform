from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import TracebackType
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import AccountId, MonotonicNanos
from cex_quant.execution import (
    BinanceCredentials,
    BinanceFuturesUserStreamControlAdapter,
    BinanceHttpRequest,
    BinanceHttpResponse,
    BinanceOrderNormalizationError,
    BinancePrivateOrderStreamProcessor,
    BinancePrivateStreamDisposition,
    BinanceUserStreamLeaseExpiredError,
    PrivateOrderStreamSession,
    PrivateOrderStreamSupervisor,
    build_spot_user_stream_subscription,
    canonical_query,
    parse_spot_user_stream_subscription,
)
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.market_data.adapters.binance import ConnectionState
from cex_quant.oms import OrderReconciliationSnapshot, OrderStatus

FIXTURES = Path(__file__).parent / "fixtures" / "binance"


class BinancePrivateStreamProtocolTests(TestCase):
    def test_builds_current_spot_signature_subscription(self) -> None:
        credentials = BinanceCredentials(
            api_key="test-api-key",
            secret="test-secret",
        )

        encoded = build_spot_user_stream_subscription(
            credentials,
            request_id="subscription-1",
            timestamp_ms=1_700_000_000_123,
        )
        payload = json.loads(encoded)
        parameters = payload["params"]
        signature = parameters.pop("signature")

        self.assertEqual(
            payload["method"],
            "userDataStream.subscribe.signature",
        )
        self.assertEqual(
            signature,
            credentials.sign(canonical_query(parameters)),
        )
        self.assertNotIn(b"test-secret", encoded)

    def test_parses_subscription_response_and_rejects_identity_mismatch(
        self,
    ) -> None:
        response = json.dumps(
            {
                "id": "subscription-1",
                "status": 200,
                "result": {"subscriptionId": 7},
            }
        )

        self.assertEqual(
            parse_spot_user_stream_subscription(
                response,
                expected_request_id="subscription-1",
            ),
            7,
        )
        with self.assertRaises(BinanceOrderNormalizationError):
            parse_spot_user_stream_subscription(
                response,
                expected_request_id="other",
            )

    def test_classifies_order_account_and_rotation_events(self) -> None:
        processor = BinancePrivateOrderStreamProcessor(
            product=BinanceProduct.SPOT
        )

        order = processor.process(
            (FIXTURES / "spot_execution_report.json").read_bytes()
        )
        ignored = processor.process(
            b'{"event":{"e":"outboundAccountPosition","E":1}}'
        )
        rotate = processor.process(
            b'{"event":{"e":"serverShutdown","E":2}}'
        )

        self.assertEqual(
            order.disposition,
            BinancePrivateStreamDisposition.ORDER_UPDATE,
        )
        self.assertIsNotNone(order.snapshot)
        self.assertEqual(order.snapshot.status, OrderStatus.FILLED)  # type: ignore[union-attr]
        self.assertEqual(
            ignored.disposition,
            BinancePrivateStreamDisposition.IGNORED,
        )
        self.assertEqual(
            rotate.disposition,
            BinancePrivateStreamDisposition.RECONNECT_REQUIRED,
        )

    def test_futures_listen_key_expiry_requires_reconnect(self) -> None:
        processor = BinancePrivateOrderStreamProcessor(
            product=BinanceProduct.USD_M
        )

        message = processor.process(
            b'{"e":"listenKeyExpired","E":1,"listenKey":"redacted"}'
        )

        self.assertEqual(
            message.disposition,
            BinancePrivateStreamDisposition.RECONNECT_REQUIRED,
        )


class StaticCredentials:
    def __init__(self, credentials: BinanceCredentials) -> None:
        self.credentials = credentials

    def credentials_for(self, account_id: AccountId) -> BinanceCredentials:
        del account_id
        return self.credentials


class CapturingHttpTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[BinanceProduct, BinanceHttpRequest]] = []
        self.responses: list[BinanceHttpResponse] = []

    async def send(
        self,
        product: BinanceProduct,
        request: BinanceHttpRequest,
    ) -> BinanceHttpResponse:
        self.calls.append((product, request))
        return self.responses.pop(0)


class BinanceFuturesStreamControlTests(IsolatedAsyncioTestCase):
    async def test_creates_renews_and_closes_redacted_lease(self) -> None:
        transport = CapturingHttpTransport()
        transport.responses = [
            BinanceHttpResponse(
                status_code=200,
                body=b'{"listenKey":"super-secret-listen-key"}',
            ),
            BinanceHttpResponse(status_code=200, body=b"{}"),
            BinanceHttpResponse(status_code=200, body=b"{}"),
        ]
        adapter = BinanceFuturesUserStreamControlAdapter(
            product=BinanceProduct.USD_M,
            credential_provider=StaticCredentials(
                BinanceCredentials(api_key="api-key", secret="secret")
            ),
            transport=transport,
        )

        lease = await adapter.open(AccountId("testnet"))
        await adapter.keepalive(AccountId("testnet"), lease)
        await adapter.close(AccountId("testnet"), lease)

        self.assertNotIn("super-secret-listen-key", repr(lease))
        self.assertEqual(
            lease.websocket_uri("wss://fstream.binance.test"),
            "wss://fstream.binance.test/ws/super-secret-listen-key",
        )
        self.assertEqual(
            [request.method for _, request in transport.calls],
            ["POST", "PUT", "DELETE"],
        )
        self.assertTrue(
            all(
                request.path == "/fapi/v1/listenKey"
                and request.query == ""
                and request.headers["X-MBX-APIKEY"] == "api-key"
                for _, request in transport.calls
            )
        )

    async def test_control_error_is_typed(self) -> None:
        transport = CapturingHttpTransport()
        transport.responses = [
            BinanceHttpResponse(
                status_code=400,
                body=b'{"code":-1125,"msg":"listenKey missing"}',
            )
        ]
        adapter = BinanceFuturesUserStreamControlAdapter(
            product=BinanceProduct.COIN_M,
            credential_provider=StaticCredentials(
                BinanceCredentials(api_key="api-key", secret="secret")
            ),
            transport=transport,
        )

        with self.assertRaisesRegex(
            BinanceUserStreamLeaseExpiredError,
            "-1125",
        ):
            await adapter.open(AccountId("testnet"))


class FakeConnection:
    def __init__(
        self,
        messages: list[bytes],
        *,
        release: asyncio.Event | None = None,
    ) -> None:
        self._messages = messages
        self._release = release
        self._index = 0
        self.closed = False
        self.iteration_cancelled = False

    def __aiter__(self) -> FakeConnection:
        return self

    async def __anext__(self) -> bytes:
        if self._release is not None:
            try:
                await self._release.wait()
            except asyncio.CancelledError:
                self.iteration_cancelled = True
                raise
            self._release = None
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
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def connect(self) -> FakeContext:
        return FakeContext(self.connection)


class PrivateOrderStreamSessionTests(IsolatedAsyncioTestCase):
    async def test_session_renews_and_delivers_order_updates(self) -> None:
        release = asyncio.Event()
        connection = FakeConnection(
            [(FIXTURES / "usdm_order_trade_update.json").read_bytes()],
            release=release,
        )
        snapshots: list[OrderReconciliationSnapshot] = []
        renewals = 0

        async def on_snapshot(
            snapshot: OrderReconciliationSnapshot,
        ) -> None:
            snapshots.append(snapshot)

        async def keepalive() -> None:
            nonlocal renewals
            renewals += 1
            release.set()

        async def immediate_sleep(_: float) -> None:
            await asyncio.sleep(0)

        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.USD_M
            ),
            on_snapshot=on_snapshot,
            keepalive=keepalive,
            keepalive_interval_seconds=1,
            sleep=immediate_sleep,
        )

        await session.run_once(FakeTransport(connection))

        self.assertGreaterEqual(renewals, 1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(
            session.lifecycle.state,
            ConnectionState.RECONNECT_WAIT,
        )
        self.assertTrue(connection.closed)

    async def test_session_records_injected_monotonic_connection_time(
        self,
    ) -> None:
        release = asyncio.Event()
        connection = FakeConnection([], release=release)

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no snapshot expected")

        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.USD_M
            ),
            on_snapshot=on_snapshot,
            monotonic_now=lambda: MonotonicNanos(123_456_789),
        )

        task = asyncio.create_task(session.run_once(FakeTransport(connection)))
        while session.lifecycle.state is not ConnectionState.ACTIVE:
            await asyncio.sleep(0)

        self.assertEqual(session.lifecycle.connected_at_ns, 123_456_789)
        release.set()
        await task

    async def test_supervisor_recreates_transport_after_rotation(self) -> None:
        transports = [
            FakeTransport(
                FakeConnection([b'{"e":"serverShutdown","E":1}'])
            ),
            FakeTransport(
                FakeConnection([b'{"e":"ACCOUNT_UPDATE","E":2}'])
            ),
        ]
        created = 0
        delays: list[float] = []

        async def factory() -> FakeTransport:
            nonlocal created
            transport = transports[created]
            created += 1
            return transport

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no order update expected")

        async def record_sleep(delay: float) -> None:
            delays.append(delay)

        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.USD_M
            ),
            on_snapshot=on_snapshot,
        )
        supervisor = PrivateOrderStreamSupervisor(
            session=session,
            transport_factory=factory,
            sleep=record_sleep,
        )

        cycles = await supervisor.run(max_cycles=2)

        self.assertEqual(cycles, 2)
        self.assertEqual(created, 2)
        self.assertEqual(delays, [0.25])
        self.assertIsNone(supervisor.last_error)

    async def test_supervisor_backs_off_after_authorization_failure(
        self,
    ) -> None:
        attempts = 0
        delays: list[float] = []

        async def factory() -> FakeTransport:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("authorization unavailable")
            return FakeTransport(FakeConnection([]))

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no order update expected")

        async def record_sleep(delay: float) -> None:
            delays.append(delay)

        supervisor = PrivateOrderStreamSupervisor(
            session=PrivateOrderStreamSession(
                processor=BinancePrivateOrderStreamProcessor(
                    product=BinanceProduct.USD_M
                ),
                on_snapshot=on_snapshot,
            ),
            transport_factory=factory,
            sleep=record_sleep,
        )

        self.assertEqual(await supervisor.run(max_cycles=2), 2)
        self.assertEqual(attempts, 2)
        self.assertEqual(delays, [0.25])
        self.assertIsNone(supervisor.last_error)

    async def test_supervisor_uses_exponential_backoff_for_consecutive_failures(
        self,
    ) -> None:
        attempts = 0
        delays: list[float] = []

        async def factory() -> FakeTransport:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("authorization unavailable")

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no snapshot expected")

        async def record_sleep(delay: float) -> None:
            delays.append(delay)

        supervisor = PrivateOrderStreamSupervisor(
            session=PrivateOrderStreamSession(
                processor=BinancePrivateOrderStreamProcessor(
                    product=BinanceProduct.USD_M
                ),
                on_snapshot=on_snapshot,
            ),
            transport_factory=factory,
            sleep=record_sleep,
        )

        self.assertEqual(await supervisor.run(max_cycles=4), 4)
        self.assertEqual(attempts, 4)
        self.assertEqual(delays, [0.25, 0.5, 1.0])
        self.assertIsInstance(supervisor.last_error, RuntimeError)

    async def test_supervisor_backs_off_for_consecutive_session_failures(
        self,
    ) -> None:
        delays: list[float] = []

        async def factory() -> FakeTransport:
            return FakeTransport(FakeConnection([b"not-json"]))

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no snapshot expected")

        async def record_sleep(delay: float) -> None:
            delays.append(delay)

        supervisor = PrivateOrderStreamSupervisor(
            session=PrivateOrderStreamSession(
                processor=BinancePrivateOrderStreamProcessor(
                    product=BinanceProduct.USD_M
                ),
                on_snapshot=on_snapshot,
            ),
            transport_factory=factory,
            sleep=record_sleep,
        )

        self.assertEqual(await supervisor.run(max_cycles=3), 3)
        self.assertEqual(delays, [0.25, 0.5])
        self.assertIsInstance(
            supervisor.last_error,
            BinanceOrderNormalizationError,
        )

    async def test_stop_interrupts_active_connection_and_closes_it(
        self,
    ) -> None:
        release = asyncio.Event()
        connection = FakeConnection([], release=release)

        async def factory() -> FakeTransport:
            return FakeTransport(connection)

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no snapshot expected")

        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.USD_M
            ),
            on_snapshot=on_snapshot,
        )
        supervisor = PrivateOrderStreamSupervisor(
            session=session,
            transport_factory=factory,
        )

        task = asyncio.create_task(supervisor.run())
        while session.lifecycle.state is not ConnectionState.ACTIVE:
            await asyncio.sleep(0)
        supervisor.request_stop()

        self.assertEqual(await asyncio.wait_for(task, timeout=1), 1)
        self.assertTrue(connection.closed)
        self.assertTrue(connection.iteration_cancelled)
        self.assertEqual(session.lifecycle.state, ConnectionState.STOPPED)

    async def test_stop_interrupts_backoff_without_leaking_sleep_task(
        self,
    ) -> None:
        sleep_entered = asyncio.Event()
        sleep_cancelled = asyncio.Event()

        async def factory() -> FakeTransport:
            raise RuntimeError("authorization unavailable")

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no snapshot expected")

        async def blocking_sleep(_: float) -> None:
            sleep_entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                sleep_cancelled.set()
                raise

        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.USD_M
            ),
            on_snapshot=on_snapshot,
        )
        supervisor = PrivateOrderStreamSupervisor(
            session=session,
            transport_factory=factory,
            sleep=blocking_sleep,
        )

        task = asyncio.create_task(supervisor.run())
        await sleep_entered.wait()
        supervisor.request_stop()

        self.assertEqual(await asyncio.wait_for(task, timeout=1), 1)
        self.assertTrue(sleep_cancelled.is_set())
        self.assertEqual(session.lifecycle.state, ConnectionState.STOPPED)

    async def test_renewal_failure_ends_connection_fail_closed(self) -> None:
        connection = FakeConnection([], release=asyncio.Event())

        async def on_snapshot(_: OrderReconciliationSnapshot) -> None:
            self.fail("no snapshot expected")

        async def keepalive() -> None:
            raise RuntimeError("renewal failed")

        async def immediate_sleep(_: float) -> None:
            await asyncio.sleep(0)

        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.COIN_M
            ),
            on_snapshot=on_snapshot,
            keepalive=keepalive,
            keepalive_interval_seconds=1,
            sleep=immediate_sleep,
        )

        with self.assertRaisesRegex(RuntimeError, "renewal failed"):
            await session.run_once(FakeTransport(connection))

        self.assertEqual(
            session.lifecycle.state,
            ConnectionState.RECONNECT_WAIT,
        )
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    import unittest

    unittest.main()
