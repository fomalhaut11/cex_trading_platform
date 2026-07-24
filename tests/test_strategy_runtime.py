import unittest
from dataclasses import FrozenInstanceError

from cex_quant.core import (
    IntentId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.features import FeatureSnapshot
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.strategy import (
    InvalidStrategyInputError,
    PositionTargetIntent,
    StrategyContext,
    StrategyExecutionError,
    StrategyLifecycleError,
    StrategyPhase,
    StrategyRuntime,
    StrategyScopeError,
    StrategyStatus,
)

INSTRUMENT_ID = InstrumentId(
    venue=VenueId("test"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)
DEFAULT_STRATEGY_ID = StrategyId("deterministic")


def intent(
    intent_id: str,
    strategy_id: StrategyId = DEFAULT_STRATEGY_ID,
) -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId(intent_id),
        strategy_id=strategy_id,
        instrument_id=INSTRUMENT_ID,
        target_quantity=Quantity(raw=10, scale=1),
        decision_time_ns=UnixNanos(100),
        valid_until_ns=UnixNanos(200),
        reason="test",
    )


class RecordingStrategy:
    def __init__(self) -> None:
        self.strategy_id = StrategyId("deterministic")
        self.started = 0
        self.stopped = 0
        self.contexts: list[StrategyContext] = []

    def on_start(self) -> None:
        self.started += 1

    def on_input(
        self, context: StrategyContext
    ) -> tuple[PositionTargetIntent, ...]:
        self.contexts.append(context)
        return (intent(f"intent-{context.input_sequence}"),)

    def on_stop(self) -> None:
        self.stopped += 1


class RaisingStrategy(RecordingStrategy):
    def on_input(
        self, context: StrategyContext
    ) -> tuple[PositionTargetIntent, ...]:
        self.contexts.append(context)
        raise ArithmeticError("bad signal")


class BadOutputStrategy(RecordingStrategy):
    def on_input(self, context: StrategyContext) -> object:
        self.contexts.append(context)
        return [intent("not-a-tuple")]


class UnsupportedOutputStrategy(RecordingStrategy):
    def on_input(self, context: StrategyContext) -> object:
        self.contexts.append(context)
        return (object(),)


class HookFailureStrategy(RecordingStrategy):
    def __init__(self, phase: StrategyPhase) -> None:
        super().__init__()
        self.phase = phase

    def on_start(self) -> None:
        if self.phase is StrategyPhase.START:
            raise LookupError("start failed")

    def on_stop(self) -> None:
        if self.phase is StrategyPhase.STOP:
            raise LookupError("stop failed")


class ReentrantStopStrategy(RecordingStrategy):
    def __init__(self) -> None:
        super().__init__()
        self.runtime: StrategyRuntime | None = None

    def on_input(
        self, context: StrategyContext
    ) -> tuple[PositionTargetIntent, ...]:
        assert self.runtime is not None
        self.runtime.stop()
        return ()


class StrategyRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = FeatureSnapshot(scope="BTCUSDT", values=())

    def test_lifecycle_and_input_order_are_synchronous(self) -> None:
        strategy = RecordingStrategy()
        runtime = StrategyRuntime(strategy=strategy)

        self.assertEqual(runtime.status, StrategyStatus.CREATED)
        runtime.start()
        first = runtime.on_input(self.snapshot)
        second = runtime.on_input(self.snapshot)
        runtime.stop()

        self.assertEqual(strategy.started, 1)
        self.assertEqual(strategy.stopped, 1)
        self.assertEqual(runtime.status, StrategyStatus.STOPPED)
        self.assertEqual(runtime.input_sequence, 2)
        self.assertEqual(
            tuple(context.input_sequence for context in strategy.contexts),
            (1, 2),
        )
        self.assertEqual(first.intents, (intent("intent-1"),))
        self.assertEqual(second.intents, (intent("intent-2"),))

    def test_replay_of_same_inputs_produces_same_decisions(self) -> None:
        decisions = []
        for _ in range(2):
            runtime = StrategyRuntime(strategy=RecordingStrategy())
            runtime.start()
            decisions.append(
                (
                    runtime.on_input(self.snapshot),
                    runtime.on_input(self.snapshot),
                )
            )

        self.assertEqual(decisions[0], decisions[1])

    def test_context_intent_and_decision_are_immutable(self) -> None:
        runtime = StrategyRuntime(strategy=RecordingStrategy())
        runtime.start()
        decision = runtime.on_input(self.snapshot)

        with self.assertRaises(FrozenInstanceError):
            decision.input_sequence = 9  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            decision.intents[0].reason = "changed"  # type: ignore[misc]

    def test_invalid_lifecycle_never_invokes_strategy(self) -> None:
        strategy = RecordingStrategy()
        runtime = StrategyRuntime(strategy=strategy)

        with self.assertRaises(StrategyLifecycleError):
            runtime.on_input(self.snapshot)
        with self.assertRaises(StrategyLifecycleError):
            runtime.stop()
        self.assertEqual(strategy.contexts, [])
        self.assertEqual(strategy.stopped, 0)

        runtime.start()
        with self.assertRaises(StrategyLifecycleError):
            runtime.start()
        runtime.stop()
        with self.assertRaises(StrategyLifecycleError):
            runtime.on_input(self.snapshot)

    def test_noncanonical_input_is_rejected_without_consuming_sequence(self) -> None:
        runtime = StrategyRuntime(strategy=RecordingStrategy())
        runtime.start()

        with self.assertRaises(InvalidStrategyInputError):
            runtime.on_input(object())  # type: ignore[arg-type]

        self.assertEqual(runtime.status, StrategyStatus.RUNNING)
        self.assertEqual(runtime.input_sequence, 0)

    def test_scope_locks_by_default_and_multiscope_is_explicit(self) -> None:
        strategy = RecordingStrategy()
        runtime = StrategyRuntime(strategy=strategy)
        runtime.start()
        runtime.on_input(self.snapshot)

        with self.assertRaisesRegex(StrategyScopeError, "locked scope"):
            runtime.on_input(FeatureSnapshot(scope="ETHUSDT", values=()))
        self.assertEqual(runtime.input_sequence, 1)
        self.assertEqual(len(strategy.contexts), 1)

        multiscope_strategy = RecordingStrategy()
        multiscope = StrategyRuntime(
            strategy=multiscope_strategy,
            accepted_scopes=frozenset({"BTCUSDT", "ETHUSDT"}),
        )
        multiscope.start()
        multiscope.on_input(self.snapshot)
        multiscope.on_input(FeatureSnapshot(scope="ETHUSDT", values=()))
        self.assertEqual(
            tuple(
                context.input_scope
                for context in multiscope_strategy.contexts
            ),
            ("BTCUSDT", "ETHUSDT"),
        )

    def test_reentrant_stop_fails_without_running_stop_hook(self) -> None:
        strategy = ReentrantStopStrategy()
        runtime = StrategyRuntime(strategy=strategy)
        strategy.runtime = runtime
        runtime.start()

        with self.assertRaisesRegex(
            StrategyExecutionError, "during a strategy callback"
        ):
            runtime.on_input(self.snapshot)

        self.assertEqual(runtime.status, StrategyStatus.FAILED)
        self.assertEqual(strategy.stopped, 0)
        assert runtime.failure is not None
        self.assertEqual(
            runtime.failure.exception_type, "StrategyLifecycleError"
        )

    def test_exception_is_latched_and_blocks_all_later_events(self) -> None:
        strategy = RaisingStrategy()
        runtime = StrategyRuntime(strategy=strategy)
        runtime.start()

        with self.assertRaisesRegex(StrategyExecutionError, "bad signal"):
            runtime.on_input(self.snapshot)

        self.assertEqual(runtime.status, StrategyStatus.FAILED)
        self.assertEqual(runtime.input_sequence, 0)
        self.assertIsNotNone(runtime.failure)
        assert runtime.failure is not None
        self.assertEqual(runtime.failure.phase, StrategyPhase.INPUT)
        self.assertEqual(runtime.failure.input_sequence, 1)
        self.assertEqual(runtime.failure.exception_type, "ArithmeticError")

        with self.assertRaises(StrategyLifecycleError):
            runtime.on_input(self.snapshot)
        self.assertEqual(len(strategy.contexts), 1)

    def test_lifecycle_hook_failures_are_latched(self) -> None:
        start_runtime = StrategyRuntime(
            strategy=HookFailureStrategy(StrategyPhase.START)
        )
        with self.assertRaisesRegex(StrategyExecutionError, "start failed"):
            start_runtime.start()
        self.assertEqual(start_runtime.status, StrategyStatus.FAILED)
        assert start_runtime.failure is not None
        self.assertEqual(start_runtime.failure.phase, StrategyPhase.START)

        stop_runtime = StrategyRuntime(
            strategy=HookFailureStrategy(StrategyPhase.STOP)
        )
        stop_runtime.start()
        stop_runtime.on_input(self.snapshot)
        with self.assertRaisesRegex(StrategyExecutionError, "stop failed"):
            stop_runtime.stop()
        self.assertEqual(stop_runtime.status, StrategyStatus.FAILED)
        assert stop_runtime.failure is not None
        self.assertEqual(stop_runtime.failure.phase, StrategyPhase.STOP)
        self.assertEqual(stop_runtime.failure.input_sequence, 1)

    def test_invalid_output_is_a_latched_strategy_failure(self) -> None:
        runtime = StrategyRuntime(strategy=BadOutputStrategy())  # type: ignore[arg-type]
        runtime.start()

        with self.assertRaisesRegex(
            StrategyExecutionError, "output must be a tuple"
        ):
            runtime.on_input(self.snapshot)

        self.assertEqual(runtime.status, StrategyStatus.FAILED)
        assert runtime.failure is not None
        self.assertEqual(
            runtime.failure.exception_type, "InvalidStrategyOutputError"
        )

        unsupported = StrategyRuntime(
            strategy=UnsupportedOutputStrategy()  # type: ignore[arg-type]
        )
        unsupported.start()
        with self.assertRaisesRegex(
            StrategyExecutionError, "unsupported decision intent"
        ):
            unsupported.on_input(self.snapshot)
        self.assertEqual(unsupported.status, StrategyStatus.FAILED)

    def test_mismatched_strategy_and_duplicate_intent_ids_fail(self) -> None:
        class MismatchStrategy(RecordingStrategy):
            def on_input(
                self, context: StrategyContext
            ) -> tuple[PositionTargetIntent, ...]:
                return (intent("one", StrategyId("other")),)

        mismatch = StrategyRuntime(strategy=MismatchStrategy())
        mismatch.start()
        with self.assertRaisesRegex(
            StrategyExecutionError, "does not match"
        ):
            mismatch.on_input(self.snapshot)

        class DuplicateStrategy(RecordingStrategy):
            def on_input(
                self, context: StrategyContext
            ) -> tuple[PositionTargetIntent, ...]:
                return (intent("same"), intent("same"))

        duplicate = StrategyRuntime(strategy=DuplicateStrategy())
        duplicate.start()
        with self.assertRaisesRegex(StrategyExecutionError, "unique"):
            duplicate.on_input(self.snapshot)

    def test_intent_validity_window_is_checked(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            PositionTargetIntent(
                intent_id=IntentId("bad"),
                strategy_id=StrategyId("deterministic"),
                instrument_id=INSTRUMENT_ID,
                target_quantity=Quantity(raw=0, scale=0),
                decision_time_ns=UnixNanos(200),
                valid_until_ns=UnixNanos(199),
            )


if __name__ == "__main__":
    unittest.main()
