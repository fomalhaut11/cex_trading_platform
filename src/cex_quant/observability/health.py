"""Small, dependency-free health reporting primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from cex_quant.core.time import UnixNanos


class HealthStatus(StrEnum):
    """Operational severity ordered from normal to unavailable."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


_SEVERITY = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.DEGRADED: 2,
    HealthStatus.UNHEALTHY: 3,
}


@dataclass(frozen=True, slots=True)
class HealthIssue:
    """A machine-readable reason for a non-healthy status."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Immutable point-in-time component health report."""

    component: str
    status: HealthStatus
    observed_at_ns: UnixNanos
    issues: tuple[HealthIssue, ...] = ()


class HealthCheck(Protocol):
    """Interface implemented by components that expose current health."""

    @property
    def component(self) -> str:
        """Return the stable component name."""

    def health(self) -> HealthReport:
        """Evaluate and return current health."""


def aggregate_health(
    component: str,
    observed_at_ns: UnixNanos,
    reports: tuple[HealthReport, ...],
) -> HealthReport:
    """Aggregate child reports using their worst status."""

    if not reports:
        return HealthReport(
            component=component,
            status=HealthStatus.UNKNOWN,
            observed_at_ns=observed_at_ns,
            issues=(
                HealthIssue(
                    code="NO_HEALTH_CHECKS",
                    message="no child health checks are registered",
                ),
            ),
        )

    status = max((report.status for report in reports), key=_SEVERITY.__getitem__)
    issues = tuple(
        HealthIssue(
            code=f"{report.component}:{issue.code}",
            message=issue.message,
        )
        for report in reports
        for issue in report.issues
    )
    return HealthReport(
        component=component,
        status=status,
        observed_at_ns=observed_at_ns,
        issues=issues,
    )


__all__ = [
    "HealthCheck",
    "HealthIssue",
    "HealthReport",
    "HealthStatus",
    "aggregate_health",
]
