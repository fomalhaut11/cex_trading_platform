"""A015 offline acceptance for ADR-012 Portfolio Risk authorization."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_quant.core import UnixNanos
from cex_quant.instruments import InstrumentKind
from cex_quant.oms import OrderGroupAdmission
from cex_quant.risk import (
    JsonLinesPortfolioRiskJournal,
    PortfolioRiskAuthorizationError,
    PortfolioRiskCoordinator,
    PortfolioRiskEngine,
)
from cex_quant.runtime import (
    GroupedExecutionBlockedError,
    OrderGroupRuntime,
)
from cex_quant.strategy import basket_target_intent_checksum
from tests.group_test_support import (
    ManualClock,
    action_for,
    execution_plan,
    three_leg_basket,
    two_leg_basket,
)
from tests.portfolio_risk_test_support import (
    NOW,
    policy,
    portfolio_snapshot,
    position_view,
    product,
    publication,
    sensitivity,
)


class Adr012AcceptanceTests(unittest.TestCase):
    def test_two_leg_residual_gets_exact_permit_but_external_route_stays_off(
        self,
    ) -> None:
        spot = product(InstrumentKind.SPOT, "BTCUSDT")
        perp = product(InstrumentKind.PERPETUAL, "BTCUSDT")
        instruments = (spot, perp)
        sensitivities = (
            sensitivity(spot.instrument_id, delta="1", margin="0"),
            sensitivity(perp.instrument_id, delta="1", margin="10"),
        )
        selected_policy = policy(instruments)
        basket = two_leg_basket()
        engine = PortfolioRiskEngine()
        decision = engine.assess_basket(
            basket,
            publication(portfolio_snapshot(instruments, sensitivities)),
            selected_policy,
            now_ns=NOW,
        )
        self.assertTrue(decision.allowed)
        assert decision.approval is not None

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio-risk.jsonl"
            journal = JsonLinesPortfolioRiskJournal(path)
            coordinator = PortfolioRiskCoordinator(
                journal=journal,
                risk_policy_version=selected_policy.version,
                reservation_lifetime_ns=(
                    selected_policy.reservation_lifetime_ns
                ),
                max_active_reservations=(
                    selected_policy.max_active_reservations
                ),
                now_ns=NOW,
            )
            approval = coordinator.reserve_approval(decision, now_ns=NOW)
            clock = ManualClock(value=2_010)
            runtime = OrderGroupRuntime(now_ns=clock)
            created = runtime.create_group(
                OrderGroupAdmission(
                    approval_id=approval.approval_id,
                    basket=basket,
                    basket_checksum=basket_target_intent_checksum(basket),
                    approved_at_ns=approval.approved_at_ns,
                    valid_until_ns=approval.valid_until_ns,
                    risk_policy_version=approval.risk_policy_version,
                ),
                execution_plan(),
            )
            group = runtime.activate_group(created.order_group_id)
            attached = coordinator.attach_reservation(
                approval.approval_id,
                group.order_group_id,
                now_ns=UnixNanos(2_015),
            )

            action = action_for(
                group,
                leg_index=0,
                now_ns=UnixNanos(2_020),
                quantity="10",
            )
            action_decision = engine.authorize_action(
                group,
                action,
                publication(
                    portfolio_snapshot(
                        instruments,
                        sensitivities,
                        positions=position_view(
                            {spot.instrument_id: "10"}
                        ),
                        groups=(group,),
                        reservations=(attached,),
                    )
                ),
                selected_policy,
                now_ns=UnixNanos(2_020),
            )
            self.assertEqual(
                action_decision.current_exposure.factors[
                    0
                ].net_delta.as_decimal(),
                10,
            )
            self.assertEqual(
                action_decision.projected_exposure.factors[
                    0
                ].net_delta.as_decimal(),
                0,
            )
            permit = coordinator.issue_permit(
                action_decision,
                now_ns=UnixNanos(2_020),
            )
            clock.value = 2_030
            request = runtime.prepare_child_submit(
                action=action,
                permit=permit,
            )
            coordinator.validate_permit(
                permit=permit,
                action=action,
                group=runtime.group(group.order_group_id),
                now_ns=UnixNanos(2_030),
            )
            with self.assertRaises(GroupedExecutionBlockedError):
                runtime.submit_prepared_child(request.client_order_id)
            journal.close()

            recovered_journal = JsonLinesPortfolioRiskJournal(path)
            recovered = PortfolioRiskCoordinator(
                journal=recovered_journal,
                risk_policy_version=selected_policy.version,
                reservation_lifetime_ns=(
                    selected_policy.reservation_lifetime_ns
                ),
                max_active_reservations=(
                    selected_policy.max_active_reservations
                ),
                now_ns=UnixNanos(2_040),
            )
            with self.assertRaises(PortfolioRiskAuthorizationError):
                recovered.validate_permit(
                    permit=permit,
                    action=action,
                    group=runtime.group(group.order_group_id),
                    now_ns=UnixNanos(2_040),
                )
            recovered_journal.close()

    def test_generic_three_leg_option_spread_and_delta_hedge_admit(self) -> None:
        option_a = product(InstrumentKind.OPTION, "BTC-30000-C")
        option_b = product(InstrumentKind.OPTION, "BTC-35000-C")
        perp = product(InstrumentKind.PERPETUAL, "BTCUSDT")
        instruments = (option_a, option_b, perp)
        decision = PortfolioRiskEngine().assess_basket(
            three_leg_basket(),
            publication(
                portfolio_snapshot(
                    instruments,
                    (
                        sensitivity(
                            option_a.instrument_id,
                            delta="0.50",
                            margin="5",
                            gamma="0.01",
                            vega="2",
                        ),
                        sensitivity(
                            option_b.instrument_id,
                            delta="0.20",
                            margin="5",
                            gamma="0.02",
                            vega="3",
                        ),
                        sensitivity(
                            perp.instrument_id,
                            delta="1",
                            margin="10",
                        ),
                    ),
                )
            ),
            policy(instruments),
            now_ns=NOW,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(len(decision.basket.legs), 3)
if __name__ == "__main__":
    unittest.main()
