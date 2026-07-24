from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from unittest import TestCase

from cex_quant.execution.adapters import BinanceProduct
from cex_quant.runtime.binance_environment import (
    BinanceEnvironment,
    BinanceEnvironmentConfig,
    BinanceProductEndpoints,
)


class BinanceEnvironmentConfigTests(TestCase):
    def test_defaults_to_complete_testnet_profile(self) -> None:
        config = BinanceEnvironmentConfig()

        self.assertIs(config.environment, BinanceEnvironment.TESTNET)
        self.assertEqual(
            config.spot.rest_base_url,
            "https://testnet.binance.vision",
        )
        self.assertEqual(
            config.spot.public_ws_base_url,
            "wss://stream.testnet.binance.vision/stream",
        )
        self.assertEqual(
            config.spot.private_ws_base_url,
            "wss://ws-api.testnet.binance.vision/ws-api/v3",
        )
        self.assertEqual(
            config.usd_m.rest_base_url,
            "https://demo-fapi.binance.com",
        )
        self.assertEqual(
            config.usd_m.public_ws_base_url,
            "wss://demo-fstream.binance.com/stream",
        )
        self.assertEqual(
            config.coin_m.private_ws_base_url,
            "wss://demo-dstream.binance.com",
        )

    def test_selects_each_product_with_typed_lookup(self) -> None:
        config = BinanceEnvironmentConfig()

        self.assertIs(
            config.endpoints_for(BinanceProduct.SPOT),
            config.spot,
        )
        self.assertIs(
            config.endpoints_for(BinanceProduct.USD_M),
            config.usd_m,
        )
        self.assertIs(
            config.endpoints_for(BinanceProduct.COIN_M),
            config.coin_m,
        )
        with self.assertRaisesRegex(ValueError, "BinanceProduct"):
            config.endpoints_for("spot")  # type: ignore[arg-type]

    def test_production_requires_explicit_permission(self) -> None:
        with self.assertRaisesRegex(ValueError, "allow_production=True"):
            BinanceEnvironmentConfig(
                environment=BinanceEnvironment.PRODUCTION
            )

        config = BinanceEnvironmentConfig(
            environment=BinanceEnvironment.PRODUCTION,
            allow_production=True,
        )

        self.assertEqual(config.spot.rest_base_url, "https://api.binance.com")
        self.assertEqual(
            config.usd_m.private_ws_base_url,
            "wss://fstream.binance.com",
        )
        self.assertEqual(
            config.coin_m.public_ws_base_url,
            "wss://dstream.binance.com/stream",
        )

    def test_testnet_rejects_production_permission(self) -> None:
        with self.assertRaisesRegex(ValueError, "remain false"):
            BinanceEnvironmentConfig(allow_production=True)

    def test_rejects_mixed_environment_product_endpoints(self) -> None:
        production = BinanceEnvironmentConfig(
            environment=BinanceEnvironment.PRODUCTION,
            allow_production=True,
        )

        with self.assertRaisesRegex(ValueError, "cannot be mixed"):
            BinanceEnvironmentConfig(spot=production.spot)

    def test_rejects_product_assigned_to_wrong_slot(self) -> None:
        config = BinanceEnvironmentConfig()

        with self.assertRaisesRegex(ValueError, "wrong slots"):
            BinanceEnvironmentConfig(spot=config.usd_m, usd_m=config.spot)

    def test_rejects_insecure_or_credential_bearing_urls(self) -> None:
        config = BinanceEnvironmentConfig()

        with self.assertRaisesRegex(ValueError, "must use https"):
            replace(config.spot, rest_base_url="http://testnet.binance.vision")
        with self.assertRaisesRegex(ValueError, "must use wss"):
            replace(
                config.spot,
                public_ws_base_url=(
                    "ws://stream.testnet.binance.vision/stream"
                ),
            )
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            replace(
                config.spot,
                rest_base_url=(
                    "https://api-key:test-secret@testnet.binance.vision"
                ),
            )

    def test_rejects_host_claiming_the_wrong_environment(self) -> None:
        config = BinanceEnvironmentConfig()

        with self.assertRaisesRegex(ValueError, "do not belong to testnet"):
            replace(
                config.spot,
                rest_base_url="https://api.binance.com",
            )

    def test_rejects_query_fragment_and_missing_host(self) -> None:
        config = BinanceEnvironmentConfig()

        with self.assertRaisesRegex(ValueError, "query or fragment"):
            replace(
                config.spot,
                public_ws_base_url=(
                    "wss://stream.testnet.binance.vision/stream?token=value"
                ),
            )
        with self.assertRaisesRegex(ValueError, "include a host"):
            replace(config.spot, private_ws_base_url="wss:///ws-api/v3")

    def test_values_are_immutable_and_repr_contains_no_permission_flag(
        self,
    ) -> None:
        config = BinanceEnvironmentConfig()

        with self.assertRaises(FrozenInstanceError):
            config.environment = BinanceEnvironment.PRODUCTION  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            config.spot.rest_base_url = "https://api.binance.com"  # type: ignore[misc]
        rendered = repr(config)
        self.assertNotIn("allow_production", rendered)
        self.assertNotIn("credential", rendered.lower())
        self.assertNotIn("secret", rendered.lower())

    def test_endpoint_contract_rejects_wrong_types(self) -> None:
        config = BinanceEnvironmentConfig()

        with self.assertRaisesRegex(ValueError, "BinanceEnvironment"):
            replace(config.spot, environment="testnet")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "BinanceProduct"):
            replace(config.spot, product="spot")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "BinanceProductEndpoints"):
            BinanceEnvironmentConfig(spot="not-endpoints")  # type: ignore[arg-type]


class BinanceProductEndpointsTests(TestCase):
    def test_endpoint_value_has_no_credential_fields(self) -> None:
        fields = BinanceProductEndpoints.__dataclass_fields__

        self.assertNotIn("api_key", fields)
        self.assertNotIn("secret", fields)
        self.assertNotIn("credentials", fields)
