from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_quant.core import Price, Quantity
from cex_quant.instruments import InstrumentKind
from cex_quant.oms import (
    ExecutionActionState,
    JsonLinesOmsJournal,
    OrderEvent,
    OrderGroupStatus,
    OrderStatus,
)
from cex_quant.portfolio import PositionRiskReadiness
from cex_quant.risk import (
    JsonLinesPortfolioRiskJournal,
    PortfolioRiskCoordinator,
    PortfolioRiskEngine,
)
from cex_quant.runtime import (
    GROUPED_BOOTSTRAP_ORDER,
    DeterministicOfflineExecutionPort,
    GroupedAdmissionDisposition,
    GroupedBootstrapEvidence,
    GroupedBootstrapStep,
    GroupedCancelDisposition,
    GroupedExecutionRuntime,
    GroupedExecutionRuntimeStateError,
    GroupedExecutionRuntimeStatus,
    GroupedExecutionStepDisposition,
    OfflineExecutionDirective,
    OfflineExecutionDirectiveKind,
    OrderGroupRuntime,
)
from tests.group_test_support import (
    ManualClock,
    execution_plan,
    two_leg_basket,
)
from tests.portfolio_risk_test_support import (
    NOW,
    policy,
    portfolio_snapshot,
    position_view,
    product,
    publication,
    sensitivity,
)


class _AllowSubmitGuard:
    def assert_submit_allowed(self, request: object) -> None:
        del request


class _HaltSubmitGuard:
    def assert_submit_allowed(self, request: object) -> None:
        del request
        raise RuntimeError("operator halted")


class _AdvanceClockGuard:
    def __init__(self, clock: ManualClock, amount: int) -> None:
        self._clock = clock
        self._amount = amount

    def assert_submit_allowed(self, request: object) -> None:
        del request
        self._clock.step(self._amount)


class GroupedExecutionRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.clock = ManualClock(value=int(NOW))
        self.spot = product(InstrumentKind.SPOT, "BTCUSDT")
        self.perpetual = product(InstrumentKind.PERPETUAL, "BTCUSDT")
        self.instruments = (self.spot, self.perpetual)
        self.sensitivities = (
            sensitivity(self.spot.instrument_id, delta="1", margin="0"),
            sensitivity(
                self.perpetual.instrument_id,
                delta="1",
                margin="10",
            ),
        )
        self.policy = policy(self.instruments)
        self.journal = JsonLinesPortfolioRiskJournal(
            Path(self._temporary.name) / "risk.jsonl"
        )
        self.addCleanup(self.journal.close)
        self.coordinator = PortfolioRiskCoordinator(
            journal=self.journal,
            risk_policy_version=self.policy.version,
            reservation_lifetime_ns=self.policy.reservation_lifetime_ns,
            max_active_reservations=self.policy.max_active_reservations,
            now_ns=NOW,
        )
        self.groups = OrderGroupRuntime(now_ns=self.clock)

    def runtime(
        self,
        *directives: OfflineExecutionDirective,
        halt: bool = False,
        guard: object | None = None,
        cancel_directives: tuple[OfflineExecutionDirective, ...] = (),
    ) -> tuple[GroupedExecutionRuntime, DeterministicOfflineExecutionPort]:
        execution = DeterministicOfflineExecutionPort(
            tuple(directives),
            cancel_directives=cancel_directives,
        )
        runtime = GroupedExecutionRuntime(
            risk_engine=PortfolioRiskEngine(),
            risk_coordinator=self.coordinator,
            groups=self.groups,
            execution=execution,
            cancel_execution=execution,
            platform_guard=(
                guard
                or (_HaltSubmitGuard() if halt else _AllowSubmitGuard())
            ),
            execution_plan=execution_plan(),
            now_ns=self.clock,
        )
        runtime.start()
        return runtime, execution

    def admit(self, runtime: GroupedExecutionRuntime):
        return runtime.admit(
            two_leg_basket(),
            publication(
                portfolio_snapshot(self.instruments, self.sensitivities)
            ),
            self.policy,
        )

    def action_snapshot(self, admission, quantities=None):
        assert admission.group is not None
        assert admission.reservation is not None
        return publication(
            portfolio_snapshot(
                self.instruments,
                self.sensitivities,
                positions=position_view(quantities),
                groups=(self.groups.group(admission.group.order_group_id),),
                reservations=(admission.reservation,),
            )
        )

    def fill(self, runtime: GroupedExecutionRuntime, step, quantity: str) -> None:
        assert step.action is not None
        action_view = next(
            item
            for item in step.group.actions
            if item.action.action_id == step.action.action_id
        )
        self.clock.step()
        runtime.apply_child_event(
            OrderEvent(
                venue_update_id=f"fill:{action_view.child_order_id}",
                client_order_id=action_view.child_order_id,
                status=OrderStatus.FILLED,
                cumulative_filled_quantity=Quantity.from_str(quantity),
                event_time_ns=self.clock(),
                venue_order_id=action_view.venue_order_id,
                average_fill_price=Price.from_str("100"),
            )
        )

    def test_two_leg_loop_uses_exact_permits_and_no_network(self) -> None:
        accepted = OfflineExecutionDirective(
            kind=OfflineExecutionDirectiveKind.ACCEPT
        )
        runtime, execution = self.runtime(accepted, accepted)
        admission = self.admit(runtime)
        self.assertEqual(
            admission.disposition,
            GroupedAdmissionDisposition.ADMITTED,
        )
        assert admission.group is not None

        first = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        self.assertEqual(
            first.disposition,
            GroupedExecutionStepDisposition.ACCEPTED,
        )
        self.assertEqual(first.action.quantity.as_decimal(), 10)
        self.fill(runtime, first, "10")

        first_quantities = {
            first.action.instrument_id: (
                "10" if first.action.side.value == "buy" else "-10"
            )
        }

        second = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(
                admission,
                first_quantities,
            ),
            self.policy,
        )
        self.assertEqual(
            second.disposition,
            GroupedExecutionStepDisposition.ACCEPTED,
        )
        self.assertEqual(second.action.quantity.as_decimal(), 10)
        self.assertNotEqual(
            first.action.instrument_id,
            second.action.instrument_id,
        )
        self.assertEqual(
            {first.action.side.value, second.action.side.value},
            {"buy", "sell"},
        )
        self.fill(runtime, second, "10")

        complete = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(
                admission,
                {
                    self.spot.instrument_id: "10",
                    self.perpetual.instrument_id: "-10",
                },
            ),
            self.policy,
        )
        self.assertEqual(
            complete.disposition,
            GroupedExecutionStepDisposition.NO_ACTION,
        )
        self.assertEqual(len(execution.submissions), 2)
        self.assertEqual(runtime.status, GroupedExecutionRuntimeStatus.RUNNING)

    def test_timeout_after_send_latches_recovery_and_no_blind_retry(self) -> None:
        runtime, execution = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.UNKNOWN,
                reason="timeout after send",
            )
        )
        admission = self.admit(runtime)
        assert admission.group is not None
        result = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        self.assertEqual(
            result.disposition,
            GroupedExecutionStepDisposition.UNKNOWN,
        )
        self.assertEqual(
            result.group.actions[0].state,
            ExecutionActionState.UNKNOWN,
        )
        self.assertEqual(
            runtime.status,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        )
        self.assertEqual(len(execution.submissions), 1)
        with self.assertRaises(GroupedExecutionRuntimeStateError):
            runtime.execute_next(
                admission.group.order_group_id,
                self.action_snapshot(admission),
                self.policy,
            )
        self.assertEqual(len(execution.submissions), 1)

    def test_operator_halt_is_durable_definitely_not_sent(self) -> None:
        runtime, execution = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.ACCEPT
            ),
            halt=True,
        )
        admission = self.admit(runtime)
        assert admission.group is not None
        result = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        self.assertEqual(
            result.disposition,
            GroupedExecutionStepDisposition.DEFINITELY_NOT_SENT,
        )
        self.assertEqual(execution.submissions, ())
        self.assertIn(
            result.group.actions[0].state,
            {
                ExecutionActionState.RETRY_ELIGIBLE,
                ExecutionActionState.REJECTED,
            },
        )
        self.assertEqual(
            runtime.status,
            GroupedExecutionRuntimeStatus.HALTED,
        )

    def test_immediate_reject_routes_to_exact_group_action(self) -> None:
        runtime, _ = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.REJECT,
                reason="venue rejected",
            )
        )
        admission = self.admit(runtime)
        assert admission.group is not None
        result = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        self.assertEqual(
            result.disposition,
            GroupedExecutionStepDisposition.REJECTED,
        )
        self.assertEqual(
            result.group.actions[0].state,
            ExecutionActionState.REJECTED,
        )
        self.assertEqual(
            runtime.status,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        )

    def test_restart_blocks_submission_until_ordered_bootstrap_is_complete(
        self,
    ) -> None:
        oms_path = Path(self._temporary.name) / "oms.jsonl"
        first_journal = JsonLinesOmsJournal(oms_path)
        self.groups = OrderGroupRuntime(
            now_ns=self.clock,
            journal=first_journal,
        )
        first, _ = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.UNKNOWN,
                reason="timeout after send",
            )
        )
        admission = self.admit(first)
        assert admission.group is not None
        step = first.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        assert step.action is not None
        child = step.group.actions[0]
        first_journal.close()

        replay_journal = JsonLinesOmsJournal(oms_path)
        self.addCleanup(replay_journal.close)
        self.groups = OrderGroupRuntime(
            now_ns=self.clock,
            journal=replay_journal,
        )
        restarted, execution = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.ACCEPT,
            )
        )
        self.assertEqual(
            restarted.status,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        )
        with self.assertRaises(GroupedExecutionRuntimeStateError):
            restarted.execute_next(
                admission.group.order_group_id,
                self.action_snapshot(admission),
                self.policy,
            )
        self.assertEqual(execution.submissions, ())

        self.clock.step()
        restarted.apply_recovery_child_event(
            OrderEvent(
                venue_update_id="recovered-fill",
                client_order_id=child.child_order_id,
                status=OrderStatus.FILLED,
                cumulative_filled_quantity=child.action.quantity,
                event_time_ns=self.clock(),
                average_fill_price=Price.from_str("100"),
            )
        )
        incomplete = GroupedBootstrapEvidence(
            completed_steps=GROUPED_BOOTSTRAP_ORDER[:-1],
            external_io_disabled=True,
            healthy=True,
        )
        with self.assertRaises(GroupedExecutionRuntimeStateError):
            restarted.complete_bootstrap(incomplete)
        restarted.complete_bootstrap(
            GroupedBootstrapEvidence(
                completed_steps=GROUPED_BOOTSTRAP_ORDER,
                external_io_disabled=True,
                healthy=True,
            ),
            recovery_authorization_id="operator-recovery-1",
        )
        self.assertEqual(
            restarted.status,
            GroupedExecutionRuntimeStatus.RUNNING,
        )

    def test_bootstrap_evidence_rejects_out_of_order_steps(self) -> None:
        with self.assertRaisesRegex(ValueError, "out of order"):
            GroupedBootstrapEvidence(
                completed_steps=(
                    GroupedBootstrapStep.JOURNALS_REPLAYED,
                    GroupedBootstrapStep.ORDERS_RECONCILED,
                ),
                external_io_disabled=True,
                healthy=True,
            )

    def test_permit_expiry_at_immediate_guard_prevents_external_io(self) -> None:
        runtime, execution = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.ACCEPT,
            ),
            guard=_AdvanceClockGuard(self.clock, 101),
        )
        admission = self.admit(runtime)
        assert admission.group is not None
        result = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        self.assertEqual(
            result.disposition,
            GroupedExecutionStepDisposition.DEFINITELY_NOT_SENT,
        )
        self.assertEqual(execution.submissions, ())
        self.assertEqual(
            runtime.status,
            GroupedExecutionRuntimeStatus.HALTED,
        )

    def test_unreconciled_position_change_is_risk_rejected(self) -> None:
        runtime, execution = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.ACCEPT,
            )
        )
        admission = self.admit(runtime)
        assert admission.group is not None
        assert admission.reservation is not None
        unsafe_snapshot = publication(
            portfolio_snapshot(
                self.instruments,
                self.sensitivities,
                positions=position_view(
                    readiness=PositionRiskReadiness.RECOVERY_REQUIRED,
                ),
                groups=(self.groups.group(admission.group.order_group_id),),
                reservations=(admission.reservation,),
            )
        )
        result = runtime.execute_next(
            admission.group.order_group_id,
            unsafe_snapshot,
            self.policy,
        )
        self.assertEqual(
            result.disposition,
            GroupedExecutionStepDisposition.RISK_REJECTED,
        )
        self.assertEqual(execution.submissions, ())

    def test_cancel_transport_failure_latches_group_recovery(self) -> None:
        runtime, execution = self.runtime(
            OfflineExecutionDirective(
                kind=OfflineExecutionDirectiveKind.ACCEPT,
            ),
            cancel_directives=(
                OfflineExecutionDirective(
                    kind=(
                        OfflineExecutionDirectiveKind.DEFINITELY_NOT_SENT
                    ),
                    reason="cancel transport unavailable",
                ),
            ),
        )
        admission = self.admit(runtime)
        assert admission.group is not None
        submitted = runtime.execute_next(
            admission.group.order_group_id,
            self.action_snapshot(admission),
            self.policy,
        )
        assert submitted.action is not None
        child = submitted.group.actions[0]
        self.clock.step()
        runtime.apply_child_event(
            OrderEvent(
                venue_update_id="child-open",
                client_order_id=child.child_order_id,
                status=OrderStatus.OPEN,
                cumulative_filled_quantity=Quantity.from_str("0"),
                event_time_ns=self.clock(),
                venue_order_id=child.venue_order_id,
            )
        )
        canceled = runtime.cancel_child(
            admission.group.order_group_id,
            child.child_order_id,
        )
        self.assertEqual(
            canceled.disposition,
            GroupedCancelDisposition.DEFINITELY_NOT_SENT,
        )
        self.assertEqual(len(execution.cancellations), 1)
        self.assertEqual(
            canceled.group.status,
            OrderGroupStatus.RECOVERY_REQUIRED,
        )
        self.assertEqual(
            runtime.status,
            GroupedExecutionRuntimeStatus.RECOVERY_REQUIRED,
        )


if __name__ == "__main__":
    unittest.main()
