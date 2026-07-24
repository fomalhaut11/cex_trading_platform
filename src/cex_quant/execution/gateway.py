"""Execution gateway protocol and typed boundary failures."""

from typing import Protocol

from cex_quant.oms import OrderRequest

from .contracts import CancelOrder, CancelResult, SubmitResult


class ExecutionGateway(Protocol):
    """Asynchronous venue boundary; implementations own transport and signing."""

    async def submit(self, command: OrderRequest) -> SubmitResult:
        """Submit once using `command.client_order_id` as idempotency key."""

        ...

    async def cancel(self, command: CancelOrder) -> CancelResult:
        """Cancel the order identified by its original client order ID."""

        ...


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


__all__ = [
    "ExecutionGateway",
    "ExecutionGatewayError",
    "ExecutionStateUnknownError",
    "ExecutionTransportError",
    "InvalidExecutionRequestError",
    "UnsupportedExecutionFeatureError",
]
