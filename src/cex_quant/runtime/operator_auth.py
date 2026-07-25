"""Authenticated, authorized and replay-safe operator command boundary."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from cex_quant.core import UnixNanos
from cex_quant.observability import Clock

from .operations import (
    OperatorAction,
    OperatorCommand,
    OperatorController,
    OperatorControlSnapshot,
)

_ENVIRONMENT_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
_SIGNATURE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_VALIDITY_NS = 60_000_000_000
DEFAULT_CLOCK_SKEW_NS = 5_000_000_000


class OperatorAuthenticationError(RuntimeError):
    """Sanitized rejection at the operator authentication boundary."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorCommandEnvelope:
    """Signed transport-neutral representation of one operator command."""

    key_id: str
    command_id: str
    action: OperatorAction
    reason: str
    issued_at_ns: UnixNanos
    expires_at_ns: UnixNanos
    signature: str

    def __post_init__(self) -> None:
        _validate_text("key_id", self.key_id, maximum=128)
        _validate_text("command_id", self.command_id, maximum=128)
        _validate_text("reason", self.reason, maximum=512)
        if not isinstance(self.action, OperatorAction):
            raise ValueError("action must be an OperatorAction")
        if (
            not isinstance(self.issued_at_ns, int)
            or isinstance(self.issued_at_ns, bool)
            or self.issued_at_ns < 0
        ):
            raise ValueError("issued_at_ns must be a non-negative int")
        if (
            not isinstance(self.expires_at_ns, int)
            or isinstance(self.expires_at_ns, bool)
            or self.expires_at_ns <= self.issued_at_ns
        ):
            raise ValueError("expires_at_ns must be later than issued_at_ns")
        if not _SIGNATURE.fullmatch(self.signature):
            raise ValueError("signature must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorKeyBinding:
    """Deployment metadata for one operator signing identity."""

    actor: str
    secret_variable: str
    allowed_actions: tuple[OperatorAction, ...]

    def __post_init__(self) -> None:
        _validate_text("actor", self.actor, maximum=128)
        if not _ENVIRONMENT_NAME.fullmatch(self.secret_variable):
            raise ValueError("secret_variable is invalid")
        if (
            not isinstance(self.allowed_actions, tuple)
            or not self.allowed_actions
            or any(
                not isinstance(action, OperatorAction)
                for action in self.allowed_actions
            )
            or len(self.allowed_actions) != len(set(self.allowed_actions))
        ):
            raise ValueError(
                "allowed_actions must be a non-empty tuple of unique actions"
            )


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class OperatorKeyMaterial:
    """Fresh signing material returned by a deployment adapter."""

    actor: str
    secret: str
    allowed_actions: tuple[OperatorAction, ...]

    def __post_init__(self) -> None:
        _validate_text("actor", self.actor, maximum=128)
        if not _valid_secret(self.secret):
            raise ValueError("secret is invalid")
        if (
            not isinstance(self.allowed_actions, tuple)
            or not self.allowed_actions
            or any(
                not isinstance(action, OperatorAction)
                for action in self.allowed_actions
            )
        ):
            raise ValueError("allowed_actions is invalid")

    def __repr__(self) -> str:
        return "OperatorKeyMaterial(<redacted>)"


class OperatorKeyProvider(Protocol):
    def key_for(self, key_id: str) -> OperatorKeyMaterial: ...


@dataclass(slots=True, kw_only=True)
class EnvironmentOperatorKeyProvider:
    """Resolve fresh operator keys from explicit environment bindings."""

    bindings: Mapping[str, OperatorKeyBinding]
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, Mapping):
            raise ValueError("bindings must be a mapping")
        copied: dict[str, OperatorKeyBinding] = {}
        variables: set[str] = set()
        actors: set[str] = set()
        for key_id, binding in self.bindings.items():
            _validate_text("key_id", key_id, maximum=128)
            if not isinstance(binding, OperatorKeyBinding):
                raise ValueError("operator key binding is invalid")
            if binding.secret_variable in variables:
                raise ValueError("operator secret variables cannot be shared")
            if binding.actor in actors:
                raise ValueError("operator actors cannot be shared across keys")
            copied[key_id] = binding
            variables.add(binding.secret_variable)
            actors.add(binding.actor)
        if not copied:
            raise ValueError("at least one operator key binding is required")
        if not isinstance(self.environ, Mapping):
            raise ValueError("environ must be a mapping")
        self.bindings = MappingProxyType(copied)

    def __repr__(self) -> str:
        return (
            "EnvironmentOperatorKeyProvider("
            "bindings=<redacted>, environ=<redacted>)"
        )

    def key_for(self, key_id: str) -> OperatorKeyMaterial:
        binding = self.bindings.get(key_id)
        if binding is None:
            raise OperatorAuthenticationError(
                "operator command authentication failed"
            )
        try:
            secret = self.environ[binding.secret_variable]
        except Exception:
            raise OperatorAuthenticationError(
                "operator command authentication failed"
            ) from None
        if not _valid_secret(secret):
            raise OperatorAuthenticationError(
                "operator command authentication failed"
            )
        return OperatorKeyMaterial(
            actor=binding.actor,
            secret=secret,
            allowed_actions=binding.allowed_actions,
        )


class HmacOperatorCommandAuthenticator:
    """Verify freshness, HMAC identity and least-privilege authorization."""

    def __init__(
        self,
        *,
        clock: Clock,
        key_provider: OperatorKeyProvider,
        max_validity_ns: int = DEFAULT_MAX_VALIDITY_NS,
        clock_skew_ns: int = DEFAULT_CLOCK_SKEW_NS,
    ) -> None:
        if (
            not isinstance(max_validity_ns, int)
            or isinstance(max_validity_ns, bool)
            or max_validity_ns < 1
        ):
            raise ValueError("max_validity_ns must be a positive int")
        if (
            not isinstance(clock_skew_ns, int)
            or isinstance(clock_skew_ns, bool)
            or clock_skew_ns < 0
        ):
            raise ValueError("clock_skew_ns must be a non-negative int")
        self._clock = clock
        self._key_provider = key_provider
        self._max_validity_ns = max_validity_ns
        self._clock_skew_ns = clock_skew_ns

    def authenticate(self, envelope: OperatorCommandEnvelope) -> OperatorCommand:
        if not isinstance(envelope, OperatorCommandEnvelope):
            raise OperatorAuthenticationError(
                "operator command authentication failed"
            )
        now_ns = int(self._clock.wall_time_ns())
        issued_at_ns = int(envelope.issued_at_ns)
        expires_at_ns = int(envelope.expires_at_ns)
        if (
            expires_at_ns - issued_at_ns > self._max_validity_ns
            or issued_at_ns > now_ns + self._clock_skew_ns
            or expires_at_ns < now_ns - self._clock_skew_ns
        ):
            raise OperatorAuthenticationError(
                "operator command is outside its validity window"
            )
        material = self._key_provider.key_for(envelope.key_id)
        expected = operator_command_signature(
            envelope,
            secret=material.secret,
        )
        if not hmac.compare_digest(expected, envelope.signature):
            raise OperatorAuthenticationError(
                "operator command authentication failed"
            )
        if envelope.action not in material.allowed_actions:
            raise OperatorAuthenticationError(
                "operator command is not authorized"
            )
        return OperatorCommand(
            command_id=envelope.command_id,
            action=envelope.action,
            actor=material.actor,
            reason=envelope.reason,
        )


class AuthenticatedOperatorCommandService:
    """Authenticate commands before applying durable idempotent authority."""

    def __init__(
        self,
        *,
        authenticator: HmacOperatorCommandAuthenticator,
        controller: OperatorController,
    ) -> None:
        self._authenticator = authenticator
        self._controller = controller

    def execute(
        self,
        envelope: OperatorCommandEnvelope,
    ) -> OperatorControlSnapshot:
        command = self._authenticator.authenticate(envelope)
        return self._controller.apply(command)


def operator_command_signature(
    envelope: OperatorCommandEnvelope,
    *,
    secret: str,
) -> str:
    """Return the canonical HMAC-SHA256 signature for an envelope."""

    if not isinstance(envelope, OperatorCommandEnvelope):
        raise ValueError("envelope must be an OperatorCommandEnvelope")
    if not _valid_secret(secret):
        raise ValueError("secret is invalid")
    return hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(envelope),
        hashlib.sha256,
    ).hexdigest()


def _canonical_payload(envelope: OperatorCommandEnvelope) -> bytes:
    return json.dumps(
        {
            "action": envelope.action.value,
            "command_id": envelope.command_id,
            "expires_at_ns": int(envelope.expires_at_ns),
            "issued_at_ns": int(envelope.issued_at_ns),
            "key_id": envelope.key_id,
            "reason": envelope.reason,
            "version": 1,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _valid_secret(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) >= 32
        and value == value.strip()
        and not any(
            ord(character) < 32 or ord(character) == 127
            for character in value
        )
    )


def _validate_text(name: str, value: str, *, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(
            f"{name} must be non-empty, trimmed and at most {maximum} characters"
        )


__all__ = [
    "AuthenticatedOperatorCommandService",
    "EnvironmentOperatorKeyProvider",
    "HmacOperatorCommandAuthenticator",
    "OperatorAuthenticationError",
    "OperatorCommandEnvelope",
    "OperatorKeyBinding",
    "OperatorKeyMaterial",
    "OperatorKeyProvider",
    "operator_command_signature",
]
