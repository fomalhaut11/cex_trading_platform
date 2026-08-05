from __future__ import annotations

import unittest

from cex_quant.core import ExecutionPlanId, ObjectiveTypeId, UnixNanos
from cex_quant.oms import (
    ExecutionPlanRef,
    ExecutionStage,
    execution_plan_parameters_checksum,
)
from cex_quant.runtime import (
    ExecutionPlannerBinding,
    ExecutionPlannerRegistry,
    ExecutionPlanningConfigurationError,
    ObjectiveExecutionPlanBinding,
    ObjectiveExecutionPlanResolver,
    OrderGroupRuntime,
    SequentialResidualExecutionPlanner,
)
from cex_quant.strategy import BasketTargetIntent
from tests.group_test_support import (
    ManualClock,
    admission,
    cross_venue_basket,
    execution_plan,
    four_leg_basket,
    max_leg_basket,
    three_leg_basket,
    two_leg_basket,
)
from tests.portfolio_risk_test_support import portfolio_snapshot


def alternate_plan() -> ExecutionPlanRef:
    return ExecutionPlanRef(
        execution_plan_id=ExecutionPlanId("alternate-sequential"),
        version=1,
        parameters_checksum=execution_plan_parameters_checksum(
            {"max_working_actions": 1}
        ),
    )


class ExecutionPlannerRegistryTests(unittest.TestCase):
    def test_registry_keys_on_complete_plan_reference(self) -> None:
        plan = execution_plan()
        planner = SequentialResidualExecutionPlanner()
        registry = ExecutionPlannerRegistry(
            (ExecutionPlannerBinding(execution_plan=plan, planner=planner),)
        )

        self.assertIs(registry.require(plan), planner)
        with self.assertRaisesRegex(
            ExecutionPlanningConfigurationError,
            "not registered",
        ):
            registry.require(alternate_plan())

    def test_registry_is_bounded_and_rejects_duplicates(self) -> None:
        plan = execution_plan()
        binding = ExecutionPlannerBinding(
            execution_plan=plan,
            planner=SequentialResidualExecutionPlanner(),
        )
        with self.assertRaisesRegex(
            ExecutionPlanningConfigurationError,
            "duplicate",
        ):
            ExecutionPlannerRegistry((binding, binding))
        with self.assertRaisesRegex(
            ExecutionPlanningConfigurationError,
            "exceeds",
        ):
            ExecutionPlannerRegistry((binding, binding), max_registered_plans=1)

    def test_objective_resolver_is_exact_and_fail_closed(self) -> None:
        basket = two_leg_basket()
        plan = execution_plan()
        resolver = ObjectiveExecutionPlanResolver(
            (
                ObjectiveExecutionPlanBinding(
                    objective=basket.objective,
                    execution_plan=plan,
                ),
            )
        )

        self.assertEqual(resolver.resolve(basket), plan)
        unknown_objective_basket = type(basket)(
            intent_id=basket.intent_id,
            strategy_id=basket.strategy_id,
            decision_snapshot_id=basket.decision_snapshot_id,
            objective=type(basket.objective)(
                objective_type_id=ObjectiveTypeId("portfolio.other"),
                version=1,
            ),
            legs=basket.legs,
            decision_time_ns=basket.decision_time_ns,
            valid_until_ns=basket.valid_until_ns,
            policy_version=basket.policy_version,
            reason=basket.reason,
        )
        with self.assertRaisesRegex(
            ExecutionPlanningConfigurationError,
            "not configured",
        ):
            resolver.resolve(unknown_objective_basket)


class SequentialResidualExecutionPlannerFitnessTests(unittest.TestCase):
    def test_same_planner_accepts_two_three_four_and_sixteen_legs(self) -> None:
        for basket in (
            two_leg_basket(),
            three_leg_basket(),
            four_leg_basket(),
            max_leg_basket(),
        ):
            with self.subTest(legs=len(basket.legs)):
                stage = self._first_stage(basket)
                action = stage.actions[0]
                self.assertEqual(stage.dispatch_width, 1)
                self.assertIn(
                    action.instrument_id,
                    tuple(leg.instrument_id for leg in basket.legs),
                )

    def test_same_planner_accepts_cross_venue_multi_account_basket(self) -> None:
        basket = cross_venue_basket()

        stage = self._first_stage(basket)
        action = stage.actions[0]

        self.assertIn(str(action.instrument_id.venue), {"BINANCE", "OKX"})
        self.assertIn(
            str(action.account_id),
            {"binance-primary", "okx-primary"},
        )

    @staticmethod
    def _first_stage(basket: BasketTargetIntent) -> ExecutionStage:
        clock = ManualClock(value=2_000)
        groups = OrderGroupRuntime(now_ns=clock)
        plan = execution_plan()
        created = groups.create_group(admission(basket), plan)
        group = groups.activate_group(created.order_group_id)
        planner = SequentialResidualExecutionPlanner()
        stage = planner.propose(
            group,
            portfolio_snapshot((), ()),
            UnixNanos(2_010),
        )
        assert stage is not None
        return stage


if __name__ == "__main__":
    unittest.main()
