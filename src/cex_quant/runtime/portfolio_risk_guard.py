"""Runtime composition for ADR-012 immediate pre-I/O authorization."""

from __future__ import annotations

from collections.abc import Callable

from cex_quant.core import OrderGroupId, UnixNanos
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionPermit,
    OrderGroupView,
    OrderRequest,
    child_order_id_for_action,
)
from cex_quant.risk import PortfolioRiskCoordinator

from .execution_handoff import ExternalSubmitGuardPort


class PortfolioRiskExecutionGuard:
    """Combine platform safety and one exact consumable Portfolio Risk permit."""

    def __init__(
        self,
        *,
        coordinator: PortfolioRiskCoordinator,
        action: ExecutionAction,
        permit: ExecutionActionPermit,
        group_view: Callable[[OrderGroupId], OrderGroupView],
        now_ns: Callable[[], UnixNanos],
        platform_guard: ExternalSubmitGuardPort,
    ) -> None:
        self._coordinator = coordinator
        self._action = action
        self._permit = permit
        self._group_view = group_view
        self._now_ns = now_ns
        self._platform_guard = platform_guard

    def assert_submit_allowed(self, request: OrderRequest) -> None:
        """Run every check after durable SUBMITTING and consume Risk authority."""

        if (
            request.client_order_id
            != child_order_id_for_action(self._action.action_id)
            or request.approval_id != str(self._permit.permit_id)
        ):
            raise ValueError("request does not match guarded group action")
        self._platform_guard.assert_submit_allowed(request)
        self._coordinator.consume_for_external_io(
            permit=self._permit,
            action=self._action,
            group=self._group_view(self._action.group_id),
            now_ns=self._now_ns(),
        )


__all__ = ["PortfolioRiskExecutionGuard"]
