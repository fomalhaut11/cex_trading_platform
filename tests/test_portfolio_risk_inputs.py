from __future__ import annotations

import unittest
from threading import Thread

from group_test_support import ACCOUNT_ID, instrument

from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
    EventId,
    Money,
    PortfolioReconciliationId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentKind
from cex_quant.portfolio import (
    AccountSnapshot,
    ExecutionConsistentPositionState,
    ExecutionCoverage,
    ExecutionPositionEffect,
    ExecutionPositionEffectBatch,
    PortfolioPositionConflictError,
    PortfolioPositionCoverageError,
    PortfolioPositionWriterViolationError,
    Position,
    PositionAccounting,
    PositionRiskReadiness,
    ReconciledAccountBaseline,
)
from cex_quant.snapshots import ObservationId

BTC_SPOT = instrument(InstrumentKind.SPOT, "BTCUSDT")


def account_snapshot(quantity: str = "0") -> AccountSnapshot:
    positions = ()
    if quantity != "0":
        positions = (
            Position(
                instrument_id=BTC_SPOT,
                accounting=PositionAccounting.SPOT,
                quantity=Quantity.from_str(quantity),
                cost_basis=Money.from_str("100"),
                realized_pnl=Money.from_str("0"),
                pnl_asset=AssetId("USDT"),
                average_entry_price=Price.from_str("100"),
            ),
        )
    return AccountSnapshot(
        account_id=ACCOUNT_ID,
        venue=VenueId("BINANCE"),
        balances=(),
        positions=positions,
        as_of_time_ns=UnixNanos(1_000),
        sequence=1,
    )


def baseline(
    *,
    coverage: int = 10,
    quantity: str = "0",
    reconciliation_id: str = "recon-1",
) -> ReconciledAccountBaseline:
    return ReconciledAccountBaseline(
        reconciliation_id=PortfolioReconciliationId(reconciliation_id),
        observation_id=ObservationId(f"account-{reconciliation_id}"),
        account=account_snapshot(quantity),
        coverage=ExecutionCoverage(
            through_oms_journal_sequence=coverage
        ),
        reconciled_at_ns=UnixNanos(1_010),
    )


def effect(
    *,
    effect_id: str,
    sequence: int,
    cumulative: str,
    delta: str,
    client_order_id: str = "child-1",
) -> ExecutionPositionEffect:
    return ExecutionPositionEffect(
        effect_id=EventId(effect_id),
        oms_journal_sequence=sequence,
        client_order_id=ClientOrderId(client_order_id),
        account_id=ACCOUNT_ID,
        instrument_id=BTC_SPOT,
        cumulative_filled_quantity=Quantity.from_str(cumulative),
        signed_fill_delta=Quantity.from_str(delta),
        accepted_at_ns=UnixNanos(1_020 + sequence),
    )


class ExecutionConsistentPositionStateTests(unittest.TestCase):
    def test_baseline_overlay_partial_fill_and_duplicate_batch(self) -> None:
        state = ExecutionConsistentPositionState(ACCOUNT_ID)
        state.accept_baseline(baseline())
        first = ExecutionPositionEffectBatch(
            from_sequence_exclusive=10,
            through_sequence_inclusive=12,
            effects=(
                effect(
                    effect_id="fill-1",
                    sequence=12,
                    cumulative="1",
                    delta="1",
                ),
            ),
        )
        state.apply_execution_batch(first)
        second = ExecutionPositionEffectBatch(
            from_sequence_exclusive=12,
            through_sequence_inclusive=15,
            effects=(
                effect(
                    effect_id="fill-2",
                    sequence=15,
                    cumulative="3",
                    delta="2",
                ),
            ),
        )
        state.apply_execution_batch(second)
        state.apply_execution_batch(second)

        view = state.view()
        self.assertEqual(view.readiness, PositionRiskReadiness.READY)
        self.assertEqual(
            view.positions[0].effective_quantity.as_decimal(),
            Quantity.from_str("3").as_decimal(),
        )
        self.assertEqual(view.coverage.through_oms_journal_sequence, 15)

    def test_new_baseline_covers_old_fills_without_double_count(self) -> None:
        state = ExecutionConsistentPositionState(ACCOUNT_ID)
        state.accept_baseline(baseline())
        state.apply_execution_batch(
            ExecutionPositionEffectBatch(
                from_sequence_exclusive=10,
                through_sequence_inclusive=12,
                effects=(
                    effect(
                        effect_id="fill-1",
                        sequence=12,
                        cumulative="3",
                        delta="3",
                    ),
                ),
            )
        )
        state.accept_baseline(
            baseline(
                coverage=12,
                quantity="3",
                reconciliation_id="recon-2",
            )
        )

        view = state.view()
        self.assertEqual(
            view.positions[0].baseline_quantity.as_decimal(),
            Quantity.from_str("3").as_decimal(),
        )
        self.assertEqual(view.positions[0].post_baseline_fill_delta.raw, 0)
        self.assertEqual(
            view.positions[0].effective_quantity.as_decimal(),
            Quantity.from_str("3").as_decimal(),
        )

    def test_missing_range_and_decreasing_fill_fail_closed(self) -> None:
        state = ExecutionConsistentPositionState(ACCOUNT_ID)
        state.accept_baseline(baseline())
        with self.assertRaises(PortfolioPositionCoverageError):
            state.apply_execution_batch(
                ExecutionPositionEffectBatch(
                    from_sequence_exclusive=11,
                    through_sequence_inclusive=12,
                    effects=(),
                )
            )
        self.assertEqual(
            state.view().readiness,
            PositionRiskReadiness.RECOVERY_REQUIRED,
        )

        recovered = ExecutionConsistentPositionState(ACCOUNT_ID)
        recovered.accept_baseline(baseline())
        recovered.apply_execution_batch(
            ExecutionPositionEffectBatch(
                from_sequence_exclusive=10,
                through_sequence_inclusive=12,
                effects=(
                    effect(
                        effect_id="fill-1",
                        sequence=12,
                        cumulative="3",
                        delta="3",
                    ),
                ),
            )
        )
        with self.assertRaises(PortfolioPositionConflictError):
            recovered.apply_execution_batch(
                ExecutionPositionEffectBatch(
                    from_sequence_exclusive=12,
                    through_sequence_inclusive=13,
                    effects=(
                        effect(
                            effect_id="fill-2",
                            sequence=13,
                            cumulative="2",
                            delta="-1",
                        ),
                    ),
                )
            )
        self.assertEqual(
            recovered.view().readiness,
            PositionRiskReadiness.RECOVERY_REQUIRED,
        )

    def test_same_watermark_divergence_requires_explicit_reset(self) -> None:
        state = ExecutionConsistentPositionState(ACCOUNT_ID)
        state.accept_baseline(baseline(quantity="1"))
        state.accept_baseline(
            baseline(quantity="2", reconciliation_id="recon-2")
        )
        self.assertEqual(
            state.view().readiness,
            PositionRiskReadiness.DIVERGENT,
        )
        state.accept_baseline(
            baseline(quantity="2", reconciliation_id="recon-3"),
            allow_recovery_reset=True,
        )
        self.assertEqual(state.view().readiness, PositionRiskReadiness.READY)

    def test_scope_identity_and_single_writer_are_enforced(self) -> None:
        state = ExecutionConsistentPositionState(ACCOUNT_ID)
        state.accept_baseline(baseline())
        errors: list[Exception] = []

        def other_writer() -> None:
            try:
                state.mark_recovery_required("operator reconciliation")
            except Exception as error:
                errors.append(error)

        worker = Thread(target=other_writer)
        worker.start()
        worker.join()
        self.assertIsInstance(
            errors[0],
            PortfolioPositionWriterViolationError,
        )

        other = ExecutionConsistentPositionState(AccountId("other"))
        with self.assertRaisesRegex(
            RuntimeError,
            "baseline account",
        ):
            other.accept_baseline(baseline())


if __name__ == "__main__":
    unittest.main()
