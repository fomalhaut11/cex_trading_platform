from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from cex_quant.core import AccountId
from cex_quant.execution import (
    AuthenticatedBinanceExecutionAdapter,
    BinanceCredentialBinding,
    EnvironmentBinanceCredentialProvider,
)
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.runtime import (
    JsonLinesOperatorCommandJournal,
    OperatorAction,
    OperatorController,
    OperatorMode,
)
from tests.test_binance_authenticated import (
    CapturingTransport,
    order,
    response,
)
from tests.test_runtime_operations import ManualClock, command


class SecurityAndOperatorRecoveryAcceptanceTests(IsolatedAsyncioTestCase):
    async def test_rotation_and_restart_recovery_do_not_persist_secrets(
        self,
    ) -> None:
        account_id = AccountId("primary")
        environ = {
            "TESTNET_API_KEY": "fixture-key-v1",
            "TESTNET_SIGNING_SECRET": "fixture-signing-v1",
        }
        provider = EnvironmentBinanceCredentialProvider(
            bindings={
                account_id: BinanceCredentialBinding(
                    api_key_variable="TESTNET_API_KEY",
                    secret_variable="TESTNET_SIGNING_SECRET",
                )
            },
            environ=environ,
        )
        transport = CapturingTransport(
            response(
                200,
                {"orderId": 123, "clientOrderId": "strategy-1"},
            )
        )
        adapter = AuthenticatedBinanceExecutionAdapter(
            product=BinanceProduct.SPOT,
            credential_provider=provider,
            transport=transport,
            timestamp_ms=lambda: 1_700_000_000_000,
        )

        await adapter.submit(order())
        environ["TESTNET_API_KEY"] = "fixture-key-v2"
        environ["TESTNET_SIGNING_SECRET"] = "fixture-signing-v2"
        await adapter.submit(order())

        self.assertEqual(
            tuple(
                request.headers["X-MBX-APIKEY"]
                for _, request in transport.calls
            ),
            ("fixture-key-v1", "fixture-key-v2"),
        )
        self.assertNotEqual(
            transport.calls[0][1].query,
            transport.calls[1][1].query,
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "operator.jsonl"
            with JsonLinesOperatorCommandJournal(path) as journal:
                controller = OperatorController(
                    clock=ManualClock(),
                    journal=journal,
                )
                controller.apply(
                    command("activate", OperatorAction.ACTIVATE)
                )
                expected = controller.apply(
                    command(
                        "reduce",
                        OperatorAction.ENABLE_REDUCE_ONLY,
                    )
                )

            with JsonLinesOperatorCommandJournal(path) as journal:
                restored = OperatorController(
                    clock=ManualClock(9_000),
                    journal=journal,
                )

            self.assertEqual(restored.snapshot, expected)
            self.assertEqual(
                restored.snapshot.mode,
                OperatorMode.REDUCE_ONLY,
            )
            persisted = path.read_text(encoding="ascii")
            for sensitive in (
                "fixture-key-v1",
                "fixture-key-v2",
                "fixture-signing-v1",
                "fixture-signing-v2",
            ):
                self.assertNotIn(sensitive, persisted)


if __name__ == "__main__":
    import unittest

    unittest.main()
