from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cex_quant.core import UnixNanos
from cex_quant.runtime import (
    OperatorAction,
    OperatorAuthenticationError,
    OperatorCommandEnvelope,
    OperatorControlDeploymentConfig,
    OperatorControlRuntime,
    OperatorKeyBinding,
    OperatorMode,
    operator_command_signature,
)
from tests.test_operator_auth import SECRET
from tests.test_runtime_operations import ManualClock


class AuthenticatedOperatorDeploymentAcceptanceTests(TestCase):
    def test_expired_unauthorized_and_replayed_commands_cannot_change_authority(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            journal_path = Path(directory) / "operator.jsonl"
            config = OperatorControlDeploymentConfig(
                journal_path=journal_path,
                key_bindings={
                    "activator": OperatorKeyBinding(
                        actor="release-operator",
                        secret_variable="ACTIVATOR_SECRET",
                        allowed_actions=(OperatorAction.ACTIVATE,),
                    ),
                    "safety": OperatorKeyBinding(
                        actor="safety-operator",
                        secret_variable="SAFETY_SECRET",
                        allowed_actions=(
                            OperatorAction.ENABLE_REDUCE_ONLY,
                            OperatorAction.HALT,
                        ),
                    ),
                },
                max_validity_ns=1_000,
                clock_skew_ns=0,
            )
            clock = ManualClock(1_500)
            environment = {
                "ACTIVATOR_SECRET": SECRET,
                "SAFETY_SECRET": "fixture-safety-signing-secret-00000002",
            }
            with OperatorControlRuntime(
                config=config,
                clock=clock,
                environ=environment,
            ) as runtime:
                active = self._signed(
                    key_id="activator",
                    command_id="release-1",
                    action=OperatorAction.ACTIVATE,
                    secret=SECRET,
                )
                active_snapshot = runtime.commands.execute(active)
                self.assertEqual(active_snapshot.mode, OperatorMode.ACTIVE)

                unauthorized = self._signed(
                    key_id="activator",
                    command_id="halt-unauthorized",
                    action=OperatorAction.HALT,
                    secret=SECRET,
                )
                with self.assertRaises(OperatorAuthenticationError):
                    runtime.commands.execute(unauthorized)
                self.assertEqual(runtime.controller.snapshot, active_snapshot)

                clock.now = 10_000
                with self.assertRaises(OperatorAuthenticationError):
                    runtime.commands.execute(active)
                self.assertEqual(runtime.controller.snapshot, active_snapshot)

                clock.now = 1_500
                replay = runtime.commands.execute(active)
                self.assertEqual(replay, active_snapshot)
                self.assertEqual(journal_path.read_bytes().count(b"\n"), 1)

            with OperatorControlRuntime(
                config=config,
                clock=clock,
                environ=environment,
            ) as restored:
                self.assertEqual(restored.controller.snapshot, active_snapshot)
                halt = self._signed(
                    key_id="safety",
                    command_id="incident-1",
                    action=OperatorAction.HALT,
                    secret=environment["SAFETY_SECRET"],
                )
                self.assertEqual(
                    restored.commands.execute(halt).mode,
                    OperatorMode.HALTED,
                )

    @staticmethod
    def _signed(
        *,
        key_id: str,
        command_id: str,
        action: OperatorAction,
        secret: str,
    ) -> OperatorCommandEnvelope:
        value = OperatorCommandEnvelope(
            key_id=key_id,
            command_id=command_id,
            action=action,
            reason="acceptance authority transition",
            issued_at_ns=UnixNanos(1_000),
            expires_at_ns=UnixNanos(2_000),
            signature="0" * 64,
        )
        return replace(
            value,
            signature=operator_command_signature(value, secret=secret),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
