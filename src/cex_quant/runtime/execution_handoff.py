"""Shared durable-before-external-I/O submission boundary."""

from __future__ import annotations

from typing import Protocol

from cex_quant.core import ClientOrderId
from cex_quant.execution import (
    ExecutionStateUnknownError,
    ExecutionTransportError,
    SubmitResult,
)
from cex_quant.oms import OrderRequest, OrderSubmitOutcome


class DurableSubmitStatePort(Protocol):
    """OMS-side state needed by the shared submit handoff."""

    def prepare_submit(self, request: OrderRequest) -> object: ...

    def record_submit_result(self, result: SubmitResult) -> object: ...

    def record_submit_failure(
        self,
        client_order_id: ClientOrderId,
        *,
        outcome: OrderSubmitOutcome,
        reason: str,
    ) -> object: ...


class SynchronousExecutionSubmitPort(Protocol):
    def submit(self, request: OrderRequest) -> SubmitResult: ...


class ExternalSubmitGuardPort(Protocol):
    """Recheck runtime/operator authority immediately before external I/O."""

    def assert_submit_allowed(self, request: OrderRequest) -> None: ...


class ExternalSubmitBlockedError(RuntimeError):
    """A durable submit intent was stopped before reaching Execution."""


class DurableExecutionHandoff:
    """Persist SUBMITTING before I/O and persist every immediate outcome."""

    def __init__(
        self,
        *,
        oms: DurableSubmitStatePort,
        execution: SynchronousExecutionSubmitPort,
        guard: ExternalSubmitGuardPort,
    ) -> None:
        self._oms = oms
        self._execution = execution
        self._guard = guard

    def submit(self, request: OrderRequest) -> SubmitResult:
        self._oms.prepare_submit(request)
        try:
            self._guard.assert_submit_allowed(request)
        except Exception as error:
            self._record_failure(
                request.client_order_id,
                outcome=OrderSubmitOutcome.DEFINITELY_NOT_SENT,
                error=error,
            )
            raise ExternalSubmitBlockedError(
                "external submit blocked by the immediate safety recheck"
            ) from error
        try:
            result = self._execution.submit(request)
        except ExecutionTransportError as error:
            self._record_failure(
                request.client_order_id,
                outcome=OrderSubmitOutcome.DEFINITELY_NOT_SENT,
                error=error,
            )
            raise
        except ExecutionStateUnknownError as error:
            self._record_failure(
                request.client_order_id,
                outcome=OrderSubmitOutcome.UNKNOWN,
                error=error,
            )
            raise
        except Exception as error:
            self._record_failure(
                request.client_order_id,
                outcome=OrderSubmitOutcome.UNKNOWN,
                error=error,
            )
            raise
        if result.client_order_id != request.client_order_id:
            self._oms.record_submit_failure(
                request.client_order_id,
                outcome=OrderSubmitOutcome.UNKNOWN,
                reason="execution result client_order_id mismatch",
            )
            raise RuntimeError("execution result does not belong to submitted order")
        self._oms.record_submit_result(result)
        return result

    def _record_failure(
        self,
        client_order_id: ClientOrderId,
        *,
        outcome: OrderSubmitOutcome,
        error: Exception,
    ) -> None:
        reason = str(error).strip() or type(error).__name__
        self._oms.record_submit_failure(
            client_order_id,
            outcome=outcome,
            reason=reason[:512],
        )


__all__ = [
    "DurableExecutionHandoff",
    "DurableSubmitStatePort",
    "ExternalSubmitBlockedError",
    "ExternalSubmitGuardPort",
    "SynchronousExecutionSubmitPort",
]
