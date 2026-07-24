"""Pure Binance Spot and Futures request parameter mappings.

Authentication, timestamps, signatures, HTTP and response decoding are
deliberately outside this module.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from cex_quant.instruments import InstrumentKind
from cex_quant.oms import (
    OrderRequest,
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
)

from ..contracts import CancelOrder, QueryOrder
from ..gateway import (
    InvalidExecutionRequestError,
    UnsupportedExecutionFeatureError,
)


class BinanceProduct(StrEnum):
    SPOT = "spot"
    USD_M = "usd_m"
    COIN_M = "coin_m"


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceRequest:
    method: str
    path: str
    parameters: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "parameters", MappingProxyType(dict(self.parameters))
        )


_PATHS = {
    BinanceProduct.SPOT: "/api/v3/order",
    BinanceProduct.USD_M: "/fapi/v1/order",
    BinanceProduct.COIN_M: "/dapi/v1/order",
}


def map_binance_submit(
    product: BinanceProduct, command: OrderRequest
) -> BinanceRequest:
    """Map a canonical submit command without adding signed-request fields."""

    _validate_product(product)
    _validate_command_enums(command)
    _validate_product_kind(product, command.instrument_id.kind)
    parameters = {
        "symbol": command.instrument_id.symbol,
        "side": command.side.value.upper(),
        "type": command.order_type.value.upper(),
        "quantity": str(command.quantity),
        "newClientOrderId": str(command.client_order_id),
    }
    if command.order_type not in {OrderType.MARKET, OrderType.LIMIT}:
        raise UnsupportedExecutionFeatureError(
            f"Binance foundational mapper does not support {command.order_type.value}"
        )
    if command.post_only or command.time_in_force is TimeInForce.GTX:
        raise UnsupportedExecutionFeatureError(
            "Binance foundational mapper does not support post-only orders"
        )
    if command.order_type is OrderType.LIMIT:
        if command.limit_price is None:
            raise InvalidExecutionRequestError("limit order requires limit_price")
        parameters["price"] = str(command.limit_price)
        parameters["timeInForce"] = command.time_in_force.value.upper()

    if product is BinanceProduct.SPOT:
        if command.reduce_only or command.position_side is not PositionSide.NET:
            raise InvalidExecutionRequestError(
                "Binance Spot requires non-reducing NET position semantics"
            )
    else:
        parameters["positionSide"] = (
            "BOTH"
            if command.position_side is PositionSide.NET
            else command.position_side.value.upper()
        )
        if command.position_side is not PositionSide.NET and command.reduce_only:
            raise InvalidExecutionRequestError(
                "Binance Futures forbids reduceOnly in hedge position mode"
            )
        if command.reduce_only:
            parameters["reduceOnly"] = "true"

    return BinanceRequest(
        method="POST", path=_PATHS[product], parameters=parameters
    )


def map_binance_cancel(
    product: BinanceProduct, command: CancelOrder
) -> BinanceRequest:
    """Map cancellation by the unchanged original client order ID."""

    _validate_product(product)
    _validate_product_kind(product, command.instrument_id.kind)
    return BinanceRequest(
        method="DELETE",
        path=_PATHS[product],
        parameters={
            "symbol": command.instrument_id.symbol,
            "origClientOrderId": str(command.client_order_id),
        },
    )


def map_binance_query_order(
    product: BinanceProduct,
    command: QueryOrder,
) -> BinanceRequest:
    """Map a signed query by the original client order ID."""

    _validate_product(product)
    _validate_product_kind(product, command.instrument_id.kind)
    return BinanceRequest(
        method="GET",
        path=_PATHS[product],
        parameters={
            "symbol": command.instrument_id.symbol,
            "origClientOrderId": str(command.client_order_id),
        },
    )


def _validate_product_kind(
    product: BinanceProduct, kind: InstrumentKind
) -> None:
    if kind is InstrumentKind.OPTION:
        raise UnsupportedExecutionFeatureError(
            "Binance Options execution mapping is not defined"
        )
    if product is BinanceProduct.SPOT and kind is not InstrumentKind.SPOT:
        raise InvalidExecutionRequestError(
            "Binance Spot requires a spot instrument"
        )
    if product is not BinanceProduct.SPOT and kind not in {
        InstrumentKind.PERPETUAL,
        InstrumentKind.FUTURE,
    }:
        raise InvalidExecutionRequestError(
            "Binance Futures requires a perpetual or future instrument"
        )


def _validate_product(product: BinanceProduct) -> None:
    if not isinstance(product, BinanceProduct):
        raise InvalidExecutionRequestError(
            "product must be a BinanceProduct"
        )


def _validate_command_enums(command: OrderRequest) -> None:
    if not isinstance(command.side, OrderSide):
        raise InvalidExecutionRequestError("side must be an OrderSide")
    if not isinstance(command.order_type, OrderType):
        raise InvalidExecutionRequestError("order_type must be an OrderType")
    if not isinstance(command.time_in_force, TimeInForce):
        raise InvalidExecutionRequestError(
            "time_in_force must be a TimeInForce"
        )
    if not isinstance(command.position_side, PositionSide):
        raise InvalidExecutionRequestError(
            "position_side must be a PositionSide"
        )
    if not isinstance(command.reduce_only, bool):
        raise InvalidExecutionRequestError("reduce_only must be a bool")


__all__ = [
    "BinanceProduct",
    "BinanceRequest",
    "map_binance_cancel",
    "map_binance_query_order",
    "map_binance_submit",
]
