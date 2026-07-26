"""Bounded mTLS-aware request adapter for authenticated operator commands."""

from __future__ import annotations

import json
import re
from collections import OrderedDict, deque
from dataclasses import dataclass
from enum import StrEnum
from threading import BoundedSemaphore, Lock
from typing import Protocol, cast

from cex_quant.core import UnixNanos
from cex_quant.observability import (
    Clock,
    HealthIssue,
    HealthReport,
    HealthStatus,
)

from .operations import (
    OperatorAction,
    OperatorCommandConflictError,
    OperatorControlDurabilityError,
    OperatorControlSnapshot,
)
from .operator_auth import (
    OperatorAuthenticationError,
    OperatorCommandEnvelope,
)

_CERTIFICATE_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_FIELDS = frozenset(
    {
        "version",
        "key_id",
        "command_id",
        "action",
        "reason",
        "issued_at_ns",
        "expires_at_ns",
        "signature",
    }
)


class OperatorEndpointError(RuntimeError):
    """Sanitized base error returned by the operator endpoint adapter."""


class OperatorTransportRejectedError(OperatorEndpointError):
    """Raised when a request lacks a trusted mutually authenticated peer."""


class OperatorRequestRejectedError(OperatorEndpointError):
    """Raised when a request is malformed or its command is rejected."""


class OperatorRateLimitError(OperatorEndpointError):
    """Raised when a client exceeds its bounded request rate."""


class OperatorConcurrencyLimitError(OperatorEndpointError):
    """Raised rather than waiting when all command slots are occupied."""


class OperatorAuditUnavailableError(OperatorEndpointError):
    """Raised after audit persistence fails and the endpoint is latched."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MutualTlsIdentity:
    """Identity asserted by a trusted TLS terminator after certificate checks."""

    client_id: str
    certificate_sha256: str
    mutually_authenticated: bool

    def __post_init__(self) -> None:
        _validate_text("client_id", self.client_id, maximum=128)
        if not _CERTIFICATE_FINGERPRINT.fullmatch(self.certificate_sha256):
            raise ValueError(
                "certificate_sha256 must be 64 lowercase hexadecimal characters"
            )
        if not isinstance(self.mutually_authenticated, bool):
            raise ValueError("mutually_authenticated must be a bool")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorHttpRequest:
    """Small framework-neutral request passed by a bounded HTTP adapter."""

    body: bytes
    content_type: str
    identity: MutualTlsIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.body, bytes):
            raise ValueError("body must be bytes")
        if not isinstance(self.content_type, str):
            raise ValueError("content_type must be a string")
        if not isinstance(self.identity, MutualTlsIdentity):
            raise ValueError("identity must be a MutualTlsIdentity")


class OperatorAuditStage(StrEnum):
    RECEIVED = "received"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorAuditRecord:
    """Secret-free event for a deployment-owned authenticated audit sink."""

    observed_at_ns: UnixNanos
    client_id: str
    certificate_sha256: str
    stage: OperatorAuditStage
    command_id: str = ""
    key_id: str = ""
    action: str = ""
    result_code: str = ""

    def __post_init__(self) -> None:
        if (
            not isinstance(self.observed_at_ns, int)
            or isinstance(self.observed_at_ns, bool)
            or self.observed_at_ns < 0
        ):
            raise ValueError("observed_at_ns must be a non-negative int")
        _validate_text("client_id", self.client_id, maximum=128)
        if not _CERTIFICATE_FINGERPRINT.fullmatch(self.certificate_sha256):
            raise ValueError(
                "certificate_sha256 must be 64 lowercase hexadecimal characters"
            )
        if not isinstance(self.stage, OperatorAuditStage):
            raise ValueError("stage must be an OperatorAuditStage")
        for name, value, maximum in (
            ("command_id", self.command_id, 128),
            ("key_id", self.key_id, 128),
            ("action", self.action, 64),
            ("result_code", self.result_code, 64),
        ):
            _validate_optional_text(name, value, maximum=maximum)
        if self.stage in {
            OperatorAuditStage.RECEIVED,
            OperatorAuditStage.APPLIED,
        } and not all((self.command_id, self.key_id, self.action)):
            raise ValueError(
                "received and applied audit records require command fields"
            )


class OperatorAuditSink(Protocol):
    """Bounded durable sink supplied by the deployment environment."""

    def append(self, record: OperatorAuditRecord) -> None: ...


class OperatorCommandExecutor(Protocol):
    def execute(
        self,
        envelope: OperatorCommandEnvelope,
    ) -> OperatorControlSnapshot: ...


class OperatorEndpointFailureHandler(Protocol):
    def __call__(self, code: str) -> None: ...


class OperatorRequestRateLimiter:
    """Thread-safe fixed-window limiter with bounded LRU client state."""

    def __init__(
        self,
        *,
        clock: Clock,
        max_requests: int = 10,
        window_ns: int = 1_000_000_000,
        max_clients: int = 128,
    ) -> None:
        for name, value in (
            ("max_requests", max_requests),
            ("window_ns", window_ns),
            ("max_clients", max_clients),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise ValueError(f"{name} must be a positive int")
        self._clock = clock
        self._max_requests = max_requests
        self._window_ns = window_ns
        self._max_clients = max_clients
        self._clients: OrderedDict[str, deque[int]] = OrderedDict()
        self._last_now_ns: int | None = None
        self._failed = False
        self._lock = Lock()

    @property
    def retained_clients(self) -> int:
        with self._lock:
            return len(self._clients)

    @property
    def failed(self) -> bool:
        with self._lock:
            return self._failed

    def allow(self, client_id: str) -> bool:
        _validate_text("client_id", client_id, maximum=128)
        now_ns = int(self._clock.monotonic_time_ns())
        with self._lock:
            if self._failed:
                return False
            if self._last_now_ns is not None and now_ns < self._last_now_ns:
                self._failed = True
                return False
            self._last_now_ns = now_ns
            history = self._clients.get(client_id)
            if history is None:
                if len(self._clients) >= self._max_clients:
                    self._clients.popitem(last=False)
                history = deque()
                self._clients[client_id] = history
            else:
                self._clients.move_to_end(client_id)
            cutoff = now_ns - self._window_ns
            while history and history[0] <= cutoff:
                history.popleft()
            if len(history) >= self._max_requests:
                return False
            history.append(now_ns)
            return True


class OperatorCommandEndpoint:
    """Fail-closed entry boundary around an authenticated command executor."""

    component = "operator-endpoint"

    def __init__(
        self,
        *,
        clock: Clock,
        executor: OperatorCommandExecutor,
        audit_sink: OperatorAuditSink,
        rate_limiter: OperatorRequestRateLimiter,
        failure_handler: OperatorEndpointFailureHandler,
        max_request_bytes: int = 4_096,
        max_concurrency: int = 4,
    ) -> None:
        for name, value in (
            ("max_request_bytes", max_request_bytes),
            ("max_concurrency", max_concurrency),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise ValueError(f"{name} must be a positive int")
        self._clock = clock
        self._executor = executor
        self._audit_sink = audit_sink
        self._rate_limiter = rate_limiter
        self._failure_handler = failure_handler
        self._max_request_bytes = max_request_bytes
        self._slots = BoundedSemaphore(max_concurrency)
        self._audit_lock = Lock()
        self._audit_failed = False
        self._failure_lock = Lock()
        self._failure_notified = False

    def handle(self, request: OperatorHttpRequest) -> OperatorControlSnapshot:
        if not isinstance(request, OperatorHttpRequest):
            raise OperatorRequestRejectedError("operator request was rejected")
        self._ensure_available()
        identity = request.identity
        if not identity.mutually_authenticated:
            self._audit_rejection(identity, "MTLS_REQUIRED")
            raise OperatorTransportRejectedError(
                "mutually authenticated transport is required"
            )
        if not self._rate_limiter.allow(identity.client_id):
            code = (
                "RATE_CLOCK_FAILED"
                if self._rate_limiter.failed
                else "RATE_LIMITED"
            )
            if self._rate_limiter.failed:
                self._notify_failure(code)
            self._audit_rejection(identity, code)
            raise OperatorRateLimitError("operator request rate limit exceeded")
        if not self._slots.acquire(blocking=False):
            self._audit_rejection(identity, "CONCURRENCY_LIMITED")
            raise OperatorConcurrencyLimitError(
                "operator request concurrency limit exceeded"
            )
        try:
            return self._handle_acquired(request)
        finally:
            self._slots.release()

    def health(self) -> HealthReport:
        issues: tuple[HealthIssue, ...]
        if self._audit_failed:
            status = HealthStatus.UNHEALTHY
            issues = (
                HealthIssue(
                    code="AUDIT_UNAVAILABLE",
                    message="operator audit sink is unavailable",
                ),
            )
        elif self._rate_limiter.failed:
            status = HealthStatus.UNHEALTHY
            issues = (
                HealthIssue(
                    code="MONOTONIC_CLOCK_REGRESSION",
                    message="operator rate-limit clock moved backwards",
                ),
            )
        else:
            status = HealthStatus.HEALTHY
            issues = ()
        return HealthReport(
            component=self.component,
            status=status,
            observed_at_ns=self._clock.wall_time_ns(),
            issues=issues,
        )

    def _handle_acquired(
        self,
        request: OperatorHttpRequest,
    ) -> OperatorControlSnapshot:
        try:
            envelope = decode_operator_request(
                request,
                max_request_bytes=self._max_request_bytes,
            )
        except (TypeError, ValueError):
            self._audit_rejection(request.identity, "MALFORMED_REQUEST")
            raise OperatorRequestRejectedError(
                "operator request was rejected"
            ) from None

        self._append_audit(
            _audit_record(
                self._clock,
                request.identity,
                OperatorAuditStage.RECEIVED,
                envelope=envelope,
            )
        )
        try:
            snapshot = self._executor.execute(envelope)
        except (
            OperatorAuthenticationError,
            OperatorCommandConflictError,
        ):
            self._append_audit(
                _audit_record(
                    self._clock,
                    request.identity,
                    OperatorAuditStage.REJECTED,
                    envelope=envelope,
                    result_code="COMMAND_REJECTED",
                )
            )
            raise OperatorRequestRejectedError(
                "operator command was rejected"
            ) from None
        except OperatorControlDurabilityError:
            self._notify_failure("DURABILITY_FAILED")
            self._append_audit(
                _audit_record(
                    self._clock,
                    request.identity,
                    OperatorAuditStage.FAILED,
                    envelope=envelope,
                    result_code="DURABILITY_FAILED",
                )
            )
            raise OperatorRequestRejectedError(
                "operator command could not be applied"
            ) from None
        except Exception:
            self._notify_failure("EXECUTOR_FAILED")
            self._append_audit(
                _audit_record(
                    self._clock,
                    request.identity,
                    OperatorAuditStage.FAILED,
                    envelope=envelope,
                    result_code="EXECUTOR_FAILED",
                )
            )
            raise OperatorRequestRejectedError(
                "operator command could not be applied"
            ) from None

        self._append_audit(
            _audit_record(
                self._clock,
                request.identity,
                OperatorAuditStage.APPLIED,
                envelope=envelope,
                result_code=snapshot.mode.value.upper(),
            )
        )
        return snapshot

    def _audit_rejection(
        self,
        identity: MutualTlsIdentity,
        code: str,
    ) -> None:
        self._append_audit(
            OperatorAuditRecord(
                observed_at_ns=self._clock.wall_time_ns(),
                client_id=identity.client_id,
                certificate_sha256=identity.certificate_sha256,
                stage=OperatorAuditStage.REJECTED,
                result_code=code,
            )
        )

    def _append_audit(self, record: OperatorAuditRecord) -> None:
        with self._audit_lock:
            if self._audit_failed:
                raise OperatorAuditUnavailableError(
                    "operator audit sink is unavailable"
                )
            try:
                self._audit_sink.append(record)
            except Exception:
                self._audit_failed = True
                self._notify_failure("AUDIT_UNAVAILABLE")
                raise OperatorAuditUnavailableError(
                    "operator audit sink is unavailable"
                ) from None

    def _ensure_available(self) -> None:
        with self._audit_lock:
            if self._audit_failed:
                raise OperatorAuditUnavailableError(
                    "operator audit sink is unavailable"
                )

    def _notify_failure(self, code: str) -> None:
        with self._failure_lock:
            if self._failure_notified:
                return
            self._failure_notified = True
        try:
            self._failure_handler(code)
        except Exception:
            return


def decode_operator_request(
    request: OperatorHttpRequest,
    *,
    max_request_bytes: int = 4_096,
) -> OperatorCommandEnvelope:
    """Strictly decode a bounded JSON request without accepting extra fields."""

    if not isinstance(request, OperatorHttpRequest):
        raise ValueError("request must be an OperatorHttpRequest")
    if (
        not isinstance(max_request_bytes, int)
        or isinstance(max_request_bytes, bool)
        or max_request_bytes < 1
    ):
        raise ValueError("max_request_bytes must be a positive int")
    if request.content_type.lower() != "application/json":
        raise ValueError("content_type must be application/json")
    if not request.body or len(request.body) > max_request_bytes:
        raise ValueError("request body size is invalid")
    try:
        value = json.loads(
            request.body,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("request body is not valid JSON") from None
    if not isinstance(value, dict):
        raise ValueError("request body must be an object")
    payload = cast(dict[str, object], value)
    version = payload.get("version")
    if (
        frozenset(payload) != _EXPECTED_FIELDS
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version != 1
    ):
        raise ValueError("request schema is invalid")
    try:
        action = OperatorAction(_required_string(payload, "action"))
        issued_at_ns = _required_int(payload, "issued_at_ns")
        expires_at_ns = _required_int(payload, "expires_at_ns")
        return OperatorCommandEnvelope(
            key_id=_required_string(payload, "key_id"),
            command_id=_required_string(payload, "command_id"),
            action=action,
            reason=_required_string(payload, "reason"),
            issued_at_ns=UnixNanos(issued_at_ns),
            expires_at_ns=UnixNanos(expires_at_ns),
            signature=_required_string(payload, "signature"),
        )
    except (TypeError, ValueError):
        raise ValueError("request fields are invalid") from None


def _audit_record(
    clock: Clock,
    identity: MutualTlsIdentity,
    stage: OperatorAuditStage,
    *,
    envelope: OperatorCommandEnvelope,
    result_code: str = "",
) -> OperatorAuditRecord:
    return OperatorAuditRecord(
        observed_at_ns=clock.wall_time_ns(),
        client_id=identity.client_id,
        certificate_sha256=identity.certificate_sha256,
        stage=stage,
        command_id=envelope.command_id,
        key_id=envelope.key_id,
        action=envelope.action.value,
        result_code=result_code,
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _required_string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ValueError("string field is invalid")
    return result


def _required_int(value: dict[str, object], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool) or result < 0:
        raise ValueError("integer field is invalid")
    return result


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


def _validate_optional_text(name: str, value: str, *, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(
            f"{name} must be trimmed and at most {maximum} characters"
        )


__all__ = [
    "MutualTlsIdentity",
    "OperatorAuditRecord",
    "OperatorAuditSink",
    "OperatorAuditStage",
    "OperatorAuditUnavailableError",
    "OperatorCommandEndpoint",
    "OperatorCommandExecutor",
    "OperatorConcurrencyLimitError",
    "OperatorEndpointError",
    "OperatorEndpointFailureHandler",
    "OperatorHttpRequest",
    "OperatorRateLimitError",
    "OperatorRequestRateLimiter",
    "OperatorRequestRejectedError",
    "OperatorTransportRejectedError",
    "decode_operator_request",
]
