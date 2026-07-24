"""Execution gateway protocol and typed boundary failures."""

from typing import Protocol

from cex_quant.oms import OrderReconciliationSnapshot, OrderRequest

from .contracts import CancelOrder, CancelResult, QueryOrder, SubmitResult


class ExecutionGateway(Protocol):
    """Asynchronous venue boundary; implementations own transport and signing."""

    async def submit(self, command: OrderRequest) -> SubmitResult:
        """Submit once using `command.client_order_id` as idempotency key."""

        ...

    async def cancel(self, command: CancelOrder) -> CancelResult:
        """Cancel the order identified by its original client order ID."""

        ...


class OrderReconciliationGateway(Protocol):
    """Read-only venue lookup used after unknown state or OMS restart."""

    async def query_order(
        self,
        command: QueryOrder,
    ) -> OrderReconciliationSnapshot | None: ...


class ExecutionGatewayError(Exception):
    """Base class for typed execution-boundary failures."""


class InvalidExecutionRequestError(ExecutionGatewayError, ValueError):
    """The canonical request is invalid for the selected venue product."""


class UnsupportedExecutionFeatureError(ExecutionGatewayError):
    """The venue product cannot express a requested canonical feature."""


class ExecutionTransportError(ExecutionGatewayError):
    """The request was definitely not accepted by the venue transport."""


class ExecutionStateUnknownError(ExecutionGatewayError):
    """Transport failed after send and venue acceptance is unknown."""


class ExecutionQueryError(ExecutionGatewayError):
    """A read-only venue order query was rejected or unusable."""


__all__ = [
    "ExecutionGateway",
    "ExecutionGatewayError",
    "ExecutionQueryError",
    "ExecutionStateUnknownError",
    "ExecutionTransportError",
    "InvalidExecutionRequestError",
    "OrderReconciliationGateway",
    "UnsupportedExecutionFeatureError",
]
