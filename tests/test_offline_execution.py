from __future__ import annotations

import unittest
from typing import cast

from cex_quant.core import (
    ClientOrderId,
    IntentId,
    Quantity,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.execution import (
    CancelOrder,
    ExecutionOutcome,
    ExecutionStateUnknownError,
    ExecutionTransportError,
)
from cex_quant.instruments import InstrumentKind
from cex_quant.oms import OrderRequest, OrderSide, OrderType
from cex_quant.runtime import (
    DeterministicOfflineExecutionPort,
    OfflineExecutionDirective,
    OfflineExecutionDirectiveKind,
    OfflineExecutionScriptExhaustedError,
)
from tests.group_test_support import ACCOUNT_ID, instrument

CLIENT_ORDER_ID = ClientOrderId("offline-client")
INSTRUMENT_ID = instrument(InstrumentKind.SPOT, "BTCUSDT")


def request() -> OrderRequest:
    return OrderRequest(
        client_order_id=CLIENT_ORDER_ID,
        approval_id="offline-approval",
        intent_id=IntentId("offline-intent"),
        account_id=ACCOUNT_ID,
        instrument_id=INSTRUMENT_ID,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity.from_str("1"),
        created_at_ns=UnixNanos(1_000),
    )


def cancel() -> CancelOrder:
    return CancelOrder(
        account_id=ACCOUNT_ID,
        instrument_id=INSTRUMENT_ID,
        client_order_id=CLIENT_ORDER_ID,
    )


class DeterministicOfflineExecutionPortTests(unittest.TestCase):
    def test_submit_script_routes_all_immediate_outcomes(self) -> None:
        port = DeterministicOfflineExecutionPort(
            (
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.ACCEPT,
                    venue_order_id=VenueOrderId("offline-venue"),
                ),
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.REJECT,
                    reason="rejected",
                ),
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.DEFINITELY_NOT_SENT,
                    reason="before send",
                ),
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.UNKNOWN,
                    reason="after send",
                ),
            )
        )
        accepted = port.submit(request())
        rejected = port.submit(request())
        with self.assertRaises(ExecutionTransportError):
            port.submit(request())
        with self.assertRaises(ExecutionStateUnknownError):
            port.submit(request())
        with self.assertRaises(OfflineExecutionScriptExhaustedError):
            port.submit(request())

        self.assertEqual(accepted.outcome, ExecutionOutcome.ACCEPTED)
        self.assertEqual(accepted.venue_order_id, VenueOrderId("offline-venue"))
        self.assertEqual(rejected.outcome, ExecutionOutcome.REJECTED)
        self.assertEqual(port.remaining, 0)
        self.assertEqual(
            port.submitted_client_order_ids(),
            (CLIENT_ORDER_ID,) * 4,
        )

    def test_cancel_script_routes_accept_reject_unknown_and_exhaustion(self) -> None:
        port = DeterministicOfflineExecutionPort(
            (
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.ACCEPT
                ),
            ),
            cancel_directives=(
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.ACCEPT
                ),
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.REJECT,
                    reason="cancel rejected",
                ),
                OfflineExecutionDirective(
                    kind=OfflineExecutionDirectiveKind.UNKNOWN,
                    reason="cancel unknown",
                ),
            ),
        )
        accepted = port.cancel(cancel())
        rejected = port.cancel(cancel())
        with self.assertRaises(ExecutionStateUnknownError):
            port.cancel(cancel())
        with self.assertRaises(OfflineExecutionScriptExhaustedError):
            port.cancel(cancel())

        self.assertEqual(accepted.outcome, ExecutionOutcome.ACCEPTED)
        self.assertEqual(rejected.outcome, ExecutionOutcome.REJECTED)
        self.assertEqual(len(port.cancellations), 3)

    def test_directive_and_script_validation_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            DeterministicOfflineExecutionPort(())
        with self.assertRaisesRegex(ValueError, "kind"):
            OfflineExecutionDirective(
                kind=cast(OfflineExecutionDirectiveKind, "invalid")
            )
        with self.assertRaisesRegex(ValueError, "trimmed"):
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.REJECT,
                reason=" bad ",
            )
        with self.assertRaisesRegex(ValueError, "cannot contain"):
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.ACCEPT,
                reason="unexpected",
            )
        with self.assertRaisesRegex(ValueError, "requires a reason"):
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.UNKNOWN
            )
        with self.assertRaisesRegex(ValueError, "venue_order_id"):
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.REJECT,
                reason="rejected",
                venue_order_id=VenueOrderId("not-allowed"),
            )


if __name__ == "__main__":
    unittest.main()
