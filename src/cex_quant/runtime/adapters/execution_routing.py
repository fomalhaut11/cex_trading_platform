"""Runtime-owned fail-closed routing by exact execution scope."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice
from types import MappingProxyType
from typing import Protocol

from cex_quant.core import AccountId
from cex_quant.execution import (
    CancelOrder,
    CancelResult,
    ExecutionGateway,
    InvalidExecutionRequestError,
    OrderReconciliationGateway,
    QueryOrder,
    SubmitResult,
)
from cex_quant.instruments import InstrumentId
from cex_quant.oms import OrderReconciliationSnapshot, OrderRequest

MAX_CONFIGURED_EXECUTION_ROUTES = 256


class RoutedExecutionGateway(
    ExecutionGateway,
    OrderReconciliationGateway,
    Protocol,
):
    """A configured child-order gateway with reconciliation support."""


class ExecutionRoutingError(InvalidExecutionRequestError):
    """An execution command referenced an unconfigured exact scope."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExactExecutionRoute:
    """Bind one exact account/instrument scope to a configured gateway."""

    account_id: AccountId
    instrument_id: InstrumentId
    gateway: RoutedExecutionGateway

    def __post_init__(self) -> None:
        if not self.account_id or self.account_id.strip() != self.account_id:
            raise ValueError("route account_id must be a non-empty trimmed string")
        for operation in ("submit", "cancel", "query_order"):
            if not callable(getattr(self.gateway, operation, None)):
                raise ValueError(
                    "route gateway must provide submit, cancel, and query_order"
                )

    @property
    def scope(self) -> tuple[AccountId, InstrumentId]:
        return self.account_id, self.instrument_id


class ExactExecutionGatewayRouter:
    """Dispatch child commands through an immutable exact-scope allowlist.

    The router is independent of strategy leg count and venue product mix. It
    never infers a route from a symbol, instrument kind, venue, or fallback.
    Product-specific gateways remain responsible for canonical request
    validation before external I/O.
    """

    def __init__(
        self,
        routes: Iterable[ExactExecutionRoute],
        *,
        max_configured_routes: int = MAX_CONFIGURED_EXECUTION_ROUTES,
    ) -> None:
        if max_configured_routes <= 0:
            raise ValueError("max_configured_routes must be positive")
        configured = tuple(islice(iter(routes), max_configured_routes + 1))
        if not configured:
            raise ValueError("exact execution router requires at least one route")
        if len(configured) > max_configured_routes:
            raise ValueError("exact execution router exceeds max_configured_routes")
        by_scope: dict[
            tuple[AccountId, InstrumentId],
            RoutedExecutionGateway,
        ] = {}
        for route in configured:
            if not isinstance(route, ExactExecutionRoute):
                raise ValueError("routes must contain ExactExecutionRoute values")
            if route.scope in by_scope:
                raise ValueError(
                    "execution routes contain a duplicate account/instrument scope"
                )
            by_scope[route.scope] = route.gateway
        self._routes = configured
        self._by_scope = MappingProxyType(by_scope)

    @property
    def routes(self) -> tuple[ExactExecutionRoute, ...]:
        return self._routes

    def gateway_for(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
    ) -> RoutedExecutionGateway:
        try:
            return self._by_scope[(account_id, instrument_id)]
        except KeyError as error:
            raise ExecutionRoutingError(
                "execution route is not configured for "
                f"account={account_id}, instrument={instrument_id}"
            ) from error

    async def submit(self, command: OrderRequest) -> SubmitResult:
        gateway = self.gateway_for(command.account_id, command.instrument_id)
        return await gateway.submit(command)

    async def cancel(self, command: CancelOrder) -> CancelResult:
        gateway = self.gateway_for(command.account_id, command.instrument_id)
        return await gateway.cancel(command)

    async def query_order(
        self,
        command: QueryOrder,
    ) -> OrderReconciliationSnapshot | None:
        gateway = self.gateway_for(command.account_id, command.instrument_id)
        return await gateway.query_order(command)


__all__ = [
    "MAX_CONFIGURED_EXECUTION_ROUTES",
    "ExactExecutionGatewayRouter",
    "ExactExecutionRoute",
    "ExecutionRoutingError",
    "RoutedExecutionGateway",
]
