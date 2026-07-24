"""Offline acceptance scenarios for the synchronous trading path."""

from __future__ import annotations

from dataclasses import replace
from unittest import TestCase

from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
    EventId,
    EventMetadata,
    EventSource,
    FeatureId,
    IntentId,
    Price,
    Quantity,
    SchemaVersion,
    StrategyId,
    TimePrecision,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.execution import ExecutionOutcome, SubmitResult
from cex_quant.execution.adapters import (
    BinanceProduct,
    map_binance_submit,
)
from cex_quant.features import (
    FeatureDefinition,
    FeatureOutput,
    FeatureQuality,
    FeatureRef,
    FeatureVersion,
    OnlineFeatureEngine,
)
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
from cex_quant.market_data.state import L1State
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.oms import (
    DuplicateUpdateConflictError,
    InvalidOrderTransitionError,
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStateMachine,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
    UpdateDisposition,
)
from cex_quant.risk import RiskContext, RiskEngine, RiskLimits
from cex_quant.runtime import (
    PipelineOutcome,
    PipelineStage,
    StateGate,
    TradingPipeline,
)
from cex_quant.strategy import PositionTargetIntent, StrategyDecision

NOW = UnixNanos(2_000)
STRATEGY_ID = StrategyId("acceptance-maker")
ACCOUNT_ID = AccountId("acceptance-account")


def _instrument(
    kind: InstrumentKind = InstrumentKind.SPOT,
    symbol: str = "BTCUSDT",
) -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=kind,
            symbol=symbol,
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USDT"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.0001"),
        status=InstrumentStatus.ACTIVE,
        specification=SpotSpecification(),
    )


def _book(
    instrument: Instrument,
    *,
    bid: str = "99.90",
    ask: str = "100.10",
) -> BestBidAsk:
    return BestBidAsk(
        metadata=EventMetadata(
            event_id=EventId("acceptance-event-1"),
            event_time_ns=UnixNanos(1_900),
            receive_time_ns=UnixNanos(1_950),
            source=EventSource(
                venue=VenueId("BINANCE"),
                channel="bookTicker",
            ),
            schema_version=SchemaVersion(1),
            source_time_precision=TimePrecision.NANOSECOND,
            sequence=10,
        ),
        instrument_id=instrument.instrument_id,
        bid=BookLevel(
            price=Price.from_str(bid),
            quantity=Quantity.from_str("2.5"),
        ),
        ask=BookLevel(
            price=Price.from_str(ask),
            quantity=Quantity.from_str("3.5"),
        ),
    )


def _intent(instrument: Instrument, quantity: str = "1.25") -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId("acceptance-intent-1"),
        strategy_id=STRATEGY_ID,
        instrument_id=instrument.instrument_id,
        target_quantity=Quantity.from_str(quantity),
        decision_time_ns=UnixNanos(1_960),
        valid_until_ns=UnixNanos(2_100),
        reason="acceptance scenario",
    )


class _Health:
    def __init__(self, trace: list[str], status: HealthStatus) -> None:
        self._trace = trace
        self._status = status

    def health(self) -> HealthReport:
        self._trace.append("health")
        return HealthReport(
            component="acceptance-clock",
            status=self._status,
            observed_at_ns=NOW,
        )


class _Validator:
    def __init__(self, trace: list[str]) -> None:
        self._trace = trace
        self._validator = MarketDataValidator()

    def validate(self, event: BestBidAsk):
        self._trace.append("validation")
        return self._validator.validate(event, now_ns=NOW)


class _State:
    def __init__(self, trace: list[str], instrument: Instrument) -> None:
        self._trace = trace
        self.state = L1State(instrument_id=instrument.instrument_id)

    def apply(self, event: BestBidAsk) -> StateGate:
        self._trace.append("state")
        result = self.state.apply(event)
        return StateGate(accepted=result.status.value == "live")


class _Features:
    def __init__(self, trace: list[str], instrument: Instrument) -> None:
        self._trace = trace
        midpoint = FeatureRef(
            feature_id=FeatureId("midpoint"),
            version=FeatureVersion(1),
        )

        def calculate(context):
            event = context.event
            value = (
                event.bid.price.as_decimal() + event.ask.price.as_decimal()
            ) / 2
            return FeatureOutput(
                value=float(value),
                unit="USDT",
                quality=FeatureQuality.GOOD,
                valid_until_ns=UnixNanos(2_100),
            )

        self.engine = OnlineFeatureEngine(
            scope=str(instrument.instrument_id),
            definitions=(
                FeatureDefinition(
                    ref=midpoint,
                    event_types=(BestBidAsk,),
                    calculator=calculate,
                ),
            ),
        )

    def on_event(self, event: BestBidAsk):
        self._trace.append("feature")
        self.engine.on_event(event)
        return self.engine.snapshot()


class _Strategy:
    def __init__(
        self,
        trace: list[str],
        intent: PositionTargetIntent,
    ) -> None:
        self._trace = trace
        self._intent = intent

    def on_input(self, value) -> StrategyDecision:
        self._trace.append("strategy")
        self.input = value
        return StrategyDecision(
            strategy_id=STRATEGY_ID,
            input_sequence=1,
            intents=(self._intent,),
        )


class _Portfolio:
    def __init__(
        self,
        trace: list[str],
        instrument: Instrument,
        *,
        clock_status: HealthStatus = HealthStatus.HEALTHY,
    ) -> None:
        self._trace = trace
        self._instrument = instrument
        self._clock_status = clock_status

    def risk_context(self, intent: PositionTargetIntent) -> RiskContext:
        self._trace.append("portfolio")
        return RiskContext(
            now_ns=NOW,
            strategy_id=STRATEGY_ID,
            instrument=self._instrument,
            current_strategy_position=Quantity.from_str("0"),
            current_global_position=Quantity.from_str("0"),
            reference_price=Price.from_str("100.00"),
            market_data_as_of_ns=UnixNanos(1_900),
            feature_data_as_of_ns=UnixNanos(1_900),
            feature_data_valid_until_ns=UnixNanos(2_100),
            feature_quality=FeatureQuality.GOOD,
            clock_status=self._clock_status,
        )


class _Risk:
    def __init__(self, trace: list[str], limit: str = "2") -> None:
        self._trace = trace
        self._engine = RiskEngine(
            RiskLimits(
                max_abs_strategy_position=Quantity.from_str(limit),
                max_abs_global_position=Quantity.from_str(limit),
                max_market_data_age_ns=1_000,
                max_feature_data_age_ns=1_000,
            )
        )

    def evaluate(self, intent, context):
        self._trace.append("risk")
        return self._engine.evaluate(intent, context)


class _Oms:
    def __init__(self, trace: list[str]) -> None:
        self._trace = trace
        self.state: OrderStateMachine | None = None

    def create_order(self, intent, approval) -> OrderRequest:
        self._trace.append("oms")
        if not approval.allowed:
            raise AssertionError("rejected intent reached OMS")
        request = OrderRequest(
            client_order_id=ClientOrderId("acceptance:BTC:000001"),
            approval_id="acceptance-approval-1",
            intent_id=intent.intent_id,
            account_id=ACCOUNT_ID,
            instrument_id=intent.instrument_id,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=intent.target_quantity,
            created_at_ns=NOW,
            limit_price=Price.from_str("100.10"),
            time_in_force=TimeInForce.GTC,
        )
        self.state = OrderStateMachine(request)
        self.state.mark_submitting(at_ns=NOW)
        return request


class _Execution:
    def __init__(self, trace: list[str]) -> None:
        self._trace = trace
        self.requests = []

    def submit(self, request: OrderRequest) -> SubmitResult:
        self._trace.append("execution")
        mapped = map_binance_submit(BinanceProduct.SPOT, request)
        self.requests.append(mapped)
        return SubmitResult(
            client_order_id=request.client_order_id,
            outcome=ExecutionOutcome.ACCEPTED,
            venue_order_id=VenueOrderId("binance-order-1"),
        )


def _pipeline(
    *,
    health_status: HealthStatus = HealthStatus.HEALTHY,
    risk_limit: str = "2",
    risk_clock_status: HealthStatus = HealthStatus.HEALTHY,
) -> tuple[TradingPipeline, list[str], Instrument, _Execution]:
    trace: list[str] = []
    instrument = _instrument()
    execution = _Execution(trace)
    pipeline = TradingPipeline(
        health=_Health(trace, health_status),
        validator=_Validator(trace),
        market_state=_State(trace, instrument),
        features=_Features(trace, instrument),
        strategy=_Strategy(trace, _intent(instrument)),
        portfolio=_Portfolio(
            trace,
            instrument,
            clock_status=risk_clock_status,
        ),
        risk=_Risk(trace, risk_limit),
        oms=_Oms(trace),
        execution=execution,
    )
    return pipeline, trace, instrument, execution


class TradingPipelineAcceptanceTests(TestCase):
    def test_happy_path_composes_real_domain_modules_in_strict_order(self) -> None:
        pipeline, calls, instrument, execution = _pipeline()

        result = pipeline.process(_book(instrument))

        self.assertEqual(result.outcome, PipelineOutcome.COMPLETED)
        self.assertEqual(
            calls,
            [
                "health",
                "validation",
                "state",
                "feature",
                "strategy",
                "portfolio",
                "risk",
                "oms",
                "execution",
            ],
        )
        self.assertEqual(
            [entry.stage for entry in result.trace],
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
        self.assertEqual([entry.sequence for entry in result.trace], list(range(1, 9)))
        self.assertEqual(len(result.order_requests), 1)
        self.assertEqual(
            dict(execution.requests[0].parameters),
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "quantity": "1.25",
                "newClientOrderId": "acceptance:BTC:000001",
                "price": "100.10",
                "timeInForce": "GTC",
            },
        )

    def test_risk_rejection_never_reaches_oms_or_execution(self) -> None:
        pipeline, calls, instrument, execution = _pipeline(risk_limit="1")

        result = pipeline.process(_book(instrument))

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(result.trace[-1].stage, PipelineStage.RISK)
        self.assertNotIn("oms", calls)
        self.assertNotIn("execution", calls)
        self.assertEqual(execution.requests, [])

    def test_unhealthy_system_clock_stops_before_validation(self) -> None:
        pipeline, calls, instrument, execution = _pipeline(
            health_status=HealthStatus.UNHEALTHY
        )

        result = pipeline.process(_book(instrument))

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(calls, ["health"])
        self.assertEqual(result.trace[-1].stage, PipelineStage.HEALTH)
        self.assertEqual(execution.requests, [])

    def test_unhealthy_risk_clock_is_fail_closed_before_execution(self) -> None:
        pipeline, calls, instrument, execution = _pipeline(
            risk_clock_status=HealthStatus.DEGRADED
        )

        result = pipeline.process(_book(instrument))

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(result.trace[-1].stage, PipelineStage.RISK)
        self.assertNotIn("oms", calls)
        self.assertNotIn("execution", calls)
        self.assertEqual(execution.requests, [])

    def test_validation_failure_stops_before_state_and_execution(self) -> None:
        pipeline, calls, instrument, execution = _pipeline()

        result = pipeline.process(_book(instrument, bid="101", ask="100"))

        self.assertEqual(result.outcome, PipelineOutcome.REJECTED)
        self.assertEqual(calls, ["health", "validation"])
        self.assertEqual(result.trace[-1].stage, PipelineStage.VALIDATION)
        self.assertEqual(execution.requests, [])


def _order_request(
    *,
    kind: InstrumentKind = InstrumentKind.PERPETUAL,
    quantity: str = "10.000",
) -> OrderRequest:
    return OrderRequest(
        client_order_id=ClientOrderId("golden:BTC:000042"),
        approval_id="approval-42",
        intent_id=IntentId("intent-42"),
        account_id=ACCOUNT_ID,
        instrument_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=kind,
            symbol="BTCUSDT" if kind is not InstrumentKind.FUTURE else "BTCUSD_260925",
        ),
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Quantity.from_str(quantity),
        created_at_ns=NOW,
        limit_price=Price.from_str("64000.10"),
        time_in_force=TimeInForce.IOC,
    )


def _venue_event(
    update_id: str,
    status: OrderStatus,
    cumulative: str,
    *,
    reason: str = "",
) -> OrderEvent:
    return OrderEvent(
        venue_update_id=update_id,
        client_order_id=ClientOrderId("golden:BTC:000042"),
        venue_order_id=VenueOrderId("venue-42"),
        status=status,
        cumulative_filled_quantity=Quantity.from_str(cumulative),
        average_fill_price=(
            None if cumulative == "0" else Price.from_str("64000.10")
        ),
        event_time_ns=UnixNanos(2_100 + len(update_id)),
        reason=reason,
    )


class OmsAcceptanceTests(TestCase):
    def test_duplicate_update_is_idempotent_and_conflict_is_rejected(self) -> None:
        state = OrderStateMachine(_order_request())
        state.mark_submitting(at_ns=NOW)
        update = _venue_event("update-1", OrderStatus.OPEN, "0")

        first = state.apply_venue_update(update)
        duplicate = state.apply_venue_update(update)

        self.assertEqual(first.disposition, UpdateDisposition.APPLIED)
        self.assertEqual(duplicate.disposition, UpdateDisposition.DUPLICATE)
        self.assertEqual(duplicate.before, duplicate.after)
        with self.assertRaises(DuplicateUpdateConflictError):
            state.apply_venue_update(replace(update, reason="different payload"))

    def test_cancel_pending_allows_fill_but_canceled_is_terminal(
        self,
    ) -> None:
        state = OrderStateMachine(_order_request())
        state.mark_submitting(at_ns=NOW)
        state.apply_venue_update(_venue_event("update-open", OrderStatus.OPEN, "0"))
        state.request_cancel(at_ns=UnixNanos(2_050))

        filled = state.apply_venue_update(
            _venue_event("update-filled", OrderStatus.FILLED, "10.000")
        )

        self.assertEqual(filled.after.status, OrderStatus.FILLED)
        self.assertEqual(filled.after.remaining_quantity.as_decimal(), 0)

        canceled = OrderStateMachine(_order_request())
        canceled.mark_submitting(at_ns=NOW)
        canceled.apply_venue_update(
            _venue_event("update-canceled", OrderStatus.CANCELED, "0")
        )
        with self.assertRaises(InvalidOrderTransitionError):
            canceled.apply_venue_update(
                _venue_event("update-late-fill", OrderStatus.FILLED, "10.000")
            )


class BinanceGoldenMappingAcceptanceTests(TestCase):
    def test_spot_usdm_coinm_mapping_preserves_exact_decimals_and_client_id(
        self,
    ) -> None:
        spot = map_binance_submit(
            BinanceProduct.SPOT,
            _order_request(kind=InstrumentKind.SPOT, quantity="1.2300"),
        )
        usd_m = map_binance_submit(
            BinanceProduct.USD_M,
            _order_request(kind=InstrumentKind.PERPETUAL, quantity="0.00100"),
        )
        coin_m = map_binance_submit(
            BinanceProduct.COIN_M,
            replace(
                _order_request(kind=InstrumentKind.FUTURE, quantity="7.00"),
                reduce_only=True,
                position_side=PositionSide.NET,
            ),
        )

        self.assertEqual(
            (spot.path, spot.parameters["quantity"], spot.parameters["price"]),
            ("/api/v3/order", "1.2300", "64000.10"),
        )
        self.assertEqual(
            (usd_m.path, usd_m.parameters["quantity"], usd_m.parameters["price"]),
            ("/fapi/v1/order", "0.00100", "64000.10"),
        )
        self.assertEqual(
            (
                coin_m.path,
                coin_m.parameters["quantity"],
                coin_m.parameters["price"],
                coin_m.parameters["reduceOnly"],
            ),
            ("/dapi/v1/order", "7.00", "64000.10", "true"),
        )
        for mapped in (spot, usd_m, coin_m):
            self.assertEqual(
                mapped.parameters["newClientOrderId"],
                "golden:BTC:000042",
            )
            self.assertNotIn("apiKey", mapped.parameters)
            self.assertNotIn("signature", mapped.parameters)


if __name__ == "__main__":
    import unittest

    unittest.main()
