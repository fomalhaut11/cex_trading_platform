from __future__ import annotations

import asyncio
from types import TracebackType
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import ClientOrderId, UnixNanos
from cex_quant.execution import (
    BinancePrivateOrderStreamProcessor,
    PrivateOrderStreamSession,
    PrivateOrderStreamSupervisor,
)
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.oms import (
    OrderReconciliationSnapshot,
    OrderView,
    ReconciliationResult,
    ReconciliationSource,
)
from cex_quant.runtime import (
    BinanceEnvironment,
    BinanceEnvironmentConfig,
    PrivateStreamApplication,
    PrivateStreamApplicationState,
    StartupOrderReconciliationCoordinator,
)


class EmptyOms:
    def reconciliation_candidates(self) -> tuple[OrderView, ...]:
        return ()

    def reconcile(
        self,
        snapshot: OrderReconciliationSnapshot,
    ) -> ReconciliationResult:
        raise AssertionError(f"unexpected stream snapshot: {snapshot!r}")

    def reconcile_not_found(
        self,
        client_order_id: ClientOrderId,
        *,
        source: ReconciliationSource,
        observed_at_ns: UnixNanos,
    ) -> ReconciliationResult:
        raise AssertionError(
            f"unexpected not-found result: {client_order_id!r}, "
            f"{source!r}, {observed_at_ns!r}"
        )


class NoQueryGateway:
    async def query_order(
        self,
        command: object,
    ) -> OrderReconciliationSnapshot | None:
        raise AssertionError(f"unexpected REST query: {command!r}")


class BlockingConnection:
    def __init__(self) -> None:
        self._release = asyncio.Event()
        self.opened = asyncio.Event()
        self.closed = False

    def __aiter__(self) -> BlockingConnection:
        return self

    async def __anext__(self) -> bytes:
        await self._release.wait()
        raise StopAsyncIteration

    async def close(self) -> None:
        self.closed = True
        self._release.set()


class ConnectionContext:
    def __init__(self, connection: BlockingConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> BlockingConnection:
        self._connection.opened.set()
        return self._connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._connection.close()


class BlockingTransport:
    def __init__(self, connection: BlockingConnection) -> None:
        self._connection = connection

    def connect(self) -> ConnectionContext:
        return ConnectionContext(self._connection)


class BinanceEnvironmentAcceptanceTests(TestCase):
    def test_testnet_is_default_and_production_requires_acknowledgement(
        self,
    ) -> None:
        testnet = BinanceEnvironmentConfig()

        self.assertIs(testnet.environment, BinanceEnvironment.TESTNET)
        self.assertTrue(testnet.spot.rest_base_url.startswith("https://testnet"))
        self.assertIn("demo-fapi", testnet.usd_m.rest_base_url)
        self.assertIn("demo-dapi", testnet.coin_m.rest_base_url)
        with self.assertRaisesRegex(ValueError, "allow_production=True"):
            BinanceEnvironmentConfig(
                environment=BinanceEnvironment.PRODUCTION
            )


class PrivateStreamSupervisionAcceptanceTests(IsolatedAsyncioTestCase):
    async def test_stream_first_reconciliation_opens_and_closes_gate(
        self,
    ) -> None:
        connection = BlockingConnection()
        coordinator = StartupOrderReconciliationCoordinator(
            oms=EmptyOms(),
            gateway=NoQueryGateway(),  # type: ignore[arg-type]
            now_ns=lambda: UnixNanos(1),
        )
        session = PrivateOrderStreamSession(
            processor=BinancePrivateOrderStreamProcessor(
                product=BinanceProduct.SPOT
            ),
            on_snapshot=coordinator.on_stream_snapshot,
        )

        async def transport_factory() -> BlockingTransport:
            return BlockingTransport(connection)

        application = PrivateStreamApplication(
            supervisor=PrivateOrderStreamSupervisor(
                session=session,
                transport_factory=transport_factory,
            ),
            reconciliation=coordinator,
            stop_timeout_seconds=1,
        )

        started = await application.start()

        self.assertTrue(started.ready)
        self.assertEqual(
            started.state,
            PrivateStreamApplicationState.READY,
        )
        await connection.opened.wait()
        stopped = await application.stop()
        self.assertEqual(
            stopped.state,
            PrivateStreamApplicationState.STOPPED,
        )
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    import unittest

    unittest.main()
