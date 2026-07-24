"""Strongly typed Binance endpoint profiles without credential ownership."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import SplitResult, urlsplit

from cex_quant.execution.adapters import BinanceProduct


class BinanceEnvironment(StrEnum):
    """Deployment environment selected for every Binance product endpoint."""

    TESTNET = "testnet"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceProductEndpoints:
    """REST and WebSocket origins for one product in one environment."""

    environment: BinanceEnvironment
    product: BinanceProduct
    rest_base_url: str
    public_ws_base_url: str
    private_ws_base_url: str

    def __post_init__(self) -> None:
        if not isinstance(self.environment, BinanceEnvironment):
            raise ValueError("environment must be a BinanceEnvironment")
        if not isinstance(self.product, BinanceProduct):
            raise ValueError("product must be a BinanceProduct")
        _validate_url(
            self.rest_base_url,
            expected_scheme="https",
            field_name="rest_base_url",
        )
        _validate_url(
            self.public_ws_base_url,
            expected_scheme="wss",
            field_name="public_ws_base_url",
        )
        _validate_url(
            self.private_ws_base_url,
            expected_scheme="wss",
            field_name="private_ws_base_url",
        )
        expected_hosts = _EXPECTED_HOSTS[(self.environment, self.product)]
        actual_hosts = (
            _host(self.rest_base_url),
            _host(self.public_ws_base_url),
            _host(self.private_ws_base_url),
        )
        if actual_hosts != expected_hosts:
            raise ValueError(
                f"{self.product.value} endpoints do not belong to "
                f"{self.environment.value}"
            )


@dataclass(frozen=True, slots=True, kw_only=True, init=False)
class BinanceEnvironmentConfig:
    """Complete, immutable endpoint selection for the trading runtime.

    Testnet is the default. Production construction requires an explicit
    acknowledgement at the call site. Credentials deliberately are not part
    of this value and remain owned by ``BinanceCredentialProvider``.
    """

    environment: BinanceEnvironment
    spot: BinanceProductEndpoints
    usd_m: BinanceProductEndpoints
    coin_m: BinanceProductEndpoints

    def __init__(
        self,
        *,
        environment: BinanceEnvironment = BinanceEnvironment.TESTNET,
        spot: BinanceProductEndpoints | None = None,
        usd_m: BinanceProductEndpoints | None = None,
        coin_m: BinanceProductEndpoints | None = None,
        allow_production: bool = False,
    ) -> None:
        if not isinstance(environment, BinanceEnvironment):
            raise ValueError("environment must be a BinanceEnvironment")
        if not isinstance(allow_production, bool):
            raise ValueError("allow_production must be a bool")
        if (
            environment is BinanceEnvironment.PRODUCTION
            and not allow_production
        ):
            raise ValueError(
                "production endpoints require allow_production=True"
            )
        if environment is BinanceEnvironment.TESTNET and allow_production:
            raise ValueError(
                "allow_production must remain false for testnet"
            )

        defaults = _defaults(environment)
        resolved_spot = defaults[0] if spot is None else spot
        resolved_usd_m = defaults[1] if usd_m is None else usd_m
        resolved_coin_m = defaults[2] if coin_m is None else coin_m
        endpoints = (resolved_spot, resolved_usd_m, resolved_coin_m)
        if not all(isinstance(item, BinanceProductEndpoints) for item in endpoints):
            raise ValueError("all product endpoints must be BinanceProductEndpoints")
        if tuple(item.product for item in endpoints) != (
            BinanceProduct.SPOT,
            BinanceProduct.USD_M,
            BinanceProduct.COIN_M,
        ):
            raise ValueError("product endpoints are assigned to the wrong slots")
        if any(item.environment is not environment for item in endpoints):
            raise ValueError("product endpoint environments cannot be mixed")
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "spot", resolved_spot)
        object.__setattr__(self, "usd_m", resolved_usd_m)
        object.__setattr__(self, "coin_m", resolved_coin_m)

    def endpoints_for(
        self, product: BinanceProduct
    ) -> BinanceProductEndpoints:
        """Return the selected endpoints for a strongly typed product."""

        if product is BinanceProduct.SPOT:
            return self.spot
        if product is BinanceProduct.USD_M:
            return self.usd_m
        if product is BinanceProduct.COIN_M:
            return self.coin_m
        raise ValueError("product must be a BinanceProduct")

    def __repr__(self) -> str:
        return (
            "BinanceEnvironmentConfig("
            f"environment={self.environment.value!r}, "
            f"spot={self.spot!r}, usd_m={self.usd_m!r}, "
            f"coin_m={self.coin_m!r})"
        )


def _validate_url(
    value: str,
    *,
    expected_scheme: str,
    field_name: str,
) -> SplitResult:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty trimmed URL")
    parsed = urlsplit(value)
    if parsed.scheme != expected_scheme:
        raise ValueError(f"{field_name} must use {expected_scheme}")
    if not parsed.hostname:
        raise ValueError(f"{field_name} must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must not contain query or fragment")
    return parsed


def _host(value: str) -> str:
    host = urlsplit(value).hostname
    assert host is not None
    return host.lower()


_EXPECTED_HOSTS: dict[
    tuple[BinanceEnvironment, BinanceProduct],
    tuple[str, str, str],
] = {
    (BinanceEnvironment.TESTNET, BinanceProduct.SPOT): (
        "testnet.binance.vision",
        "stream.testnet.binance.vision",
        "ws-api.testnet.binance.vision",
    ),
    (BinanceEnvironment.TESTNET, BinanceProduct.USD_M): (
        "demo-fapi.binance.com",
        "demo-fstream.binance.com",
        "demo-fstream.binance.com",
    ),
    (BinanceEnvironment.TESTNET, BinanceProduct.COIN_M): (
        "demo-dapi.binance.com",
        "demo-dstream.binance.com",
        "demo-dstream.binance.com",
    ),
    (BinanceEnvironment.PRODUCTION, BinanceProduct.SPOT): (
        "api.binance.com",
        "stream.binance.com",
        "ws-api.binance.com",
    ),
    (BinanceEnvironment.PRODUCTION, BinanceProduct.USD_M): (
        "fapi.binance.com",
        "fstream.binance.com",
        "fstream.binance.com",
    ),
    (BinanceEnvironment.PRODUCTION, BinanceProduct.COIN_M): (
        "dapi.binance.com",
        "dstream.binance.com",
        "dstream.binance.com",
    ),
}


_TESTNET_ENDPOINTS = (
    BinanceProductEndpoints(
        environment=BinanceEnvironment.TESTNET,
        product=BinanceProduct.SPOT,
        rest_base_url="https://testnet.binance.vision",
        public_ws_base_url="wss://stream.testnet.binance.vision/stream",
        private_ws_base_url=(
            "wss://ws-api.testnet.binance.vision/ws-api/v3"
        ),
    ),
    BinanceProductEndpoints(
        environment=BinanceEnvironment.TESTNET,
        product=BinanceProduct.USD_M,
        rest_base_url="https://demo-fapi.binance.com",
        public_ws_base_url="wss://demo-fstream.binance.com/stream",
        private_ws_base_url="wss://demo-fstream.binance.com",
    ),
    BinanceProductEndpoints(
        environment=BinanceEnvironment.TESTNET,
        product=BinanceProduct.COIN_M,
        rest_base_url="https://demo-dapi.binance.com",
        public_ws_base_url="wss://demo-dstream.binance.com/stream",
        private_ws_base_url="wss://demo-dstream.binance.com",
    ),
)

_PRODUCTION_ENDPOINTS = (
    BinanceProductEndpoints(
        environment=BinanceEnvironment.PRODUCTION,
        product=BinanceProduct.SPOT,
        rest_base_url="https://api.binance.com",
        public_ws_base_url="wss://stream.binance.com:9443/stream",
        private_ws_base_url="wss://ws-api.binance.com/ws-api/v3",
    ),
    BinanceProductEndpoints(
        environment=BinanceEnvironment.PRODUCTION,
        product=BinanceProduct.USD_M,
        rest_base_url="https://fapi.binance.com",
        public_ws_base_url="wss://fstream.binance.com/stream",
        private_ws_base_url="wss://fstream.binance.com",
    ),
    BinanceProductEndpoints(
        environment=BinanceEnvironment.PRODUCTION,
        product=BinanceProduct.COIN_M,
        rest_base_url="https://dapi.binance.com",
        public_ws_base_url="wss://dstream.binance.com/stream",
        private_ws_base_url="wss://dstream.binance.com",
    ),
)


def _defaults(
    environment: BinanceEnvironment,
) -> tuple[
    BinanceProductEndpoints,
    BinanceProductEndpoints,
    BinanceProductEndpoints,
]:
    if environment is BinanceEnvironment.TESTNET:
        return _TESTNET_ENDPOINTS
    if environment is BinanceEnvironment.PRODUCTION:
        return _PRODUCTION_ENDPOINTS
    raise ValueError("environment must be a BinanceEnvironment")


__all__ = [
    "BinanceEnvironment",
    "BinanceEnvironmentConfig",
    "BinanceProductEndpoints",
]
