from unittest import TestCase

from cex_quant.core import DurationNanos, MonotonicNanos
from cex_quant.market_data.adapters.binance import (
    ConnectionLifecycle,
    ConnectionPolicy,
    ConnectionState,
    ConnectionTransitionError,
    ReconnectPolicy,
)


class ReconnectPolicyTest(TestCase):
    def test_exponential_delay_is_capped(self) -> None:
        policy = ReconnectPolicy(
            base_delay_ns=DurationNanos(100),
            max_delay_ns=DurationNanos(500),
            multiplier=2,
            jitter_limit_basis_points=1_000,
        )

        self.assertEqual(policy.delay_ns(attempt=1), 100)
        self.assertEqual(policy.delay_ns(attempt=3), 400)
        self.assertEqual(policy.delay_ns(attempt=10), 500)

    def test_jitter_is_explicit_and_deterministic(self) -> None:
        policy = ReconnectPolicy(
            base_delay_ns=DurationNanos(1_000),
            max_delay_ns=DurationNanos(10_000),
            jitter_limit_basis_points=2_000,
        )

        self.assertEqual(
            policy.delay_ns(attempt=1, jitter_basis_points=1_000),
            1_100,
        )
        self.assertEqual(
            policy.delay_ns(attempt=1, jitter_basis_points=-1_000),
            900,
        )

    def test_connection_rotation_uses_monotonic_time(self) -> None:
        policy = ConnectionPolicy(max_connection_age_ns=DurationNanos(1_000))

        self.assertFalse(
            policy.should_rotate(
                connected_at_ns=MonotonicNanos(100),
                now_ns=MonotonicNanos(1_099),
            )
        )
        self.assertTrue(
            policy.should_rotate(
                connected_at_ns=MonotonicNanos(100),
                now_ns=MonotonicNanos(1_100),
            )
        )


class ConnectionLifecycleTest(TestCase):
    def test_connect_loss_retry_and_recovery(self) -> None:
        lifecycle = ConnectionLifecycle()

        lifecycle.start()
        self.assertEqual(lifecycle.state, ConnectionState.CONNECTING)
        lifecycle.connected(now_ns=MonotonicNanos(100))
        self.assertEqual(lifecycle.state, ConnectionState.ACTIVE)
        lifecycle.connection_lost(reason="peer closed")
        self.assertEqual(lifecycle.state, ConnectionState.RECONNECT_WAIT)
        self.assertEqual(lifecycle.reconnect_attempt, 1)
        lifecycle.retry()
        lifecycle.connected(now_ns=MonotonicNanos(200))

        self.assertEqual(lifecycle.state, ConnectionState.ACTIVE)
        self.assertEqual(lifecycle.reconnect_attempt, 0)
        self.assertIsNone(lifecycle.last_failure)

    def test_stop_during_wait_prevents_retry(self) -> None:
        lifecycle = ConnectionLifecycle()
        lifecycle.start()
        lifecycle.connection_lost(reason="connect timeout")

        lifecycle.request_stop()

        self.assertEqual(lifecycle.state, ConnectionState.STOPPED)
        with self.assertRaises(ConnectionTransitionError):
            lifecycle.retry()

    def test_active_stop_requires_transport_confirmation(self) -> None:
        lifecycle = ConnectionLifecycle()
        lifecycle.start()
        lifecycle.connected(now_ns=MonotonicNanos(100))

        lifecycle.request_stop()
        self.assertEqual(lifecycle.state, ConnectionState.STOPPING)
        lifecycle.stopped()

        self.assertEqual(lifecycle.state, ConnectionState.STOPPED)
        self.assertIsNone(lifecycle.connected_at_ns)

    def test_illegal_transition_is_rejected(self) -> None:
        lifecycle = ConnectionLifecycle()

        with self.assertRaises(ConnectionTransitionError):
            lifecycle.connected(now_ns=MonotonicNanos(100))


if __name__ == "__main__":
    import unittest

    unittest.main()
