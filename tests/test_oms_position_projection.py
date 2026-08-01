from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_quant.core import (
    PortfolioReconciliationId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.oms import JsonLinesOmsJournal, OrderEvent, OrderStatus
from cex_quant.portfolio import (
    AccountSnapshot,
    ExecutionConsistentPositionState,
    ExecutionCoverage,
    ReconciledAccountBaseline,
)
from cex_quant.runtime import (
    OmsExecutionEffectProjector,
    OmsExecutionProjectionError,
    OrderGroupRuntime,
)
from cex_quant.snapshots import ObservationId
from tests.group_test_support import (
    ACCOUNT_ID,
    ManualClock,
    action_for,
    admission,
    execution_plan,
    permit_for,
)


def empty_baseline(*, coverage: int) -> ReconciledAccountBaseline:
    return ReconciledAccountBaseline(
        reconciliation_id=PortfolioReconciliationId("projection-recon"),
        observation_id=ObservationId("projection-account"),
        account=AccountSnapshot(
            account_id=ACCOUNT_ID,
            venue=VenueId("BINANCE"),
            balances=(),
            positions=(),
            as_of_time_ns=UnixNanos(1_000),
            sequence=1,
        ),
        coverage=ExecutionCoverage(
            through_oms_journal_sequence=coverage,
        ),
        reconciled_at_ns=UnixNanos(1_010),
    )


class OmsExecutionEffectProjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.journal = JsonLinesOmsJournal(
            Path(self._temporary.name) / "oms.jsonl"
        )
        self.addCleanup(self.journal.close)
        self.clock = ManualClock(value=2_000)
        self.groups = OrderGroupRuntime(
            now_ns=self.clock,
            journal=self.journal,
        )
        created = self.groups.create_group(admission(), execution_plan())
        active = self.groups.activate_group(created.order_group_id)
        self.action = action_for(
            active,
            leg_index=0,
            now_ns=self.clock.step(),
            quantity="10",
        )
        self.permit = permit_for(
            self.action,
            issued_at_ns=self.clock.step(),
        )
        self.request = self.groups.prepare_child_submit(
            action=self.action,
            permit=self.permit,
        )
        self.groups.mark_transmitting(
            self.action.group_id,
            self.action.action_id,
        )
        self.groups.record_acknowledged(
            self.action.group_id,
            self.action.action_id,
        )

    def apply_fill(self, cumulative: str, update: str) -> None:
        self.groups.apply_child_event(
            OrderEvent(
                venue_update_id=update,
                client_order_id=self.request.client_order_id,
                status=(
                    OrderStatus.FILLED
                    if cumulative == "10"
                    else OrderStatus.PARTIALLY_FILLED
                ),
                cumulative_filled_quantity=Quantity.from_str(cumulative),
                event_time_ns=self.clock.step(),
                average_fill_price=Price.from_str("100"),
            )
        )

    def test_projects_incremental_fill_deltas_and_advances_coverage(self) -> None:
        self.apply_fill("4", "partial-1")
        self.apply_fill("10", "fill-2")
        batch = OmsExecutionEffectProjector(self.journal).project(
            ACCOUNT_ID,
            from_sequence_exclusive=0,
        )
        assert batch is not None
        self.assertEqual(
            tuple(
                item.signed_fill_delta.as_decimal()
                for item in batch.effects
            ),
            (-4, -6),
        )
        self.assertEqual(
            tuple(
                item.cumulative_filled_quantity.as_decimal()
                for item in batch.effects
            ),
            (4, 10),
        )

        state = ExecutionConsistentPositionState(ACCOUNT_ID)
        state.accept_baseline(empty_baseline(coverage=0))
        state.apply_execution_batch(batch)
        view = state.view()
        self.assertEqual(
            view.coverage.through_oms_journal_sequence,
            batch.through_sequence_inclusive,
        )
        projected_position = next(
            item
            for item in view.positions
            if item.instrument_id == self.action.instrument_id
        )
        self.assertEqual(
            projected_position.effective_quantity.as_decimal(),
            -10,
        )

    def test_projection_after_covered_partial_uses_only_uncovered_delta(self) -> None:
        self.apply_fill("4", "partial-1")
        covered_through = sum(1 for _ in self.journal.read())
        self.apply_fill("10", "fill-2")
        batch = OmsExecutionEffectProjector(self.journal).project(
            ACCOUNT_ID,
            from_sequence_exclusive=covered_through,
        )
        assert batch is not None
        self.assertEqual(len(batch.effects), 1)
        self.assertEqual(batch.effects[0].signed_fill_delta.as_decimal(), -6)

    def test_rejects_portfolio_coverage_beyond_journal(self) -> None:
        with self.assertRaises(OmsExecutionProjectionError):
            OmsExecutionEffectProjector(self.journal).project(
                ACCOUNT_ID,
                from_sequence_exclusive=10_000,
            )

    def test_rejects_invalid_projection_start_and_no_advance_is_none(self) -> None:
        projector = OmsExecutionEffectProjector(self.journal)
        with self.assertRaisesRegex(ValueError, "account_id"):
            projector.project("", from_sequence_exclusive=0)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "negative"):
            projector.project(ACCOUNT_ID, from_sequence_exclusive=-1)
        current = sum(1 for _ in self.journal.read())
        self.assertIsNone(
            projector.project(
                ACCOUNT_ID,
                from_sequence_exclusive=current,
            )
        )


if __name__ == "__main__":
    unittest.main()
