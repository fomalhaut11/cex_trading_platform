from unittest import TestCase

from cex_quant.core.time import MonotonicNanos, UnixNanos
from cex_quant.observability import (
    ClockHealthMonitor,
    ClockHealthThresholds,
    HealthReport,
    HealthStatus,
    MonotonicClockRegressionError,
    aggregate_health,
)


class ManualClock:
    def __init__(self, *, wall_ns: int, monotonic_ns: int) -> None:
        self.wall_ns = wall_ns
        self.monotonic_ns = monotonic_ns

    def wall_time_ns(self) -> UnixNanos:
        return UnixNanos(self.wall_ns)

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(self.monotonic_ns)


THRESHOLDS = ClockHealthThresholds(
    warning_abs_offset_ns=100,
    critical_abs_offset_ns=1_000,
    warning_rtt_ns=200,
    critical_rtt_ns=2_000,
    warning_sample_age_ns=500,
    critical_sample_age_ns=5_000,
    max_wall_jump_ns=50,
)


class ClockHealthMonitorTest(TestCase):
    def test_midpoint_offset_and_rtt_are_deterministic(self) -> None:
        clock = ManualClock(wall_ns=10_000, monotonic_ns=1_000)
        monitor = ClockHealthMonitor(
            venue="BINANCE",
            clock=clock,
            thresholds=THRESHOLDS,
        )
        probe = monitor.start_probe()
        clock.wall_ns = 10_100
        clock.monotonic_ns = 1_100

        sample = monitor.finish_probe(
            probe,
            venue_time_ns=UnixNanos(10_075),
        )

        self.assertEqual(int(sample.rtt_ns), 100)
        self.assertEqual(sample.offset_ns, 25)
        self.assertEqual(sample.wall_jump_ns, 0)
        self.assertEqual(monitor.health().status, HealthStatus.HEALTHY)

    def test_warning_and_critical_offset_thresholds(self) -> None:
        clock = ManualClock(wall_ns=10_000, monotonic_ns=1_000)
        monitor = ClockHealthMonitor(
            venue="BINANCE",
            clock=clock,
            thresholds=THRESHOLDS,
        )
        probe = monitor.start_probe()
        clock.wall_ns += 100
        clock.monotonic_ns += 100
        monitor.finish_probe(probe, venue_time_ns=UnixNanos(10_200))
        self.assertEqual(monitor.health().status, HealthStatus.DEGRADED)

        probe = monitor.start_probe()
        clock.wall_ns += 100
        clock.monotonic_ns += 100
        monitor.finish_probe(probe, venue_time_ns=UnixNanos(11_250))
        report = monitor.health()
        self.assertEqual(report.status, HealthStatus.UNHEALTHY)
        self.assertIn("VENUE_CLOCK_OFFSET", {item.code for item in report.issues})

    def test_rtt_and_sample_age_are_independently_checked(self) -> None:
        clock = ManualClock(wall_ns=10_000, monotonic_ns=1_000)
        monitor = ClockHealthMonitor(
            venue="BINANCE",
            clock=clock,
            thresholds=THRESHOLDS,
        )
        probe = monitor.start_probe()
        clock.wall_ns += 300
        clock.monotonic_ns += 300
        monitor.finish_probe(probe, venue_time_ns=UnixNanos(10_150))
        self.assertEqual(monitor.health().status, HealthStatus.DEGRADED)

        clock.wall_ns += 5_000
        report = monitor.health()
        self.assertEqual(report.status, HealthStatus.UNHEALTHY)
        self.assertIn("CLOCK_SAMPLE_STALE", {item.code for item in report.issues})

    def test_wall_jump_is_unhealthy(self) -> None:
        clock = ManualClock(wall_ns=10_000, monotonic_ns=1_000)
        monitor = ClockHealthMonitor(
            venue="BINANCE",
            clock=clock,
            thresholds=THRESHOLDS,
        )
        probe = monitor.start_probe()
        clock.wall_ns += 200
        clock.monotonic_ns += 100
        monitor.finish_probe(probe, venue_time_ns=UnixNanos(10_100))

        report = monitor.health()

        self.assertEqual(report.status, HealthStatus.UNHEALTHY)
        self.assertIn("WALL_CLOCK_JUMP", {item.code for item in report.issues})

    def test_monotonic_regression_raises_and_latches_unhealthy(self) -> None:
        clock = ManualClock(wall_ns=10_000, monotonic_ns=1_000)
        monitor = ClockHealthMonitor(venue="BINANCE", clock=clock)
        monitor.start_probe()
        clock.monotonic_ns = 999

        with self.assertRaises(MonotonicClockRegressionError):
            monitor.start_probe()

        self.assertEqual(monitor.health().status, HealthStatus.UNHEALTHY)

    def test_no_sample_is_unknown_and_history_is_bounded(self) -> None:
        clock = ManualClock(wall_ns=10_000, monotonic_ns=1_000)
        monitor = ClockHealthMonitor(
            venue="BINANCE",
            clock=clock,
            history_size=2,
        )
        self.assertEqual(monitor.health().status, HealthStatus.UNKNOWN)

        for index in range(3):
            probe = monitor.start_probe()
            clock.wall_ns += 1
            clock.monotonic_ns += 1
            monitor.finish_probe(
                probe,
                venue_time_ns=UnixNanos(10_001 + index),
            )

        self.assertEqual(len(monitor.samples), 2)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClockHealthThresholds(
                warning_abs_offset_ns=1_000,
                critical_abs_offset_ns=100,
            )
        clock = ManualClock(wall_ns=0, monotonic_ns=0)
        with self.assertRaises(ValueError):
            ClockHealthMonitor(venue="", clock=clock)
        with self.assertRaises(ValueError):
            ClockHealthMonitor(venue="BINANCE", clock=clock, history_size=0)


class AggregateHealthTest(TestCase):
    def test_worst_child_status_wins(self) -> None:
        reports = (
            HealthReport(
                component="one",
                status=HealthStatus.HEALTHY,
                observed_at_ns=UnixNanos(1),
            ),
            HealthReport(
                component="two",
                status=HealthStatus.DEGRADED,
                observed_at_ns=UnixNanos(1),
            ),
        )

        aggregate = aggregate_health(
            "runtime",
            UnixNanos(1),
            reports,
        )

        self.assertEqual(aggregate.status, HealthStatus.DEGRADED)


if __name__ == "__main__":
    import unittest

    unittest.main()
