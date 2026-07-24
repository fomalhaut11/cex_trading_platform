"""Canonical OMS application service used by the runtime pipeline."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    Price,
    Quantity,
    UnixNanos,
)
from cex_quant.oms import (
    ApprovedOrderIntent,
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStateMachine,
    OrderType,
    OrderView,
    PositionSide,
    TimeInForce,
)
from cex_quant.risk import RiskDecision
from cex_quant.strategy import PositionTargetIntent


class AccountPolicy(Protocol):
    def account_id(self, intent: PositionTargetIntent) -> AccountId: ...


class OmsIdentityPolicy(Protocol):
    def approval_id(
        self,
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> str: ...

    def client_order_id(
        self,
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> ClientOrderId: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderParameters:
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    time_in_force: TimeInForce = TimeInForce.GTC
    limit_price: Price | None = None
    stop_price: Price | None = None
    reduce_only: bool = False
    post_only: bool = False
    position_side: PositionSide = PositionSide.NET


class OrderPolicy(Protocol):
    """Translate an approved target into an explicit executable instruction."""

    def parameters(
        self,
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> OrderParameters: ...


class OmsInvariantError(RuntimeError):
    pass


class CanonicalOmsApplicationService:
    """Create canonical requests and own their single-writer state machines."""

    def __init__(
        self,
        *,
        accounts: AccountPolicy,
        identities: OmsIdentityPolicy,
        orders: OrderPolicy,
        now_ns: Callable[[], UnixNanos],
    ) -> None:
        self._accounts = accounts
        self._identities = identities
        self._orders = orders
        self._now_ns = now_ns
        self._machines: dict[ClientOrderId, OrderStateMachine] = {}

    def create_order(
        self,
        intent: PositionTargetIntent,
        approval: RiskDecision,
    ) -> OrderRequest:
        if not approval.allowed:
            raise OmsInvariantError("OMS cannot create an order from a rejection")
        if approval.intent != intent:
            raise OmsInvariantError("risk decision does not belong to intent")

        created_at_ns = self._now_ns()
        parameters = self._orders.parameters(intent, approval)
        approved = ApprovedOrderIntent(
            approval_id=self._identities.approval_id(intent, approval),
            intent_id=intent.intent_id,
            account_id=self._accounts.account_id(intent),
            instrument_id=intent.instrument_id,
            side=parameters.side,
            order_type=parameters.order_type,
            quantity=parameters.quantity,
            approved_at_ns=created_at_ns,
            valid_until_ns=intent.valid_until_ns,
            time_in_force=parameters.time_in_force,
            limit_price=parameters.limit_price,
            stop_price=parameters.stop_price,
            reduce_only=parameters.reduce_only,
            post_only=parameters.post_only,
            position_side=parameters.position_side,
        )
        request = OrderRequest.from_approved_intent(
            approved,
            client_order_id=self._identities.client_order_id(intent, approval),
            created_at_ns=created_at_ns,
        )
        if request.client_order_id in self._machines:
            raise OmsInvariantError("client_order_id is already owned by OMS")
        self._machines[request.client_order_id] = OrderStateMachine(request)
        return request

    def mark_submitting(
        self,
        client_order_id: ClientOrderId,
        *,
        at_ns: UnixNanos,
    ) -> OrderView:
        return self._machine(client_order_id).mark_submitting(at_ns=at_ns)

    def apply_venue_update(self, event: OrderEvent) -> OrderView:
        return self._machine(event.client_order_id).apply_venue_update(event).after

    def order(self, client_order_id: ClientOrderId) -> OrderView:
        return self._machine(client_order_id).view()

    def _machine(self, client_order_id: ClientOrderId) -> OrderStateMachine:
        try:
            return self._machines[client_order_id]
        except KeyError as error:
            raise KeyError(f"unknown client_order_id: {client_order_id}") from error


__all__ = [
    "AccountPolicy",
    "CanonicalOmsApplicationService",
    "OmsIdentityPolicy",
    "OmsInvariantError",
    "OrderParameters",
    "OrderPolicy",
]
