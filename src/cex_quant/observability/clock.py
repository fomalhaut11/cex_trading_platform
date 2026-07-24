"""Clock injection, venue offset sampling and clock-health evaluation."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from cex_quant.core.time import DurationNanos, MonotonicNanos, UnixNanos

from .health import HealthIssue, HealthReport, HealthStatus


class Clock(Protocol):
    """Source of externally comparable and duration-safe nanosecond time."""

    def wall_time_ns(self) -> UnixNanos:
        """Return current UTC Unix nanoseconds."""

    def monotonic_time_ns(self) -> MonotonicNanos:
        """Return process-local monotonic nanoseconds."""


class SystemClock:
    """Production clock backed by Python's platform clock functions."""

    def wall_time_ns(self) -> UnixNanos:
        return UnixNanos(time.time_ns())

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(time.monotonic_ns())


@dataclass(frozen=True, slots=True)
class VenueClockProbe:
    """Local timestamps captured immediately before a venue time request."""

    wall_sent_ns: UnixNanos
    monotonic_sent_ns: MonotonicNanos


@dataclass(frozen=True, slots=True)
class VenueClockSample:
    """One venue clock observation using the request midpoint estimate."""

    venue_time_ns: UnixNanos
    wall_sent_ns: UnixNanos
    wall_received_ns: UnixNanos
    monotonic_received_ns: MonotonicNanos
    rtt_ns: DurationNanos
    offset_ns: int
    wall_jump_ns: int


@dataclass(frozen=True, slots=True)
class ClockHealthThresholds:
    """Warning and critical operational thresholds in nanoseconds."""

    warning_abs_offset_ns: int = 100_000_000
    critical_abs_offset_ns: int = 1_000_000_000
    warning_rtt_ns: int = 500_000_000
    critical_rtt_ns: int = 2_000_000_000
    warning_sample_age_ns: int = 30_000_000_000
    critical_sample_age_ns: int = 120_000_000_000
    max_wall_jump_ns: int = 100_000_000

    def __post_init__(self) -> None:
        pairs = (
            (
                "offset",
                self.warning_abs_offset_ns,
                self.critical_abs_offset_ns,
            ),
            ("RTT", self.warning_rtt_ns, self.critical_rtt_ns),
            (
                "sample age",
                self.warning_sample_age_ns,
                self.critical_sample_age_ns,
            ),
        )
        for name, warning, critical in pairs:
            if warning < 0 or critical <= warning:
                raise ValueError(
                    f"{name} thresholds require 0 <= warning < critical"
                )
        if self.max_wall_jump_ns < 0:
            raise ValueError("max_wall_jump_ns must be non-negative")


class MonotonicClockRegressionError(RuntimeError):
    """Raised when a duration clock moves backwards."""


class ClockHealthMonitor:
    """Collect venue clock samples and evaluate operational clock health."""

    def __init__(
        self,
        *,
        venue: str,
        clock: Clock,
        thresholds: ClockHealthThresholds | None = None,
        history_size: int = 32,
    ) -> None:
        if not venue:
            raise ValueError("venue must not be empty")
        if history_size <= 0:
            raise ValueError("history_size must be positive")
        self._venue = venue
        self._clock = clock
        self._thresholds = thresholds or ClockHealthThresholds()
        self._samples: deque[VenueClockSample] = deque(maxlen=history_size)
        self._last_monotonic_ns: MonotonicNanos | None = None
        self._monotonic_failed = False

    @property
    def component(self) -> str:
        return f"clock:{self._venue}"

    @property
    def latest_sample(self) -> VenueClockSample | None:
        return self._samples[-1] if self._samples else None

    @property
    def samples(self) -> tuple[VenueClockSample, ...]:
        return tuple(self._samples)

    def start_probe(self) -> VenueClockProbe:
        """Capture request-start times at the venue API boundary."""

        monotonic_ns = self._read_monotonic()
        return VenueClockProbe(
            wall_sent_ns=self._clock.wall_time_ns(),
            monotonic_sent_ns=monotonic_ns,
        )

    def finish_probe(
        self,
        probe: VenueClockProbe,
        *,
        venue_time_ns: UnixNanos,
    ) -> VenueClockSample:
        """Finish a probe and retain its offset, RTT and wall-jump sample."""

        monotonic_received_ns = self._read_monotonic()
        wall_received_ns = self._clock.wall_time_ns()
        rtt = int(monotonic_received_ns) - int(probe.monotonic_sent_ns)
        if rtt < 0:
            self._monotonic_failed = True
            raise MonotonicClockRegressionError(
                "monotonic clock regressed during venue clock probe"
            )

        wall_elapsed = int(wall_received_ns) - int(probe.wall_sent_ns)
        midpoint_ns = (
            int(probe.wall_sent_ns) + int(wall_received_ns)
        ) // 2
        sample = VenueClockSample(
            venue_time_ns=venue_time_ns,
            wall_sent_ns=probe.wall_sent_ns,
            wall_received_ns=wall_received_ns,
            monotonic_received_ns=monotonic_received_ns,
            rtt_ns=DurationNanos(rtt),
            offset_ns=int(venue_time_ns) - midpoint_ns,
            wall_jump_ns=wall_elapsed - rtt,
        )
        self._samples.append(sample)
        return sample

    def health(self) -> HealthReport:
        """Evaluate latest sample without mutating it or hiding failures."""

        observed_at_ns = self._clock.wall_time_ns()
        if self._monotonic_failed:
            return HealthReport(
                component=self.component,
                status=HealthStatus.UNHEALTHY,
                observed_at_ns=observed_at_ns,
                issues=(
                    HealthIssue(
                        code="MONOTONIC_CLOCK_REGRESSION",
                        message="monotonic clock moved backwards",
                    ),
                ),
            )

        sample = self.latest_sample
        if sample is None:
            return HealthReport(
                component=self.component,
                status=HealthStatus.UNKNOWN,
                observed_at_ns=observed_at_ns,
                issues=(
                    HealthIssue(
                        code="NO_CLOCK_SAMPLE",
                        message="no venue clock sample is available",
                    ),
                ),
            )

        age_ns = max(
            0,
            int(observed_at_ns) - int(sample.wall_received_ns),
        )
        critical: list[HealthIssue] = []
        warning: list[HealthIssue] = []
        thresholds = self._thresholds

        if abs(sample.wall_jump_ns) > thresholds.max_wall_jump_ns:
            critical.append(
                HealthIssue(
                    code="WALL_CLOCK_JUMP",
                    message=(
                        "wall and monotonic elapsed time differ by "
                        f"{sample.wall_jump_ns} ns"
                    ),
                )
            )
        self._classify(
            value=abs(sample.offset_ns),
            warning_threshold=thresholds.warning_abs_offset_ns,
            critical_threshold=thresholds.critical_abs_offset_ns,
            code="VENUE_CLOCK_OFFSET",
            description=f"absolute venue clock offset is {abs(sample.offset_ns)} ns",
            warning=warning,
            critical=critical,
        )
        self._classify(
            value=int(sample.rtt_ns),
            warning_threshold=thresholds.warning_rtt_ns,
            critical_threshold=thresholds.critical_rtt_ns,
            code="VENUE_CLOCK_RTT",
            description=f"venue clock probe RTT is {int(sample.rtt_ns)} ns",
            warning=warning,
            critical=critical,
        )
        self._classify(
            value=age_ns,
            warning_threshold=thresholds.warning_sample_age_ns,
            critical_threshold=thresholds.critical_sample_age_ns,
            code="CLOCK_SAMPLE_STALE",
            description=f"venue clock sample age is {age_ns} ns",
            warning=warning,
            critical=critical,
        )

        if critical:
            status = HealthStatus.UNHEALTHY
            issues = tuple(critical + warning)
        elif warning:
            status = HealthStatus.DEGRADED
            issues = tuple(warning)
        else:
            status = HealthStatus.HEALTHY
            issues = ()
        return HealthReport(
            component=self.component,
            status=status,
            observed_at_ns=observed_at_ns,
            issues=issues,
        )

    def _read_monotonic(self) -> MonotonicNanos:
        value = self._clock.monotonic_time_ns()
        if (
            self._last_monotonic_ns is not None
            and value < self._last_monotonic_ns
        ):
            self._monotonic_failed = True
            raise MonotonicClockRegressionError(
                "monotonic clock moved backwards"
            )
        self._last_monotonic_ns = value
        return value

    @staticmethod
    def _classify(
        *,
        value: int,
        warning_threshold: int,
        critical_threshold: int,
        code: str,
        description: str,
        warning: list[HealthIssue],
        critical: list[HealthIssue],
    ) -> None:
        issue = HealthIssue(code=code, message=description)
        if value >= critical_threshold:
            critical.append(issue)
        elif value >= warning_threshold:
            warning.append(issue)


__all__ = [
    "Clock",
    "ClockHealthMonitor",
    "ClockHealthThresholds",
    "MonotonicClockRegressionError",
    "SystemClock",
    "VenueClockProbe",
    "VenueClockSample",
]
