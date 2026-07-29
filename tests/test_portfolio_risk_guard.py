from __future__ import annotations

import unittest
from typing import cast

from group_test_support import (
    ManualClock,
    action_for,
    admission,
    execution_plan,
    permit_for,
)

from cex_quant.oms import OrderRequest
from cex_quant.risk import PortfolioRiskCoordinator
from cex_quant.runtime import (
    OrderGroupRuntime,
    PortfolioRiskExecutionGuard,
)


class FakeCoordinator:
    def __init__(self) -> None:
        self.calls = 0

    def consume_for_external_io(self, **_: object) -> None:
        self.calls += 1


class PlatformGuard:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def assert_submit_allowed(self, request: OrderRequest) -> None:
        del request
        self.calls += 1
        if self.error is not None:
            raise self.error


class PortfolioRiskExecutionGuardTests(unittest.TestCase):
    def test_platform_safety_precedes_exact_permit_consumption(self) -> None:
        clock = ManualClock()
        runtime = OrderGroupRuntime(now_ns=clock)
        created = runtime.create_group(admission(), execution_plan())
        group = runtime.activate_group(created.order_group_id)
        action = action_for(
            group,
            leg_index=0,
            now_ns=clock(),
        )
        permit = permit_for(action, issued_at_ns=clock())
        request = runtime.prepare_child_submit(
            action=action,
            permit=permit,
        )
        coordinator = FakeCoordinator()
        platform = PlatformGuard()
        guard = PortfolioRiskExecutionGuard(
            coordinator=cast(PortfolioRiskCoordinator, coordinator),
            action=action,
            permit=permit,
            group_view=runtime.group,
            now_ns=clock,
            platform_guard=platform,
        )

        guard.assert_submit_allowed(request)
        self.assertEqual(platform.calls, 1)
        self.assertEqual(coordinator.calls, 1)

    def test_platform_failure_and_request_mismatch_consume_nothing(self) -> None:
        clock = ManualClock()
        runtime = OrderGroupRuntime(now_ns=clock)
        created = runtime.create_group(admission(), execution_plan())
        group = runtime.activate_group(created.order_group_id)
        action = action_for(
            group,
            leg_index=0,
            now_ns=clock(),
        )
        permit = permit_for(action, issued_at_ns=clock())
        request = runtime.prepare_child_submit(
            action=action,
            permit=permit,
        )
        coordinator = FakeCoordinator()
        platform = PlatformGuard(RuntimeError("operator halted"))
        guard = PortfolioRiskExecutionGuard(
            coordinator=cast(PortfolioRiskCoordinator, coordinator),
            action=action,
            permit=permit,
            group_view=runtime.group,
            now_ns=clock,
            platform_guard=platform,
        )
        with self.assertRaisesRegex(RuntimeError, "operator halted"):
            guard.assert_submit_allowed(request)
        self.assertEqual(coordinator.calls, 0)

        changed = OrderRequest(
            client_order_id=request.client_order_id,
            approval_id="different-permit",
            intent_id=request.intent_id,
            account_id=request.account_id,
            instrument_id=request.instrument_id,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            created_at_ns=request.created_at_ns,
            time_in_force=request.time_in_force,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            reduce_only=request.reduce_only,
            post_only=request.post_only,
            position_side=request.position_side,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            guard.assert_submit_allowed(changed)
        self.assertEqual(platform.calls, 1)


if __name__ == "__main__":
    unittest.main()
