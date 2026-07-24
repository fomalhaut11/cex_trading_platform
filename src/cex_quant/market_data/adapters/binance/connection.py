"""Transport-neutral Binance WebSocket lifecycle and reconnect policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import DurationNanos, MonotonicNanos

_DEFAULT_BASE_DELAY_NS = DurationNanos(250_000_000)
_DEFAULT_MAX_DELAY_NS = DurationNanos(30_000_000_000)
_DEFAULT_CONNECT_TIMEOUT_NS = DurationNanos(10_000_000_000)
_DEFAULT_MAX_CONNECTION_AGE_NS = DurationNanos(
    23 * 60 * 60 * 1_000_000_000 + 50 * 60 * 1_000_000_000
)


class ConnectionState(StrEnum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    ACTIVE = "active"
    RECONNECT_WAIT = "reconnect_wait"
    STOPPING = "stopping"
    FAILED = "failed"


class ConnectionTransitionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconnectPolicy:
    """Capped exponential backoff with caller-supplied deterministic jitter."""

    base_delay_ns: DurationNanos = _DEFAULT_BASE_DELAY_NS
    max_delay_ns: DurationNanos = _DEFAULT_MAX_DELAY_NS
    multiplier: int = 2
    jitter_limit_basis_points: int = 2_000

    def __post_init__(self) -> None:
        if self.base_delay_ns <= 0:
            raise ValueError("base_delay_ns must be positive")
        if self.max_delay_ns < self.base_delay_ns:
            raise ValueError("max_delay_ns cannot be less than base_delay_ns")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least one")
        if not 0 <= self.jitter_limit_basis_points <= 10_000:
            raise ValueError("jitter limit must be between 0 and 10000 basis points")

    def delay_ns(
        self,
        *,
        attempt: int,
        jitter_basis_points: int = 0,
    ) -> DurationNanos:
        """Return delay for a one-based attempt.

        Randomness is deliberately supplied by the runtime. Tests and replay can
        pass zero, while production may inject a sampled signed basis-point
        value within the configured limit.
        """

        if attempt < 1:
            raise ValueError("attempt must be at least one")
        if abs(jitter_basis_points) > self.jitter_limit_basis_points:
            raise ValueError("jitter exceeds configured limit")
        uncapped = int(self.base_delay_ns) * self.multiplier ** (attempt - 1)
        capped = min(uncapped, int(self.max_delay_ns))
        jittered = capped + capped * jitter_basis_points // 10_000
        return DurationNanos(max(jittered, 0))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectionPolicy:
    """Operational bounds independent of a concrete WebSocket client."""

    reconnect: ReconnectPolicy = ReconnectPolicy()
    connect_timeout_ns: DurationNanos = _DEFAULT_CONNECT_TIMEOUT_NS
    max_connection_age_ns: DurationNanos = _DEFAULT_MAX_CONNECTION_AGE_NS

    def __post_init__(self) -> None:
        if self.connect_timeout_ns <= 0 or self.max_connection_age_ns <= 0:
            raise ValueError("connection time bounds must be positive")

    def should_rotate(
        self,
        *,
        connected_at_ns: MonotonicNanos,
        now_ns: MonotonicNanos,
    ) -> bool:
        if now_ns < connected_at_ns:
            raise ValueError("monotonic clock moved backwards")
        return now_ns - connected_at_ns >= self.max_connection_age_ns


class ConnectionLifecycle:
    """Single-writer state machine for one physical WebSocket connection."""

    def __init__(self) -> None:
        self._state = ConnectionState.STOPPED
        self._reconnect_attempt = 0
        self._shutdown_requested = False
        self._connected_at_ns: MonotonicNanos | None = None
        self._last_failure: str | None = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def reconnect_attempt(self) -> int:
        return self._reconnect_attempt

    @property
    def connected_at_ns(self) -> MonotonicNanos | None:
        return self._connected_at_ns

    @property
    def last_failure(self) -> str | None:
        return self._last_failure

    def start(self) -> None:
        self._require(ConnectionState.STOPPED)
        self._shutdown_requested = False
        self._last_failure = None
        self._state = ConnectionState.CONNECTING

    def connected(self, *, now_ns: MonotonicNanos) -> None:
        self._require(ConnectionState.CONNECTING)
        self._state = ConnectionState.ACTIVE
        self._connected_at_ns = now_ns
        self._reconnect_attempt = 0
        self._last_failure = None

    def connection_lost(self, *, reason: str) -> None:
        self._require(ConnectionState.CONNECTING, ConnectionState.ACTIVE)
        self._connected_at_ns = None
        self._last_failure = reason
        if self._shutdown_requested:
            self._state = ConnectionState.STOPPED
            return
        self._reconnect_attempt += 1
        self._state = ConnectionState.RECONNECT_WAIT

    def retry(self) -> None:
        self._require(ConnectionState.RECONNECT_WAIT)
        if self._shutdown_requested:
            self._state = ConnectionState.STOPPED
            return
        self._state = ConnectionState.CONNECTING

    def request_stop(self) -> None:
        self._shutdown_requested = True
        if self._state is ConnectionState.STOPPED:
            return
        if self._state is ConnectionState.RECONNECT_WAIT:
            self._state = ConnectionState.STOPPED
            return
        if self._state in {ConnectionState.CONNECTING, ConnectionState.ACTIVE}:
            self._state = ConnectionState.STOPPING
            return
        if self._state is not ConnectionState.STOPPING:
            self._state = ConnectionState.STOPPED

    def stopped(self) -> None:
        self._require(ConnectionState.STOPPING)
        self._state = ConnectionState.STOPPED
        self._connected_at_ns = None

    def failed(self, *, reason: str) -> None:
        if self._state is ConnectionState.STOPPED:
            raise ConnectionTransitionError("cannot fail a stopped connection")
        self._last_failure = reason
        self._connected_at_ns = None
        self._state = ConnectionState.FAILED

    def _require(self, *allowed: ConnectionState) -> None:
        if self._state not in allowed:
            expected = ", ".join(state.value for state in allowed)
            raise ConnectionTransitionError(
                f"state {self._state.value} does not allow operation; "
                f"expected {expected}"
            )


__all__ = [
    "ConnectionLifecycle",
    "ConnectionPolicy",
    "ConnectionState",
    "ConnectionTransitionError",
    "ReconnectPolicy",
]
