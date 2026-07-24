from typing import Any, cast
from unittest import TestCase

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.execution import (
    CancelOrder,
    InvalidExecutionRequestError,
    UnsupportedExecutionFeatureError,
)
from cex_quant.execution.adapters import (
    BinanceProduct,
    map_binance_cancel,
    map_binance_submit,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    OrderRequest,
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
)


def instrument(kind: InstrumentKind, symbol: str = "BTCUSDT") -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=kind,
        symbol=symbol,
    )


def limit_order(
    *,
    kind: InstrumentKind = InstrumentKind.SPOT,
    **overrides: Any,
) -> OrderRequest:
    values: dict[str, Any] = {
        "client_order_id": ClientOrderId("alpha:BTC:000001"),
        "approval_id": "risk-approval-1",
        "intent_id": IntentId("intent-1"),
        "account_id": AccountId("primary"),
        "instrument_id": instrument(kind),
        "side": OrderSide.SELL,
        "order_type": OrderType.LIMIT,
        "quantity": Quantity.from_str("1.2300"),
        "created_at_ns": UnixNanos(1_000),
        "limit_price": Price.from_str("64000.10"),
        "time_in_force": TimeInForce.IOC,
    }
    values.update(overrides)
    return OrderRequest(**values)


class BinanceExecutionMappingTest(TestCase):
    def test_maps_spot_limit_with_exact_decimal_strings(self) -> None:
        request = map_binance_submit(BinanceProduct.SPOT, limit_order())

        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/api/v3/order")
        self.assertEqual(
            dict(request.parameters),
            {
                "symbol": "BTCUSDT",
                "side": "SELL",
                "type": "LIMIT",
                "quantity": "1.2300",
                "newClientOrderId": "alpha:BTC:000001",
                "price": "64000.10",
                "timeInForce": "IOC",
            },
        )
        with self.assertRaises(TypeError):
            request.parameters["quantity"] = "9"

    def test_maps_futures_market_and_limit_endpoints(self) -> None:
        market = limit_order(
            kind=InstrumentKind.PERPETUAL,
            order_type=OrderType.MARKET,
            limit_price=None,
            time_in_force=TimeInForce.GTC,
        )
        usd_m = map_binance_submit(BinanceProduct.USD_M, market)
        coin_m = map_binance_submit(
            BinanceProduct.COIN_M,
            limit_order(
                kind=InstrumentKind.FUTURE,
                reduce_only=True,
            ),
        )

        self.assertEqual(usd_m.path, "/fapi/v1/order")
        self.assertEqual(usd_m.parameters["positionSide"], "BOTH")
        self.assertNotIn("price", usd_m.parameters)
        self.assertNotIn("timeInForce", usd_m.parameters)
        self.assertNotIn("reduceOnly", usd_m.parameters)
        self.assertEqual(coin_m.path, "/dapi/v1/order")
        self.assertEqual(coin_m.parameters["reduceOnly"], "true")

    def test_maps_hedge_position_side_but_rejects_reduce_only(self) -> None:
        request = map_binance_submit(
            BinanceProduct.USD_M,
            limit_order(
                kind=InstrumentKind.PERPETUAL,
                position_side=PositionSide.SHORT,
            ),
        )
        self.assertEqual(request.parameters["positionSide"], "SHORT")

        with self.assertRaisesRegex(
            InvalidExecutionRequestError, "hedge position mode"
        ):
            map_binance_submit(
                BinanceProduct.USD_M,
                limit_order(
                    kind=InstrumentKind.PERPETUAL,
                    position_side=PositionSide.SHORT,
                    reduce_only=True,
                ),
            )

    def test_rejects_product_and_instrument_kind_mismatch(self) -> None:
        with self.assertRaisesRegex(
            InvalidExecutionRequestError, "requires a spot"
        ):
            map_binance_submit(
                BinanceProduct.SPOT,
                limit_order(kind=InstrumentKind.PERPETUAL),
            )
        with self.assertRaisesRegex(
            InvalidExecutionRequestError, "requires a perpetual or future"
        ):
            map_binance_submit(BinanceProduct.USD_M, limit_order())

    def test_rejects_unimplemented_stop_and_post_only_semantics(self) -> None:
        with self.assertRaisesRegex(
            UnsupportedExecutionFeatureError, "stop_market"
        ):
            map_binance_submit(
                BinanceProduct.USD_M,
                limit_order(
                    kind=InstrumentKind.PERPETUAL,
                    order_type=OrderType.STOP_MARKET,
                    limit_price=None,
                    stop_price=Price.from_str("62000"),
                ),
            )
        with self.assertRaisesRegex(
            UnsupportedExecutionFeatureError, "post-only"
        ):
            map_binance_submit(
                BinanceProduct.USD_M,
                limit_order(
                    kind=InstrumentKind.PERPETUAL,
                    post_only=True,
                    time_in_force=TimeInForce.GTX,
                ),
            )

    def test_invalid_enum_values_fail_as_typed_boundary_errors(self) -> None:
        malformed = limit_order(side=cast(Any, "SELL"))
        with self.assertRaisesRegex(
            InvalidExecutionRequestError, "side must be"
        ):
            map_binance_submit(BinanceProduct.SPOT, malformed)

        with self.assertRaisesRegex(
            InvalidExecutionRequestError, "BinanceProduct"
        ):
            map_binance_submit(cast(Any, "spot"), limit_order())

    def test_options_remain_venue_neutral_without_guessed_mapping(self) -> None:
        with self.assertRaisesRegex(
            UnsupportedExecutionFeatureError, "Options"
        ):
            map_binance_submit(
                BinanceProduct.USD_M,
                limit_order(kind=InstrumentKind.OPTION),
            )

    def test_cancel_uses_original_client_id_unchanged(self) -> None:
        command = CancelOrder(
            account_id=AccountId("primary"),
            instrument_id=instrument(InstrumentKind.PERPETUAL),
            client_order_id=ClientOrderId("alpha:BTC:000001"),
        )
        request = map_binance_cancel(BinanceProduct.COIN_M, command)

        self.assertEqual(request.method, "DELETE")
        self.assertEqual(request.path, "/dapi/v1/order")
        self.assertEqual(
            dict(request.parameters),
            {
                "symbol": "BTCUSDT",
                "origClientOrderId": "alpha:BTC:000001",
            },
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
