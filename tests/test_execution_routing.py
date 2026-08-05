from __future__ import annotations

from threading import get_ident
from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.execution import (
    CancelOrder,
    CancelResult,
    ExecutionOutcome,
    QueryOrder,
    SubmitResult,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    OrderReconciliationSnapshot,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    ReconciliationSource,
)
from cex_quant.runtime import (
    AsyncExecutionPortBridge,
    ExactExecutionGatewayRouter,
    ExactExecutionRoute,
    ExecutionRoutingError,
)

PRIMARY = AccountId("primary")
SECONDARY = AccountId("secondary")
BTC_SPOT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.SPOT,
    symbol="BTCUSDT",
)
ETH_SPOT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.SPOT,
    symbol="ETHUSDT",
)
ETH_BTC_SPOT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.SPOT,
    symbol="ETHBTC",
)
BTC_PERPETUAL = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)
BTC_CALL = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.OPTION,
    symbol="BTC-250926-100000-C",
)
BTC_PUT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.OPTION,
    symbol="BTC-250926-100000-P",
)
OKX_BTC_PERPETUAL = InstrumentId(
    venue=VenueId("OKX"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTC-USDT-SWAP",
)


def order(
    instrument_id: InstrumentId,
    account_id: AccountId = PRIMARY,
) -> OrderRequest:
    return OrderRequest(
        client_order_id=ClientOrderId(
            f"client-{instrument_id.kind.value}-{instrument_id.symbol}"
        ),
        approval_id="approval-1",
        intent_id=IntentId("intent-1"),
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity.from_str("0.001"),
        created_at_ns=UnixNanos(100),
    )


def cancel(
    instrument_id: InstrumentId,
    account_id: AccountId = PRIMARY,
) -> CancelOrder:
    return CancelOrder(
        account_id=account_id,
        instrument_id=instrument_id,
        client_order_id=ClientOrderId(
            f"client-{instrument_id.kind.value}-{instrument_id.symbol}"
        ),
    )


def query(
    instrument_id: InstrumentId,
    account_id: AccountId = PRIMARY,
) -> QueryOrder:
    return QueryOrder(
        account_id=account_id,
        instrument_id=instrument_id,
        client_order_id=ClientOrderId(
            f"client-{instrument_id.kind.value}-{instrument_id.symbol}"
        ),
    )


class _Gateway:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: list[tuple[str, AccountId, InstrumentId, int]] = []

    async def submit(self, command: OrderRequest) -> SubmitResult:
        self.calls.append(
            ("submit", command.account_id, command.instrument_id, get_ident())
        )
        return SubmitResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )

    async def cancel(self, command: CancelOrder) -> CancelResult:
        self.calls.append(
            ("cancel", command.account_id, command.instrument_id, get_ident())
        )
        return CancelResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )

    async def query_order(
        self,
        command: QueryOrder,
    ) -> OrderReconciliationSnapshot | None:
        self.calls.append(
            ("query", command.account_id, command.instrument_id, get_ident())
        )
        return OrderReconciliationSnapshot(
            source=ReconciliationSource.REST_QUERY,
            source_update_id=f"query-{self.label}",
            client_order_id=command.client_order_id,
            status=OrderStatus.OPEN,
            cumulative_filled_quantity=Quantity.from_str("0"),
            observed_at_ns=UnixNanos(200),
        )


def exact_route(
    instrument_id: InstrumentId,
    gateway: _Gateway,
    account_id: AccountId = PRIMARY,
) -> ExactExecutionRoute:
    return ExactExecutionRoute(
        account_id=account_id,
        instrument_id=instrument_id,
        gateway=gateway,
    )


def two_route_router() -> tuple[
    ExactExecutionGatewayRouter,
    _Gateway,
    _Gateway,
]:
    spot = _Gateway("spot")
    derivative = _Gateway("derivative")
    return (
        ExactExecutionGatewayRouter(
            (
                exact_route(BTC_SPOT, spot),
                exact_route(BTC_PERPETUAL, derivative),
            )
        ),
        spot,
        derivative,
    )


class ExactExecutionGatewayRouterTests(IsolatedAsyncioTestCase):
    async def test_routes_all_operations_by_exact_scope(self) -> None:
        router, spot, derivative = two_route_router()

        submit_result = await router.submit(order(BTC_SPOT))
        cancel_result = await router.cancel(cancel(BTC_PERPETUAL))
        query_result = await router.query_order(query(BTC_SPOT))

        self.assertIs(submit_result.outcome, ExecutionOutcome.ACCEPTED)
        self.assertIs(cancel_result.outcome, ExecutionOutcome.ACCEPTED)
        assert query_result is not None
        self.assertEqual(query_result.source_update_id, "query-spot")
        self.assertEqual(
            [
                (operation, account, instrument)
                for operation, account, instrument, _ in spot.calls
            ],
            [
                ("submit", PRIMARY, BTC_SPOT),
                ("query", PRIMARY, BTC_SPOT),
            ],
        )
        self.assertEqual(
            [
                (operation, account, instrument)
                for operation, account, instrument, _ in derivative.calls
            ],
            [("cancel", PRIMARY, BTC_PERPETUAL)],
        )

    async def test_same_instrument_routes_independently_by_account(self) -> None:
        primary = _Gateway("primary")
        secondary = _Gateway("secondary")
        router = ExactExecutionGatewayRouter(
            [
                exact_route(BTC_SPOT, primary, PRIMARY),
                exact_route(BTC_SPOT, secondary, SECONDARY),
            ]
        )

        await router.submit(order(BTC_SPOT, PRIMARY))
        await router.submit(order(BTC_SPOT, SECONDARY))

        self.assertEqual(primary.calls[0][1:3], (PRIMARY, BTC_SPOT))
        self.assertEqual(secondary.calls[0][1:3], (SECONDARY, BTC_SPOT))

    async def test_unknown_scope_is_rejected_before_dispatch(self) -> None:
        router, spot, derivative = two_route_router()

        for command in (
            order(ETH_SPOT),
            order(BTC_SPOT, SECONDARY),
        ):
            with self.assertRaisesRegex(
                ExecutionRoutingError,
                "route is not configured",
            ):
                await router.submit(command)

        self.assertEqual(spot.calls, [])
        self.assertEqual(derivative.calls, [])

    async def test_three_spot_routes_can_share_one_gateway(self) -> None:
        spot = _Gateway("spot")
        configured = (
            exact_route(BTC_SPOT, spot),
            exact_route(ETH_SPOT, spot),
            exact_route(ETH_BTC_SPOT, spot),
        )
        router = ExactExecutionGatewayRouter(route for route in configured)

        for instrument_id in (BTC_SPOT, ETH_SPOT, ETH_BTC_SPOT):
            await router.submit(order(instrument_id))

        self.assertEqual(router.routes, configured)
        self.assertEqual(
            [instrument for _, _, instrument, _ in spot.calls],
            [BTC_SPOT, ETH_SPOT, ETH_BTC_SPOT],
        )

    async def test_four_leg_product_mix_has_no_router_policy(self) -> None:
        options = _Gateway("options")
        spot = _Gateway("spot")
        derivative = _Gateway("derivative")
        instruments_and_gateways = (
            (BTC_CALL, options),
            (BTC_PUT, options),
            (BTC_SPOT, spot),
            (BTC_PERPETUAL, derivative),
        )
        router = ExactExecutionGatewayRouter(
            exact_route(instrument_id, gateway)
            for instrument_id, gateway in instruments_and_gateways
        )

        for instrument_id, _ in instruments_and_gateways:
            await router.submit(order(instrument_id))

        self.assertEqual(len(router.routes), 4)
        self.assertEqual(len(options.calls), 2)
        self.assertEqual(len(spot.calls), 1)
        self.assertEqual(len(derivative.calls), 1)

    async def test_cross_venue_routes_remain_exact_and_gateway_agnostic(
        self,
    ) -> None:
        binance = _Gateway("binance")
        okx = _Gateway("okx")
        router = ExactExecutionGatewayRouter(
            (
                exact_route(BTC_SPOT, binance),
                exact_route(OKX_BTC_PERPETUAL, okx, SECONDARY),
            )
        )

        await router.submit(order(BTC_SPOT))
        await router.submit(order(OKX_BTC_PERPETUAL, SECONDARY))

        self.assertEqual(binance.calls[0][1:3], (PRIMARY, BTC_SPOT))
        self.assertEqual(
            okx.calls[0][1:3],
            (SECONDARY, OKX_BTC_PERPETUAL),
        )


class ExactExecutionRouteConfigurationTests(TestCase):
    def test_requires_at_least_one_route(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            ExactExecutionGatewayRouter(())

    def test_rejects_only_duplicate_exact_scopes(self) -> None:
        gateway = _Gateway("spot")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ExactExecutionGatewayRouter(
                (
                    exact_route(BTC_SPOT, gateway),
                    exact_route(BTC_SPOT, gateway),
                )
            )

        router = ExactExecutionGatewayRouter(
            (
                exact_route(BTC_SPOT, gateway, PRIMARY),
                exact_route(BTC_SPOT, gateway, SECONDARY),
            )
        )
        self.assertEqual(len(router.routes), 2)

    def test_rejects_invalid_route_values_and_gateways(self) -> None:
        with self.assertRaisesRegex(ValueError, "ExactExecutionRoute"):
            ExactExecutionGatewayRouter([object()])  # type: ignore[list-item]
        with self.assertRaisesRegex(ValueError, "non-empty trimmed"):
            ExactExecutionRoute(
                account_id=AccountId(" "),
                instrument_id=BTC_SPOT,
                gateway=_Gateway("spot"),
            )
        with self.assertRaisesRegex(ValueError, "submit, cancel, and query_order"):
            ExactExecutionRoute(
                account_id=PRIMARY,
                instrument_id=BTC_SPOT,
                gateway=object(),  # type: ignore[arg-type]
            )

    def test_configuration_bound_does_not_encode_strategy_leg_policy(
        self,
    ) -> None:
        gateway = _Gateway("spot")
        routes = (
            exact_route(BTC_SPOT, gateway),
            exact_route(ETH_SPOT, gateway),
        )
        with self.assertRaisesRegex(ValueError, "max_configured_routes"):
            ExactExecutionGatewayRouter(routes, max_configured_routes=1)

    def test_sync_bridge_exposes_all_routed_operations(self) -> None:
        router, spot, derivative = two_route_router()
        bridge = AsyncExecutionPortBridge(router)
        bridge.start()
        try:
            submit_result = bridge.submit(order(BTC_SPOT))
            cancel_result = bridge.cancel(cancel(BTC_PERPETUAL))
            query_result = bridge.query_order(query(BTC_PERPETUAL))
        finally:
            bridge.close()

        self.assertIs(submit_result.outcome, ExecutionOutcome.ACCEPTED)
        self.assertIs(cancel_result.outcome, ExecutionOutcome.ACCEPTED)
        assert query_result is not None
        self.assertEqual(query_result.source_update_id, "query-derivative")
        operation_threads = {
            thread_id for _, _, _, thread_id in (*spot.calls, *derivative.calls)
        }
        self.assertEqual(len(operation_threads), 1)
        self.assertNotEqual(operation_threads.pop(), get_ident())


if __name__ == "__main__":
    import unittest

    unittest.main()
