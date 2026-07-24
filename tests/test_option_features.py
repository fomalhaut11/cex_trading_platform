from __future__ import annotations

import math
import unittest

from cex_quant.core import AssetId, Price, Quantity, UnixNanos, VenueId
from cex_quant.features import (
    ImpliedVolatilityError,
    ImpliedVolatilityFailure,
    OptionModelInputs,
    OptionPricingModel,
    VolatilitySurfacePoint,
    VolatilitySurfaceSnapshot,
    option_greeks,
    option_price,
    option_price_bounds,
    pricing_model_for,
    solve_implied_volatility,
)
from cex_quant.instruments import (
    ExerciseStyle,
    InstrumentId,
    InstrumentKind,
    OptionSide,
    OptionSpecification,
    SettlementType,
)

YEAR_NS = 365 * 24 * 60 * 60 * 1_000_000_000


def model_inputs(
    *,
    model: OptionPricingModel = OptionPricingModel.BLACK_76,
    side: OptionSide = OptionSide.CALL,
    price: float = 100.0,
    strike: float = 100.0,
    rate: float = 0.05,
    volatility: float = 0.2,
    valuation_ns: int = 0,
    expiry_ns: int = YEAR_NS,
    carry: float = 0.0,
) -> OptionModelInputs:
    return OptionModelInputs(
        model=model,
        option_side=side,
        underlying_price=price,
        strike=strike,
        risk_free_rate=rate,
        volatility=volatility,
        valuation_time_ns=UnixNanos(valuation_ns),
        expiry_time_ns=UnixNanos(expiry_ns),
        carry_rate=carry,
    )


def option_specification(
    underlying_kind: InstrumentKind,
    *,
    style: ExerciseStyle = ExerciseStyle.EUROPEAN,
) -> OptionSpecification:
    return OptionSpecification(
        underlying_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=underlying_kind,
            symbol="BTCUSDT",
        ),
        settlement_asset=AssetId("USDT"),
        margin_asset=AssetId("USDT"),
        contract_size=Quantity(raw=1, scale=0),
        contract_size_asset=AssetId("BTC"),
        strike=Price(raw=100, scale=0),
        option_side=OptionSide.CALL,
        exercise_style=style,
        expiry_time_ns=UnixNanos(YEAR_NS),
        settlement_type=SettlementType.CASH,
    )


class OptionPricingTests(unittest.TestCase):
    def test_black_scholes_reference_price_and_greeks(self) -> None:
        inputs = model_inputs(model=OptionPricingModel.BLACK_SCHOLES)

        self.assertAlmostEqual(option_price(inputs), 10.4505835722, places=9)
        greeks = option_greeks(inputs)
        self.assertAlmostEqual(greeks.delta, 0.6368306512, places=9)
        self.assertAlmostEqual(greeks.gamma, 0.0187620173, places=9)
        self.assertAlmostEqual(greeks.vega, 37.5240346917, places=8)
        self.assertAlmostEqual(greeks.theta, -6.4140275464, places=8)
        self.assertAlmostEqual(greeks.rho, 53.2324815454, places=8)

    def test_black_76_reference_price_and_put_call_parity(self) -> None:
        call = model_inputs()
        put = model_inputs(side=OptionSide.PUT)

        self.assertAlmostEqual(option_price(call), 7.5770821464, places=9)
        self.assertAlmostEqual(option_price(put), 7.5770821464, places=9)
        parity = option_price(call) - option_price(put)
        self.assertAlmostEqual(parity, 0.0, places=12)

        greeks = option_greeks(call)
        self.assertAlmostEqual(greeks.delta, 0.5135001229, places=9)
        self.assertGreater(greeks.gamma, 0.0)
        self.assertGreater(greeks.vega, 0.0)
        self.assertAlmostEqual(greeks.rho, -option_price(call), places=12)

    def test_analytical_greeks_match_finite_differences(self) -> None:
        for model, carry in (
            (OptionPricingModel.BLACK_SCHOLES, 0.02),
            (OptionPricingModel.BLACK_76, 0.0),
        ):
            with self.subTest(model=model):
                inputs = model_inputs(
                    model=model,
                    price=103.0,
                    strike=97.0,
                    rate=0.04,
                    volatility=0.31,
                    carry=carry,
                )
                greeks = option_greeks(inputs)
                price_step = 1e-3
                vol_step = 1e-5
                rate_step = 1e-5
                time_step_ns = 1_000_000_000
                up = model_inputs(
                    model=model,
                    price=inputs.underlying_price + price_step,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate,
                    volatility=inputs.volatility,
                    carry=carry,
                )
                down = model_inputs(
                    model=model,
                    price=inputs.underlying_price - price_step,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate,
                    volatility=inputs.volatility,
                    carry=carry,
                )
                numerical_delta = (
                    option_price(up) - option_price(down)
                ) / (2.0 * price_step)
                numerical_gamma = (
                    option_price(up)
                    - 2.0 * option_price(inputs)
                    + option_price(down)
                ) / (price_step * price_step)
                vol_up = model_inputs(
                    model=model,
                    price=inputs.underlying_price,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate,
                    volatility=inputs.volatility + vol_step,
                    carry=carry,
                )
                vol_down = model_inputs(
                    model=model,
                    price=inputs.underlying_price,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate,
                    volatility=inputs.volatility - vol_step,
                    carry=carry,
                )
                numerical_vega = (
                    option_price(vol_up) - option_price(vol_down)
                ) / (2.0 * vol_step)
                rate_up = model_inputs(
                    model=model,
                    price=inputs.underlying_price,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate + rate_step,
                    volatility=inputs.volatility,
                    carry=carry,
                )
                rate_down = model_inputs(
                    model=model,
                    price=inputs.underlying_price,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate - rate_step,
                    volatility=inputs.volatility,
                    carry=carry,
                )
                numerical_rho = (
                    option_price(rate_up) - option_price(rate_down)
                ) / (2.0 * rate_step)
                later = model_inputs(
                    model=model,
                    price=inputs.underlying_price,
                    strike=inputs.strike,
                    rate=inputs.risk_free_rate,
                    volatility=inputs.volatility,
                    valuation_ns=time_step_ns,
                    carry=carry,
                )
                numerical_theta = (
                    option_price(later) - option_price(inputs)
                ) / (time_step_ns / YEAR_NS)

                self.assertAlmostEqual(greeks.delta, numerical_delta, places=7)
                self.assertAlmostEqual(greeks.gamma, numerical_gamma, places=5)
                self.assertAlmostEqual(greeks.vega, numerical_vega, places=6)
                self.assertAlmostEqual(greeks.rho, numerical_rho, places=6)
                self.assertAlmostEqual(greeks.theta, numerical_theta, places=5)

    def test_no_arbitrage_bounds_cover_both_models_and_sides(self) -> None:
        for model, carry in (
            (OptionPricingModel.BLACK_SCHOLES, 0.02),
            (OptionPricingModel.BLACK_76, 0.0),
        ):
            for side in (OptionSide.CALL, OptionSide.PUT):
                with self.subTest(model=model, side=side):
                    inputs = model_inputs(
                        model=model,
                        side=side,
                        price=110.0,
                        strike=100.0,
                        carry=carry,
                    )
                    low, high = option_price_bounds(inputs)
                    self.assertLessEqual(low, option_price(inputs))
                    self.assertLessEqual(option_price(inputs), high)
                    self.assertAlmostEqual(
                        low,
                        option_price(
                            model_inputs(
                                model=model,
                                side=side,
                                price=110.0,
                                strike=100.0,
                                volatility=0.0,
                                carry=carry,
                            )
                        ),
                    )

    def test_expiry_and_zero_volatility_have_explicit_values(self) -> None:
        expired = model_inputs(price=120.0, expiry_ns=0)
        zero_vol = model_inputs(
            price=120.0,
            volatility=0.0,
        )

        self.assertEqual(option_price(expired), 20.0)
        self.assertAlmostEqual(
            option_price(zero_vol), math.exp(-0.05) * 20.0
        )
        with self.assertRaisesRegex(ValueError, "undefined at expiry"):
            option_greeks(expired)
        with self.assertRaisesRegex(ValueError, "positive volatility"):
            option_greeks(zero_vol)

    def test_model_selection_matches_underlying_product(self) -> None:
        self.assertIs(
            pricing_model_for(option_specification(InstrumentKind.SPOT)),
            OptionPricingModel.BLACK_SCHOLES,
        )
        for kind in (InstrumentKind.PERPETUAL, InstrumentKind.FUTURE):
            self.assertIs(
                pricing_model_for(option_specification(kind)),
                OptionPricingModel.BLACK_76,
            )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            pricing_model_for(option_specification(InstrumentKind.OPTION))

    def test_from_specification_rejects_american_exercise(self) -> None:
        with self.assertRaisesRegex(ValueError, "European"):
            OptionModelInputs.from_specification(
                option_specification(
                    InstrumentKind.SPOT, style=ExerciseStyle.AMERICAN
                ),
                underlying_price=100.0,
                risk_free_rate=0.01,
                volatility=0.2,
                valuation_time_ns=UnixNanos(0),
            )

    def test_inputs_validate_nanoseconds_and_model_domain(self) -> None:
        with self.assertRaisesRegex(ValueError, "expiry"):
            model_inputs(valuation_ns=2, expiry_ns=1)
        with self.assertRaisesRegex(ValueError, "positive"):
            model_inputs(price=0.0)
        with self.assertRaisesRegex(ValueError, "finite"):
            model_inputs(rate=float("nan"))
        with self.assertRaisesRegex(ValueError, "carry_rate"):
            model_inputs(carry=0.01)


class ImpliedVolatilityTests(unittest.TestCase):
    def test_recovers_black_76_volatility_deterministically(self) -> None:
        inputs = model_inputs(volatility=0.37, price=91.0, strike=100.0)
        market_price = option_price(inputs)

        first = solve_implied_volatility(inputs, market_price=market_price)
        second = solve_implied_volatility(inputs, market_price=market_price)

        self.assertEqual(first, second)
        self.assertAlmostEqual(first, 0.37, places=8)

    def test_returns_inclusive_lower_bound(self) -> None:
        inputs = model_inputs(volatility=0.2, price=120.0)
        lower_price = option_price(model_inputs(volatility=0.0, price=120.0))

        self.assertEqual(
            solve_implied_volatility(inputs, market_price=lower_price), 0.0
        )

    def test_typed_solver_failures(self) -> None:
        cases = (
            (
                model_inputs(expiry_ns=0),
                20.0,
                {},
                ImpliedVolatilityFailure.EXPIRED,
            ),
            (
                model_inputs(),
                500.0,
                {},
                ImpliedVolatilityFailure.PRICE_OUT_OF_BOUNDS,
            ),
            (
                model_inputs(),
                5.0,
                {"upper_bound": 0.0},
                ImpliedVolatilityFailure.INVALID_INPUT,
            ),
            (
                model_inputs(),
                option_price(model_inputs(volatility=0.123)),
                {"max_iterations": 1, "price_tolerance": 1e-16},
                ImpliedVolatilityFailure.NO_CONVERGENCE,
            ),
        )
        for inputs, price, kwargs, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(ImpliedVolatilityError) as caught:
                    solve_implied_volatility(
                        inputs, market_price=price, **kwargs
                    )
                self.assertIs(caught.exception.failure, expected)

    def test_rejects_price_above_no_arbitrage_upper_bound(self) -> None:
        inputs = model_inputs(
            model=OptionPricingModel.BLACK_SCHOLES,
            carry=0.02,
        )
        _, upper = option_price_bounds(inputs)
        with self.assertRaises(ImpliedVolatilityError) as caught:
            solve_implied_volatility(inputs, market_price=upper + 0.01)
        self.assertIs(
            caught.exception.failure,
            ImpliedVolatilityFailure.PRICE_OUT_OF_BOUNDS,
        )
        self.assertIn("no-arbitrage", str(caught.exception))


class VolatilitySurfaceTests(unittest.TestCase):
    def test_snapshot_requires_sorted_unique_future_points(self) -> None:
        underlying_id = option_specification(
            InstrumentKind.FUTURE
        ).underlying_id
        call = VolatilitySurfacePoint(
            expiry_time_ns=UnixNanos(YEAR_NS),
            strike=100.0,
            option_side=OptionSide.CALL,
            implied_volatility=0.55,
        )
        put = VolatilitySurfacePoint(
            expiry_time_ns=UnixNanos(YEAR_NS),
            strike=100.0,
            option_side=OptionSide.PUT,
            implied_volatility=0.56,
        )
        snapshot = VolatilitySurfaceSnapshot(
            underlying_id=underlying_id,
            as_of_ns=UnixNanos(1),
            model=OptionPricingModel.BLACK_76,
            points=tuple(sorted((put, call))),
        )

        self.assertEqual(len(snapshot.points), 2)
        with self.assertRaisesRegex(ValueError, "sorted"):
            VolatilitySurfaceSnapshot(
                underlying_id=underlying_id,
                as_of_ns=UnixNanos(1),
                model=OptionPricingModel.BLACK_76,
                points=(put, call),
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            VolatilitySurfaceSnapshot(
                underlying_id=underlying_id,
                as_of_ns=UnixNanos(1),
                model=OptionPricingModel.BLACK_76,
                points=(call, call),
            )
        with self.assertRaisesRegex(ValueError, "expire after"):
            VolatilitySurfaceSnapshot(
                underlying_id=underlying_id,
                as_of_ns=UnixNanos(YEAR_NS),
                model=OptionPricingModel.BLACK_76,
                points=(call,),
            )

    def test_point_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "strike"):
            VolatilitySurfacePoint(
                expiry_time_ns=UnixNanos(YEAR_NS),
                strike=0.0,
                option_side=OptionSide.CALL,
                implied_volatility=0.5,
            )
        with self.assertRaisesRegex(ValueError, "implied volatility"):
            VolatilitySurfacePoint(
                expiry_time_ns=UnixNanos(YEAR_NS),
                strike=100.0,
                option_side=OptionSide.CALL,
                implied_volatility=float("nan"),
            )


if __name__ == "__main__":
    unittest.main()
