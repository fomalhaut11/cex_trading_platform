from __future__ import annotations

from dataclasses import replace
from unittest import TestCase

from cex_quant.core import UnixNanos
from cex_quant.runtime import (
    AuthenticatedOperatorCommandService,
    EnvironmentOperatorKeyProvider,
    HmacOperatorCommandAuthenticator,
    OperatorAction,
    OperatorAuthenticationError,
    OperatorCommandEnvelope,
    OperatorController,
    OperatorKeyBinding,
    OperatorMode,
    operator_command_signature,
)
from tests.test_runtime_operations import ManualClock

SECRET = "fixture-operator-signing-secret-000001"


def binding(
    *,
    actor: str = "alice",
    variable: str = "OPERATOR_ALICE_SECRET",
    actions: tuple[OperatorAction, ...] = (
        OperatorAction.ACTIVATE,
        OperatorAction.ENABLE_REDUCE_ONLY,
        OperatorAction.HALT,
    ),
) -> OperatorKeyBinding:
    return OperatorKeyBinding(
        actor=actor,
        secret_variable=variable,
        allowed_actions=actions,
    )


def envelope(
    *,
    command_id: str = "command-1",
    action: OperatorAction = OperatorAction.ACTIVATE,
    issued_at_ns: int = 1_000,
    expires_at_ns: int = 2_000,
    reason: str = "test activation",
    key_id: str = "alice-key",
    secret: str = SECRET,
) -> OperatorCommandEnvelope:
    unsigned = OperatorCommandEnvelope(
        key_id=key_id,
        command_id=command_id,
        action=action,
        reason=reason,
        issued_at_ns=UnixNanos(issued_at_ns),
        expires_at_ns=UnixNanos(expires_at_ns),
        signature="0" * 64,
    )
    return replace(
        unsigned,
        signature=operator_command_signature(unsigned, secret=secret),
    )


class RaisingEnvironment(dict[str, str]):
    def __getitem__(self, key: str) -> str:
        raise RuntimeError(f"do-not-expose-{key}")


class OperatorAuthenticationTests(TestCase):
    def provider(
        self,
        *,
        environment: dict[str, str] | None = None,
        actions: tuple[OperatorAction, ...] = (
            OperatorAction.ACTIVATE,
            OperatorAction.ENABLE_REDUCE_ONLY,
            OperatorAction.HALT,
        ),
    ) -> EnvironmentOperatorKeyProvider:
        return EnvironmentOperatorKeyProvider(
            bindings={"alice-key": binding(actions=actions)},
            environ=(
                {"OPERATOR_ALICE_SECRET": SECRET}
                if environment is None
                else environment
            ),
        )

    def authenticator(
        self,
        *,
        clock: ManualClock | None = None,
        provider: EnvironmentOperatorKeyProvider | None = None,
    ) -> HmacOperatorCommandAuthenticator:
        return HmacOperatorCommandAuthenticator(
            clock=clock or ManualClock(1_500),
            key_provider=provider or self.provider(),
            max_validity_ns=10_000,
            clock_skew_ns=100,
        )

    def test_authentication_derives_actor_and_service_applies_command(self) -> None:
        controller = OperatorController(clock=ManualClock(1_500))
        service = AuthenticatedOperatorCommandService(
            authenticator=self.authenticator(),
            controller=controller,
        )

        snapshot = service.execute(envelope())

        self.assertEqual(snapshot.mode, OperatorMode.ACTIVE)
        self.assertEqual(snapshot.actor, "alice")
        self.assertEqual(snapshot.command_id, "command-1")

    def test_signature_covers_every_authority_field(self) -> None:
        authenticator = self.authenticator()
        original = envelope()
        mutations = (
            replace(original, command_id="other-command"),
            replace(original, action=OperatorAction.HALT),
            replace(original, reason="different reason"),
            replace(original, issued_at_ns=UnixNanos(1_001)),
            replace(original, expires_at_ns=UnixNanos(2_001)),
            replace(original, key_id="other-key"),
        )
        for changed in mutations:
            with (
                self.subTest(changed=changed),
                self.assertRaises(OperatorAuthenticationError),
            ):
                authenticator.authenticate(changed)

    def test_freshness_and_authorization_fail_closed(self) -> None:
        activate_only = self.provider(actions=(OperatorAction.ACTIVATE,))
        with self.assertRaisesRegex(
            OperatorAuthenticationError,
            "not authorized",
        ):
            self.authenticator(provider=activate_only).authenticate(
                envelope(action=OperatorAction.HALT)
            )

        for clock, value in (
            (ManualClock(10_000), envelope()),
            (
                ManualClock(0),
                envelope(issued_at_ns=1_000, expires_at_ns=2_000),
            ),
        ):
            with (
                self.subTest(now=clock.now),
                self.assertRaisesRegex(
                    OperatorAuthenticationError,
                    "validity window",
                ),
            ):
                self.authenticator(clock=clock).authenticate(value)

        too_long = envelope(expires_at_ns=20_000)
        with self.assertRaisesRegex(
            OperatorAuthenticationError,
            "validity window",
        ):
            self.authenticator().authenticate(too_long)

    def test_key_rotation_is_fresh_and_failures_are_sanitized(self) -> None:
        environment = {"OPERATOR_ALICE_SECRET": SECRET}
        provider = self.provider(environment=environment)
        authenticator = self.authenticator(provider=provider)
        first = envelope()
        authenticator.authenticate(first)

        rotated = "fixture-operator-signing-secret-rotated-02"
        environment["OPERATOR_ALICE_SECRET"] = rotated
        with self.assertRaises(OperatorAuthenticationError):
            authenticator.authenticate(first)
        authenticator.authenticate(
            envelope(command_id="command-2", secret=rotated)
        )

        for failing_provider in (
            EnvironmentOperatorKeyProvider(
                bindings={"alice-key": binding()},
                environ={},
            ),
            EnvironmentOperatorKeyProvider(
                bindings={"alice-key": binding()},
                environ=RaisingEnvironment(),
            ),
        ):
            with self.assertRaises(OperatorAuthenticationError) as caught:
                self.authenticator(
                    provider=failing_provider,
                ).authenticate(first)
            rendered = str(caught.exception)
            self.assertNotIn("ALICE", rendered)
            self.assertNotIn("fixture", rendered)
        self.assertNotIn("OPERATOR_ALICE_SECRET", repr(provider))
        self.assertNotIn(SECRET, repr(provider))

    def test_binding_and_envelope_validation_is_strict(self) -> None:
        with self.assertRaises(ValueError):
            binding(actions=())
        with self.assertRaises(ValueError):
            binding(variable="lowercase")
        with self.assertRaises(ValueError):
            EnvironmentOperatorKeyProvider(
                bindings={
                    "one": binding(actor="alice", variable="SHARED"),
                    "two": binding(actor="bob", variable="SHARED"),
                },
                environ={},
            )
        with self.assertRaises(ValueError):
            replace(envelope(), signature="not-a-signature")


if __name__ == "__main__":
    import unittest

    unittest.main()
