import unittest

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Quantity,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.execution import (
    ExecutionOutcome,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    SubmitResult,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    OrderRequest,
    OrderSide,
    OrderSubmitOutcome,
    OrderType,
)
from cex_quant.runtime import (
    DurableExecutionHandoff,
    ExecutionBridgeStateError,
    ExternalSubmitBlockedError,
)


def request() -> OrderRequest:
    return OrderRequest(
        client_order_id=ClientOrderId("handoff-order-1"),
        approval_id="approval-1",
        intent_id=IntentId("intent-1"),
        account_id=AccountId("primary"),
        instrument_id=InstrumentId(
            venue=VenueId("TEST"),
            kind=InstrumentKind.PERPETUAL,
            symbol="BTCUSDT",
        ),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity.from_str("1"),
        created_at_ns=UnixNanos(100),
    )


class _Oms:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def prepare_submit(self, value: OrderRequest) -> object:
        self.calls.append(("prepare", value.client_order_id))
        return value

    def record_submit_result(self, result: SubmitResult) -> object:
        self.calls.append(("result", result.outcome))
        return result

    def record_submit_failure(
        self,
        client_order_id: ClientOrderId,
        *,
        outcome: OrderSubmitOutcome,
        reason: str,
    ) -> object:
        self.calls.append(("failure", client_order_id, outcome, reason))
        return outcome


class _Execution:
    def __init__(
        self,
        *,
        result: SubmitResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[ClientOrderId] = []

    def submit(self, value: OrderRequest) -> SubmitResult:
        self.calls.append(value.client_order_id)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("test execution has no result")
        return self.result


class _Guard:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[ClientOrderId] = []

    def assert_submit_allowed(self, value: OrderRequest) -> None:
        self.calls.append(value.client_order_id)
        if self.error is not None:
            raise self.error


class DurableExecutionHandoffTests(unittest.TestCase):
    def test_preparation_precedes_external_call_and_result_recording(self) -> None:
        value = request()
        oms = _Oms()
        execution = _Execution(
            result=SubmitResult(
                client_order_id=value.client_order_id,
                outcome=ExecutionOutcome.ACCEPTED,
                venue_order_id=VenueOrderId("venue-1"),
            )
        )
        guard = _Guard()

        result = DurableExecutionHandoff(
            oms=oms,
            execution=execution,
            guard=guard,
        ).submit(value)

        self.assertEqual(result.outcome, ExecutionOutcome.ACCEPTED)
        self.assertEqual(guard.calls, [value.client_order_id])
        self.assertEqual(execution.calls, [value.client_order_id])
        self.assertEqual(
            oms.calls,
            [
                ("prepare", value.client_order_id),
                ("result", ExecutionOutcome.ACCEPTED),
            ],
        )

    def test_definitely_not_sent_and_unknown_failures_are_distinct(self) -> None:
        cases = (
            (
                ExecutionTransportError("connect refused"),
                OrderSubmitOutcome.DEFINITELY_NOT_SENT,
            ),
            (
                ExecutionStateUnknownError("read timed out after send"),
                OrderSubmitOutcome.UNKNOWN,
            ),
            (
                RuntimeError("untyped gateway failure"),
                OrderSubmitOutcome.UNKNOWN,
            ),
            (
                ExecutionBridgeStateError("bridge is not running"),
                OrderSubmitOutcome.DEFINITELY_NOT_SENT,
            ),
        )
        for error, expected in cases:
            with self.subTest(expected=expected):
                value = request()
                oms = _Oms()
                execution = _Execution(error=error)
                handoff = DurableExecutionHandoff(
                    oms=oms,
                    execution=execution,
                    guard=_Guard(),
                )

                with self.assertRaises(type(error)):
                    handoff.submit(value)

                self.assertEqual(oms.calls[0], ("prepare", value.client_order_id))
                failure = oms.calls[1]
                self.assertEqual(failure[0], "failure")
                self.assertEqual(failure[2], expected)

    def test_mismatched_result_identity_is_unknown_and_never_accepted(self) -> None:
        value = request()
        oms = _Oms()
        execution = _Execution(
            result=SubmitResult(
                client_order_id=ClientOrderId("another-order"),
                outcome=ExecutionOutcome.ACCEPTED,
            )
        )

        with self.assertRaisesRegex(RuntimeError, "does not belong"):
            DurableExecutionHandoff(
                oms=oms,
                execution=execution,
                guard=_Guard(),
            ).submit(value)

        self.assertEqual(
            oms.calls[-1][2],
            OrderSubmitOutcome.UNKNOWN,
        )

    def test_guard_failure_after_durability_is_definitely_not_sent(self) -> None:
        value = request()
        oms = _Oms()
        execution = _Execution(
            result=SubmitResult(
                client_order_id=value.client_order_id,
                outcome=ExecutionOutcome.ACCEPTED,
            )
        )
        guard = _Guard(error=RuntimeError("operator halted"))

        with self.assertRaises(ExternalSubmitBlockedError):
            DurableExecutionHandoff(
                oms=oms,
                execution=execution,
                guard=guard,
            ).submit(value)

        self.assertEqual(guard.calls, [value.client_order_id])
        self.assertEqual(execution.calls, [])
        self.assertEqual(oms.calls[0], ("prepare", value.client_order_id))
        self.assertEqual(
            oms.calls[1][2],
            OrderSubmitOutcome.DEFINITELY_NOT_SENT,
        )


if __name__ == "__main__":
    unittest.main()
