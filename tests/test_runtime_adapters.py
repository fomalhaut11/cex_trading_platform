import asyncio
from threading import get_ident
from unittest import TestCase

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.execution import (
    CancelResult,
    ExecutionOutcome,
    SubmitResult,
)
from cex_quant.features import FeatureSnapshot
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data.state import (
    MarketStateStatus,
    StateUpdateResult,
    UpdateDisposition,
)
from cex_quant.oms import OrderSide, OrderType
from cex_quant.risk import RiskDecision, RiskDecisionStatus, RiskRejectReason
from cex_quant.runtime import (
    AsyncExecutionPortBridge,
    CanonicalOmsApplicationService,
    ExecutionBridgeStateError,
    FeatureEngineAdapter,
    MarketStateGateAdapter,
    OmsInvariantError,
    OrderParameters,
)
from cex_quant.strategy import PositionTargetIntent

INSTRUMENT = InstrumentId(
    venue=VenueId("TEST"),
    kind=InstrumentKind.SPOT,
    symbol="BTCUSDT",
)


def intent() -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId("intent-1"),
        strategy_id=StrategyId("strategy-1"),
        instrument_id=INSTRUMENT,
        target_quantity=Quantity.from_str("2"),
        decision_time_ns=UnixNanos(100),
        valid_until_ns=UnixNanos(200),
    )


def decision(*, allowed: bool = True) -> RiskDecision:
    value = intent()
    return RiskDecision(
        status=(
            RiskDecisionStatus.ALLOW
            if allowed
            else RiskDecisionStatus.REJECT
        ),
        intent=value,
        reasons=() if allowed else (RiskRejectReason.CLOCK_UNHEALTHY,),
        projected_strategy_position=value.target_quantity,
        projected_global_position=value.target_quantity,
        projected_strategy_notional=None,
        projected_global_notional=None,
    )


class _Engine:
    def __init__(self) -> None:
        self.events: list[object] = []
        self.value = FeatureSnapshot(scope="BTCUSDT", values=())

    def on_event(self, event: object) -> object:
        self.events.append(event)
        return object()

    def snapshot(self) -> FeatureSnapshot:
        return self.value


class _Updater:
    def __init__(self, result: StateUpdateResult) -> None:
        self.result = result

    def apply(self, event: object) -> StateUpdateResult:
        del event
        return self.result


class _Accounts:
    def account_id(self, value: PositionTargetIntent) -> AccountId:
        del value
        return AccountId("primary")


class _Identities:
    def approval_id(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> str:
        del value, approval
        return "approval-1"

    def client_order_id(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> ClientOrderId:
        del value, approval
        return ClientOrderId("client-1")


class _Orders:
    def parameters(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> OrderParameters:
        del value, approval
        return OrderParameters(
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity.from_str("2"),
        )


class _Gateway:
    def __init__(self) -> None:
        self.thread_id: int | None = None

    async def submit(self, command: object) -> SubmitResult:
        self.thread_id = get_ident()
        return SubmitResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )

    async def cancel(self, command: object) -> CancelResult:
        raise NotImplementedError


class RuntimeAdapterTests(TestCase):
    def test_feature_adapter_updates_before_snapshot(self) -> None:
        engine = _Engine()
        adapter = FeatureEngineAdapter(engine)  # type: ignore[arg-type]
        marker = object()

        snapshot = adapter.on_event(marker)  # type: ignore[arg-type]

        self.assertEqual(engine.events, [marker])
        self.assertIs(snapshot, engine.value)

    def test_market_state_gate_requires_live_usable_result(self) -> None:
        accepted = MarketStateGateAdapter(
            _Updater(
                StateUpdateResult(
                    disposition=UpdateDisposition.INITIALIZED,
                    status=MarketStateStatus.LIVE,
                    sequence=1,
                )
            )
        ).apply(object())  # type: ignore[arg-type]
        rejected = MarketStateGateAdapter(
            _Updater(
                StateUpdateResult(
                    disposition=UpdateDisposition.GAP_DETECTED,
                    status=MarketStateStatus.GAP,
                    sequence=1,
                    reason="missing update",
                )
            )
        ).apply(object())  # type: ignore[arg-type]

        self.assertTrue(accepted.accepted)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "missing update")

    def test_oms_requires_approval_and_owns_state_machine(self) -> None:
        service = CanonicalOmsApplicationService(
            accounts=_Accounts(),
            identities=_Identities(),
            orders=_Orders(),
            now_ns=lambda: UnixNanos(150),
        )

        request = service.create_order(intent(), decision())
        view = service.order(request.client_order_id)

        self.assertEqual(request.account_id, AccountId("primary"))
        self.assertEqual(view.request, request)
        self.assertEqual(
            service.mark_submitting(
                request.client_order_id,
                at_ns=UnixNanos(151),
            ).status.value,
            "submitting",
        )
        with self.assertRaises(OmsInvariantError):
            service.create_order(intent(), decision(allowed=False))

    def test_oms_rejects_duplicate_policy_identifier(self) -> None:
        service = CanonicalOmsApplicationService(
            accounts=_Accounts(),
            identities=_Identities(),
            orders=_Orders(),
            now_ns=lambda: UnixNanos(150),
        )
        service.create_order(intent(), decision())
        with self.assertRaisesRegex(OmsInvariantError, "already owned"):
            service.create_order(intent(), decision())

    def test_async_gateway_runs_on_owned_loop_thread(self) -> None:
        gateway = _Gateway()
        service = CanonicalOmsApplicationService(
            accounts=_Accounts(),
            identities=_Identities(),
            orders=_Orders(),
            now_ns=lambda: UnixNanos(150),
        )
        request = service.create_order(intent(), decision())
        bridge = AsyncExecutionPortBridge(gateway)
        bridge.start()
        try:
            result = bridge.submit(request)
        finally:
            bridge.close()

        self.assertEqual(result.outcome, ExecutionOutcome.ACCEPTED)
        self.assertNotEqual(gateway.thread_id, get_ident())

    def test_bridge_rejects_blocking_call_inside_running_loop(self) -> None:
        gateway = _Gateway()
        service = CanonicalOmsApplicationService(
            accounts=_Accounts(),
            identities=_Identities(),
            orders=_Orders(),
            now_ns=lambda: UnixNanos(150),
        )
        request = service.create_order(intent(), decision())
        bridge = AsyncExecutionPortBridge(gateway)
        bridge.start()

        async def misuse() -> None:
            with self.assertRaisesRegex(
                ExecutionBridgeStateError,
                "active event loop",
            ):
                bridge.submit(request)

        try:
            asyncio.run(misuse())
        finally:
            bridge.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
