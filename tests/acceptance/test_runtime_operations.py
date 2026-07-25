from __future__ import annotations

from dataclasses import replace
from unittest import TestCase

from cex_quant.core import (
    MonotonicNanos,
    Price,
    Quantity,
    UnixNanos,
)
from cex_quant.features import FeatureQuality
from cex_quant.market_data import MarketDataValidator
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.risk import RiskContext, RiskEngine, RiskLimits
from cex_quant.runtime import (
    OperatorAction,
    OperatorCommand,
    OperatorController,
    OperatorRiskGate,
    PipelineOutcome,
    RuntimeHealthService,
    TradingPipeline,
)
from cex_quant.strategy import PositionTargetIntent
from tests.test_runtime_pipeline import (
    NOW,
    STRATEGY_ID,
    Execution,
    Features,
    Oms,
    State,
    Strategy,
    event,
    instrument,
    intent,
)


class ManualClock:
    def wall_time_ns(self) -> UnixNanos:
        return NOW

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(int(NOW))


class SystemCheck:
    component = "system"

    def health(self) -> HealthReport:
        return HealthReport(
            component=self.component,
            status=HealthStatus.HEALTHY,
            observed_at_ns=NOW,
        )


class Portfolio:
    def __init__(self, quantity: str) -> None:
        self.instrument = instrument()
        self.quantity = Quantity.from_str(quantity)

    def risk_context(self, target: PositionTargetIntent) -> RiskContext:
        del target
        return RiskContext(
            now_ns=NOW,
            strategy_id=STRATEGY_ID,
            instrument=self.instrument,
            current_strategy_position=self.quantity,
            current_global_position=self.quantity,
            reference_price=Price.from_str("100"),
            market_data_as_of_ns=UnixNanos(1_900),
            feature_data_as_of_ns=UnixNanos(1_900),
            feature_data_valid_until_ns=UnixNanos(2_100),
            feature_quality=FeatureQuality.GOOD,
            clock_status=HealthStatus.HEALTHY,
        )


def operator_command(
    command_id: str,
    action: OperatorAction,
) -> OperatorCommand:
    return OperatorCommand(
        command_id=command_id,
        action=action,
        actor="acceptance-operator",
        reason="acceptance scenario",
    )


class RuntimeOperationsAcceptanceTests(TestCase):
    def test_active_reduce_only_and_halt_control_execution(self) -> None:
        calls: list[str] = []
        product = instrument()
        strategy = Strategy(calls, intent(product))
        portfolio = Portfolio("2")
        clock = ManualClock()
        controller = OperatorController(clock=clock)
        infrastructure = RuntimeHealthService(
            component="infrastructure",
            clock=clock,
            checks=(SystemCheck(),),
        )
        operations = RuntimeHealthService(
            component="operations",
            clock=clock,
            checks=(SystemCheck(), controller),
        )
        runtime = TradingPipeline(
            health=infrastructure,
            validator=MarketDataValidator(),
            market_state=State(calls),
            features=Features(calls),
            strategy=strategy,
            portfolio=portfolio,
            risk=OperatorRiskGate(
                delegate=RiskEngine(RiskLimits()),
                controller=controller,
            ),
            oms=Oms(calls),
            execution=Execution(calls),
        )
        market_event = event(product)

        controller.apply(
            operator_command("activate", OperatorAction.ACTIVATE)
        )
        strategy.intent = replace(
            strategy.intent,
            target_quantity=Quantity.from_str("3"),
        )
        active = runtime.process(market_event)
        self.assertEqual(active.outcome, PipelineOutcome.COMPLETED)
        self.assertEqual(calls.count("execution"), 1)
        self.assertEqual(operations.health().status, HealthStatus.HEALTHY)

        controller.apply(
            operator_command(
                "reduce",
                OperatorAction.ENABLE_REDUCE_ONLY,
            )
        )
        strategy.intent = replace(
            strategy.intent,
            target_quantity=Quantity.from_str("1"),
        )
        reducing = runtime.process(market_event)
        self.assertEqual(reducing.outcome, PipelineOutcome.COMPLETED)
        self.assertEqual(calls.count("execution"), 2)
        self.assertEqual(operations.health().status, HealthStatus.DEGRADED)

        strategy.intent = replace(
            strategy.intent,
            target_quantity=Quantity.from_str("3"),
        )
        expanding = runtime.process(market_event)
        self.assertEqual(expanding.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(calls.count("execution"), 2)

        controller.apply(
            operator_command("halt", OperatorAction.HALT)
        )
        strategy.intent = replace(
            strategy.intent,
            target_quantity=Quantity.from_str("0"),
        )
        halted = runtime.process(market_event)
        self.assertEqual(halted.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(calls.count("execution"), 2)
        self.assertEqual(operations.health().status, HealthStatus.UNHEALTHY)


if __name__ == "__main__":
    import unittest

    unittest.main()
