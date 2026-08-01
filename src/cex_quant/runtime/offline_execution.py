"""Deterministic, fault-injectable execution port for offline acceptance."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import ClientOrderId, VenueOrderId
from cex_quant.execution import (
    CancelOrder,
    CancelResult,
    ExecutionOutcome,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    SubmitResult,
)
from cex_quant.oms import OrderRequest


class OfflineExecutionDirectiveKind(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFINITELY_NOT_SENT = "definitely_not_sent"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class OfflineExecutionDirective:
    kind: OfflineExecutionDirectiveKind
    reason: str = ""
    venue_order_id: VenueOrderId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, OfflineExecutionDirectiveKind):
            raise ValueError("kind must be an OfflineExecutionDirectiveKind")
        if self.reason and self.reason.strip() != self.reason:
            raise ValueError("directive reason must be trimmed")
        if self.kind is OfflineExecutionDirectiveKind.ACCEPT:
            if self.reason:
                raise ValueError("accepted directive cannot contain a reason")
        elif not self.reason:
            raise ValueError("non-accepted directive requires a reason")
        if (
            self.kind is not OfflineExecutionDirectiveKind.ACCEPT
            and self.venue_order_id is not None
        ):
            raise ValueError("only accepted directive can contain venue_order_id")


class OfflineExecutionScriptExhaustedError(RuntimeError):
    pass


class DeterministicOfflineExecutionPort:
    """Execute a predeclared script without network or venue side effects."""

    def __init__(
        self,
        directives: tuple[OfflineExecutionDirective, ...],
        *,
        cancel_directives: tuple[OfflineExecutionDirective, ...] = (),
    ) -> None:
        if not directives:
            raise ValueError("offline execution script cannot be empty")
        self._directives = deque(directives)
        self._cancel_directives = deque(cancel_directives)
        self._submissions: list[OrderRequest] = []
        self._cancellations: list[CancelOrder] = []

    @property
    def submissions(self) -> tuple[OrderRequest, ...]:
        return tuple(self._submissions)

    @property
    def remaining(self) -> int:
        return len(self._directives)

    @property
    def cancellations(self) -> tuple[CancelOrder, ...]:
        return tuple(self._cancellations)

    def submit(self, request: OrderRequest) -> SubmitResult:
        if not self._directives:
            raise OfflineExecutionScriptExhaustedError(
                "offline execution script is exhausted"
            )
        self._submissions.append(request)
        directive = self._directives.popleft()
        if directive.kind is OfflineExecutionDirectiveKind.ACCEPT:
            return SubmitResult(
                client_order_id=request.client_order_id,
                outcome=ExecutionOutcome.ACCEPTED,
                venue_order_id=(
                    directive.venue_order_id
                    or VenueOrderId(f"offline-{request.client_order_id}")
                ),
            )
        if directive.kind is OfflineExecutionDirectiveKind.REJECT:
            return SubmitResult(
                client_order_id=request.client_order_id,
                outcome=ExecutionOutcome.REJECTED,
                rejection_code="OFFLINE_REJECT",
                rejection_message=directive.reason,
            )
        if directive.kind is OfflineExecutionDirectiveKind.DEFINITELY_NOT_SENT:
            raise ExecutionTransportError(directive.reason)
        raise ExecutionStateUnknownError(directive.reason)

    def submitted_client_order_ids(self) -> tuple[ClientOrderId, ...]:
        return tuple(item.client_order_id for item in self._submissions)

    def cancel(self, command: CancelOrder) -> CancelResult:
        if not self._cancel_directives:
            raise OfflineExecutionScriptExhaustedError(
                "offline cancel script is exhausted"
            )
        self._cancellations.append(command)
        directive = self._cancel_directives.popleft()
        if directive.kind is OfflineExecutionDirectiveKind.ACCEPT:
            return CancelResult(
                client_order_id=command.client_order_id,
                outcome=ExecutionOutcome.ACCEPTED,
                venue_order_id=directive.venue_order_id,
            )
        if directive.kind is OfflineExecutionDirectiveKind.REJECT:
            return CancelResult(
                client_order_id=command.client_order_id,
                outcome=ExecutionOutcome.REJECTED,
                rejection_code="OFFLINE_CANCEL_REJECT",
                rejection_message=directive.reason,
            )
        if directive.kind is OfflineExecutionDirectiveKind.DEFINITELY_NOT_SENT:
            raise ExecutionTransportError(directive.reason)
        raise ExecutionStateUnknownError(directive.reason)


__all__ = [
    "DeterministicOfflineExecutionPort",
    "OfflineExecutionDirective",
    "OfflineExecutionDirectiveKind",
    "OfflineExecutionScriptExhaustedError",
]
