from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import FrozenInstanceError
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import MonotonicNanos, UnixNanos
from cex_quant.execution.adapters.binance import BinanceProduct
from cex_quant.execution.adapters.binance_authenticated import (
    BinanceHttpRequest,
    BinanceHttpResponse,
    BinanceHttpTransportFailure,
)
from cex_quant.observability.clock import ClockHealthMonitor
from cex_quant.runtime.binance_clock import (
    BinanceClockProbePolicy,
    BinanceClockProbeService,
    BinanceClockProbeState,
    BinanceServerTimeAdapter,
    BinanceServerTimeError,
)


class ManualClock:
    def __init__(self, *, wall_ns: int, monotonic_ns: int) -> None:
        self.wall_ns = wall_ns
        self.monotonic_ns = monotonic_ns

    def wall_time_ns(self) -> UnixNanos:
        return UnixNanos(self.wall_ns)

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(self.monotonic_ns)


class CapturingTransport:
    def __init__(self, outcomes: list[BinanceHttpResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.requests: list[tuple[BinanceProduct, BinanceHttpRequest]] = []

    async def send(
        self,
        product: BinanceProduct,
        request: BinanceHttpRequest,
    ) -> BinanceHttpResponse:
        self.requests.append((product, request))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class DelayedTransport(CapturingTransport):
    def __init__(self, response: BinanceHttpResponse) -> None:
        super().__init__([response])
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send(
        self,
        product: BinanceProduct,
        request: BinanceHttpRequest,
    ) -> BinanceHttpResponse:
        self.started.set()
        await self.release.wait()
        return await super().send(product, request)


def adapter(
    product: BinanceProduct,
    transport: CapturingTransport,
    clock: ManualClock,
    *,
    history_size: int = 32,
) -> BinanceServerTimeAdapter:
    return BinanceServerTimeAdapter(
        product=product,
        transport=transport,
        monitor=ClockHealthMonitor(
            venue=f"BINANCE:{product.value}",
            clock=clock,
            history_size=history_size,
        ),
    )


class BinanceServerTimeAdapterTests(IsolatedAsyncioTestCase):
    async def test_all_products_use_public_time_paths_and_midpoint(self) -> None:
        paths = {
            BinanceProduct.SPOT: "/api/v3/time",
            BinanceProduct.USD_M: "/fapi/v1/time",
            BinanceProduct.COIN_M: "/dapi/v1/time",
        }
        for product, path in paths.items():
            with self.subTest(product=product):
                clock = ManualClock(
                    wall_ns=1_000_000_000,
                    monotonic_ns=100,
                )
                transport = DelayedTransport(
                    BinanceHttpResponse(
                        status_code=200,
                        body=b'{"serverTime":1001}',
                    )
                )
                target = adapter(product, transport, clock)
                task = asyncio.create_task(target.probe())
                await transport.started.wait()
                clock.wall_ns = 1_002_000_000
                clock.monotonic_ns = 2_000_100
                transport.release.set()

                sample = await task

                sent_product, request = transport.requests[0]
                self.assertIs(sent_product, product)
                self.assertEqual(request.method, "GET")
                self.assertEqual(request.path, path)
                self.assertEqual(request.query, "")
                self.assertEqual(dict(request.headers), {})
                self.assertEqual(sample.offset_ns, 0)
                self.assertEqual(int(sample.rtt_ns), 2_000_000)
                self.assertEqual(int(sample.venue_time_ns), 1_001_000_000)

    async def test_rejects_status_json_shape_and_server_time(self) -> None:
        outcomes = (
            BinanceHttpResponse(status_code=503, body=b'{"secret":"value"}'),
            BinanceHttpResponse(status_code=200, body=b"not-json"),
            BinanceHttpResponse(status_code=200, body=b"[]"),
            BinanceHttpResponse(
                status_code=200,
                body=b'{"serverTime":true}',
            ),
            BinanceHttpResponse(
                status_code=200,
                body=b'{"serverTime":-1}',
            ),
        )
        expected = (
            "HTTP 503",
            "not valid JSON",
            "must be an object",
            "invalid serverTime",
            "invalid serverTime",
        )
        for outcome, message in zip(outcomes, expected, strict=True):
            with self.subTest(message=message):
                target = adapter(
                    BinanceProduct.SPOT,
                    CapturingTransport([outcome]),
                    ManualClock(wall_ns=0, monotonic_ns=0),
                )
                with self.assertRaisesRegex(
                    BinanceServerTimeError,
                    message,
                ):
                    await target.probe()

    async def test_transport_exception_is_sanitized(self) -> None:
        secret = "do-not-leak-this-token"
        target = adapter(
            BinanceProduct.USD_M,
            CapturingTransport(
                [
                    BinanceHttpTransportFailure(
                        f"failed with {secret}",
                        request_sent=False,
                    )
                ]
            ),
            ManualClock(wall_ns=0, monotonic_ns=0),
        )

        with self.assertRaises(BinanceServerTimeError) as captured:
            await target.probe()

        self.assertNotIn(secret, str(captured.exception))
        self.assertEqual(
            str(captured.exception),
            "Binance server-time transport failed",
        )


class BinanceClockProbePolicyTests(TestCase):
    def test_policy_is_validated_and_backoff_is_capped(self) -> None:
        policy = BinanceClockProbePolicy(
            base_backoff_seconds=0.25,
            max_backoff_seconds=1.0,
        )
        self.assertEqual(
            [policy.failure_delay(value) for value in range(1, 5)],
            [0.25, 0.5, 1.0, 1.0],
        )
        self.assertEqual(policy.failure_delay(1_000_000), 1.0)
        with self.assertRaises(ValueError):
            BinanceClockProbePolicy(interval_seconds=0)
        with self.assertRaises(ValueError):
            BinanceClockProbePolicy(history_size=0)
        with self.assertRaises(ValueError):
            BinanceClockProbePolicy(interval_seconds=True)
        with self.assertRaises(ValueError):
            BinanceClockProbePolicy(backoff_multiplier=True)
        with self.assertRaises(ValueError):
            BinanceClockProbePolicy(history_size=True)
        with self.assertRaises(ValueError):
            policy.failure_delay(0)
        with self.assertRaises(ValueError):
            policy.failure_delay(True)


class BinanceClockProbeServiceTests(IsolatedAsyncioTestCase):
    async def test_probe_limit_rejects_bool(self) -> None:
        service = BinanceClockProbeService(
            adapter=adapter(
                BinanceProduct.SPOT,
                CapturingTransport([]),
                ManualClock(wall_ns=0, monotonic_ns=0),
            )
        )

        with self.assertRaisesRegex(ValueError, "max_probes"):
            await service.run(max_probes=True)

    async def test_periodic_success_uses_interval_and_bounded_history(
        self,
    ) -> None:
        clock = ManualClock(wall_ns=1_000_000_000, monotonic_ns=0)
        transport = CapturingTransport(
            [
                BinanceHttpResponse(
                    status_code=200,
                    body=b'{"serverTime":1000}',
                )
                for _ in range(3)
            ]
        )
        delays: list[float] = []

        async def advance(delay: float) -> None:
            delays.append(delay)
            clock.wall_ns += 1_000_000
            clock.monotonic_ns += 1_000_000

        service = BinanceClockProbeService(
            adapter=adapter(
                BinanceProduct.SPOT,
                transport,
                clock,
                history_size=2,
            ),
            policy=BinanceClockProbePolicy(
                interval_seconds=5,
                history_size=2,
            ),
            sleep=advance,
        )

        self.assertEqual(await service.run(max_probes=3), 3)
        snapshot = service.snapshot()

        self.assertEqual(delays, [5, 5])
        self.assertEqual(snapshot.state, BinanceClockProbeState.STOPPED)
        self.assertEqual(snapshot.successes, 3)
        self.assertEqual(snapshot.failures, 0)
        self.assertEqual(
            [record.sequence for record in snapshot.records],
            [2, 3],
        )
        with self.assertRaises(FrozenInstanceError):
            snapshot.probes = 4  # type: ignore[misc]

    async def test_failures_back_off_and_success_resets_counter(self) -> None:
        clock = ManualClock(wall_ns=1_000_000_000, monotonic_ns=0)
        secret = "private-error-text"
        transport = CapturingTransport(
            [
                BinanceHttpTransportFailure(
                    secret,
                    request_sent=False,
                ),
                BinanceHttpResponse(status_code=503, body=b"{}"),
                BinanceHttpResponse(
                    status_code=200,
                    body=b'{"serverTime":1000}',
                ),
            ]
        )
        delays: list[float] = []

        async def advance(delay: float) -> None:
            delays.append(delay)
            clock.wall_ns += 1
            clock.monotonic_ns += 1

        service = BinanceClockProbeService(
            adapter=adapter(BinanceProduct.COIN_M, transport, clock),
            policy=BinanceClockProbePolicy(interval_seconds=7),
            sleep=advance,
        )

        await service.run(max_probes=3)
        snapshot = service.snapshot()

        self.assertEqual(delays, [0.25, 0.5])
        self.assertEqual(snapshot.successes, 1)
        self.assertEqual(snapshot.failures, 2)
        self.assertEqual(snapshot.consecutive_failures, 0)
        self.assertIsNone(snapshot.last_error)
        self.assertNotIn(
            secret,
            " ".join(record.error or "" for record in snapshot.records),
        )

    async def test_stop_interrupts_backoff_and_active_probe(self) -> None:
        for stop_during_probe in (False, True):
            with self.subTest(stop_during_probe=stop_during_probe):
                clock = ManualClock(wall_ns=0, monotonic_ns=0)
                sleep_started = asyncio.Event()
                sleep_cancelled = asyncio.Event()
                blocking_sleep = make_blocking_sleep(
                    sleep_started,
                    sleep_cancelled,
                )

                if stop_during_probe:
                    transport = BlockingTransport()
                else:
                    transport = CapturingTransport(
                        [
                            BinanceHttpResponse(
                                status_code=503,
                                body=b"{}",
                            )
                        ]
                    )
                service = BinanceClockProbeService(
                    adapter=BinanceServerTimeAdapter(
                        product=BinanceProduct.SPOT,
                        transport=transport,
                        monitor=ClockHealthMonitor(
                            venue="BINANCE:spot",
                            clock=clock,
                        ),
                    ),
                    sleep=blocking_sleep,
                )

                task = asyncio.create_task(service.run())
                if stop_during_probe:
                    await transport.started.wait()
                else:
                    await sleep_started.wait()
                service.request_stop()

                self.assertEqual(
                    await asyncio.wait_for(task, timeout=1),
                    1,
                )
                self.assertEqual(
                    service.state,
                    BinanceClockProbeState.STOPPED,
                )
                if stop_during_probe:
                    self.assertTrue(transport.cancelled.is_set())
                else:
                    self.assertTrue(sleep_cancelled.is_set())


class BlockingTransport:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def send(
        self,
        product: BinanceProduct,
        request: BinanceHttpRequest,
    ) -> BinanceHttpResponse:
        del product, request
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        raise AssertionError("unreachable")


def make_blocking_sleep(
    started: asyncio.Event,
    cancelled: asyncio.Event,
) -> Callable[[float], Awaitable[None]]:
    async def blocking_sleep(_: float) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    return blocking_sleep


if __name__ == "__main__":
    import unittest

    unittest.main()
