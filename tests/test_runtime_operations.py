from __future__ import annotations

from dataclasses import replace
from unittest import TestCase

from cex_quant.core import MonotonicNanos, Price, Quantity, UnixNanos
from cex_quant.features import FeatureQuality
from cex_quant.observability import (
    HealthIssue,
    HealthReport,
    HealthStatus,
)
from cex_quant.risk import (
    RiskContext,
    RiskDecision,
    RiskDecisionStatus,
    RiskRejectReason,
)
from cex_quant.runtime import (
    OperatorAction,
    OperatorCommand,
    OperatorCommandConflictError,
    OperatorController,
    OperatorMode,
    OperatorRiskGate,
    RuntimeHealthService,
)
from cex_quant.strategy import PositionTargetIntent
from tests.test_runtime_pipeline import STRATEGY_ID, instrument, intent


class ManualClock:
    def __init__(self, now: int = 1_000) -> None:
        self.now = now

    def wall_time_ns(self) -> UnixNanos:
        return UnixNanos(self.now)

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(self.now)


def command(
    command_id: str,
    action: OperatorAction,
    *,
    reason: str = "planned operation",
) -> OperatorCommand:
    return OperatorCommand(
        command_id=command_id,
        action=action,
        actor="operator@example.test",
        reason=reason,
    )


class Check:
    def __init__(
        self,
        component: str,
        status: HealthStatus,
        *,
        issue: str = "",
    ) -> None:
        self.component = component
        self.status = status
        self.issue = issue

    def health(self) -> HealthReport:
        return HealthReport(
            component=self.component,
            status=self.status,
            observed_at_ns=UnixNanos(900),
            issues=(
                ()
                if not self.issue
                else (HealthIssue(code="ISSUE", message=self.issue),)
            ),
        )


class FailingCheck:
    component = "failing"

    def health(self) -> HealthReport:
        raise RuntimeError("sensitive-api-key")


class InvalidCheck:
    component = "invalid"

    def health(self) -> HealthReport:
        return HealthReport(
            component="wrong",
            status=HealthStatus.HEALTHY,
            observed_at_ns=UnixNanos(1),
        )


class AllowRisk:
    def __init__(
        self,
        controller: OperatorController | None = None,
        *,
        reject: bool = False,
    ) -> None:
        self.controller = controller
        self.reject = reject

    def evaluate(
        self,
        target: PositionTargetIntent,
        context: RiskContext,
    ) -> RiskDecision:
        if self.controller is not None:
            self.controller.apply(command("race-halt", OperatorAction.HALT))
        target_value = target.target_quantity.as_decimal()
        current_strategy = context.current_strategy_position.as_decimal()
        current_global = context.current_global_position.as_decimal()
        projected_global = current_global + target_value - current_strategy
        return RiskDecision(
            status=(
                RiskDecisionStatus.REJECT
                if self.reject
                else RiskDecisionStatus.ALLOW
            ),
            intent=target,
            reasons=(
                (RiskRejectReason.GLOBAL_POSITION_LIMIT,)
                if self.reject
                else ()
            ),
            projected_strategy_position=target.target_quantity,
            projected_global_position=Quantity.from_str(
                format(projected_global, "f")
            ),
            projected_strategy_notional=None,
            projected_global_notional=None,
        )


def context(
    *,
    current_strategy: str,
    current_global: str,
) -> RiskContext:
    value = instrument()
    return RiskContext(
        now_ns=UnixNanos(2_000),
        strategy_id=STRATEGY_ID,
        instrument=value,
        current_strategy_position=Quantity.from_str(current_strategy),
        current_global_position=Quantity.from_str(current_global),
        reference_price=Price.from_str("100"),
        market_data_as_of_ns=UnixNanos(1_900),
        feature_data_as_of_ns=UnixNanos(1_900),
        feature_data_valid_until_ns=UnixNanos(2_100),
        feature_quality=FeatureQuality.GOOD,
        clock_status=HealthStatus.HEALTHY,
    )


def target(quantity: str) -> PositionTargetIntent:
    return replace(
        intent(instrument()),
        target_quantity=Quantity.from_str(quantity),
    )


class OperatorControllerTests(TestCase):
    def test_commands_are_idempotent_and_health_tracks_mode(self) -> None:
        clock = ManualClock()
        controller = OperatorController(clock=clock)
        self.assertEqual(controller.snapshot.mode, OperatorMode.HALTED)
        self.assertEqual(controller.health().status, HealthStatus.UNHEALTHY)

        controller.apply(command("activate-0", OperatorAction.ACTIVATE))
        self.assertEqual(controller.snapshot.mode, OperatorMode.ACTIVE)
        self.assertEqual(controller.health().status, HealthStatus.HEALTHY)

        reduce = command("reduce-1", OperatorAction.ENABLE_REDUCE_ONLY)
        first = controller.apply(reduce)
        duplicate = controller.apply(reduce)
        self.assertIs(first, duplicate)
        self.assertEqual(first.generation, 2)
        self.assertEqual(controller.health().status, HealthStatus.DEGRADED)

        clock.now = 2_000
        halted = controller.apply(command("halt-1", OperatorAction.HALT))
        self.assertEqual(halted.mode, OperatorMode.HALTED)
        self.assertEqual(halted.changed_at_ns, UnixNanos(2_000))
        self.assertEqual(controller.health().status, HealthStatus.UNHEALTHY)

        active = controller.apply(
            command("activate-1", OperatorAction.ACTIVATE)
        )
        self.assertEqual(active.mode, OperatorMode.ACTIVE)
        self.assertEqual(active.generation, 4)

    def test_conflicting_idempotency_key_is_rejected(self) -> None:
        controller = OperatorController(clock=ManualClock())
        controller.apply(command("same", OperatorAction.HALT))
        with self.assertRaises(OperatorCommandConflictError):
            controller.apply(
                command("same", OperatorAction.ACTIVATE)
            )

    def test_commands_and_history_bounds_are_strict(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive int"):
            OperatorController(
                clock=ManualClock(),
                command_history_size=True,
            )
        for field, value in (
            ("command_id", ""),
            ("actor", " actor"),
            ("reason", "bad\nreason"),
        ):
            values = {
                "command_id": "id",
                "action": OperatorAction.HALT,
                "actor": "actor",
                "reason": "reason",
            }
            values[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                OperatorCommand(**values)  # type: ignore[arg-type]


class RuntimeHealthServiceTests(TestCase):
    def test_reports_are_stable_and_worst_status_wins(self) -> None:
        service = RuntimeHealthService(
            component="runtime",
            clock=ManualClock(),
            checks=(
                Check("clock", HealthStatus.HEALTHY),
                Check("stream", HealthStatus.DEGRADED, issue="reconnecting"),
            ),
        )

        snapshot = service.snapshot()

        self.assertEqual(
            tuple(report.component for report in snapshot.reports),
            ("clock", "stream"),
        )
        self.assertEqual(snapshot.aggregate.status, HealthStatus.DEGRADED)
        self.assertEqual(
            snapshot.aggregate.issues[0].code,
            "stream:ISSUE",
        )

    def test_empty_failure_and_invalid_report_fail_closed(self) -> None:
        empty = RuntimeHealthService(
            component="empty",
            clock=ManualClock(),
            checks=(),
        )
        self.assertEqual(empty.health().status, HealthStatus.UNKNOWN)

        service = RuntimeHealthService(
            component="runtime",
            clock=ManualClock(),
            checks=(FailingCheck(), InvalidCheck()),
        )
        snapshot = service.snapshot()
        self.assertEqual(snapshot.aggregate.status, HealthStatus.UNHEALTHY)
        rendered = repr(snapshot)
        self.assertNotIn("sensitive-api-key", rendered)
        self.assertEqual(
            tuple(report.issues[0].code for report in snapshot.reports),
            ("CHECK_FAILED", "INVALID_REPORT"),
        )

    def test_duplicate_or_unreadable_components_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            RuntimeHealthService(
                component="runtime",
                clock=ManualClock(),
                checks=(
                    Check("same", HealthStatus.HEALTHY),
                    Check("same", HealthStatus.HEALTHY),
                ),
            )


class OperatorRiskGateTests(TestCase):
    def test_active_delegates_and_halt_rejects(self) -> None:
        controller = OperatorController(clock=ManualClock())
        controller.apply(command("activate", OperatorAction.ACTIVATE))
        gate = OperatorRiskGate(
            delegate=AllowRisk(),
            controller=controller,
        )
        risk_context = context(current_strategy="10", current_global="10")
        self.assertTrue(gate.evaluate(target("12"), risk_context).allowed)

        controller.apply(command("halt", OperatorAction.HALT))
        decision = gate.evaluate(target("0"), risk_context)
        self.assertFalse(decision.allowed)
        self.assertIn(RiskRejectReason.OPERATOR_HALTED, decision.reasons)

    def test_reduce_only_requires_strategy_and_global_reduction(self) -> None:
        controller = OperatorController(clock=ManualClock())
        controller.apply(
            command("reduce", OperatorAction.ENABLE_REDUCE_ONLY)
        )
        gate = OperatorRiskGate(
            delegate=AllowRisk(),
            controller=controller,
        )

        reducing = gate.evaluate(
            target("5"),
            context(current_strategy="10", current_global="10"),
        )
        self.assertTrue(reducing.allowed)

        for quantity, risk_context in (
            ("12", context(current_strategy="10", current_global="10")),
            ("-1", context(current_strategy="10", current_global="10")),
            ("5", context(current_strategy="10", current_global="2")),
            ("1", context(current_strategy="0", current_global="0")),
        ):
            with self.subTest(quantity=quantity):
                decision = gate.evaluate(target(quantity), risk_context)
                self.assertFalse(decision.allowed)
                self.assertIn(
                    RiskRejectReason.REDUCE_ONLY_VIOLATION,
                    decision.reasons,
                )

    def test_most_restrictive_concurrent_mode_and_base_rejection_win(self) -> None:
        controller = OperatorController(clock=ManualClock())
        controller.apply(command("activate", OperatorAction.ACTIVATE))
        racing = OperatorRiskGate(
            delegate=AllowRisk(controller),
            controller=controller,
        )
        decision = racing.evaluate(
            target("0"),
            context(current_strategy="1", current_global="1"),
        )
        self.assertIn(RiskRejectReason.OPERATOR_HALTED, decision.reasons)

        rejected = OperatorRiskGate(
            delegate=AllowRisk(reject=True),
            controller=controller,
        ).evaluate(
            target("0"),
            context(current_strategy="1", current_global="1"),
        )
        self.assertEqual(
            rejected.reasons,
            (
                RiskRejectReason.GLOBAL_POSITION_LIMIT,
                RiskRejectReason.OPERATOR_HALTED,
            ),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
