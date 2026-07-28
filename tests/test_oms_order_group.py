import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Thread

from group_test_support import (
    ManualClock,
    action_for,
    admission,
    execution_plan,
    max_leg_basket,
    permit_for,
    three_leg_basket,
    two_leg_basket,
)

from cex_quant.core import (
    ClientOrderId,
    ExecutionPermitId,
    GroupActionId,
    OrderGroupId,
    PortfolioApprovalId,
    Quantity,
    UnixNanos,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentKind
from cex_quant.oms import (
    MAX_GROUP_CHILDREN,
    ExecutionActionState,
    JsonLinesOmsJournal,
    OrderEvent,
    OrderGroupAuthorizationError,
    OrderGroupCapacityError,
    OrderGroupCloseOutcome,
    OrderGroupIdentityError,
    OrderGroupLimits,
    OrderGroupStateMachine,
    OrderGroupStatus,
    OrderGroupTransitionError,
    OrderGroupWriterViolationError,
    OrderStatus,
    decode_execution_action,
    decode_execution_action_permit,
    decode_execution_plan_ref,
    decode_order_group_admission,
    deterministic_order_group_id,
    encode_execution_action,
    encode_execution_action_permit,
    encode_execution_plan_ref,
    encode_order_group_admission,
)
from cex_quant.runtime import (
    GroupedExecutionBlockedError,
    OrderGroupPersistenceError,
    OrderGroupRuntime,
    OrderGroupRuntimeError,
)


def active_runtime(
    *,
    basket=None,
    journal=None,
) -> tuple[OrderGroupRuntime, ManualClock]:
    clock = ManualClock()
    runtime = OrderGroupRuntime(now_ns=clock, journal=journal)
    created = runtime.create_group(admission(basket), execution_plan())
    clock.step()
    runtime.activate_group(created.order_group_id)
    return runtime, clock


def child_event(
    client_order_id: ClientOrderId,
    *,
    status: OrderStatus,
    cumulative: str,
    at_ns: UnixNanos,
    update_id: str,
) -> OrderEvent:
    return OrderEvent(
        venue_update_id=update_id,
        client_order_id=client_order_id,
        venue_order_id=VenueOrderId("venue-child-011"),
        status=status,
        cumulative_filled_quantity=Quantity.from_str(cumulative),
        event_time_ns=at_ns,
    )


class OrderGroupContractTests(unittest.TestCase):
    def test_two_and_three_leg_contracts_are_generic_and_create_no_children(
        self,
    ) -> None:
        for basket, kinds in (
            (
                two_leg_basket(),
                {InstrumentKind.SPOT, InstrumentKind.PERPETUAL},
            ),
            (
                three_leg_basket(),
                {InstrumentKind.OPTION, InstrumentKind.PERPETUAL},
            ),
        ):
            runtime, _ = active_runtime(basket=basket)
            view = runtime.groups()[0]

            self.assertEqual(len(view.legs), len(basket.legs))
            self.assertEqual(
                {item.instrument_id.kind for item in view.legs},
                kinds,
            )
            self.assertEqual(view.actions, ())
            self.assertTrue(all(item.child_order_ids == () for item in view.legs))

    def test_identities_and_contract_codecs_are_deterministic_and_strict(
        self,
    ) -> None:
        admitted = admission()
        plan = execution_plan()
        group_id = deterministic_order_group_id(admitted)
        machine = OrderGroupStateMachine(
            admission=admitted,
            execution_plan=plan,
            group_id=group_id,
            created_at_ns=UnixNanos(1_200),
        )
        machine.transition_control(
            OrderGroupStatus.ACTIVE,
            at_ns=UnixNanos(1_210),
        )
        action = action_for(
            machine.view(),
            leg_index=0,
            now_ns=UnixNanos(1_220),
        )
        permit = permit_for(action, issued_at_ns=UnixNanos(1_220))

        values = (
            (admitted, encode_order_group_admission, decode_order_group_admission),
            (plan, encode_execution_plan_ref, decode_execution_plan_ref),
            (action, encode_execution_action, decode_execution_action),
            (
                permit,
                encode_execution_action_permit,
                decode_execution_action_permit,
            ),
        )
        for value, encoder, decoder in values:
            encoded = encoder(value)
            self.assertEqual(encoded, encoder(value))
            self.assertEqual(decoder(encoded), value)
            tampered = json.loads(encoded)
            tampered["payload"][next(iter(tampered["payload"]))] = "tampered"
            with self.assertRaises(ArithmeticError):
                decoder(
                    json.dumps(
                        tampered,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                )

        self.assertEqual(group_id, deterministic_order_group_id(admitted))
        self.assertEqual(len(str(group_id)), 64)
        with self.assertRaises(FrozenInstanceError):
            action.quantity = Quantity.from_str("2")  # type: ignore[misc]

    def test_contract_validation_rejects_changed_evidence(self) -> None:
        admitted = admission()
        with self.assertRaisesRegex(ValueError, "checksum"):
            replace(admitted, basket_checksum="0" * 64)
        with self.assertRaisesRegex(ValueError, "outlive"):
            replace(admitted, valid_until_ns=UnixNanos(5_001))
        with self.assertRaisesRegex(ValueError, "positive"):
            replace(execution_plan(), version=0)
        runtime, clock = active_runtime()
        action = action_for(
            runtime.groups()[0],
            leg_index=0,
            now_ns=clock.step(),
        )
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            replace(action, action_id=GroupActionId("not-a-sha256-id"))


class OrderGroupStateTests(unittest.TestCase):
    def test_suspended_group_cannot_start_prepared_transmission(self) -> None:
        runtime, clock = active_runtime()
        group = runtime.groups()[0]
        action = action_for(group, leg_index=0, now_ns=clock.step())
        runtime.prepare_child_submit(
            action=action,
            permit=permit_for(action, issued_at_ns=clock()),
        )
        runtime.suspend_group(group.order_group_id, reason="operator halted")

        with self.assertRaisesRegex(OrderGroupTransitionError, "ACTIVE"):
            runtime.mark_transmitting(group.order_group_id, action.action_id)

    def test_configured_and_hard_child_bounds_fail_closed(self) -> None:
        limits = OrderGroupLimits(
            max_child_attempts_per_leg=1,
            max_children_per_group=2,
            max_retained_groups=1,
        )
        clock = ManualClock()
        journal = _RecordingJournal()
        runtime = OrderGroupRuntime(
            now_ns=clock,
            limits=limits,
            journal=journal,
        )
        created = runtime.create_group(admission(), execution_plan())
        clock.step()
        runtime.activate_group(created.order_group_id)
        first = action_for(
            runtime.group(created.order_group_id),
            leg_index=0,
            now_ns=clock.step(),
        )
        runtime.prepare_child_submit(
            action=first,
            permit=permit_for(first, issued_at_ns=clock()),
        )
        runtime.mark_transmitting(created.order_group_id, first.action_id)
        runtime.record_rejected(
            created.order_group_id,
            first.action_id,
            reason="venue rejected",
        )
        second_same_leg = action_for(
            runtime.group(created.order_group_id),
            leg_index=0,
            now_ns=clock.step(),
            leg_attempt_sequence=2,
        )
        with self.assertRaisesRegex(OrderGroupCapacityError, "leg child"):
            runtime.prepare_child_submit(
                action=second_same_leg,
                permit=permit_for(
                    second_same_leg,
                    issued_at_ns=clock(),
                    permit_id="permit-at-configured-limit",
                ),
            )
        self.assertEqual(
            runtime.group(created.order_group_id).status,
            OrderGroupStatus.SUSPENDED,
        )
        recovered = OrderGroupRuntime(
            now_ns=clock,
            limits=limits,
            journal=journal,
        )
        self.assertEqual(
            recovered.group(created.order_group_id).status,
            OrderGroupStatus.SUSPENDED,
        )
        with self.assertRaisesRegex(OrderGroupRuntimeError, "capacity"):
            runtime.create_group(
                admission(
                    three_leg_basket(),
                    approval_id="second-group-approval",
                ),
                execution_plan(),
            )
        with self.assertRaises(ValueError):
            OrderGroupLimits(max_children_per_group=MAX_GROUP_CHILDREN + 1)

    def test_sixty_four_child_hard_bound_is_enforced(self) -> None:
        runtime, clock = active_runtime(basket=max_leg_basket())
        group_id = runtime.groups()[0].order_group_id
        permit_sequence = 0
        for attempt in range(1, 5):
            for leg_index in range(16):
                permit_sequence += 1
                action = action_for(
                    runtime.group(group_id),
                    leg_index=leg_index,
                    now_ns=clock.step(),
                    leg_attempt_sequence=attempt,
                    action_kind=f"bounded-attempt-{attempt}",
                )
                runtime.prepare_child_submit(
                    action=action,
                    permit=permit_for(
                        action,
                        issued_at_ns=clock(),
                        permit_id=f"bounded-permit-{permit_sequence}",
                    ),
                )
                runtime.mark_transmitting(group_id, action.action_id)
                runtime.record_rejected(
                    group_id,
                    action.action_id,
                    reason="bounded synthetic rejection",
                )

        self.assertEqual(len(runtime.group(group_id).actions), MAX_GROUP_CHILDREN)
        overflow = action_for(
            runtime.group(group_id),
            leg_index=0,
            now_ns=clock.step(),
            leg_attempt_sequence=5,
            action_kind="hard-cap-overflow",
        )
        with self.assertRaisesRegex(OrderGroupCapacityError, "group child"):
            runtime.prepare_child_submit(
                action=overflow,
                permit=permit_for(
                    overflow,
                    issued_at_ns=clock(),
                    permit_id="hard-cap-overflow-permit",
                ),
            )

    def test_permit_identity_cannot_authorize_a_second_action(self) -> None:
        runtime, clock = active_runtime()
        group_id = runtime.groups()[0].order_group_id
        first = action_for(
            runtime.group(group_id),
            leg_index=0,
            now_ns=clock.step(),
        )
        runtime.prepare_child_submit(
            action=first,
            permit=permit_for(
                first,
                issued_at_ns=clock(),
                permit_id="single-use-permit",
            ),
        )
        runtime.mark_transmitting(group_id, first.action_id)
        runtime.record_rejected(
            group_id,
            first.action_id,
            reason="first action rejected",
        )
        second = action_for(
            runtime.group(group_id),
            leg_index=1,
            now_ns=clock.step(),
        )
        with self.assertRaisesRegex(OrderGroupRuntimeError, "another action"):
            runtime.prepare_child_submit(
                action=second,
                permit=permit_for(
                    second,
                    issued_at_ns=clock(),
                    permit_id="single-use-permit",
                ),
            )

    def test_exact_permit_revision_and_action_content_are_required(self) -> None:
        runtime, clock = active_runtime()
        view = runtime.groups()[0]
        action = action_for(view, leg_index=0, now_ns=clock.step())
        permit = permit_for(action, issued_at_ns=clock())

        with self.assertRaisesRegex(
            OrderGroupAuthorizationError,
            "checksum",
        ):
            runtime.prepare_child_submit(
                action=action,
                permit=replace(permit, action_checksum="0" * 64),
            )
        with self.assertRaisesRegex(
            OrderGroupAuthorizationError,
            "revision",
        ):
            stale_action = replace(action, expected_group_revision=1)
            runtime.prepare_child_submit(
                action=stale_action,
                permit=replace(
                    permit_for(stale_action, issued_at_ns=clock()),
                    expected_group_revision=1,
                ),
            )
        with self.assertRaisesRegex(OrderGroupIdentityError, "action identity"):
            different_action_id = GroupActionId("f" * 64)
            runtime.prepare_child_submit(
                action=action,
                permit=replace(
                    permit,
                    action_id=replace(
                        action,
                        action_id=different_action_id,
                    ).action_id,
                ),
            )

        clock.value = 4_600
        with self.assertRaisesRegex(
            OrderGroupAuthorizationError,
            "currently valid",
        ):
            runtime.prepare_child_submit(action=action, permit=permit)
        self.assertEqual(runtime.group(view.order_group_id).actions, ())

    def test_one_unresolved_action_and_one_same_identity_retry(self) -> None:
        runtime, clock = active_runtime()
        group = runtime.groups()[0]
        action = action_for(group, leg_index=0, now_ns=clock.step())
        permit = permit_for(action, issued_at_ns=clock())
        request = runtime.prepare_child_submit(action=action, permit=permit)

        next_action = action_for(
            runtime.group(group.order_group_id),
            leg_index=1,
            now_ns=clock.step(),
        )
        with self.assertRaisesRegex(OrderGroupCapacityError, "one unresolved"):
            runtime.prepare_child_submit(
                action=next_action,
                permit=permit_for(
                    next_action,
                    issued_at_ns=clock(),
                    permit_id="next-action-permit",
                ),
            )
        self.assertEqual(
            runtime.group(group.order_group_id).status,
            OrderGroupStatus.SUSPENDED,
        )
        runtime.activate_group(group.order_group_id)

        first = runtime.mark_transmitting(group.order_group_id, action.action_id)
        self.assertEqual(first.actions[0].transport_attempts, 1)
        retry = runtime.record_definitely_not_sent(
            group.order_group_id,
            action.action_id,
            reason="connect failed before send",
        )
        self.assertEqual(
            retry.actions[0].state,
            ExecutionActionState.RETRY_ELIGIBLE,
        )
        clock.step()
        retransmitting = runtime.mark_transmitting(
            group.order_group_id,
            action.action_id,
        )
        self.assertEqual(retransmitting.actions[0].transport_attempts, 2)
        terminal = runtime.record_definitely_not_sent(
            group.order_group_id,
            action.action_id,
            reason="second connect failure",
        )
        self.assertEqual(
            terminal.actions[0].state,
            ExecutionActionState.REJECTED,
        )
        self.assertEqual(
            runtime.child(request.client_order_id).status,
            OrderStatus.FAILED,
        )
        with self.assertRaises(OrderGroupTransitionError):
            runtime.mark_transmitting(group.order_group_id, action.action_id)

    def test_signed_leg_fills_and_multiple_children_remain_execution_facts(
        self,
    ) -> None:
        runtime, clock = active_runtime()
        group_id = runtime.groups()[0].order_group_id

        first = action_for(
            runtime.group(group_id),
            leg_index=1,
            now_ns=clock.step(),
            quantity="6",
        )
        first_request = runtime.prepare_child_submit(
            action=first,
            permit=permit_for(first, issued_at_ns=clock()),
        )
        runtime.mark_transmitting(group_id, first.action_id)
        runtime.record_acknowledged(
            group_id,
            first.action_id,
            venue_order_id=VenueOrderId("spot-1"),
        )
        partial = runtime.apply_child_event(
            child_event(
                first_request.client_order_id,
                status=OrderStatus.PARTIALLY_FILLED,
                cumulative="4",
                at_ns=clock.step(),
                update_id="partial-spot-1",
            )
        )
        spot = partial.legs[1]
        self.assertEqual(spot.signed_cumulative_filled_delta, Quantity.from_str("4"))
        self.assertEqual(spot.signed_working_quantity, Quantity.from_str("2"))

        runtime.apply_child_event(
            child_event(
                first_request.client_order_id,
                status=OrderStatus.FILLED,
                cumulative="6",
                at_ns=clock.step(),
                update_id="filled-spot-1",
            )
        )
        second = action_for(
            runtime.group(group_id),
            leg_index=1,
            now_ns=clock.step(),
            leg_attempt_sequence=2,
            quantity="4",
            action_kind="completion",
        )
        second_request = runtime.prepare_child_submit(
            action=second,
            permit=permit_for(
                second,
                issued_at_ns=clock(),
                permit_id="execution-permit-012",
            ),
        )
        runtime.mark_transmitting(group_id, second.action_id)
        runtime.record_acknowledged(group_id, second.action_id)
        completed = runtime.apply_child_event(
            child_event(
                second_request.client_order_id,
                status=OrderStatus.FILLED,
                cumulative="4",
                at_ns=clock.step(),
                update_id="filled-spot-2",
            )
        )
        spot = completed.legs[1]
        self.assertEqual(spot.signed_cumulative_filled_delta, Quantity.from_str("10"))
        self.assertEqual(spot.signed_working_quantity, Quantity.from_str("0"))
        self.assertEqual(len(spot.child_order_ids), 2)
        self.assertNotIn("HEDGED", OrderGroupStatus.__members__)
        self.assertNotIn("PARTIALLY_HEDGED", OrderGroupStatus.__members__)

    def test_unknown_requires_recovery_and_close_requires_external_evidence(
        self,
    ) -> None:
        runtime, clock = active_runtime()
        group_id = runtime.groups()[0].order_group_id
        action = action_for(
            runtime.group(group_id),
            leg_index=0,
            now_ns=clock.step(),
        )
        request = runtime.prepare_child_submit(
            action=action,
            permit=permit_for(action, issued_at_ns=clock()),
        )
        runtime.mark_transmitting(group_id, action.action_id)
        unknown = runtime.record_unknown(
            group_id,
            action.action_id,
            reason="response lost after send",
        )

        self.assertEqual(unknown.status, OrderGroupStatus.RECOVERY_REQUIRED)
        self.assertEqual(
            unknown.actions[0].state,
            ExecutionActionState.UNKNOWN,
        )
        self.assertEqual(
            tuple(
                item.request.client_order_id for item in runtime.recovery_candidates()
            ),
            (request.client_order_id,),
        )
        with self.assertRaisesRegex(OrderGroupTransitionError, "remains unknown"):
            runtime.resume_group(
                group_id,
                recovery_authorization_id="operator-and-risk-1",
            )
        with self.assertRaisesRegex(GroupedExecutionBlockedError, "ADR-012"):
            runtime.submit_prepared_child(request.client_order_id)

        runtime.apply_child_event(
            child_event(
                request.client_order_id,
                status=OrderStatus.FILLED,
                cumulative="1",
                at_ns=clock.step(),
                update_id="reconciled-fill",
            )
        )
        runtime.resume_group(
            group_id,
            recovery_authorization_id="operator-and-risk-1",
        )
        runtime.begin_closing(group_id)
        with self.assertRaisesRegex(
            OrderGroupAuthorizationError,
            "Portfolio/Risk",
        ):
            runtime.close_group(
                group_id,
                outcome=OrderGroupCloseOutcome.TARGET_CONFIRMED,
            )
        closed = runtime.close_group(
            group_id,
            outcome=OrderGroupCloseOutcome.TARGET_CONFIRMED,
            portfolio_confirmation_id="portfolio-confirmation-1",
        )
        self.assertEqual(closed.status, OrderGroupStatus.CLOSED)


class _RecordingJournal:
    def __init__(self) -> None:
        self.entries = []
        self.fail = False

    def read(self):
        return iter(self.entries)

    def append(self, entry) -> None:
        if self.fail:
            raise OSError("durability unavailable")
        self.entries.append(entry)


class OrderGroupRuntimeTests(unittest.TestCase):
    def test_failed_group_append_creates_no_group_and_latches_runtime(self) -> None:
        journal = _RecordingJournal()
        journal.fail = True
        runtime = OrderGroupRuntime(now_ns=ManualClock(), journal=journal)

        with self.assertRaises(OrderGroupPersistenceError):
            runtime.create_group(admission(), execution_plan())

        self.assertEqual(runtime.groups(), ())
        with self.assertRaisesRegex(OrderGroupPersistenceError, "restart"):
            runtime.create_group(admission(), execution_plan())

    def test_restart_recovers_group_after_append_before_registration(self) -> None:
        journal = _RecordingJournal()
        clock = ManualClock()
        runtime = OrderGroupRuntime(now_ns=clock, journal=journal)

        def crash_after_append(*args, **kwargs) -> None:
            del args, kwargs
            raise RuntimeError("injected process stop after group append")

        runtime._register_group = crash_after_append  # type: ignore[method-assign]
        with self.assertRaisesRegex(RuntimeError, "after group append"):
            runtime.create_group(admission(), execution_plan())

        recovered = OrderGroupRuntime(now_ns=clock, journal=journal)
        self.assertEqual(len(recovered.groups()), 1)
        self.assertEqual(recovered.groups()[0].status, OrderGroupStatus.CREATED)

    def test_active_group_limit_suspends_the_candidate_group(self) -> None:
        limits = OrderGroupLimits(
            max_active_groups_per_strategy_account=1,
        )
        clock = ManualClock()
        runtime = OrderGroupRuntime(now_ns=clock, limits=limits)
        first = runtime.create_group(admission(), execution_plan())
        second = runtime.create_group(
            admission(
                three_leg_basket(),
                approval_id="second-portfolio-approval",
            ),
            execution_plan(),
        )
        clock.step()
        runtime.activate_group(first.order_group_id)

        with self.assertRaisesRegex(
            OrderGroupRuntimeError,
            "strategy/account",
        ):
            runtime.activate_group(second.order_group_id)

        self.assertEqual(
            runtime.group(second.order_group_id).status,
            OrderGroupStatus.SUSPENDED,
        )
        runtime.suspend_group(first.order_group_id, reason="operator rotation")
        self.assertEqual(
            runtime.activate_group(second.order_group_id).status,
            OrderGroupStatus.ACTIVE,
        )

    def test_child_identity_collision_cannot_overwrite_group_owner(self) -> None:
        clock = ManualClock()
        runtime = OrderGroupRuntime(now_ns=clock)
        first_group = runtime.create_group(admission(), execution_plan())
        second_group = runtime.create_group(
            admission(
                three_leg_basket(),
                approval_id="second-portfolio-approval",
            ),
            execution_plan(),
        )
        clock.step()
        runtime.activate_group(first_group.order_group_id)
        runtime.activate_group(second_group.order_group_id)
        shared_prefix = "a" * 32
        first_action = replace(
            action_for(
                runtime.group(first_group.order_group_id),
                leg_index=0,
                now_ns=clock.step(),
            ),
            action_id=GroupActionId(shared_prefix + ("0" * 32)),
        )
        first_request = runtime.prepare_child_submit(
            action=first_action,
            permit=permit_for(
                first_action,
                issued_at_ns=clock(),
                permit_id="first-collision-permit",
            ),
        )
        second_action = replace(
            action_for(
                runtime.group(second_group.order_group_id),
                leg_index=0,
                now_ns=clock.step(),
            ),
            action_id=GroupActionId(shared_prefix + ("1" * 32)),
        )

        with self.assertRaisesRegex(OrderGroupRuntimeError, "ClientOrderId"):
            runtime.prepare_child_submit(
                action=second_action,
                permit=permit_for(
                    second_action,
                    issued_at_ns=clock(),
                    permit_id="second-collision-permit",
                ),
            )

        self.assertEqual(
            runtime.child(first_request.client_order_id).request.client_order_id,
            first_request.client_order_id,
        )
        self.assertEqual(
            runtime.group(second_group.order_group_id).actions,
            (),
        )

    def test_runtime_mutation_from_non_owner_thread_is_rejected(self) -> None:
        runtime = OrderGroupRuntime(now_ns=ManualClock())
        errors: list[Exception] = []

        def mutate() -> None:
            try:
                runtime.create_group(admission(), execution_plan())
            except Exception as error:
                errors.append(error)

        thread = Thread(target=mutate)
        thread.start()
        thread.join()

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], OrderGroupWriterViolationError)
        self.assertEqual(runtime.groups(), ())

    def test_admission_is_idempotent_but_changed_approval_conflicts(self) -> None:
        clock = ManualClock()
        runtime = OrderGroupRuntime(now_ns=clock)
        admitted = admission()
        first = runtime.create_group(admitted, execution_plan())
        second = runtime.create_group(admitted, execution_plan())

        self.assertEqual(first, second)
        with self.assertRaisesRegex(OrderGroupRuntimeError, "already owned"):
            runtime.create_group(
                admission(
                    admitted.basket,
                    approval_id="different-portfolio-approval",
                ),
                execution_plan(),
            )

    def test_failed_preparation_append_creates_no_child_and_latches(self) -> None:
        journal = _RecordingJournal()
        runtime, clock = active_runtime(journal=journal)
        group = runtime.groups()[0]
        action = action_for(group, leg_index=0, now_ns=clock.step())
        journal.fail = True

        with self.assertRaises(OrderGroupPersistenceError):
            runtime.prepare_child_submit(
                action=action,
                permit=permit_for(action, issued_at_ns=clock()),
            )
        self.assertEqual(runtime.group(group.order_group_id).actions, ())
        with self.assertRaisesRegex(OrderGroupPersistenceError, "restart"):
            runtime.prepare_child_submit(
                action=action,
                permit=permit_for(action, issued_at_ns=clock()),
            )

    def test_json_journal_replays_group_mapping_and_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oms.jsonl"
            clock = ManualClock()
            with JsonLinesOmsJournal(path) as journal:
                runtime = OrderGroupRuntime(now_ns=clock, journal=journal)
                group = runtime.create_group(admission(), execution_plan())
                clock.step()
                runtime.activate_group(group.order_group_id)
                action = action_for(
                    runtime.group(group.order_group_id),
                    leg_index=0,
                    now_ns=clock.step(),
                )
                request = runtime.prepare_child_submit(
                    action=action,
                    permit=permit_for(action, issued_at_ns=clock()),
                )
                runtime.mark_transmitting(group.order_group_id, action.action_id)
                expected = runtime.record_unknown(
                    group.order_group_id,
                    action.action_id,
                    reason="unknown after send",
                )

            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(all(item["version"] == 2 for item in records))
            with JsonLinesOmsJournal(path) as recovered_journal:
                recovered = OrderGroupRuntime(
                    now_ns=clock,
                    journal=recovered_journal,
                )
                self.assertEqual(recovered.group(group.order_group_id), expected)
                self.assertEqual(
                    recovered.child(request.client_order_id).status,
                    OrderStatus.SUBMITTING,
                )
                self.assertEqual(
                    len(recovered.recovery_candidates()),
                    1,
                )

    def test_wrong_group_identity_is_rejected(self) -> None:
        admitted = admission()
        with self.assertRaises(OrderGroupIdentityError):
            OrderGroupStateMachine(
                admission=admitted,
                execution_plan=execution_plan(),
                group_id=OrderGroupId("wrong-group"),
                created_at_ns=UnixNanos(1_200),
            )
        with self.assertRaises(ValueError):
            replace(admitted, approval_id=PortfolioApprovalId(""))
        with self.assertRaises(ValueError):
            replace(
                permit_for(
                    action_for(
                        active_runtime()[0].groups()[0],
                        leg_index=0,
                        now_ns=UnixNanos(1_220),
                    ),
                    issued_at_ns=UnixNanos(1_220),
                ),
                permit_id=ExecutionPermitId(""),
            )


if __name__ == "__main__":
    unittest.main()
