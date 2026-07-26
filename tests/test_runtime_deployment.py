from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cex_quant.core import UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    OperatorAction,
    OperatorCommandEnvelope,
    OperatorControlDeploymentConfig,
    OperatorControlRuntime,
    OperatorEndpointDeploymentConfig,
    OperatorKeyBinding,
    OperatorMode,
    TradingDeploymentRuntime,
    operator_command_signature,
)
from tests.test_operator_auth import SECRET
from tests.test_operator_endpoint import MemoryAuditSink, request
from tests.test_runtime_operations import AllowRisk, ManualClock


def signed(
    *,
    command_id: str,
    action: OperatorAction,
    secret: str = SECRET,
) -> OperatorCommandEnvelope:
    value = OperatorCommandEnvelope(
        key_id="admin-key",
        command_id=command_id,
        action=action,
        reason=f"{action.value} during deployment test",
        issued_at_ns=UnixNanos(1_000),
        expires_at_ns=UnixNanos(2_000),
        signature="0" * 64,
    )
    return replace(
        value,
        signature=operator_command_signature(value, secret=secret),
    )


class OperatorControlDeploymentTests(TestCase):
    def config(self, path: Path) -> OperatorControlDeploymentConfig:
        return OperatorControlDeploymentConfig(
            journal_path=path,
            key_bindings={
                "admin-key": OperatorKeyBinding(
                    actor="deployment-admin",
                    secret_variable="DEPLOYMENT_OPERATOR_SECRET",
                    allowed_actions=(
                        OperatorAction.ACTIVATE,
                        OperatorAction.ENABLE_REDUCE_ONLY,
                        OperatorAction.HALT,
                    ),
                )
            },
            max_validity_ns=10_000,
            clock_skew_ns=100,
        )

    def test_assembly_authenticates_persists_restores_and_owns_lifecycle(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            config = self.config(path)
            with OperatorControlRuntime(
                config=config,
                clock=ManualClock(1_500),
                environ={"DEPLOYMENT_OPERATOR_SECRET": SECRET},
            ) as runtime:
                self.assertEqual(runtime.controller.snapshot.mode, OperatorMode.HALTED)
                self.assertEqual(
                    runtime.health.health().status,
                    HealthStatus.UNHEALTHY,
                )
                active = runtime.commands.execute(
                    signed(
                        command_id="activate",
                        action=OperatorAction.ACTIVATE,
                    )
                )
                self.assertEqual(active.mode, OperatorMode.ACTIVE)
                self.assertEqual(runtime.health.health().status, HealthStatus.HEALTHY)
                gate = runtime.risk_gate(AllowRisk())
                self.assertIsNotNone(gate)

            self.assertTrue(runtime.closed)
            with OperatorControlRuntime(
                config=config,
                clock=ManualClock(1_500),
                environ={"DEPLOYMENT_OPERATOR_SECRET": SECRET},
            ) as restored:
                self.assertEqual(restored.controller.snapshot, active)
                retried = restored.commands.execute(
                    signed(
                        command_id="activate",
                        action=OperatorAction.ACTIVATE,
                    )
                )
                self.assertEqual(retried, active)
            self.assertEqual(path.read_text(encoding="ascii").count("\n"), 1)
            self.assertNotIn(SECRET, path.read_text(encoding="ascii"))

    def test_closed_runtime_rejects_new_composition(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = OperatorControlRuntime(
                config=self.config(Path(directory) / "operator.jsonl"),
                clock=ManualClock(1_500),
                environ={"DEPLOYMENT_OPERATOR_SECRET": SECRET},
            )
            runtime.close()
            runtime.close()
            with self.assertRaisesRegex(RuntimeError, "closed"):
                runtime.risk_gate(AllowRisk())
            with self.assertRaisesRegex(RuntimeError, "closed"):
                runtime.__enter__()

    def test_config_rejects_missing_parent_and_invalid_limits(self) -> None:
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing" / "operator.jsonl"
            with self.assertRaisesRegex(ValueError, "parent"):
                self.config(missing)
            valid = Path(directory) / "operator.jsonl"
            with self.assertRaises(ValueError):
                replace(self.config(valid), command_history_size=0)
            source = dict(self.config(valid).key_bindings)
            config = replace(self.config(valid), key_bindings=source)
            source.clear()
            self.assertEqual(len(config.key_bindings), 1)

    def test_trading_assembly_makes_operator_health_and_risk_mandatory(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            runtime = TradingDeploymentRuntime(
                operator_config=self.config(
                    Path(directory) / "operator.jsonl"
                ),
                clock=ManualClock(1_500),
                health_checks=(),
                validator=object(),  # type: ignore[arg-type]
                market_state=object(),  # type: ignore[arg-type]
                features=object(),  # type: ignore[arg-type]
                strategy=object(),  # type: ignore[arg-type]
                portfolio=object(),  # type: ignore[arg-type]
                risk=AllowRisk(),
                oms=object(),  # type: ignore[arg-type]
                execution_gateway=object(),  # type: ignore[arg-type]
                environ={"DEPLOYMENT_OPERATOR_SECRET": SECRET},
            )
            self.assertEqual(runtime.health.health().status, HealthStatus.UNHEALTHY)
            runtime.operator.commands.execute(
                signed(
                    command_id="activate",
                    action=OperatorAction.ACTIVATE,
                )
            )
            self.assertEqual(runtime.health.health().status, HealthStatus.HEALTHY)
            runtime.start()
            self.assertTrue(runtime.started)
            runtime.close()
            self.assertTrue(runtime.closed)
            self.assertTrue(runtime.operator.closed)
            with self.assertRaisesRegex(RuntimeError, "closed"):
                runtime.start()

    def test_endpoint_audit_failure_durably_halts_operator_runtime(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            config = self.config(path)
            with OperatorControlRuntime(
                config=config,
                clock=ManualClock(1_500),
                environ={"DEPLOYMENT_OPERATOR_SECRET": SECRET},
            ) as runtime:
                endpoint = runtime.create_endpoint(
                    config=OperatorEndpointDeploymentConfig(
                        max_requests_per_window=2,
                    ),
                    audit_sink=MemoryAuditSink(fail_at=2),
                )
                with self.assertRaisesRegex(RuntimeError, "audit"):
                    endpoint.handle(request(key_id="admin-key"))
                self.assertEqual(
                    runtime.controller.snapshot.mode,
                    OperatorMode.HALTED,
                )
                with self.assertRaisesRegex(RuntimeError, "already"):
                    runtime.create_endpoint(
                        config=OperatorEndpointDeploymentConfig(),
                        audit_sink=MemoryAuditSink(),
                    )

            with OperatorControlRuntime(
                config=config,
                clock=ManualClock(2_500),
                environ={"DEPLOYMENT_OPERATOR_SECRET": SECRET},
            ) as restored:
                self.assertEqual(
                    restored.controller.snapshot.mode,
                    OperatorMode.HALTED,
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
