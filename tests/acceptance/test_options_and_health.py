"""Scenario acceptance tests for option analytics and clock fail-closed safety."""

from dataclasses import replace
from math import exp, isclose
from unittest import TestCase

from cex_quant.core import (
    AssetId,
    IntentId,
    MonotonicNanos,
    Price,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.features import (
    FeatureQuality,
    ImpliedVolatilityError,
    ImpliedVolatilityFailure,
    OptionModelInputs,
    OptionPricingModel,
    option_greeks,
    option_price,
    option_price_bounds,
    solve_implied_volatility,
)
from cex_quant.instruments import (
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    OptionSide,
    SpotSpecification,
)
from cex_quant.observability import (
    ClockHealthMonitor,
    ClockHealthThresholds,
    HealthStatus,
    MonotonicClockRegressionError,
)
from cex_quant.risk import (
    RiskContext,
    RiskDecisionStatus,
    RiskEngine,
    RiskLimits,
    RiskRejectReason,
)
from cex_quant.strategy import PositionTargetIntent

YEAR_NS = 365 * 24 * 60 * 60 * 1_000_000_000
VALUATION_NS = UnixNanos(1_700_000_000_000_000_000)
NOW = UnixNanos(10_000)
STRATEGY = StrategyId("acceptance")


def model_inputs(
    *,
    model: OptionPricingModel,
    side: OptionSide,
    underlying: float = 100.0,
    strike: float = 100.0,
    expiry_years: float = 1.0,
    volatility: float = 0.25,
) -> OptionModelInputs:
    return OptionModelInputs(
        model=model,
        option_side=side,
        underlying_price=underlying,
        strike=strike,
        risk_free_rate=0.03,
        carry_rate=0.01 if model is OptionPricingModel.BLACK_SCHOLES else 0.0,
        volatility=volatility,
        valuation_time_ns=VALUATION_NS,
        expiry_time_ns=UnixNanos(
            int(VALUATION_NS) + round(expiry_years * YEAR_NS)
        ),
    )


class OptionAnalyticsAcceptanceTest(TestCase):
    def test_call_put_parity_uses_model_specific_discounting(self) -> None:
        for model in OptionPricingModel:
            with self.subTest(model=model):
                call = model_inputs(model=model, side=OptionSide.CALL)
                put = replace(call, option_side=OptionSide.PUT)
                actual = option_price(call) - option_price(put)
                time = call.years_to_expiry
                if model is OptionPricingModel.BLACK_SCHOLES:
                    expected = (
                        call.underlying_price * exp(-call.carry_rate * time)
                        - call.strike * exp(-call.risk_free_rate * time)
                    )
                else:
                    expected = exp(-call.risk_free_rate * time) * (
                        call.underlying_price - call.strike
                    )
                self.assertTrue(
                    isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                    (model, actual, expected),
                )

    def test_price_iv_price_roundtrip_across_moneyness_and_expiry(self) -> None:
        for model in OptionPricingModel:
            for side in OptionSide:
                for strike in (75.0, 100.0, 130.0):
                    for expiry in (7 / 365, 0.5, 2.0):
                        case = model_inputs(
                            model=model,
                            side=side,
                            strike=strike,
                            expiry_years=expiry,
                            volatility=0.37,
                        )
                        price = option_price(case)
                        solved = solve_implied_volatility(
                            replace(case, volatility=0.05),
                            market_price=price,
                        )
                        repriced = option_price(replace(case, volatility=solved))
                        with self.subTest(
                            model=model,
                            side=side,
                            strike=strike,
                            expiry=expiry,
                        ):
                            self.assertGreaterEqual(solved, 0.0)
                            self.assertLessEqual(solved, 5.0)
                            self.assertTrue(
                                isclose(
                                    repriced,
                                    price,
                                    rel_tol=0.0,
                                    abs_tol=2e-9,
                                ),
                                (repriced, price),
                            )

    def test_key_analytical_greeks_match_central_finite_differences(self) -> None:
        for model in OptionPricingModel:
            for side in OptionSide:
                case = model_inputs(
                    model=model,
                    side=side,
                    underlying=103.0,
                    strike=97.0,
                    expiry_years=0.8,
                    volatility=0.31,
                )
                greeks = option_greeks(case)
                price = option_price(case)
                price_step = 0.01
                up = option_price(
                    replace(case, underlying_price=103.0 + price_step)
                )
                down = option_price(
                    replace(case, underlying_price=103.0 - price_step)
                )
                numerical_delta = (up - down) / (2.0 * price_step)
                numerical_gamma = (
                    up - 2.0 * price + down
                ) / (price_step * price_step)
                vol_step = 1e-5
                numerical_vega = (
                    option_price(replace(case, volatility=0.31 + vol_step))
                    - option_price(replace(case, volatility=0.31 - vol_step))
                ) / (2.0 * vol_step)

                with self.subTest(model=model, side=side):
                    self.assertTrue(
                        isclose(
                            greeks.delta,
                            numerical_delta,
                            rel_tol=2e-7,
                            abs_tol=2e-7,
                        )
                    )
                    self.assertTrue(
                        isclose(
                            greeks.gamma,
                            numerical_gamma,
                            rel_tol=2e-5,
                            abs_tol=2e-7,
                        )
                    )
                    self.assertTrue(
                        isclose(
                            greeks.vega,
                            numerical_vega,
                            rel_tol=2e-8,
                            abs_tol=2e-7,
                        )
                    )

    def test_iv_solver_explicitly_rejects_no_arbitrage_violation(self) -> None:
        case = model_inputs(
            model=OptionPricingModel.BLACK_76,
            side=OptionSide.CALL,
        )
        _, upper = option_price_bounds(case)
        with self.assertRaises(ImpliedVolatilityError) as caught:
            solve_implied_volatility(case, market_price=upper + 0.01)
        self.assertEqual(
            caught.exception.failure,
            ImpliedVolatilityFailure.PRICE_OUT_OF_BOUNDS,
        )


class ManualClock:
    def __init__(self, *, wall_ns: int = 10_000, monotonic_ns: int = 1_000):
        self.wall_ns = wall_ns
        self.monotonic_ns = monotonic_ns

    def wall_time_ns(self) -> UnixNanos:
        return UnixNanos(self.wall_ns)

    def monotonic_time_ns(self) -> MonotonicNanos:
        return MonotonicNanos(self.monotonic_ns)


THRESHOLDS = ClockHealthThresholds(
    warning_abs_offset_ns=100,
    critical_abs_offset_ns=1_000,
    warning_rtt_ns=200,
    critical_rtt_ns=2_000,
    warning_sample_age_ns=500,
    critical_sample_age_ns=5_000,
    max_wall_jump_ns=50,
)


def spot() -> Instrument:
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


def risk_decision(clock_status: HealthStatus):
    instrument = spot()
    intent = PositionTargetIntent(
        intent_id=IntentId("clock-health-intent"),
        strategy_id=STRATEGY,
        instrument_id=instrument.instrument_id,
        target_quantity=Quantity.from_str("1"),
        decision_time_ns=UnixNanos(9_900),
        valid_until_ns=UnixNanos(10_100),
    )
    context = RiskContext(
        now_ns=NOW,
        strategy_id=STRATEGY,
        instrument=instrument,
        current_strategy_position=Quantity.from_str("0"),
        current_global_position=Quantity.from_str("0"),
        reference_price=Price.from_str("20000"),
        market_data_as_of_ns=UnixNanos(9_950),
        feature_data_as_of_ns=UnixNanos(9_950),
        feature_data_valid_until_ns=UnixNanos(10_050),
        feature_quality=FeatureQuality.GOOD,
        clock_status=clock_status,
    )
    return RiskEngine(RiskLimits()).evaluate(intent, context)


class ClockFailClosedAcceptanceTest(TestCase):
    def _monitor(self, clock: ManualClock) -> ClockHealthMonitor:
        return ClockHealthMonitor(
            venue="TEST",
            clock=clock,
            thresholds=THRESHOLDS,
        )

    def _assert_unhealthy_is_rejected(
        self, monitor: ClockHealthMonitor, expected_issue: str
    ) -> None:
        report = monitor.health()
        self.assertEqual(report.status, HealthStatus.UNHEALTHY)
        self.assertIn(expected_issue, {issue.code for issue in report.issues})
        decision = risk_decision(report.status)
        self.assertEqual(decision.status, RiskDecisionStatus.REJECT)
        self.assertIn(RiskRejectReason.CLOCK_UNHEALTHY, decision.reasons)

    def test_critical_offset_rtt_staleness_and_wall_jump_fail_closed(self) -> None:
        scenarios = (
            ("VENUE_CLOCK_OFFSET", 100, 100, 1_050, 0),
            ("VENUE_CLOCK_RTT", 2_000, 2_000, 1_000, 0),
            ("WALL_CLOCK_JUMP", 200, 100, 10_100, 0),
            ("CLOCK_SAMPLE_STALE", 100, 100, 10_050, 5_000),
        )
        for issue, wall_elapsed, mono_elapsed, venue_time, age in scenarios:
            with self.subTest(issue=issue):
                clock = ManualClock()
                monitor = self._monitor(clock)
                probe = monitor.start_probe()
                clock.wall_ns += wall_elapsed
                clock.monotonic_ns += mono_elapsed
                monitor.finish_probe(
                    probe,
                    venue_time_ns=UnixNanos(venue_time),
                )
                clock.wall_ns += age
                self._assert_unhealthy_is_rejected(monitor, issue)

    def test_monotonic_regression_latches_unhealthy_and_fails_closed(self) -> None:
        clock = ManualClock()
        monitor = self._monitor(clock)
        monitor.start_probe()
        clock.monotonic_ns -= 1
        with self.assertRaises(MonotonicClockRegressionError):
            monitor.start_probe()
        self._assert_unhealthy_is_rejected(
            monitor, "MONOTONIC_CLOCK_REGRESSION"
        )
