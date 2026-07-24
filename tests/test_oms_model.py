import unittest
from dataclasses import FrozenInstanceError

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    ApprovedOrderIntent,
    OrderRequest,
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
)

PERPETUAL = InstrumentId(
    venue=VenueId("test"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)
SPOT = InstrumentId(
    venue=VenueId("test"),
    kind=InstrumentKind.SPOT,
    symbol="ETHUSDT",
)
OPTION = InstrumentId(
    venue=VenueId("test"),
    kind=InstrumentKind.OPTION,
    symbol="BTC-20261225-100000-C",
)
DEFAULT_LIMIT_PRICE = Price(raw=100_000, scale=1)


def approved(
    *,
    instrument_id: InstrumentId = PERPETUAL,
    order_type: OrderType = OrderType.LIMIT,
    limit_price: Price | None = DEFAULT_LIMIT_PRICE,
    stop_price: Price | None = None,
    reduce_only: bool = False,
    position_side: PositionSide = PositionSide.NET,
) -> ApprovedOrderIntent:
    return ApprovedOrderIntent(
        approval_id="approval-1",
        intent_id=IntentId("intent-1"),
        account_id=AccountId("account-1"),
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Quantity(raw=15, scale=1),
        limit_price=limit_price,
        stop_price=stop_price,
        reduce_only=reduce_only,
        position_side=position_side,
        approved_at_ns=UnixNanos(100),
        valid_until_ns=UnixNanos(200),
    )


class OmsModelTests(unittest.TestCase):
    def test_request_is_created_only_while_approval_is_valid(self) -> None:
        request = OrderRequest.from_approved_intent(
            approved(),
            client_order_id=ClientOrderId("client-1"),
            created_at_ns=UnixNanos(150),
        )
        self.assertEqual(request.instrument_id, PERPETUAL)
        self.assertEqual(request.approval_id, "approval-1")
        with self.assertRaises(ValueError):
            OrderRequest.from_approved_intent(
                approved(),
                client_order_id=ClientOrderId("client-2"),
                created_at_ns=UnixNanos(201),
            )
        with self.assertRaisesRegex(ValueError, "precede approval"):
            OrderRequest.from_approved_intent(
                approved(),
                client_order_id=ClientOrderId("client-3"),
                created_at_ns=UnixNanos(99),
            )

    def test_contract_and_option_fields_use_common_instrument_identity(self) -> None:
        contract = approved(
            reduce_only=True,
            position_side=PositionSide.LONG,
        )
        option = approved(instrument_id=OPTION)
        self.assertTrue(contract.reduce_only)
        self.assertEqual(option.instrument_id.kind, InstrumentKind.OPTION)

    def test_spot_rejects_derivatives_position_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "reduce_only"):
            approved(instrument_id=SPOT, reduce_only=True)
        with self.assertRaisesRegex(ValueError, "NET"):
            approved(instrument_id=SPOT, position_side=PositionSide.LONG)

    def test_order_type_price_contracts_are_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "limit_price"):
            approved(order_type=OrderType.MARKET, limit_price=Price(raw=1, scale=0))
        with self.assertRaisesRegex(ValueError, "stop_price"):
            approved(
                order_type=OrderType.STOP_MARKET,
                limit_price=None,
                stop_price=None,
            )
        stop_limit = approved(
            order_type=OrderType.STOP_LIMIT,
            stop_price=Price(raw=99_000, scale=1),
        )
        self.assertIsNotNone(stop_limit.stop_price)

    def test_post_only_requires_limit_gtx_pair(self) -> None:
        with self.assertRaisesRegex(ValueError, "GTX"):
            ApprovedOrderIntent(
                approval_id="approval",
                intent_id=IntentId("intent"),
                account_id=AccountId("account"),
                instrument_id=PERPETUAL,
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=Quantity(raw=1, scale=0),
                limit_price=Price(raw=1, scale=0),
                post_only=True,
                time_in_force=TimeInForce.GTC,
                approved_at_ns=UnixNanos(1),
            )

    def test_contracts_are_immutable(self) -> None:
        value = approved()
        with self.assertRaises(FrozenInstanceError):
            value.approval_id = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
