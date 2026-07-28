"""A014 offline acceptance for the accepted ADR-011 boundary."""

import tempfile
import unittest
from pathlib import Path

from cex_quant.core import Quantity
from cex_quant.instruments import InstrumentKind
from cex_quant.oms import (
    JsonLinesOmsJournal,
    OrderGroupStatus,
)
from cex_quant.runtime import (
    GroupedExecutionBlockedError,
    OrderGroupRuntime,
)
from tests.group_test_support import (
    ManualClock,
    action_for,
    admission,
    execution_plan,
    permit_for,
    three_leg_basket,
    two_leg_basket,
)


class Adr011AcceptanceTests(unittest.TestCase):
    def test_two_leg_target_becomes_durable_group_but_not_exchange_call(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            clock = ManualClock()
            with JsonLinesOmsJournal(path) as journal:
                runtime = OrderGroupRuntime(now_ns=clock, journal=journal)
                created = runtime.create_group(
                    admission(two_leg_basket()),
                    execution_plan(),
                )

                self.assertEqual(created.status, OrderGroupStatus.CREATED)
                self.assertEqual(created.actions, ())
                self.assertEqual(
                    tuple(item.target_quantity for item in created.legs),
                    (Quantity.from_str("-10"), Quantity.from_str("10")),
                )
                clock.step()
                active = runtime.activate_group(created.order_group_id)
                action = action_for(
                    active,
                    leg_index=1,
                    now_ns=clock.step(),
                    quantity="10",
                )
                child = runtime.prepare_child_submit(
                    action=action,
                    permit=permit_for(action, issued_at_ns=clock()),
                )
                with self.assertRaisesRegex(
                    GroupedExecutionBlockedError,
                    "ADR-012",
                ):
                    runtime.submit_prepared_child(child.client_order_id)

            with JsonLinesOmsJournal(path) as recovered_journal:
                recovered = OrderGroupRuntime(
                    now_ns=clock,
                    journal=recovered_journal,
                )
                self.assertEqual(
                    recovered.child(child.client_order_id).request,
                    child,
                )
                self.assertEqual(len(recovered.recovery_candidates()), 1)

    def test_same_group_contract_accepts_option_spread_plus_delta_hedge(
        self,
    ) -> None:
        runtime = OrderGroupRuntime(now_ns=ManualClock())
        view = runtime.create_group(
            admission(three_leg_basket()),
            execution_plan(),
        )

        self.assertEqual(len(view.legs), 3)
        self.assertEqual(
            {item.instrument_id.kind for item in view.legs},
            {InstrumentKind.OPTION, InstrumentKind.PERPETUAL},
        )
        self.assertEqual(view.actions, ())
        self.assertFalse(
            {"HEDGED", "PARTIALLY_HEDGED"} & set(OrderGroupStatus.__members__)
        )


if __name__ == "__main__":
    unittest.main()
