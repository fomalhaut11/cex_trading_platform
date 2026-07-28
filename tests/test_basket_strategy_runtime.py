from unittest import TestCase

from cex_quant.core import (
    AccountId,
    DurationNanos,
    ObjectiveTypeId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.features import FeatureSnapshot
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.snapshots import (
    DecisionSnapshotId,
    DecisionSnapshotMetadata,
    DecisionSnapshotPublication,
    ObservationId,
    SnapshotAssessment,
    SnapshotReadiness,
)
from cex_quant.strategy import (
    BasketIntentPolicy,
    BasketTargetIntent,
    BasketTargetLeg,
    DecisionIntent,
    ObjectiveTypeDefinition,
    ObjectiveTypeRef,
    ObjectiveTypeRegistry,
    StrategyContext,
    StrategyExecutionError,
    StrategyRuntime,
    StrategyStatus,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)

STRATEGY_ID = StrategyId("basket-runtime")
SNAPSHOT_ID = DecisionSnapshotId("snapshot-input")
DECISION_TIME_NS = UnixNanos(1_000)
OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding"),
    version=1,
)
REGISTRY = ObjectiveTypeRegistry(
    (
        ObjectiveTypeDefinition(
            ref=OBJECTIVE,
            owner="applications.carry",
        ),
    )
)
POLICY = BasketIntentPolicy(
    max_legs=3,
    max_validity_ns=DurationNanos(1_000),
    allowed_objectives=(OBJECTIVE,),
)


def publication() -> DecisionSnapshotPublication[object]:
    return DecisionSnapshotPublication(
        metadata=DecisionSnapshotMetadata(
            snapshot_id=SNAPSHOT_ID,
            scope="BTC-carry",
            snapshot_sequence=1,
            assembled_at_ns=UnixNanos(1_000),
            assembled_at_monotonic_ns=1_100,
            policy_version=1,
            observation_ids=(ObservationId("spot"), ObservationId("perp")),
            coherence=(),
        ),
        assessment=SnapshotAssessment(
            readiness=SnapshotReadiness.READY,
            issues=(),
            policy_version=1,
        ),
        value={"spot": "100", "perp": "101"},
    )


def target(
    *,
    decision_snapshot_id: DecisionSnapshotId = SNAPSHOT_ID,
    decision_time_ns: UnixNanos = DECISION_TIME_NS,
) -> BasketTargetIntent:
    legs = []
    for kind, quantity in (
        (InstrumentKind.SPOT, "10"),
        (InstrumentKind.PERPETUAL, "-10"),
    ):
        instrument_id = InstrumentId(
            venue=VenueId("BINANCE"),
            kind=kind,
            symbol="BTCUSDT",
        )
        legs.append(
            BasketTargetLeg(
                leg_id=deterministic_basket_leg_id(
                    decision_snapshot_id=decision_snapshot_id,
                    account_id=AccountId("primary"),
                    instrument_id=instrument_id,
                ),
                account_id=AccountId("primary"),
                instrument_id=instrument_id,
                target_quantity=Quantity.from_str(quantity),
            )
        )
    return create_basket_target_intent(
        strategy_id=STRATEGY_ID,
        decision_snapshot_id=decision_snapshot_id,
        objective=OBJECTIVE,
        legs=tuple(legs),
        decision_time_ns=decision_time_ns,
        valid_until_ns=UnixNanos(2_000),
        policy_version=1,
    )


class BasketStrategy:
    strategy_id = STRATEGY_ID

    def __init__(self, result: BasketTargetIntent) -> None:
        self.result = result

    def on_start(self) -> None:
        pass

    def on_input(
        self,
        context: StrategyContext,
    ) -> tuple[DecisionIntent, ...]:
        del context
        return (self.result,)

    def on_stop(self) -> None:
        pass


class BasketStrategyRuntimeTests(TestCase):
    def test_matching_snapshot_publication_can_cause_basket(self) -> None:
        expected = target()
        runtime = StrategyRuntime(
            strategy=BasketStrategy(expected),
            basket_policy=POLICY,
            objective_registry=REGISTRY,
        )
        runtime.start()

        decision = runtime.on_input(publication())

        self.assertEqual(decision.intents, (expected,))
        self.assertEqual(runtime.status, StrategyStatus.RUNNING)

    def test_mismatched_snapshot_id_is_latched_and_rejected(self) -> None:
        runtime = StrategyRuntime(
            strategy=BasketStrategy(
                target(
                    decision_snapshot_id=DecisionSnapshotId(
                        "different-snapshot"
                    )
                )
            ),
            basket_policy=POLICY,
            objective_registry=REGISTRY,
        )
        runtime.start()

        with self.assertRaisesRegex(
            StrategyExecutionError,
            "decision_snapshot_id does not match",
        ):
            runtime.on_input(publication())

        self.assertEqual(runtime.status, StrategyStatus.FAILED)
        assert runtime.failure is not None
        self.assertEqual(
            runtime.failure.exception_type,
            "InvalidStrategyOutputError",
        )

    def test_basket_requires_snapshot_publication(self) -> None:
        runtime = StrategyRuntime(strategy=BasketStrategy(target()))
        runtime.start()

        with self.assertRaisesRegex(
            StrategyExecutionError,
            "requires a decision snapshot",
        ):
            runtime.on_input(
                FeatureSnapshot(scope="BTC-carry", values=())
            )

    def test_decision_cannot_predate_snapshot_assembly(self) -> None:
        runtime = StrategyRuntime(
            strategy=BasketStrategy(
                target(decision_time_ns=UnixNanos(999))
            )
        )
        runtime.start()

        with self.assertRaisesRegex(
            StrategyExecutionError,
            "precedes snapshot assembly",
        ):
            runtime.on_input(publication())

    def test_basket_support_requires_complete_explicit_configuration(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "configured together"):
            StrategyRuntime(
                strategy=BasketStrategy(target()),
                basket_policy=POLICY,
            )

        runtime = StrategyRuntime(strategy=BasketStrategy(target()))
        runtime.start()
        with self.assertRaisesRegex(
            StrategyExecutionError,
            "Basket output is not enabled",
        ):
            runtime.on_input(publication())
