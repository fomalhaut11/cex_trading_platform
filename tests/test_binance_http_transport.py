from __future__ import annotations

import asyncio
import ssl
from collections.abc import Callable
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.execution.adapters.binance import BinanceProduct
from cex_quant.execution.adapters.binance_authenticated import (
    BinanceHttpRequest,
    BinanceHttpTransportFailure,
)
from cex_quant.execution.adapters.binance_http_transport import (
    AsyncioBinanceHttpTransport,
    BinanceHttpTimeouts,
)


class FakeWriter:
    def __init__(
        self,
        *,
        drain_failure: Exception | None = None,
    ) -> None:
        self.data = bytearray()
        self.drain_failure = drain_failure
        self.closed = False

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        if self.drain_failure is not None:
            raise self.drain_failure

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class FakeOpener:
    def __init__(
        self,
        response: bytes = b"",
        *,
        failure: Exception | None = None,
        writer: FakeWriter | None = None,
    ) -> None:
        self.response = response
        self.failure = failure
        self.writer = writer or FakeWriter()
        self.calls: list[tuple[str, int, ssl.SSLContext, str]] = []

    async def __call__(
        self,
        host: str,
        port: int,
        ssl_context: ssl.SSLContext,
        server_hostname: str,
    ) -> tuple[asyncio.StreamReader, FakeWriter]:
        self.calls.append((host, port, ssl_context, server_hostname))
        if self.failure is not None:
            raise self.failure
        reader = asyncio.StreamReader()
        reader.feed_data(self.response)
        reader.feed_eof()
        return reader, self.writer


def request(
    *,
    method: str = "GET",
    path: str = "/api/v3/order",
    query: str = "symbol=BTCUSDT&signature=sensitive-signature",
    headers: dict[str, str] | None = None,
) -> BinanceHttpRequest:
    return BinanceHttpRequest(
        method=method,
        path=path,
        query=query,
        headers=headers or {"X-MBX-APIKEY": "sensitive-api-key"},
    )


def response(
    body: bytes,
    *,
    status: int = 200,
    extra_headers: bytes = b"",
) -> bytes:
    return (
        f"HTTP/1.1 {status} Result\r\n".encode()
        + f"Content-Length: {len(body)}\r\n".encode()
        + extra_headers
        + b"\r\n"
        + body
    )


class AsyncioBinanceHttpTransportTests(IsolatedAsyncioTestCase):
    def build(
        self,
        opener: FakeOpener | Callable[..., object],
        *,
        resolver: Callable[[BinanceProduct], str] | None = None,
        max_body: int = 1024,
        timeouts: BinanceHttpTimeouts | None = None,
    ) -> AsyncioBinanceHttpTransport:
        return AsyncioBinanceHttpTransport(
            rest_base_url=resolver
            or (
                lambda product: {
                    BinanceProduct.SPOT: "https://spot.test:8443",
                    BinanceProduct.USD_M: "https://usd-m.test",
                    BinanceProduct.COIN_M: "https://coin-m.test",
                }[product]
            ),
            connection_opener=opener,  # type: ignore[arg-type]
            max_response_body_bytes=max_body,
            timeouts=timeouts or BinanceHttpTimeouts(),
        )

    async def test_selects_product_endpoint_and_sends_safe_request(self) -> None:
        opener = FakeOpener(response(b'{"orderId":1}'))
        transport = self.build(opener)

        result = await transport.send(BinanceProduct.SPOT, request())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, b'{"orderId":1}')
        self.assertEqual(opener.calls[0][0:2], ("spot.test", 8443))
        self.assertEqual(opener.calls[0][3], "spot.test")
        transmitted = bytes(opener.writer.data)
        self.assertIn(
            b"GET /api/v3/order?symbol=BTCUSDT&signature="
            b"sensitive-signature HTTP/1.1\r\n",
            transmitted,
        )
        self.assertIn(b"Host: spot.test:8443\r\n", transmitted)
        self.assertIn(b"X-MBX-APIKEY: sensitive-api-key\r\n", transmitted)
        self.assertTrue(opener.writer.closed)

    async def test_reads_chunked_response_within_bound(self) -> None:
        opener = FakeOpener(
            b"HTTP/1.1 400 Bad\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"4\r\nfail\r\n3\r\nure\r\n0\r\n\r\n"
        )

        result = await self.build(opener).send(
            BinanceProduct.USD_M,
            request(method="POST", path="/fapi/v1/order"),
        )

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.body, b"failure")
        self.assertEqual(opener.calls[0][0], "usd-m.test")

    async def test_connect_failure_is_classified_not_sent_and_redacted(
        self,
    ) -> None:
        opener = FakeOpener(
            failure=OSError(
                "sensitive-api-key sensitive-signature should not escape"
            )
        )

        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await self.build(opener).send(BinanceProduct.SPOT, request())

        self.assertFalse(caught.exception.request_sent)
        self.assertNotIn("sensitive", str(caught.exception))

    async def test_failure_after_write_is_classified_sent_and_redacted(
        self,
    ) -> None:
        writer = FakeWriter(
            drain_failure=OSError("sensitive-api-key should not escape")
        )
        opener = FakeOpener(writer=writer)

        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await self.build(opener).send(BinanceProduct.SPOT, request())

        self.assertTrue(caught.exception.request_sent)
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertTrue(writer.closed)

    async def test_read_timeout_is_bounded_and_classified_sent(self) -> None:
        started = asyncio.Event()

        async def stalled_opener(
            host: str,
            port: int,
            context: ssl.SSLContext,
            server_hostname: str,
        ) -> tuple[asyncio.StreamReader, FakeWriter]:
            del host, port, context, server_hostname
            reader = asyncio.StreamReader()
            started.set()
            return reader, FakeWriter()

        transport = self.build(
            stalled_opener,
            timeouts=BinanceHttpTimeouts(
                connect_seconds=0.1,
                read_seconds=0.01,
                total_seconds=0.2,
            ),
        )

        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await transport.send(BinanceProduct.SPOT, request())

        self.assertTrue(started.is_set())
        self.assertTrue(caught.exception.request_sent)
        self.assertIn("timed out", str(caught.exception))

    async def test_connect_timeout_is_bounded_and_not_sent(self) -> None:
        async def stalled_opener(
            host: str,
            port: int,
            context: ssl.SSLContext,
            server_hostname: str,
        ) -> tuple[asyncio.StreamReader, FakeWriter]:
            del host, port, context, server_hostname
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        transport = self.build(
            stalled_opener,
            timeouts=BinanceHttpTimeouts(
                connect_seconds=0.01,
                read_seconds=0.1,
                total_seconds=0.2,
            ),
        )

        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await transport.send(BinanceProduct.SPOT, request())

        self.assertFalse(caught.exception.request_sent)
        self.assertIn("timed out", str(caught.exception))

    async def test_total_timeout_bounds_send_and_cleanup(self) -> None:
        class StalledWriter(FakeWriter):
            async def drain(self) -> None:
                await asyncio.Event().wait()

            async def wait_closed(self) -> None:
                await asyncio.Event().wait()

        writer = StalledWriter()
        opener = FakeOpener(writer=writer)
        transport = self.build(
            opener,
            timeouts=BinanceHttpTimeouts(
                connect_seconds=0.01,
                read_seconds=1.0,
                total_seconds=0.03,
            ),
        )
        loop = asyncio.get_running_loop()
        started = loop.time()

        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await transport.send(BinanceProduct.SPOT, request())

        self.assertTrue(caught.exception.request_sent)
        self.assertIn("total timeout", str(caught.exception))
        self.assertLess(loop.time() - started, 0.2)
        self.assertTrue(writer.closed)

    async def test_rejects_oversized_body_after_send(self) -> None:
        opener = FakeOpener(response(b"12345"))

        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await self.build(opener, max_body=4).send(
                BinanceProduct.SPOT, request()
            )

        self.assertTrue(caught.exception.request_sent)
        self.assertIn("exceeds", str(caught.exception))
        self.assertNotIn("12345", str(caught.exception))

    async def test_rejects_unsafe_request_before_opening_connection(self) -> None:
        unsafe = (
            request(method="PATCH"),
            request(path="//attacker.test/order"),
            request(path="/api/v3/order with space"),
            request(query="x=1\r\nX-Evil: yes"),
            request(query="x=unencoded value"),
            request(headers={"Host": "attacker.test"}),
            request(headers={"X-Key": "value\r\nX-Evil: yes"}),
        )
        for item in unsafe:
            with self.subTest(request=item):
                opener = FakeOpener(response(b""))
                with self.assertRaises(ValueError):
                    await self.build(opener).send(BinanceProduct.SPOT, item)
                self.assertEqual(opener.calls, [])

    async def test_rejects_unsafe_endpoint_without_echoing_it(self) -> None:
        for endpoint in (
            "http://spot.test",
            "https://key:secret@spot.test",
            "https://spot.test/base",
            "https://spot.test?signature=sensitive",
        ):
            with self.subTest(endpoint=endpoint):
                opener = FakeOpener()
                transport = self.build(
                    opener,
                    resolver=lambda product, value=endpoint: value,
                )
                with self.assertRaises(ValueError) as caught:
                    await transport.send(BinanceProduct.SPOT, request())
                self.assertNotIn(endpoint, str(caught.exception))
                self.assertEqual(opener.calls, [])

    async def test_endpoint_resolution_failure_is_not_sent_or_echoed(
        self,
    ) -> None:
        def failing_resolver(product: BinanceProduct) -> str:
            del product
            raise RuntimeError("sensitive-api-key")

        opener = FakeOpener()
        with self.assertRaises(BinanceHttpTransportFailure) as caught:
            await self.build(opener, resolver=failing_resolver).send(
                BinanceProduct.SPOT,
                request(),
            )

        self.assertFalse(caught.exception.request_sent)
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(opener.calls, [])


class BinanceHttpTimeoutTests(TestCase):
    def test_validates_all_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "connect_seconds"):
            BinanceHttpTimeouts(connect_seconds=0)
        with self.assertRaisesRegex(ValueError, "read_seconds"):
            BinanceHttpTimeouts(read_seconds=True)
        with self.assertRaisesRegex(ValueError, "read_seconds"):
            BinanceHttpTimeouts(read_seconds=float("nan"))
        with self.assertRaisesRegex(ValueError, "total_seconds"):
            BinanceHttpTimeouts(total_seconds=float("inf"))
        with self.assertRaisesRegex(ValueError, "at least"):
            BinanceHttpTimeouts(connect_seconds=2, total_seconds=1)
