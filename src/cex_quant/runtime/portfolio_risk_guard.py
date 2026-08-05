"""Runtime composition for ADR-012 immediate pre-I/O authorization."""

from __future__ import annotations

from collections.abc import Callable

from cex_quant.core import OrderGroupId, UnixNanos
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionStage,
    ExecutionStagePermit,
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


class PortfolioRiskExecutionStageGuard:
    """Consume aggregate Stage authority before one width-one Child I/O."""

    def __init__(
        self,
        *,
        coordinator: PortfolioRiskCoordinator,
        stage: ExecutionStage,
        permit: ExecutionStagePermit,
        group_view: Callable[[OrderGroupId], OrderGroupView],
        now_ns: Callable[[], UnixNanos],
        platform_guard: ExternalSubmitGuardPort,
    ) -> None:
        if len(stage.actions) != 1 or len(permit.action_permits) != 1:
            raise ValueError("current Stage guard supports width one")
        self._coordinator = coordinator
        self._stage = stage
        self._permit = permit
        self._action = stage.actions[0]
        self._action_permit = permit.action_permits[0]
        self._group_view = group_view
        self._now_ns = now_ns
        self._platform_guard = platform_guard

    def assert_submit_allowed(self, request: OrderRequest) -> None:
        if (
            request.client_order_id
            != child_order_id_for_action(self._action.action_id)
            or request.approval_id != str(self._action_permit.permit_id)
        ):
            raise ValueError("request does not match guarded Stage Action")
        self._platform_guard.assert_submit_allowed(request)
        group = self._group_view(self._stage.group_id)
        now_ns = self._now_ns()
        self._coordinator.consume_stage_for_external_io(
            permit=self._permit,
            stage=self._stage,
            group=group,
            now_ns=now_ns,
        )
        self._coordinator.consume_for_external_io(
            permit=self._action_permit,
            action=self._action,
            group=group,
            now_ns=now_ns,
            stage_permit=self._permit,
        )


__all__ = [
    "PortfolioRiskExecutionGuard",
    "PortfolioRiskExecutionStageGuard",
]
