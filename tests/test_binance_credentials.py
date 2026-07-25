from unittest import TestCase

from cex_quant.core import AccountId
from cex_quant.execution import (
    BinanceCredentialBinding,
    BinanceCredentialError,
    EnvironmentBinanceCredentialProvider,
)


class RaisingEnvironment(dict[str, str]):
    def __getitem__(self, key: str) -> str:
        raise RuntimeError(f"do-not-expose-{key}")


def binding(
    api_key: str = "BINANCE_TEST_API_KEY",
    secret: str = "BINANCE_TEST_SECRET",
) -> BinanceCredentialBinding:
    return BinanceCredentialBinding(
        api_key_variable=api_key,
        secret_variable=secret,
    )


class EnvironmentBinanceCredentialProviderTests(TestCase):
    def test_reads_fresh_values_for_explicit_account_rotation(self) -> None:
        account_id = AccountId("testnet")
        environ = {
            "BINANCE_TEST_API_KEY": "fixture-key-v1",
            "BINANCE_TEST_SECRET": "fixture-signing-value-v1",
        }
        provider = EnvironmentBinanceCredentialProvider(
            bindings={account_id: binding()},
            environ=environ,
        )

        first = provider.credentials_for(account_id)
        environ["BINANCE_TEST_API_KEY"] = "fixture-key-v2"
        environ["BINANCE_TEST_SECRET"] = "fixture-signing-value-v2"
        second = provider.credentials_for(account_id)

        self.assertEqual(first.api_key, "fixture-key-v1")
        self.assertEqual(second.api_key, "fixture-key-v2")
        self.assertNotEqual(first.sign("payload"), second.sign("payload"))
        rendered = repr(provider)
        self.assertNotIn("BINANCE_TEST", rendered)
        self.assertNotIn("fixture", rendered)

    def test_missing_invalid_and_source_failures_are_sanitized(self) -> None:
        account_id = AccountId("testnet")
        for environ in (
            {},
            {
                "BINANCE_TEST_API_KEY": " fixture-key",
                "BINANCE_TEST_SECRET": "fixture-signing-value",
            },
            RaisingEnvironment(),
        ):
            with self.subTest(environ=type(environ).__name__):
                provider = EnvironmentBinanceCredentialProvider(
                    bindings={account_id: binding()},
                    environ=environ,
                )
                with self.assertRaises(BinanceCredentialError) as caught:
                    provider.credentials_for(account_id)
                rendered = str(caught.exception)
                self.assertNotIn("BINANCE_TEST", rendered)
                self.assertNotIn("fixture", rendered)

        provider = EnvironmentBinanceCredentialProvider(
            bindings={account_id: binding()},
            environ={
                "BINANCE_TEST_API_KEY": "fixture-key",
                "BINANCE_TEST_SECRET": "fixture-signing-value",
            },
        )
        with self.assertRaisesRegex(
            BinanceCredentialError,
            "not configured",
        ):
            provider.credentials_for(AccountId("other"))

    def test_bindings_are_strict_immutable_and_not_shared(self) -> None:
        for api_key, secret in (
            ("lowercase", "SECRET"),
            ("1INVALID", "SECRET"),
            ("SAME", "SAME"),
        ):
            with (
                self.subTest(api_key=api_key, secret=secret),
                self.assertRaises(ValueError),
            ):
                binding(api_key, secret)

        source = {AccountId("one"): binding("ONE_KEY", "ONE_SECRET")}
        provider = EnvironmentBinanceCredentialProvider(
            bindings=source,
            environ={"ONE_KEY": "key", "ONE_SECRET": "signing"},
        )
        source.clear()
        self.assertEqual(len(provider.bindings), 1)
        with self.assertRaisesRegex(ValueError, "shared"):
            EnvironmentBinanceCredentialProvider(
                bindings={
                    AccountId("one"): binding("SHARED", "ONE_SECRET"),
                    AccountId("two"): binding("SHARED", "TWO_SECRET"),
                },
                environ={},
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
