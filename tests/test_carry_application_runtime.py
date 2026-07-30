from unittest import TestCase

from carry_test_support import (
    SCOPE,
    STRATEGY_ID,
    entry_observations,
)
from test_funding_carry_policy import (
    coordinator,
    economic_policy,
)

from cex_quant.applications.carry.funding_arbitrage import (
    FUNDING_OPEN_OBJECTIVE,
    FundingCarryStrategy,
    funding_objective_registry,
)
from cex_quant.core import DurationNanos, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    CarryApplicationRuntime,
    CarryApplicationRuntimeError,
    CarryApplicationRuntimeStateError,
    CarryApplicationRuntimeStatus,
    CarryRuntimeDisposition,
)
from cex_quant.strategy import BasketIntentPolicy, StrategyRuntime


class Evidence:
    def __init__(self, *, fail: bool = False) -> None:
        self.items = []
        self.fail = fail

    def record(self, publication, decision) -> None:
        if self.fail:
            raise OSError("evidence unavailable")
        self.items.append((publication, decision))


def runtime(*, evidence=None):
    return CarryApplicationRuntime(
        snapshots=coordinator(),
        strategy=StrategyRuntime(
            strategy=FundingCarryStrategy(
                strategy_id=STRATEGY_ID,
                policy=economic_policy(),
            ),
            accepted_scopes=frozenset({SCOPE}),
            basket_policy=BasketIntentPolicy(
                max_legs=2,
                max_validity_ns=DurationNanos(1_000),
                allowed_objectives=(FUNDING_OPEN_OBJECTIVE,),
            ),
            objective_registry=funding_objective_registry(),
        ),
        evidence=evidence,
    )


def evaluate(target: CarryApplicationRuntime):
    return target.evaluate(
        now_ns=UnixNanos(1_100),
        now_monotonic_ns=200,
        clock_status=HealthStatus.HEALTHY,
    )


class CarryApplicationRuntimeTests(TestCase):
    def test_records_offline_basket_and_has_no_external_execution_port(
        self,
    ) -> None:
        evidence = Evidence()
        target = runtime(evidence=evidence)
        target.start()
        for item in entry_observations():
            target.accept(item)

        result = evaluate(target)

        self.assertEqual(
            result.disposition,
            CarryRuntimeDisposition.BASKET_RECORDED_EXTERNAL_BLOCKED,
        )
        self.assertTrue(result.external_execution_blocked)
        self.assertEqual(len(result.baskets), 1)
        self.assertEqual(len(evidence.items), 1)
        self.assertFalse(hasattr(target, "execution_gateway"))
        self.assertFalse(hasattr(target, "submit"))

    def test_not_ready_repeat_and_no_intent_are_explicit(self) -> None:
        missing = runtime()
        missing.start()
        missing.accept(entry_observations()[0])
        self.assertEqual(
            evaluate(missing).disposition,
            CarryRuntimeDisposition.NOT_READY,
        )

        profitable = runtime()
        profitable.start()
        for item in entry_observations():
            profitable.accept(item)
        evaluate(profitable)
        self.assertEqual(
            evaluate(profitable).disposition,
            CarryRuntimeDisposition.NO_NEW_SNAPSHOT,
        )

        negative = runtime()
        negative.start()
        for item in entry_observations(funding_rate="-0.001"):
            negative.accept(item)
        self.assertEqual(
            evaluate(negative).disposition,
            CarryRuntimeDisposition.NO_ECONOMIC_INTENT,
        )

    def test_evidence_failure_latches_before_any_route(self) -> None:
        target = runtime(evidence=Evidence(fail=True))
        target.start()
        for item in entry_observations():
            target.accept(item)

        with self.assertRaisesRegex(
            CarryApplicationRuntimeError,
            "evidence unavailable",
        ):
            evaluate(target)

        self.assertEqual(target.status, CarryApplicationRuntimeStatus.FAILED)
        with self.assertRaises(CarryApplicationRuntimeStateError):
            evaluate(target)

    def test_lifecycle_is_owned_and_bounded(self) -> None:
        target = runtime()
        with self.assertRaises(CarryApplicationRuntimeStateError):
            evaluate(target)
        target.start()
        with self.assertRaises(CarryApplicationRuntimeStateError):
            target.start()
        target.stop()
        self.assertEqual(target.status, CarryApplicationRuntimeStatus.STOPPED)
        with self.assertRaises(CarryApplicationRuntimeStateError):
            target.accept(entry_observations()[0])


if __name__ == "__main__":
    import unittest

    unittest.main()
