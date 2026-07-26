from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cex_quant.runtime import (
    OperatorAction,
    OperatorAuditStage,
    OperatorCommandEndpoint,
    OperatorControlDeploymentConfig,
    OperatorControlRuntime,
    OperatorKeyBinding,
    OperatorMode,
    OperatorRequestRateLimiter,
    OperatorTransportRejectedError,
)
from tests.test_operator_auth import SECRET
from tests.test_operator_endpoint import MemoryAuditSink, request
from tests.test_runtime_operations import ManualClock


class OperatorEndpointRecoveryAcceptanceTests(TestCase):
    def test_mtls_command_audit_idempotency_and_restart_recovery(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            config = OperatorControlDeploymentConfig(
                journal_path=path,
                key_bindings={
                    "alice-key": OperatorKeyBinding(
                        actor="release-operator",
                        secret_variable="OPERATOR_SECRET",
                        allowed_actions=(
                            OperatorAction.ACTIVATE,
                            OperatorAction.HALT,
                        ),
                    )
                },
                max_validity_ns=10_000,
                clock_skew_ns=0,
            )
            clock = ManualClock(1_500)
            environment = {"OPERATOR_SECRET": SECRET}
            audit = MemoryAuditSink()
            with OperatorControlRuntime(
                config=config,
                clock=clock,
                environ=environment,
            ) as runtime:
                endpoint = OperatorCommandEndpoint(
                    clock=clock,
                    executor=runtime.commands,
                    audit_sink=audit,
                    rate_limiter=OperatorRequestRateLimiter(
                        clock=clock,
                        max_requests=10,
                        window_ns=1_000,
                    ),
                    failure_handler=lambda code: None,
                )
                first = endpoint.handle(request(command_id="release-1"))
                retried = endpoint.handle(request(command_id="release-1"))
                self.assertEqual(first, retried)
                self.assertEqual(first.mode, OperatorMode.ACTIVE)

                with self.assertRaises(OperatorTransportRejectedError):
                    endpoint.handle(
                        request(
                            command_id="incident-unauthenticated",
                            action=OperatorAction.HALT,
                            authenticated=False,
                        )
                    )
                self.assertEqual(runtime.controller.snapshot, first)

            self.assertEqual(path.read_bytes().count(b"\n"), 1)
            with OperatorControlRuntime(
                config=config,
                clock=clock,
                environ=environment,
            ) as restored:
                self.assertEqual(restored.controller.snapshot, first)

            self.assertEqual(
                tuple(record.stage for record in audit.records),
                (
                    OperatorAuditStage.RECEIVED,
                    OperatorAuditStage.APPLIED,
                    OperatorAuditStage.RECEIVED,
                    OperatorAuditStage.APPLIED,
                    OperatorAuditStage.REJECTED,
                ),
            )
            persisted = path.read_text(encoding="ascii")
            audit_rendered = repr(audit.records)
            self.assertNotIn(SECRET, persisted)
            self.assertNotIn(SECRET, audit_rendered)
            self.assertNotIn("test activation", audit_rendered)


if __name__ == "__main__":
    import unittest

    unittest.main()
