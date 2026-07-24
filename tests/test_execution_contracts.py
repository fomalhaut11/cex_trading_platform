from unittest import IsolatedAsyncioTestCase, TestCase

from cex_quant.core import AccountId, ClientOrderId, VenueId
from cex_quant.execution import (
    CancelOrder,
    CancelResult,
    ExecutionGateway,
    ExecutionOutcome,
    SubmitResult,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import OrderRequest


def instrument() -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=InstrumentKind.SPOT,
        symbol="BTCUSDT",
    )


class ExecutionContractsTest(TestCase):
    def test_constructs_cancel_command_with_original_client_id(self) -> None:
        cancel = CancelOrder(
            account_id=AccountId("primary"),
            instrument_id=instrument(),
            client_order_id=ClientOrderId("strategy-42"),
        )
        self.assertEqual(cancel.client_order_id, ClientOrderId("strategy-42"))

    def test_cancel_rejects_invalid_client_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "client_order_id"):
            CancelOrder(
                account_id=AccountId("primary"),
                instrument_id=instrument(),
                client_order_id=ClientOrderId(" bad "),
            )

    def test_rejected_result_requires_complete_details(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires rejection"):
            SubmitResult(
                client_order_id=ClientOrderId("strategy-42"),
                outcome=ExecutionOutcome.REJECTED,
            )
        accepted = CancelResult(
            client_order_id=ClientOrderId("strategy-42"),
            outcome=ExecutionOutcome.ACCEPTED,
        )
        self.assertIsNone(accepted.rejection_code)

    def test_non_rejected_result_forbids_rejection_details(self) -> None:
        with self.assertRaisesRegex(ValueError, "only a rejected"):
            SubmitResult(
                client_order_id=ClientOrderId("strategy-42"),
                outcome=ExecutionOutcome.ACCEPTED,
                rejection_code="timeout",
                rejection_message="unexpected detail",
            )


class ExampleGateway:
    async def submit(self, command: OrderRequest) -> SubmitResult:
        return SubmitResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )

    async def cancel(self, command: CancelOrder) -> CancelResult:
        return CancelResult(
            client_order_id=command.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )


class ExecutionGatewayProtocolTest(IsolatedAsyncioTestCase):
    async def test_protocol_accepts_oms_order_request(self) -> None:
        gateway: ExecutionGateway = ExampleGateway()
        cancel = CancelOrder(
            account_id=AccountId("primary"),
            instrument_id=instrument(),
            client_order_id=ClientOrderId("strategy-42"),
        )
        result = await gateway.cancel(cancel)
        self.assertIs(result.outcome, ExecutionOutcome.ACCEPTED)


if __name__ == "__main__":
    import unittest

    unittest.main()
