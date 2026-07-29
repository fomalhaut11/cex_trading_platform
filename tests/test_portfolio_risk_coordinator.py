from __future__ import annotations

import tempfile
import unittest
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from threading import Thread

from group_test_support import (
    ManualClock,
    action_for,
    execution_plan,
    two_leg_basket,
)
from portfolio_risk_test_support import (
    NOW,
    policy,
    portfolio_snapshot,
    position_view,
    product,
    publication,
    sensitivity,
)

from cex_quant.core import (
    IntentId,
    Money,
    OrderGroupId,
    PortfolioReconciliationId,
    Quantity,
    RiskDirectiveId,
    StrategyId,
    UnixNanos,
)
from cex_quant.instruments import Instrument, InstrumentKind
from cex_quant.oms import OrderGroupAdmission, OrderGroupView
from cex_quant.risk import (
    InstrumentSensitivity,
    InstrumentTargetTolerance,
    JsonLinesPortfolioRiskJournal,
    PortfolioApprovalEvidence,
    PortfolioRiskAuthorizationError,
    PortfolioRiskCoordinator,
    PortfolioRiskDirective,
    PortfolioRiskDirectiveKind,
    PortfolioRiskEngine,
    PortfolioRiskJournalEntry,
    PortfolioRiskJournalEntryKind,
    PortfolioRiskJournalIntegrityError,
    PortfolioRiskPersistenceError,
    PortfolioRiskPolicy,
    PortfolioRiskRejectReason,
    PortfolioRiskReservationState,
    PortfolioRiskWriterViolationError,
    RecoveryAuthorizationMode,
    RiskInvalidationTrigger,
    TargetMatchPolicy,
)
from cex_quant.runtime import OrderGroupRuntime
from cex_quant.snapshots import ObservationId
from cex_quant.strategy import (
    BasketTargetIntent,
    basket_target_intent_checksum,
    create_basket_target_intent,
)


class MemoryRiskJournal:
    def __init__(self) -> None:
        self.entries: list[PortfolioRiskJournalEntry] = []
        self.fail = False

    def read(self) -> Iterator[PortfolioRiskJournalEntry]:
        yield from self.entries

    def append(self, entry: PortfolioRiskJournalEntry) -> None:
        if self.fail:
            raise OSError("synthetic disk failure")
        self.entries.append(entry)


def risk_inputs() -> tuple[
    Instrument,
    Instrument,
    tuple[Instrument, ...],
    tuple[InstrumentSensitivity, ...],
]:
    spot = product(InstrumentKind.SPOT, "BTCUSDT")
    perp = product(InstrumentKind.PERPETUAL, "BTCUSDT")
    instruments = (spot, perp)
    sensitivities = (
        sensitivity(spot.instrument_id, delta="1", margin="0"),
        sensitivity(perp.instrument_id, delta="1", margin="10"),
    )
    return spot, perp, instruments, sensitivities


def basket_for_products(
    spot: Instrument,
    perp: Instrument,
    *,
    intent_id: str,
) -> BasketTargetIntent:
    base = two_leg_basket()
    return create_basket_target_intent(
        strategy_id=base.strategy_id,
        decision_snapshot_id=base.decision_snapshot_id,
        objective=base.objective,
        legs=(
            replace(base.legs[0], instrument_id=spot.instrument_id),
            replace(base.legs[1], instrument_id=perp.instrument_id),
        ),
        decision_time_ns=base.decision_time_ns,
        valid_until_ns=base.valid_until_ns,
        policy_version=base.policy_version,
        reason=f"resource test {intent_id}",
        intent_id=IntentId(intent_id),
    )


def create_group(
    approval: PortfolioApprovalEvidence,
    clock: ManualClock,
) -> tuple[OrderGroupRuntime, OrderGroupView]:
    basket = two_leg_basket()
    runtime = OrderGroupRuntime(now_ns=clock)
    view = runtime.create_group(
        OrderGroupAdmission(
            approval_id=approval.approval_id,
            basket=basket,
            basket_checksum=basket_target_intent_checksum(basket),
            approved_at_ns=approval.approved_at_ns,
            valid_until_ns=approval.valid_until_ns,
            risk_policy_version=approval.risk_policy_version,
        ),
        execution_plan(),
    )
    return runtime, runtime.activate_group(view.order_group_id)


class PortfolioRiskCoordinatorTests(unittest.TestCase):
    def test_typed_resources_allow_independence_and_serialize_capacity(
        self,
    ) -> None:
        btc_spot, btc_perp, _, _ = risk_inputs()
        eth_spot = product(InstrumentKind.SPOT, "ETHUSDT")
        eth_perp = product(InstrumentKind.PERPETUAL, "ETHUSDT")
        instruments = (btc_spot, eth_spot, btc_perp, eth_perp)
        sensitivities = tuple(
            sensitivity(
                item.instrument_id,
                delta="1",
                margin=(
                    "0"
                    if item.instrument_id.kind is InstrumentKind.SPOT
                    else "10"
                ),
            )
            for item in instruments
        )
        engine = PortfolioRiskEngine()
        normal_policy = policy(instruments)
        snapshot = publication(portfolio_snapshot(instruments, sensitivities))
        btc_decision = engine.assess_basket(
            basket_for_products(
                btc_spot,
                btc_perp,
                intent_id="btc-resource-basket",
            ),
            snapshot,
            normal_policy,
            now_ns=NOW,
        )
        eth_decision = engine.assess_basket(
            basket_for_products(
                eth_spot,
                eth_perp,
                intent_id="eth-resource-basket",
            ),
            snapshot,
            normal_policy,
            now_ns=NOW,
        )
        coordinator = PortfolioRiskCoordinator(
            journal=MemoryRiskJournal(),
            risk_policy_version=normal_policy.version,
            reservation_lifetime_ns=normal_policy.reservation_lifetime_ns,
            max_active_reservations=normal_policy.max_active_reservations,
            now_ns=NOW,
        )
        coordinator.reserve_approval(btc_decision, now_ns=NOW)
        coordinator.reserve_approval(eth_decision, now_ns=NOW)
        self.assertEqual(len(coordinator.reservations()), 2)

        constrained_policy = replace(
            normal_policy,
            max_gross_notional=Money.from_str("3000"),
        )
        btc_constrained = engine.assess_basket(
            btc_decision.basket,
            snapshot,
            constrained_policy,
            now_ns=NOW,
        )
        eth_constrained = engine.assess_basket(
            eth_decision.basket,
            snapshot,
            constrained_policy,
            now_ns=NOW,
        )
        constrained = PortfolioRiskCoordinator(
            journal=MemoryRiskJournal(),
            risk_policy_version=constrained_policy.version,
            reservation_lifetime_ns=constrained_policy.reservation_lifetime_ns,
            max_active_reservations=constrained_policy.max_active_reservations,
            now_ns=NOW,
        )
        constrained.reserve_approval(btc_constrained, now_ns=NOW)
        with self.assertRaisesRegex(
            PortfolioRiskAuthorizationError,
            "capacity exceeded",
        ):
            constrained.reserve_approval(eth_constrained, now_ns=NOW)

    def _admit(
        self,
        journal: MemoryRiskJournal | JsonLinesPortfolioRiskJournal,
    ) -> tuple[
        PortfolioApprovalEvidence,
        PortfolioRiskCoordinator,
        Instrument,
        Instrument,
        tuple[
            tuple[Instrument, ...],
            tuple[InstrumentSensitivity, ...],
            PortfolioRiskPolicy,
        ],
    ]:
        spot, perp, instruments, sensitivities = risk_inputs()
        selected_instruments = instruments
        selected_sensitivities = sensitivities
        selected_policy = policy(selected_instruments)
        decision = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(
                portfolio_snapshot(
                    selected_instruments,
                    selected_sensitivities,
                )
            ),
            selected_policy,
            now_ns=NOW,
        )
        coordinator = PortfolioRiskCoordinator(
            journal=journal,
            risk_policy_version=selected_policy.version,
            reservation_lifetime_ns=selected_policy.reservation_lifetime_ns,
            max_active_reservations=selected_policy.max_active_reservations,
            now_ns=NOW,
        )
        approval = coordinator.reserve_approval(decision, now_ns=NOW)
        return (
            approval,
            coordinator,
            spot,
            perp,
            (selected_instruments, selected_sensitivities, selected_policy),
        )

    def test_reservation_is_durable_idempotent_and_serialized(self) -> None:
        journal = MemoryRiskJournal()
        approval, coordinator, _, _, context = self._admit(journal)
        instruments, sensitivities, selected_policy = context
        decision = PortfolioRiskEngine().assess_basket(
            two_leg_basket(),
            publication(portfolio_snapshot(instruments, sensitivities)),
            selected_policy,
            now_ns=NOW,
        )
        self.assertEqual(
            coordinator.reserve_approval(decision, now_ns=NOW),
            approval,
        )
        self.assertEqual(len(coordinator.reservations()), 1)

        original = two_leg_basket()
        changed_basket = create_basket_target_intent(
            strategy_id=StrategyId("another-strategy"),
            decision_snapshot_id=original.decision_snapshot_id,
            objective=original.objective,
            legs=original.legs,
            decision_time_ns=original.decision_time_ns,
            valid_until_ns=original.valid_until_ns,
            policy_version=original.policy_version,
            reason="competing target",
            intent_id=IntentId("competing-basket"),
        )
        competing = PortfolioRiskEngine().assess_basket(
            changed_basket,
            publication(portfolio_snapshot(instruments, sensitivities)),
            selected_policy,
            now_ns=NOW,
        )
        with self.assertRaisesRegex(
            PortfolioRiskAuthorizationError,
            "conflicts",
        ):
            coordinator.reserve_approval(competing, now_ns=NOW)

    def test_permit_generation_preparation_and_consumption(self) -> None:
        journal = MemoryRiskJournal()
        approval, coordinator, spot, _, context = self._admit(journal)
        instruments, sensitivities, selected_policy = context
        clock = ManualClock(value=2_010)
        runtime, group = create_group(approval, clock)
        reservation = coordinator.attach_reservation(
            approval.approval_id,
            group.order_group_id,
            now_ns=UnixNanos(2_015),
        )
        action = action_for(
            group,
            leg_index=0,
            now_ns=UnixNanos(2_020),
            quantity="10",
        )
        decision = PortfolioRiskEngine().authorize_action(
            group,
            action,
            publication(
                portfolio_snapshot(
                    instruments,
                    sensitivities,
                    positions=position_view({spot.instrument_id: "10"}),
                    groups=(group,),
                    reservations=(reservation,),
                )
            ),
            selected_policy,
            now_ns=UnixNanos(2_020),
        )
        permit = coordinator.issue_permit(
            decision,
            now_ns=UnixNanos(2_020),
        )
        clock.value = 2_030
        runtime.prepare_child_submit(action=action, permit=permit)
        prepared_group = runtime.group(group.order_group_id)
        coordinator.validate_permit(
            permit=permit,
            action=action,
            group=prepared_group,
            now_ns=UnixNanos(2_030),
        )
        coordinator.consume_for_external_io(
            permit=permit,
            action=action,
            group=prepared_group,
            now_ns=UnixNanos(2_030),
        )
        with self.assertRaisesRegex(
            PortfolioRiskAuthorizationError,
            "consumed",
        ):
            coordinator.validate_permit(
                permit=permit,
                action=action,
                group=prepared_group,
                now_ns=UnixNanos(2_031),
            )

    def test_material_change_and_restart_invalidate_old_permit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "risk.jsonl"
            first_journal = JsonLinesPortfolioRiskJournal(path)
            approval, coordinator, spot, _, context = self._admit(
                first_journal
            )
            instruments, sensitivities, selected_policy = context
            clock = ManualClock(value=2_010)
            runtime, group = create_group(approval, clock)
            reservation = coordinator.attach_reservation(
                approval.approval_id,
                group.order_group_id,
                now_ns=UnixNanos(2_015),
            )
            action = action_for(
                group,
                leg_index=0,
                now_ns=UnixNanos(2_020),
                quantity="10",
            )
            decision = PortfolioRiskEngine().authorize_action(
                group,
                action,
                publication(
                    portfolio_snapshot(
                        instruments,
                        sensitivities,
                        positions=position_view(
                            {spot.instrument_id: "10"}
                        ),
                        reservations=(reservation,),
                    )
                ),
                selected_policy,
                now_ns=UnixNanos(2_020),
            )
            permit = coordinator.issue_permit(
                decision,
                now_ns=UnixNanos(2_020),
            )
            clock.value = 2_030
            runtime.prepare_child_submit(action=action, permit=permit)
            prepared = runtime.group(group.order_group_id)
            coordinator.record_material_change(
                now_ns=UnixNanos(2_031),
                trigger=RiskInvalidationTrigger.MARGIN_CHANGE,
                reason="margin update",
            )
            self.assertEqual(
                tuple(first_journal.read())[-1].payload["trigger"],
                RiskInvalidationTrigger.MARGIN_CHANGE.value,
            )
            with self.assertRaisesRegex(
                PortfolioRiskAuthorizationError,
                "generation",
            ):
                coordinator.validate_permit(
                    permit=permit,
                    action=action,
                    group=prepared,
                    now_ns=UnixNanos(2_032),
                )
            first_journal.close()

            second_journal = JsonLinesPortfolioRiskJournal(path)
            restarted = PortfolioRiskCoordinator(
                journal=second_journal,
                risk_policy_version=selected_policy.version,
                reservation_lifetime_ns=(
                    selected_policy.reservation_lifetime_ns
                ),
                max_active_reservations=(
                    selected_policy.max_active_reservations
                ),
                now_ns=UnixNanos(2_040),
            )
            with self.assertRaisesRegex(
                PortfolioRiskAuthorizationError,
                "generation",
            ):
                restarted.validate_permit(
                    permit=permit,
                    action=action,
                    group=prepared,
                    now_ns=UnixNanos(2_041),
                )
            second_journal.close()

    def test_recovery_and_target_confirmation_are_typed_and_durable(self) -> None:
        journal = MemoryRiskJournal()
        approval, coordinator, spot, perp, _ = self._admit(journal)
        clock = ManualClock(value=2_010)
        runtime, group = create_group(approval, clock)
        coordinator.attach_reservation(
            approval.approval_id,
            group.order_group_id,
            now_ns=UnixNanos(2_015),
        )
        recovery_group = runtime.require_recovery(
            group.order_group_id,
            reason="startup reconciliation",
        )
        reconciled = replace(
            position_view(
                {
                    spot.instrument_id: "10",
                    perp.instrument_id: "-10",
                }
            ),
            reconciliation_id=PortfolioReconciliationId("portfolio-recon"),
            observation_id=ObservationId("account-reconciled"),
        )
        authorization = coordinator.authorize_group_recovery(
            group=recovery_group,
            position_views=(reconciled,),
            reconciliation_id=PortfolioReconciliationId("portfolio-recon"),
            risk_snapshot_id=approval.risk_snapshot_id,
            mode=RecoveryAuthorizationMode.RESUME_GROUP,
            issued_at_ns=UnixNanos(2_020),
            valid_until_ns=UnixNanos(2_100),
        )
        active = runtime.resume_group(
            group.order_group_id,
            recovery_authorization_id=str(authorization.authorization_id),
        )
        closing = runtime.begin_closing(active.order_group_id)
        confirmation = coordinator.confirm_portfolio_target(
            group=closing,
            basket=two_leg_basket(),
            position_views=(reconciled,),
            risk_snapshot_id=approval.risk_snapshot_id,
            match_policy=TargetMatchPolicy(
                version=1,
                default_absolute_quantity_tolerance=Quantity.from_str("0"),
                instrument_tolerances=(),
            ),
            confirmed_at_ns=UnixNanos(2_030),
        )
        self.assertEqual(confirmation.group_id, group.order_group_id)
        self.assertTrue(
            any(
                entry.kind.value == "recovery_authorized"
                for entry in journal.entries
            )
        )
        self.assertTrue(
            any(
                entry.kind.value == "target_confirmed"
                for entry in journal.entries
            )
        )

    def test_target_confirmation_uses_versioned_quantity_tolerance(self) -> None:
        journal = MemoryRiskJournal()
        approval, coordinator, spot, perp, _ = self._admit(journal)
        runtime, group = create_group(approval, ManualClock(value=2_010))
        coordinator.attach_reservation(
            approval.approval_id,
            group.order_group_id,
            now_ns=UnixNanos(2_015),
        )
        closing = runtime.begin_closing(group.order_group_id)
        near_target = position_view(
            {
                spot.instrument_id: "9.9997",
                perp.instrument_id: "-10",
            }
        )
        with self.assertRaisesRegex(
            PortfolioRiskAuthorizationError,
            "do not match",
        ):
            coordinator.confirm_portfolio_target(
                group=closing,
                basket=two_leg_basket(),
                position_views=(near_target,),
                risk_snapshot_id=approval.risk_snapshot_id,
                match_policy=TargetMatchPolicy(
                    version=1,
                    default_absolute_quantity_tolerance=Quantity.from_str("0"),
                    instrument_tolerances=(
                        InstrumentTargetTolerance(
                            instrument_id=spot.instrument_id,
                            absolute_quantity_tolerance=Quantity.from_str(
                                "0.0001"
                            ),
                        ),
                    ),
                ),
                confirmed_at_ns=UnixNanos(2_020),
            )
        confirmation = coordinator.confirm_portfolio_target(
            group=closing,
            basket=two_leg_basket(),
            position_views=(near_target,),
            risk_snapshot_id=approval.risk_snapshot_id,
            match_policy=TargetMatchPolicy(
                version=2,
                default_absolute_quantity_tolerance=Quantity.from_str("0"),
                instrument_tolerances=(
                    InstrumentTargetTolerance(
                        instrument_id=spot.instrument_id,
                        absolute_quantity_tolerance=Quantity.from_str("0.001"),
                    ),
                ),
            ),
            confirmed_at_ns=UnixNanos(2_021),
        )
        self.assertEqual(confirmation.target_match_policy_version, 2)
        self.assertEqual(len(confirmation.target_match_policy_checksum), 64)

    def test_persistence_failure_latches_and_corruption_fails_closed(self) -> None:
        journal = MemoryRiskJournal()
        journal.fail = True
        with self.assertRaises(PortfolioRiskPersistenceError):
            self._admit(journal)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "risk.jsonl"
            durable = JsonLinesPortfolioRiskJournal(path)
            entry = PortfolioRiskJournalEntry(
                kind=(
                    PortfolioRiskJournalEntryKind.AUTHORIZATION_GENERATION_CHANGED
                ),
                at_ns=UnixNanos(1),
                payload={"generation": 2, "reason": "test"},
            )
            durable.append(entry)
            durable.close()
            raw = path.read_bytes()
            path.write_bytes(raw.replace(b'"generation":2', b'"generation":3'))
            with self.assertRaises(PortfolioRiskJournalIntegrityError):
                JsonLinesPortfolioRiskJournal(path)

    def test_reservation_control_directive_and_single_writer(self) -> None:
        journal = MemoryRiskJournal()
        approval, coordinator, _, _, _ = self._admit(journal)
        expired = coordinator.expire_due(now_ns=UnixNanos(2_500))
        self.assertEqual(
            expired[0].state,
            PortfolioRiskReservationState.EXPIRED,
        )
        self.assertEqual(
            coordinator.expire_due(now_ns=UnixNanos(2_501)),
            (),
        )
        directive = PortfolioRiskDirective(
            directive_id=RiskDirectiveId("directive-1"),
            group_id=OrderGroupId("group-1"),
            expected_group_revision=1,
            risk_snapshot_id=approval.risk_snapshot_id,
            kind=PortfolioRiskDirectiveKind.BLOCK_NEW_ACTIONS,
            reasons=(PortfolioRiskRejectReason.HEALTH_NOT_READY,),
            issued_at_ns=UnixNanos(2_502),
            risk_policy_version=1,
        )
        before_generation = coordinator.authorization_generation
        coordinator.persist_directive(directive)
        self.assertEqual(journal.entries[-2].kind.value, "directive_issued")
        self.assertGreater(
            coordinator.authorization_generation,
            before_generation,
        )

        errors: list[Exception] = []

        def other_writer() -> None:
            try:
                coordinator.record_material_change(
                    now_ns=UnixNanos(2_503),
                    trigger=RiskInvalidationTrigger.POSITION_CHANGE,
                    reason="cross-thread update",
                )
            except Exception as error:
                errors.append(error)

        thread = Thread(target=other_writer)
        thread.start()
        thread.join()
        self.assertIsInstance(
            errors[0],
            PortfolioRiskWriterViolationError,
        )

    def test_release_and_recovery_required_reservations_free_capacity(self) -> None:
        released_journal = MemoryRiskJournal()
        approval, coordinator, _, _, _ = self._admit(released_journal)
        released = coordinator.release_reservation(
            approval.approval_id,
            now_ns=UnixNanos(2_100),
            reason="group rejected before creation",
        )
        self.assertEqual(
            released.state,
            PortfolioRiskReservationState.RELEASED,
        )
        self.assertEqual(
            coordinator.release_reservation(
                approval.approval_id,
                now_ns=UnixNanos(2_101),
                reason="exact redelivery",
            ),
            released,
        )

        recovery_journal = MemoryRiskJournal()
        second_approval, second, _, _, _ = self._admit(recovery_journal)
        recovery = second.mark_reservation_recovery_required(
            second_approval.approval_id,
            now_ns=UnixNanos(2_100),
            reason="journal disagreement",
        )
        self.assertEqual(
            recovery.state,
            PortfolioRiskReservationState.RECOVERY_REQUIRED,
        )
        with self.assertRaisesRegex(
            PortfolioRiskAuthorizationError,
            "inactive",
        ):
            second.release_reservation(
                second_approval.approval_id,
                now_ns=UnixNanos(2_101),
                reason="unsafe release",
            )


if __name__ == "__main__":
    unittest.main()
