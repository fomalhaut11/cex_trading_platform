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
    CancelRequestedEntry,
    OmsJournal,
    OrderCreatedEntry,
    OrderEvent,
    OrderReconciliationSnapshot,
    OrderRequest,
    OrderSide,
    OrderStateError,
    OrderStateMachine,
    OrderStatus,
    OrderSubmittingEntry,
    OrderType,
    OrderUpdateResult,
    OrderView,
    PositionSide,
    ReconciliationDisposition,
    ReconciliationResult,
    ReconciliationSource,
    TimeInForce,
    UpdateDisposition,
    VenueEventEntry,
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


class OmsPersistenceError(RuntimeError):
    """Raised after journal durability fails and OMS latches fail-closed."""


class OmsRecoveryError(RuntimeError):
    """Raised when journal history cannot rebuild canonical order state."""


class CanonicalOmsApplicationService:
    """Own canonical order state with optional durable journal recovery."""

    def __init__(
        self,
        *,
        accounts: AccountPolicy,
        identities: OmsIdentityPolicy,
        orders: OrderPolicy,
        now_ns: Callable[[], UnixNanos],
        journal: OmsJournal | None = None,
    ) -> None:
        self._accounts = accounts
        self._identities = identities
        self._orders = orders
        self._now_ns = now_ns
        self._journal = journal
        self._persistence_failure: Exception | None = None
        self._machines: dict[ClientOrderId, OrderStateMachine] = {}
        self._recover()

    def create_order(
        self,
        intent: PositionTargetIntent,
        approval: RiskDecision,
    ) -> OrderRequest:
        self._assert_persistence_healthy()
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
        self._persist(OrderCreatedEntry(request=request))
        self._machines[request.client_order_id] = OrderStateMachine(request)
        return request

    def mark_submitting(
        self,
        client_order_id: ClientOrderId,
        *,
        at_ns: UnixNanos,
    ) -> OrderView:
        self._assert_persistence_healthy()
        view = self._machine(client_order_id).mark_submitting(at_ns=at_ns)
        self._persist(
            OrderSubmittingEntry(
                client_order_id=client_order_id,
                at_ns=at_ns,
            )
        )
        return view

    def request_cancel(
        self,
        client_order_id: ClientOrderId,
        *,
        at_ns: UnixNanos,
    ) -> OrderView:
        self._assert_persistence_healthy()
        view = self._machine(client_order_id).request_cancel(at_ns=at_ns)
        self._persist(
            CancelRequestedEntry(
                client_order_id=client_order_id,
                at_ns=at_ns,
            )
        )
        return view

    def apply_venue_update(self, event: OrderEvent) -> OrderView:
        self._assert_persistence_healthy()
        return self._apply_event(event).after

    def order(self, client_order_id: ClientOrderId) -> OrderView:
        return self._machine(client_order_id).view()

    def orders(self) -> tuple[OrderView, ...]:
        return tuple(
            self._machines[client_order_id].view()
            for client_order_id in sorted(self._machines, key=str)
        )

    def reconciliation_candidates(self) -> tuple[OrderView, ...]:
        """Return orders whose venue state must be checked after restart."""

        candidates = {
            OrderStatus.SUBMITTING,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }
        return tuple(view for view in self.orders() if view.status in candidates)

    def reconcile(
        self,
        snapshot: OrderReconciliationSnapshot,
    ) -> ReconciliationResult:
        """Apply one normalized REST or user-stream venue observation."""

        self._assert_persistence_healthy()
        machine = self._machine(snapshot.client_order_id)
        current = machine.view()
        fill_conflict = _reconciliation_fill_conflict(snapshot, current)
        if fill_conflict:
            return ReconciliationResult(
                disposition=ReconciliationDisposition.CONFLICT,
                order=current,
                reason=fill_conflict,
            )
        if _is_consistent(snapshot, current):
            return ReconciliationResult(
                disposition=ReconciliationDisposition.ALREADY_CONSISTENT,
                order=current,
            )
        if current.is_terminal:
            return ReconciliationResult(
                disposition=ReconciliationDisposition.CONFLICT,
                order=current,
                reason=(
                    "venue observation conflicts with terminal canonical state"
                ),
            )
        if current.status is OrderStatus.CREATED:
            self.mark_submitting(
                snapshot.client_order_id,
                at_ns=snapshot.observed_at_ns,
            )
        try:
            update = self._apply_event(snapshot.as_order_event())
        except OrderStateError as error:
            return ReconciliationResult(
                disposition=ReconciliationDisposition.CONFLICT,
                order=machine.view(),
                reason=str(error),
            )
        disposition = (
            ReconciliationDisposition.DUPLICATE
            if update.disposition is UpdateDisposition.DUPLICATE
            else ReconciliationDisposition.APPLIED
        )
        return ReconciliationResult(
            disposition=disposition,
            order=update.after,
        )

    def reconcile_not_found(
        self,
        client_order_id: ClientOrderId,
        *,
        source: ReconciliationSource,
        observed_at_ns: UnixNanos,
    ) -> ReconciliationResult:
        """Report a completed venue lookup that did not find the order."""

        del observed_at_ns
        if not isinstance(source, ReconciliationSource):
            raise ValueError("source must be a ReconciliationSource")
        current = self.order(client_order_id)
        return ReconciliationResult(
            disposition=ReconciliationDisposition.NOT_FOUND,
            order=current,
            reason=(
                f"{source.value} did not find the order; "
                "absence is not treated as a terminal venue outcome"
            ),
        )

    def _apply_event(self, event: OrderEvent) -> OrderUpdateResult:
        update = self._machine(event.client_order_id).apply_venue_update(event)
        if update.disposition is UpdateDisposition.APPLIED:
            self._persist(VenueEventEntry(event=event))
        return update

    def _machine(self, client_order_id: ClientOrderId) -> OrderStateMachine:
        try:
            return self._machines[client_order_id]
        except KeyError as error:
            raise KeyError(f"unknown client_order_id: {client_order_id}") from error

    def _recover(self) -> None:
        if self._journal is None:
            return
        try:
            for entry in self._journal.read():
                if isinstance(entry, OrderCreatedEntry):
                    client_order_id = entry.request.client_order_id
                    if client_order_id in self._machines:
                        raise OmsRecoveryError(
                            f"duplicate recovered order: {client_order_id}"
                        )
                    self._machines[client_order_id] = OrderStateMachine(
                        entry.request
                    )
                elif isinstance(entry, OrderSubmittingEntry):
                    self._machine(entry.client_order_id).mark_submitting(
                        at_ns=entry.at_ns
                    )
                elif isinstance(entry, CancelRequestedEntry):
                    self._machine(entry.client_order_id).request_cancel(
                        at_ns=entry.at_ns
                    )
                elif isinstance(entry, VenueEventEntry):
                    self._machine(
                        entry.event.client_order_id
                    ).apply_venue_update(entry.event)
        except OmsRecoveryError:
            raise
        except (KeyError, OrderStateError, ValueError) as error:
            raise OmsRecoveryError(
                f"invalid OMS recovery history: {error}"
            ) from error

    def _persist(
        self,
        entry: (
            OrderCreatedEntry
            | OrderSubmittingEntry
            | CancelRequestedEntry
            | VenueEventEntry
        ),
    ) -> None:
        if self._journal is None:
            return
        try:
            self._journal.append(entry)
        except Exception as error:
            self._persistence_failure = error
            raise OmsPersistenceError(
                "OMS journal append failed; mutations are latched fail-closed"
            ) from error

    def _assert_persistence_healthy(self) -> None:
        if self._persistence_failure is not None:
            raise OmsPersistenceError(
                "OMS persistence is unhealthy; restart and reconcile required"
            ) from self._persistence_failure


def _is_consistent(
    snapshot: OrderReconciliationSnapshot,
    current: OrderView,
) -> bool:
    venue_id_matches = (
        snapshot.venue_order_id is None
        or current.venue_order_id == snapshot.venue_order_id
    )
    average_matches = (
        snapshot.average_fill_price is None
        or current.average_fill_price == snapshot.average_fill_price
    )
    return (
        snapshot.status is current.status
        and snapshot.cumulative_filled_quantity
        == current.cumulative_filled_quantity
        and venue_id_matches
        and average_matches
    )


def _reconciliation_fill_conflict(
    snapshot: OrderReconciliationSnapshot,
    current: OrderView,
) -> str:
    filled = snapshot.cumulative_filled_quantity.as_decimal()
    local_filled = current.cumulative_filled_quantity.as_decimal()
    requested = current.request.quantity.as_decimal()
    if snapshot.observed_at_ns < current.request.created_at_ns:
        return "venue observation predates canonical order creation"
    if filled < local_filled:
        return "venue cumulative fill is behind canonical state"
    if filled > requested:
        return "venue cumulative fill exceeds requested quantity"
    if snapshot.status is OrderStatus.FILLED and filled != requested:
        return "FILLED venue status does not contain the full quantity"
    if snapshot.status is OrderStatus.PARTIALLY_FILLED and not (
        0 < filled < requested
    ):
        return "PARTIALLY_FILLED venue status has invalid cumulative fill"
    return ""


__all__ = [
    "AccountPolicy",
    "CanonicalOmsApplicationService",
    "OmsIdentityPolicy",
    "OmsInvariantError",
    "OmsPersistenceError",
    "OmsRecoveryError",
    "OrderParameters",
    "OrderPolicy",
]
