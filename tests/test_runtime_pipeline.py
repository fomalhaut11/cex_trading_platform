from dataclasses import replace
from unittest import TestCase

from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
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
from cex_quant.execution import ExecutionOutcome, SubmitResult
from cex_quant.features import FeatureQuality
from cex_quant.instruments import (
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    SpotSpecification,
)
from cex_quant.market_data import (
    BestBidAsk,
    BookLevel,
    MarketDataValidator,
)
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.oms import (
    OrderRequest,
    OrderSide,
    OrderSubmitOutcome,
    OrderType,
)
from cex_quant.risk import (
    RiskContext,
    RiskDecision,
    RiskDecisionStatus,
    RiskRejectReason,
)
from cex_quant.runtime import (
    PipelineOutcome,
    PipelineStage,
    PipelineStateError,
    PipelineStatus,
    StageTrace,
    StateGate,
    TradingPipeline,
)
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    BasketTargetIntent,
    BasketTargetLeg,
    DecisionIntent,
    ObjectiveTypeRef,
    PositionTargetIntent,
    StrategyDecision,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)

NOW = UnixNanos(2_000)
STRATEGY_ID = StrategyId("maker")


def instrument() -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("TEST"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSD",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USD"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.001"),
        status=InstrumentStatus.ACTIVE,
        specification=SpotSpecification(),
    )


def event(inst: Instrument) -> BestBidAsk:
    return BestBidAsk(
        metadata=EventMetadata(
            event_id=EventId("event-1"),
            event_time_ns=UnixNanos(1_900),
            receive_time_ns=UnixNanos(1_950),
            source=EventSource(venue=VenueId("TEST"), channel="bookTicker"),
            schema_version=SchemaVersion(1),
            source_time_precision=TimePrecision.NANOSECOND,
        ),
        instrument_id=inst.instrument_id,
        bid=BookLevel(
            price=Price.from_str("99"),
            quantity=Quantity.from_str("2"),
        ),
        ask=BookLevel(
            price=Price.from_str("101"),
            quantity=Quantity.from_str("2"),
        ),
    )


def intent(inst: Instrument) -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId("intent-1"),
        strategy_id=STRATEGY_ID,
        instrument_id=inst.instrument_id,
        target_quantity=Quantity.from_str("1"),
        decision_time_ns=UnixNanos(1_960),
        valid_until_ns=UnixNanos(2_100),
    )


def basket_intent() -> BasketTargetIntent:
    snapshot_id = DecisionSnapshotId("snapshot-pipeline")
    legs = []
    for kind, target in (
        (InstrumentKind.SPOT, "10"),
        (InstrumentKind.PERPETUAL, "-10"),
    ):
        instrument_id = InstrumentId(
            venue=VenueId("TEST"),
            kind=kind,
            symbol="BTCUSD",
        )
        legs.append(
            BasketTargetLeg(
                leg_id=deterministic_basket_leg_id(
                    decision_snapshot_id=snapshot_id,
                    account_id=AccountId("primary"),
                    instrument_id=instrument_id,
                ),
                account_id=AccountId("primary"),
                instrument_id=instrument_id,
                target_quantity=Quantity.from_str(target),
            )
        )
    return create_basket_target_intent(
        strategy_id=STRATEGY_ID,
        decision_snapshot_id=snapshot_id,
        objective=ObjectiveTypeRef(
            objective_type_id=ObjectiveTypeId("carry.funding"),
            version=1,
        ),
        legs=tuple(legs),
        decision_time_ns=UnixNanos(1_960),
        valid_until_ns=UnixNanos(2_100),
        policy_version=1,
    )


class Health:
    def __init__(self, status: HealthStatus = HealthStatus.HEALTHY) -> None:
        self.status = status

    def health(self) -> HealthReport:
        return HealthReport(
            component="runtime",
            status=self.status,
            observed_at_ns=NOW,
        )


class State:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def apply(self, value: object) -> StateGate:
        self.calls.append("state")
        return StateGate(accepted=True)


class Features:
    def __init__(self, calls: list[str], *, fail: bool = False) -> None:
        self.calls = calls
        self.fail = fail

    def on_event(self, value: object) -> None:
        self.calls.append("feature")
        if self.fail:
            raise RuntimeError("feature exploded")
        return None


class Strategy:
    def __init__(
        self,
        calls: list[str],
        decision_intent: DecisionIntent,
    ) -> None:
        self.calls = calls
        self.intent = decision_intent

    def on_input(self, value: object) -> StrategyDecision:
        self.calls.append("strategy")
        return StrategyDecision(
            strategy_id=STRATEGY_ID,
            input_sequence=1,
            intents=(self.intent,),
        )


class Portfolio:
    def __init__(self, calls: list[str], inst: Instrument) -> None:
        self.calls = calls
        self.instrument = inst

    def risk_context(self, value: PositionTargetIntent) -> RiskContext:
        self.calls.append("portfolio")
        return RiskContext(
            now_ns=NOW,
            strategy_id=STRATEGY_ID,
            instrument=self.instrument,
            current_strategy_position=Quantity.from_str("0"),
            current_global_position=Quantity.from_str("0"),
            reference_price=Price.from_str("100"),
            market_data_as_of_ns=UnixNanos(1_900),
            feature_data_as_of_ns=UnixNanos(1_900),
            feature_data_valid_until_ns=UnixNanos(2_100),
            feature_quality=FeatureQuality.GOOD,
            clock_status=HealthStatus.HEALTHY,
        )


class Risk:
    def __init__(self, calls: list[str], *, allow: bool = True) -> None:
        self.calls = calls
        self.allow = allow

    def evaluate(
        self,
        value: PositionTargetIntent,
        context: RiskContext,
    ) -> RiskDecision:
        self.calls.append("risk")
        return RiskDecision(
            status=(
                RiskDecisionStatus.ALLOW
                if self.allow
                else RiskDecisionStatus.REJECT
            ),
            intent=value,
            reasons=(
                ()
                if self.allow
                else (RiskRejectReason.GLOBAL_POSITION_LIMIT,)
            ),
            projected_strategy_position=value.target_quantity,
            projected_global_position=value.target_quantity,
            projected_strategy_notional=None,
            projected_global_notional=None,
        )


class Oms:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def create_order(
        self,
        value: PositionTargetIntent,
        approval: RiskDecision,
    ) -> OrderRequest:
        self.calls.append("oms")
        if not approval.allowed:
            raise AssertionError("OMS received rejected risk decision")
        return OrderRequest(
            client_order_id=ClientOrderId("order-1"),
            approval_id="approval-1",
            intent_id=value.intent_id,
            account_id=AccountId("primary"),
            instrument_id=value.instrument_id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Quantity.from_str("1"),
            created_at_ns=NOW,
        )

    def prepare_submit(self, request: OrderRequest) -> OrderRequest:
        self.calls.append("oms_prepare")
        return request

    def record_submit_result(self, result: SubmitResult) -> None:
        self.calls.append("oms_result")

    def record_submit_failure(
        self,
        client_order_id: ClientOrderId,
        *,
        outcome: OrderSubmitOutcome,
        reason: str,
    ) -> None:
        del client_order_id, outcome, reason
        self.calls.append("oms_failure")


class Execution:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def submit(self, request: OrderRequest) -> SubmitResult:
        self.calls.append("execution")
        return SubmitResult(
            client_order_id=request.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
        )


class Recorder:
    def __init__(
        self,
        *,
        fail_stage: PipelineStage | None = None,
    ) -> None:
        self.stages: list[PipelineStage] = []
        self.fail_stage = fail_stage

    def record(self, trace: StageTrace, value: object) -> None:
        del value
        stage = trace.stage
        self.stages.append(stage)
        if stage is self.fail_stage:
            raise OSError("recorder unavailable")


def pipeline(
    *,
    health_status: HealthStatus = HealthStatus.HEALTHY,
    allow: bool = True,
    feature_failure: bool = False,
    recorder: Recorder | None = None,
    decision_intent: DecisionIntent | None = None,
) -> tuple[TradingPipeline, list[str], BestBidAsk]:
    calls: list[str] = []
    inst = instrument()
    value = intent(inst) if decision_intent is None else decision_intent
    return (
        TradingPipeline(
            health=Health(health_status),
            validator=MarketDataValidator(),
            market_state=State(calls),
            features=Features(calls, fail=feature_failure),
            strategy=Strategy(calls, value),
            portfolio=Portfolio(calls, inst),
            risk=Risk(calls, allow=allow),
            oms=Oms(calls),
            execution=Execution(calls),
            recorder=recorder,
        ),
        calls,
        event(inst),
    )


class RuntimePipelineTests(TestCase):
    def test_happy_path_has_deterministic_mandatory_order(self) -> None:
        runtime, calls, value = pipeline()

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.COMPLETED)
        self.assertEqual(
            calls,
            [
                "state",
                "feature",
                "strategy",
                "portfolio",
                "risk",
                "oms",
                "oms_prepare",
                "execution",
                "oms_result",
            ],
        )
        self.assertEqual(
            [item.stage for item in result.trace],
            [
                PipelineStage.HEALTH,
                PipelineStage.VALIDATION,
                PipelineStage.MARKET_STATE,
                PipelineStage.FEATURE,
                PipelineStage.STRATEGY,
                PipelineStage.RISK,
                PipelineStage.OMS,
                PipelineStage.EXECUTION,
            ],
        )
        self.assertEqual(
            [item.sequence for item in result.trace],
            list(range(1, 9)),
        )
        self.assertEqual(len(result.submit_results), 1)

    def test_risk_rejection_cannot_reach_oms_or_execution(self) -> None:
        runtime, calls, value = pipeline(allow=False)

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertIn("risk", calls)
        self.assertNotIn("oms", calls)
        self.assertNotIn("execution", calls)
        self.assertEqual(result.order_requests, ())
        self.assertEqual(result.submit_results, ())
        self.assertEqual(runtime.status, PipelineStatus.RUNNING)

    def test_basket_is_explicitly_rejected_before_single_leg_ports(
        self,
    ) -> None:
        runtime, calls, value = pipeline(decision_intent=basket_intent())

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(calls, ["state", "feature", "strategy"])
        self.assertEqual(result.trace[-1].stage, PipelineStage.STRATEGY)
        self.assertIn("does not support Basket", result.rejection_reason)
        self.assertEqual(result.risk_decisions, ())
        self.assertEqual(result.order_requests, ())
        self.assertEqual(result.submit_results, ())
        self.assertEqual(runtime.status, PipelineStatus.RUNNING)

    def test_unhealthy_gate_rejects_before_any_domain_stage(self) -> None:
        runtime, calls, value = pipeline(
            health_status=HealthStatus.DEGRADED
        )

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(calls, [])
        self.assertEqual(result.trace[-1].stage, PipelineStage.HEALTH)

    def test_stage_exception_is_latched_and_stops_future_processing(self) -> None:
        runtime, calls, value = pipeline(feature_failure=True)

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.FAILED)
        self.assertEqual(result.failure.stage, PipelineStage.FEATURE)
        self.assertEqual(runtime.status, PipelineStatus.FAILED)
        self.assertNotIn("strategy", calls)
        self.assertNotIn("execution", calls)
        with self.assertRaises(PipelineStateError):
            runtime.process(value)

    def test_mismatched_risk_decision_fails_before_oms(self) -> None:
        runtime, calls, value = pipeline()
        original = runtime._risk.evaluate

        def mismatched(
            target: PositionTargetIntent,
            context: RiskContext,
        ) -> RiskDecision:
            decision = original(target, context)
            return replace(
                decision,
                intent=replace(target, intent_id=IntentId("other")),
            )

        runtime._risk.evaluate = mismatched

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.FAILED)
        self.assertEqual(result.failure.stage, PipelineStage.RISK)
        self.assertNotIn("oms", calls)
        self.assertNotIn("execution", calls)

    def test_stop_prevents_processing(self) -> None:
        runtime, _, value = pipeline()
        runtime.stop()

        with self.assertRaises(PipelineStateError):
            runtime.process(value)

    def test_recorder_observes_order_and_failure_is_latched(self) -> None:
        recorder = Recorder(fail_stage=PipelineStage.STRATEGY)
        runtime, calls, value = pipeline(recorder=recorder)

        result = runtime.process(value)

        self.assertEqual(result.outcome, PipelineOutcome.FAILED)
        self.assertEqual(result.failure.stage, PipelineStage.RECORDER)
        self.assertEqual(
            recorder.stages,
            [
                PipelineStage.HEALTH,
                PipelineStage.VALIDATION,
                PipelineStage.MARKET_STATE,
                PipelineStage.FEATURE,
                PipelineStage.STRATEGY,
            ],
        )
        self.assertNotIn("risk", calls)
        self.assertNotIn("execution", calls)
