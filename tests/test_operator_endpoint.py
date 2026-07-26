from __future__ import annotations

import json
from dataclasses import asdict
from threading import Event, Lock, Thread
from unittest import TestCase

from cex_quant.core import UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    AuthenticatedOperatorCommandService,
    EnvironmentOperatorKeyProvider,
    HmacOperatorCommandAuthenticator,
    MutualTlsIdentity,
    OperatorAction,
    OperatorAuditRecord,
    OperatorAuditStage,
    OperatorAuditUnavailableError,
    OperatorCommandEndpoint,
    OperatorConcurrencyLimitError,
    OperatorControlDurabilityError,
    OperatorController,
    OperatorHttpRequest,
    OperatorKeyBinding,
    OperatorMode,
    OperatorRateLimitError,
    OperatorRequestRateLimiter,
    OperatorRequestRejectedError,
    OperatorTransportRejectedError,
    decode_operator_request,
)
from tests.test_operator_auth import SECRET, envelope
from tests.test_runtime_operations import ManualClock


class MemoryAuditSink:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.records: list[OperatorAuditRecord] = []
        self.fail_at = fail_at
        self._calls = 0
        self._lock = Lock()

    def append(self, record: OperatorAuditRecord) -> None:
        with self._lock:
            self._calls += 1
            if self.fail_at == self._calls:
                raise RuntimeError("sensitive audit backend failure")
            self.records.append(record)


def identity(
    *,
    client_id: str = "release-terminal",
    authenticated: bool = True,
) -> MutualTlsIdentity:
    return MutualTlsIdentity(
        client_id=client_id,
        certificate_sha256="a" * 64,
        mutually_authenticated=authenticated,
    )


def request(
    *,
    command_id: str = "command-1",
    action: OperatorAction = OperatorAction.ACTIVATE,
    authenticated: bool = True,
    content_type: str = "application/json",
    secret: str = SECRET,
    key_id: str = "alice-key",
) -> OperatorHttpRequest:
    value = envelope(
        command_id=command_id,
        action=action,
        secret=secret,
        key_id=key_id,
    )
    payload = {
        "version": 1,
        "key_id": value.key_id,
        "command_id": value.command_id,
        "action": value.action.value,
        "reason": value.reason,
        "issued_at_ns": int(value.issued_at_ns),
        "expires_at_ns": int(value.expires_at_ns),
        "signature": value.signature,
    }
    return OperatorHttpRequest(
        body=json.dumps(payload, separators=(",", ":")).encode("ascii"),
        content_type=content_type,
        identity=identity(authenticated=authenticated),
    )


def endpoint(
    *,
    clock: ManualClock | None = None,
    audit: MemoryAuditSink | None = None,
    max_requests: int = 10,
    max_clients: int = 8,
    max_concurrency: int = 2,
) -> tuple[OperatorCommandEndpoint, OperatorController, MemoryAuditSink]:
    active_clock = clock or ManualClock(1_500)
    controller = OperatorController(clock=active_clock)
    provider = EnvironmentOperatorKeyProvider(
        bindings={
            "alice-key": OperatorKeyBinding(
                actor="alice",
                secret_variable="OPERATOR_SECRET",
                allowed_actions=(
                    OperatorAction.ACTIVATE,
                    OperatorAction.ENABLE_REDUCE_ONLY,
                    OperatorAction.HALT,
                ),
            )
        },
        environ={"OPERATOR_SECRET": SECRET},
    )
    service = AuthenticatedOperatorCommandService(
        authenticator=HmacOperatorCommandAuthenticator(
            clock=active_clock,
            key_provider=provider,
            max_validity_ns=10_000,
            clock_skew_ns=0,
        ),
        controller=controller,
    )
    sink = audit or MemoryAuditSink()
    return (
        OperatorCommandEndpoint(
            clock=active_clock,
            executor=service,
            audit_sink=sink,
            rate_limiter=OperatorRequestRateLimiter(
                clock=active_clock,
                max_requests=max_requests,
                window_ns=1_000,
                max_clients=max_clients,
            ),
            failure_handler=lambda code: None,
            max_request_bytes=2_048,
            max_concurrency=max_concurrency,
        ),
        controller,
        sink,
    )


class OperatorEndpointTests(TestCase):
    def test_mtls_signed_command_is_audited_before_and_after_apply(self) -> None:
        value, controller, audit = endpoint()

        snapshot = value.handle(request())

        self.assertEqual(snapshot.mode, OperatorMode.ACTIVE)
        self.assertEqual(controller.snapshot, snapshot)
        self.assertEqual(
            tuple(record.stage for record in audit.records),
            (OperatorAuditStage.RECEIVED, OperatorAuditStage.APPLIED),
        )
        self.assertEqual(audit.records[1].result_code, "ACTIVE")
        rendered = repr(audit.records)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn("test activation", rendered)
        self.assertEqual(value.health().status, HealthStatus.HEALTHY)

    def test_transport_schema_and_signature_fail_before_authority_change(
        self,
    ) -> None:
        value, controller, audit = endpoint()

        with self.assertRaises(OperatorTransportRejectedError):
            value.handle(request(authenticated=False))
        with self.assertRaises(OperatorRequestRejectedError):
            value.handle(request(content_type="text/plain"))
        with self.assertRaises(OperatorRequestRejectedError):
            value.handle(request(secret="different-fixture-signing-secret-0002"))

        self.assertEqual(controller.snapshot.mode, OperatorMode.HALTED)
        self.assertEqual(
            tuple(record.result_code for record in audit.records),
            (
                "MTLS_REQUIRED",
                "MALFORMED_REQUEST",
                "",
                "COMMAND_REJECTED",
            ),
        )

    def test_decoder_rejects_extra_duplicate_wrong_type_and_oversize(self) -> None:
        valid = request()
        raw = json.loads(valid.body)
        assert isinstance(raw, dict)
        extra = dict(raw)
        extra["unexpected"] = "field"
        wrong_version = dict(raw)
        wrong_version["version"] = True
        duplicate = valid.body[:-1] + b',"version":1}'
        cases = (
            OperatorHttpRequest(
                body=json.dumps(extra).encode(),
                content_type="application/json",
                identity=identity(),
            ),
            OperatorHttpRequest(
                body=json.dumps(wrong_version).encode(),
                content_type="application/json",
                identity=identity(),
            ),
            OperatorHttpRequest(
                body=duplicate,
                content_type="application/json",
                identity=identity(),
            ),
            OperatorHttpRequest(
                body=b"{" + (b"x" * 100) + b"}",
                content_type="application/json",
                identity=identity(),
            ),
        )
        for index, item in enumerate(cases):
            with (
                self.subTest(index=index),
                self.assertRaises(ValueError),
            ):
                decode_operator_request(
                    item,
                    max_request_bytes=(
                        64 if index == len(cases) - 1 else 2_048
                    ),
                )

    def test_rate_limiter_is_bounded_and_clock_regression_fails_closed(
        self,
    ) -> None:
        clock = ManualClock(1_500)
        value, _, audit = endpoint(
            clock=clock,
            max_requests=1,
            max_clients=2,
        )
        value.handle(request(command_id="one"))
        with self.assertRaises(OperatorRateLimitError):
            value.handle(request(command_id="two"))

        limiter = OperatorRequestRateLimiter(
            clock=clock,
            max_requests=2,
            window_ns=100,
            max_clients=2,
        )
        self.assertTrue(limiter.allow("one"))
        self.assertTrue(limiter.allow("two"))
        self.assertTrue(limiter.allow("three"))
        self.assertEqual(limiter.retained_clients, 2)
        clock.now = 1_499
        self.assertFalse(limiter.allow("three"))
        self.assertTrue(limiter.failed)
        self.assertIn("RATE_LIMITED", tuple(r.result_code for r in audit.records))

    def test_audit_failure_before_apply_latches_endpoint(self) -> None:
        value, controller, _ = endpoint(
            audit=MemoryAuditSink(fail_at=1),
        )

        with self.assertRaises(OperatorAuditUnavailableError) as caught:
            value.handle(request())

        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(controller.snapshot.mode, OperatorMode.HALTED)
        self.assertEqual(value.health().status, HealthStatus.UNHEALTHY)
        with self.assertRaises(OperatorAuditUnavailableError):
            value.handle(request(command_id="later"))

    def test_audit_failure_after_apply_reports_unknown_response_and_latches(
        self,
    ) -> None:
        value, controller, audit = endpoint(
            audit=MemoryAuditSink(fail_at=2),
        )

        with self.assertRaises(OperatorAuditUnavailableError):
            value.handle(request())

        self.assertEqual(controller.snapshot.mode, OperatorMode.ACTIVE)
        self.assertEqual(
            tuple(record.stage for record in audit.records),
            (OperatorAuditStage.RECEIVED,),
        )
        self.assertEqual(value.health().status, HealthStatus.UNHEALTHY)

    def test_concurrency_limit_is_non_blocking_and_audited(self) -> None:
        clock = ManualClock(1_500)
        entered = Event()
        release = Event()

        class BlockingExecutor:
            def execute(self, value: object) -> object:
                del value
                entered.set()
                release.wait(timeout=2)
                return type(
                    "Snapshot",
                    (),
                    {"mode": OperatorMode.ACTIVE},
                )()

        audit = MemoryAuditSink()
        value = OperatorCommandEndpoint(
            clock=clock,
            executor=BlockingExecutor(),  # type: ignore[arg-type]
            audit_sink=audit,
            rate_limiter=OperatorRequestRateLimiter(
                clock=clock,
                max_requests=10,
            ),
            failure_handler=lambda code: None,
            max_concurrency=1,
        )
        errors: list[BaseException] = []

        def run_first() -> None:
            try:
                value.handle(request(command_id="first"))
            except BaseException as error:
                errors.append(error)

        worker = Thread(target=run_first)
        worker.start()
        self.assertTrue(entered.wait(timeout=1))
        with self.assertRaises(OperatorConcurrencyLimitError):
            value.handle(request(command_id="second"))
        release.set()
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(
            "CONCURRENCY_LIMITED",
            tuple(record.result_code for record in audit.records),
        )

    def test_executor_and_rate_clock_failures_notify_safety_handler(self) -> None:
        clock = ManualClock(1_500)

        class FailingExecutor:
            def __init__(self, error: BaseException) -> None:
                self.error = error

            def execute(self, value: object) -> object:
                del value
                raise self.error

        for error, expected in (
            (RuntimeError("sensitive failure"), "EXECUTOR_FAILED"),
            (
                OperatorControlDurabilityError("journal failed"),
                "DURABILITY_FAILED",
            ),
        ):
            notifications: list[str] = []
            audit = MemoryAuditSink()
            value = OperatorCommandEndpoint(
                clock=clock,
                executor=FailingExecutor(error),  # type: ignore[arg-type]
                audit_sink=audit,
                rate_limiter=OperatorRequestRateLimiter(clock=clock),
                failure_handler=notifications.append,
            )
            with self.assertRaises(OperatorRequestRejectedError) as caught:
                value.handle(request())
            self.assertNotIn("sensitive", str(caught.exception))
            self.assertEqual(notifications, [expected])
            self.assertEqual(audit.records[-1].result_code, expected)

        notifications = []
        limiter = OperatorRequestRateLimiter(clock=clock)
        self.assertTrue(limiter.allow("release-terminal"))
        clock.now = 1_499
        value = OperatorCommandEndpoint(
            clock=clock,
            executor=FailingExecutor(RuntimeError()),  # type: ignore[arg-type]
            audit_sink=MemoryAuditSink(),
            rate_limiter=limiter,
            failure_handler=notifications.append,
        )
        with self.assertRaises(OperatorRateLimitError):
            value.handle(request())
        self.assertEqual(notifications, ["RATE_CLOCK_FAILED"])
        self.assertEqual(value.health().status, HealthStatus.UNHEALTHY)

    def test_public_records_are_immutable_and_validate_fields(self) -> None:
        record = OperatorAuditRecord(
            observed_at_ns=UnixNanos(1),
            client_id="client",
            certificate_sha256="a" * 64,
            stage=OperatorAuditStage.REJECTED,
            result_code="REJECTED",
        )
        self.assertEqual(asdict(record)["client_id"], "client")
        with self.assertRaises(ValueError):
            OperatorAuditRecord(
                observed_at_ns=UnixNanos(1),
                client_id="client",
                certificate_sha256="a" * 64,
                stage=OperatorAuditStage.APPLIED,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
