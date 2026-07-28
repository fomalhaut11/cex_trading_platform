"""A013 offline acceptance for ADR-010 Basket Intent architecture."""

from __future__ import annotations

import unittest

from cex_quant.core import (
    AccountId,
    DurationNanos,
    EventId,
    EventMetadata,
    EventSource,
    IntentId,
    ObjectiveTypeId,
    Price,
    Quantity,
    SchemaVersion,
    StrategyId,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.features import FeatureSnapshot
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    BestBidAsk,
    BookLevel,
    MarketDataValidator,
)
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.runtime import (
    PipelineOutcome,
    PipelineStage,
    StateGate,
    TradingPipeline,
)
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
    PositionTargetIntent,
    StrategyContext,
    StrategyDecision,
    StrategyExecutionError,
    StrategyRuntime,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)

STRATEGY_ID = StrategyId("a013")
SNAPSHOT_ID = DecisionSnapshotId("a013-snapshot")
OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("portfolio.arbitrage"),
    version=1,
)
ACCOUNT_ID = AccountId("primary")
OBJECTIVE_REGISTRY = ObjectiveTypeRegistry(
    (
        ObjectiveTypeDefinition(
            ref=OBJECTIVE,
            owner="acceptance",
        ),
    )
)
BASKET_POLICY = BasketIntentPolicy(
    max_legs=3,
    max_validity_ns=DurationNanos(1_000),
    allowed_objectives=(OBJECTIVE,),
)


def instrument(kind: InstrumentKind, symbol: str) -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=kind,
        symbol=symbol,
    )


def basket_leg(
    kind: InstrumentKind,
    symbol: str,
    quantity: str,
    *,
    snapshot_id: DecisionSnapshotId = SNAPSHOT_ID,
) -> BasketTargetLeg:
    instrument_id = instrument(kind, symbol)
    return BasketTargetLeg(
        leg_id=deterministic_basket_leg_id(
            decision_snapshot_id=snapshot_id,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
        ),
        account_id=ACCOUNT_ID,
        instrument_id=instrument_id,
        target_quantity=Quantity.from_str(quantity),
    )


def basket(
    legs: tuple[BasketTargetLeg, ...],
    *,
    snapshot_id: DecisionSnapshotId = SNAPSHOT_ID,
) -> BasketTargetIntent:
    return create_basket_target_intent(
        strategy_id=STRATEGY_ID,
        decision_snapshot_id=snapshot_id,
        objective=OBJECTIVE,
        legs=legs,
        decision_time_ns=UnixNanos(1_000),
        valid_until_ns=UnixNanos(2_000),
        policy_version=1,
    )


def publication() -> DecisionSnapshotPublication[object]:
    return DecisionSnapshotPublication(
        metadata=DecisionSnapshotMetadata(
            snapshot_id=SNAPSHOT_ID,
            scope="portfolio:BTC",
            snapshot_sequence=1,
            assembled_at_ns=UnixNanos(1_000),
            assembled_at_monotonic_ns=1_000,
            policy_version=1,
            observation_ids=(
                ObservationId("spot"),
                ObservationId("perpetual"),
                ObservationId("account"),
            ),
            coherence=(),
        ),
        assessment=SnapshotAssessment(
            readiness=SnapshotReadiness.READY,
            issues=(),
            policy_version=1,
        ),
        value={"coherent": True},
    )


class FixedStrategy:
    strategy_id = STRATEGY_ID

    def __init__(self, result: DecisionIntent) -> None:
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


class Healthy:
    def health(self) -> HealthReport:
        return HealthReport(
            component="a013",
            status=HealthStatus.HEALTHY,
            observed_at_ns=UnixNanos(2_000),
        )


class AcceptingState:
    def apply(self, value: object) -> StateGate:
        del value
        return StateGate(accepted=True)


class NoFeatures:
    def on_event(self, value: object) -> None:
        del value
        return None


class BasketDecisionPort:
    def __init__(self, target: BasketTargetIntent) -> None:
        self.target = target

    def on_input(self, value: object) -> StrategyDecision:
        del value
        return StrategyDecision(
            strategy_id=STRATEGY_ID,
            input_sequence=1,
            intents=(self.target,),
        )


class NeverReached:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"single-leg port {name} was reached")


def market_event() -> BestBidAsk:
    return BestBidAsk(
        metadata=EventMetadata(
            event_id=EventId("a013-event"),
            event_time_ns=UnixNanos(1_900),
            receive_time_ns=UnixNanos(1_950),
            source=EventSource(
                venue=VenueId("BINANCE"),
                channel="bookTicker",
            ),
            schema_version=SchemaVersion(1),
            source_time_precision=TimePrecision.NANOSECOND,
        ),
        instrument_id=instrument(InstrumentKind.SPOT, "BTCUSDT"),
        bid=BookLevel(
            price=Price.from_str("99"),
            quantity=Quantity.from_str("1"),
        ),
        ask=BookLevel(
            price=Price.from_str("101"),
            quantity=Quantity.from_str("1"),
        ),
    )


class BasketIntentAcceptanceTests(unittest.TestCase):
    def test_position_target_and_n_leg_generation_are_additive(self) -> None:
        position = PositionTargetIntent(
            intent_id=IntentId("single-position"),
            strategy_id=STRATEGY_ID,
            instrument_id=instrument(
                InstrumentKind.PERPETUAL,
                "ETHUSDT",
            ),
            target_quantity=Quantity.from_str("2"),
            decision_time_ns=UnixNanos(1_000),
            valid_until_ns=UnixNanos(2_000),
        )
        single_runtime = StrategyRuntime(
            strategy=FixedStrategy(position)
        )
        single_runtime.start()
        single = single_runtime.on_input(
            FeatureSnapshot(scope="ETHUSDT", values=())
        )

        two_leg = basket(
            (
                basket_leg(InstrumentKind.SPOT, "BTCUSDT", "10"),
                basket_leg(
                    InstrumentKind.PERPETUAL,
                    "BTCUSDT",
                    "-10",
                ),
            )
        )
        three_leg = basket(
            (
                basket_leg(
                    InstrumentKind.OPTION,
                    "BTC-30000-C",
                    "10",
                ),
                basket_leg(
                    InstrumentKind.OPTION,
                    "BTC-35000-C",
                    "-10",
                ),
                basket_leg(
                    InstrumentKind.PERPETUAL,
                    "BTCUSDT",
                    "-0.35",
                ),
            )
        )

        self.assertEqual(single.intents, (position,))
        self.assertIsInstance(single.intents[0], PositionTargetIntent)
        self.assertEqual(len(two_leg.legs), 2)
        self.assertEqual(
            {
                (
                    item.instrument_id.kind,
                    item.target_quantity,
                )
                for item in two_leg.legs
            },
            {
                (InstrumentKind.SPOT, Quantity.from_str("10")),
                (
                    InstrumentKind.PERPETUAL,
                    Quantity.from_str("-10"),
                ),
            },
        )
        self.assertEqual(len(three_leg.legs), 3)
        self.assertEqual(
            sum(
                item.instrument_id.kind is InstrumentKind.OPTION
                for item in three_leg.legs
            ),
            2,
        )
        self.assertEqual(
            sum(
                item.instrument_id.kind is InstrumentKind.PERPETUAL
                for item in three_leg.legs
            ),
            1,
        )

    def test_snapshot_id_mismatch_is_rejected(self) -> None:
        other_id = DecisionSnapshotId("other-snapshot")
        target = basket(
            (
                basket_leg(
                    InstrumentKind.SPOT,
                    "BTCUSDT",
                    "10",
                    snapshot_id=other_id,
                ),
                basket_leg(
                    InstrumentKind.PERPETUAL,
                    "BTCUSDT",
                    "-10",
                    snapshot_id=other_id,
                ),
            ),
            snapshot_id=other_id,
        )
        runtime = StrategyRuntime(
            strategy=FixedStrategy(target),
            basket_policy=BASKET_POLICY,
            objective_registry=OBJECTIVE_REGISTRY,
        )
        runtime.start()

        with self.assertRaisesRegex(
            StrategyExecutionError,
            "decision_snapshot_id does not match",
        ):
            runtime.on_input(publication())

    def test_single_leg_pipeline_rejects_basket_before_risk_and_oms(
        self,
    ) -> None:
        target = basket(
            (
                basket_leg(InstrumentKind.SPOT, "BTCUSDT", "10"),
                basket_leg(
                    InstrumentKind.PERPETUAL,
                    "BTCUSDT",
                    "-10",
                ),
            )
        )
        blocked = NeverReached()
        runtime = TradingPipeline(
            health=Healthy(),
            validator=MarketDataValidator(),
            market_state=AcceptingState(),
            features=NoFeatures(),
            strategy=BasketDecisionPort(target),
            portfolio=blocked,  # type: ignore[arg-type]
            risk=blocked,  # type: ignore[arg-type]
            oms=blocked,  # type: ignore[arg-type]
            execution=blocked,  # type: ignore[arg-type]
        )

        result = runtime.process(market_event())

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(result.trace[-1].stage, PipelineStage.STRATEGY)
        self.assertIn(
            "does not support Basket",
            result.rejection_reason,
        )
        self.assertEqual(result.risk_decisions, ())
        self.assertEqual(result.order_requests, ())
        self.assertEqual(result.submit_results, ())


if __name__ == "__main__":
    unittest.main()
