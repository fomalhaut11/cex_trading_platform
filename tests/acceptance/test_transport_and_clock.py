from __future__ import annotations

import asyncio
import ssl
from unittest import IsolatedAsyncioTestCase

from cex_quant.core import MonotonicNanos, UnixNanos
from cex_quant.execution import AsyncioBinanceHttpTransport
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.observability import ClockHealthMonitor, HealthStatus
from cex_quant.runtime import (
    BinanceEnvironment,
    BinanceEnvironmentConfig,
    BinanceServerTimeAdapter,
)


class ManualClock:
    def __init__(self) -> None:
        self.wall_ns = 1_000_000_000
        self.monotonic_ns = 100

    def wall_time_ns(self) -> UnixNanos:
        return UnixNanos(self.wall_ns)

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(self.monotonic_ns)


class Writer:
    def __init__(self) -> None:
        self.request = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.request.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class ServerTimeOpener:
    def __init__(self, clock: ManualClock) -> None:
        self.clock = clock
        self.hosts: list[str] = []
        self.writers: list[Writer] = []

    async def __call__(
        self,
        host: str,
        port: int,
        ssl_context: ssl.SSLContext,
        server_hostname: str,
    ) -> tuple[asyncio.StreamReader, Writer]:
        del port, ssl_context
        self.hosts.append(host)
        if server_hostname != host:
            raise AssertionError("TLS hostname must match the selected endpoint")
        self.clock.wall_ns += 2_000_000
        self.clock.monotonic_ns += 2_000_000
        body = b'{"serverTime":1001}'
        reader = asyncio.StreamReader()
        reader.feed_data(
            b"HTTP/1.1 200 OK\r\nContent-Length: "
            + str(len(body)).encode("ascii")
            + b"\r\n\r\n"
            + body
        )
        reader.feed_eof()
        writer = Writer()
        self.writers.append(writer)
        return reader, writer


class TransportAndClockAcceptanceTests(IsolatedAsyncioTestCase):
    async def test_testnet_profiles_drive_all_public_clock_probes(self) -> None:
        expected = {
            BinanceProduct.SPOT: (
                "testnet.binance.vision",
                b"GET /api/v3/time HTTP/1.1",
            ),
            BinanceProduct.USD_M: (
                "demo-fapi.binance.com",
                b"GET /fapi/v1/time HTTP/1.1",
            ),
            BinanceProduct.COIN_M: (
                "demo-dapi.binance.com",
                b"GET /dapi/v1/time HTTP/1.1",
            ),
        }
        for product, (host, request_line) in expected.items():
            with self.subTest(product=product):
                config = BinanceEnvironmentConfig()
                self.assertIs(
                    config.environment,
                    BinanceEnvironment.TESTNET,
                )
                clock = ManualClock()
                opener = ServerTimeOpener(clock)
                transport = AsyncioBinanceHttpTransport(
                    rest_base_url=lambda selected, profile=config: (
                        profile.endpoints_for(selected).rest_base_url
                    ),
                    connection_opener=opener,
                )
                monitor = ClockHealthMonitor(
                    venue=f"BINANCE:{product.value}",
                    clock=clock,
                )
                adapter = BinanceServerTimeAdapter(
                    product=product,
                    transport=transport,
                    monitor=monitor,
                )

                sample = await adapter.probe()

                self.assertEqual(opener.hosts, [host])
                self.assertIn(request_line, opener.writers[0].request)
                self.assertTrue(opener.writers[0].closed)
                self.assertEqual(sample.offset_ns, 0)
                self.assertEqual(
                    monitor.health().status,
                    HealthStatus.HEALTHY,
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
