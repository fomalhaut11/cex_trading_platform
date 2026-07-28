from unittest import TestCase

from test_runtime_pipeline import (
    Features,
    Oms,
    Portfolio,
    State,
    Strategy,
    event,
    instrument,
    intent,
)

from cex_quant.execution import CancelResult, ExecutionOutcome, SubmitResult
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.risk import RiskDecision, RiskDecisionStatus, RiskRejectReason
from cex_quant.runtime import PipelineOutcome, TradingApplication


class _Health:
    def health(self) -> HealthReport:
        return HealthReport(
            component="application",
            status=HealthStatus.HEALTHY,
            observed_at_ns=2_000,
        )


class _Validator:
    def validate(self, value: object) -> object:
        class Result:
            is_valid = True

        return Result()


class _Risk:
    def __init__(self, calls: list[str], *, allowed: bool) -> None:
        self.calls = calls
        self.allowed = allowed

    def evaluate(self, target: object, context: object) -> RiskDecision:
        del context
        self.calls.append("risk")
        return RiskDecision(
            status=(
                RiskDecisionStatus.ALLOW
                if self.allowed
                else RiskDecisionStatus.REJECT
            ),
            intent=target,
            reasons=(
                ()
                if self.allowed
                else (RiskRejectReason.GLOBAL_POSITION_LIMIT,)
            ),
            projected_strategy_position=target.target_quantity,
            projected_global_position=target.target_quantity,
            projected_strategy_notional=None,
            projected_global_notional=None,
        )


class _Gateway:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def submit(self, command: object) -> SubmitResult:
        self.calls.append("execution")
        return SubmitResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )

    async def cancel(self, command: object) -> CancelResult:
        raise NotImplementedError


def application(*, allowed: bool) -> tuple[TradingApplication, list[str], object]:
    calls: list[str] = []
    inst = instrument()
    app = TradingApplication(
        health=_Health(),
        validator=_Validator(),  # type: ignore[arg-type]
        market_state=State(calls),
        features=Features(calls),
        strategy=Strategy(calls, intent(inst)),
        portfolio=Portfolio(calls, inst),
        risk=_Risk(calls, allowed=allowed),
        oms=Oms(calls),
        execution_gateway=_Gateway(calls),
    )
    return app, calls, event(inst)


class RuntimeApplicationTests(TestCase):
    def test_application_owns_lifecycle_and_complete_happy_path(self) -> None:
        app, calls, value = application(allowed=True)
        with self.assertRaisesRegex(RuntimeError, "not started"):
            app.process(value)

        with app:
            result = app.process(value)

        self.assertFalse(app.started)
        self.assertEqual(result.outcome, PipelineOutcome.COMPLETED)
        self.assertEqual(
            calls,
            [
                "state",
                "feature",
                "strategy",
                "portfolio",
                "risk",
                "oms",
                "oms_prepare",
                "execution",
                "oms_result",
            ],
        )

    def test_risk_rejection_never_reaches_oms_or_gateway(self) -> None:
        app, calls, value = application(allowed=False)

        with app:
            result = app.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertIn("risk", calls)
        self.assertNotIn("oms", calls)
        self.assertNotIn("execution", calls)


if __name__ == "__main__":
    import unittest

    unittest.main()
