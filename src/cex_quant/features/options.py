"""System-computed European option analytics.

Venue-published analytics are deliberately absent from this module.  The
functions below operate only on explicit model inputs and immutable instrument
definitions, making replay results deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import erf, exp, isfinite, log, pi, sqrt

from cex_quant.core import UnixNanos
from cex_quant.instruments import (
    ExerciseStyle,
    InstrumentId,
    InstrumentKind,
    OptionSide,
    OptionSpecification,
)

_NANOS_PER_YEAR = 365.0 * 24.0 * 60.0 * 60.0 * 1_000_000_000.0
_SQRT_TWO = sqrt(2.0)
_SQRT_TWO_PI = sqrt(2.0 * pi)


class OptionPricingModel(StrEnum):
    BLACK_SCHOLES = "black_scholes"
    BLACK_76 = "black_76"


class ImpliedVolatilityFailure(StrEnum):
    INVALID_INPUT = "invalid_input"
    EXPIRED = "expired"
    PRICE_OUT_OF_BOUNDS = "price_out_of_bounds"
    NO_CONVERGENCE = "no_convergence"


class ImpliedVolatilityError(ValueError):
    """Typed, deterministic IV solution failure."""

    def __init__(self, failure: ImpliedVolatilityFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionModelInputs:
    """Inputs shared by pricing, Greeks and implied-volatility solving.

    ``underlying_price`` means spot under Black-Scholes and forward/futures
    price under Black-76. Rates, carry and volatility use decimal units.
    """

    model: OptionPricingModel
    option_side: OptionSide
    underlying_price: float
    strike: float
    risk_free_rate: float
    volatility: float
    valuation_time_ns: UnixNanos
    expiry_time_ns: UnixNanos
    carry_rate: float = 0.0

    @classmethod
    def from_specification(
        cls,
        specification: OptionSpecification,
        *,
        underlying_price: float,
        risk_free_rate: float,
        volatility: float,
        valuation_time_ns: UnixNanos,
        carry_rate: float = 0.0,
    ) -> OptionModelInputs:
        if specification.exercise_style is not ExerciseStyle.EUROPEAN:
            raise ValueError("closed-form models support European options only")
        return cls(
            model=pricing_model_for(specification),
            option_side=specification.option_side,
            underlying_price=underlying_price,
            strike=float(specification.strike.as_decimal()),
            risk_free_rate=risk_free_rate,
            volatility=volatility,
            valuation_time_ns=valuation_time_ns,
            expiry_time_ns=specification.expiry_time_ns,
            carry_rate=carry_rate,
        )

    def __post_init__(self) -> None:
        numeric = (
            self.underlying_price,
            self.strike,
            self.risk_free_rate,
            self.volatility,
            self.carry_rate,
        )
        if not all(isfinite(value) for value in numeric):
            raise ValueError("option model inputs must be finite")
        if self.underlying_price <= 0.0 or self.strike <= 0.0:
            raise ValueError("underlying price and strike must be positive")
        if self.volatility < 0.0:
            raise ValueError("volatility cannot be negative")
        if self.expiry_time_ns < self.valuation_time_ns:
            raise ValueError("expiry cannot precede valuation time")
        if self.model is OptionPricingModel.BLACK_76 and self.carry_rate != 0.0:
            raise ValueError("carry_rate is not an input to Black-76")

    @property
    def years_to_expiry(self) -> float:
        return (
            int(self.expiry_time_ns) - int(self.valuation_time_ns)
        ) / _NANOS_PER_YEAR


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionGreeks:
    """First- and second-order sensitivities in decimal model units.

    Under Black-76, delta is the derivative of the discounted option value
    with respect to the quoted forward/futures price and therefore includes
    the discount factor.
    """

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float

    def __post_init__(self) -> None:
        if not all(
            isfinite(value)
            for value in (self.delta, self.gamma, self.vega, self.theta, self.rho)
        ):
            raise ValueError("Greeks must be finite")


@dataclass(frozen=True, slots=True, kw_only=True, order=True)
class VolatilitySurfacePoint:
    """One system-computed IV observation; no interpolation is implied."""

    expiry_time_ns: UnixNanos
    strike: float
    option_side: OptionSide
    implied_volatility: float

    def __post_init__(self) -> None:
        if not isfinite(self.strike) or self.strike <= 0.0:
            raise ValueError("surface strike must be positive and finite")
        if (
            not isfinite(self.implied_volatility)
            or self.implied_volatility < 0.0
        ):
            raise ValueError(
                "surface implied volatility must be non-negative and finite"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class VolatilitySurfaceSnapshot:
    """Immutable, deterministically ordered raw surface points."""

    underlying_id: InstrumentId
    as_of_ns: UnixNanos
    model: OptionPricingModel
    points: tuple[VolatilitySurfacePoint, ...]

    def __post_init__(self) -> None:
        if any(point.expiry_time_ns <= self.as_of_ns for point in self.points):
            raise ValueError("surface points must expire after as_of_ns")
        if self.points != tuple(sorted(self.points)):
            raise ValueError("surface points must be sorted")
        keys = tuple(
            (point.expiry_time_ns, point.strike, point.option_side)
            for point in self.points
        )
        if len(keys) != len(set(keys)):
            raise ValueError("surface points must be unique")


def pricing_model_for(specification: OptionSpecification) -> OptionPricingModel:
    """Choose the closed-form model from the canonical underlying product."""

    kind = specification.underlying_id.kind
    if kind is InstrumentKind.SPOT:
        return OptionPricingModel.BLACK_SCHOLES
    if kind in (InstrumentKind.PERPETUAL, InstrumentKind.FUTURE):
        return OptionPricingModel.BLACK_76
    raise ValueError(f"unsupported option underlying kind: {kind.value}")


def option_price(inputs: OptionModelInputs) -> float:
    """Return the European option value, including deterministic expiry value."""

    time = inputs.years_to_expiry
    if time == 0.0:
        return _intrinsic(
            inputs.option_side, inputs.underlying_price, inputs.strike
        )
    if inputs.volatility == 0.0:
        return _zero_volatility_price(inputs, time)

    d1, d2 = _d1_d2(inputs, time)
    sign = 1.0 if inputs.option_side is OptionSide.CALL else -1.0
    discount = exp(-inputs.risk_free_rate * time)
    if inputs.model is OptionPricingModel.BLACK_76:
        return discount * sign * (
            inputs.underlying_price * _normal_cdf(sign * d1)
            - inputs.strike * _normal_cdf(sign * d2)
        )
    carry_discount = exp(-inputs.carry_rate * time)
    return sign * (
        inputs.underlying_price * carry_discount * _normal_cdf(sign * d1)
        - inputs.strike * discount * _normal_cdf(sign * d2)
    )


def option_price_bounds(inputs: OptionModelInputs) -> tuple[float, float]:
    """Return model-independent European no-arbitrage price bounds."""

    time = inputs.years_to_expiry
    if time == 0.0:
        intrinsic = _intrinsic(
            inputs.option_side, inputs.underlying_price, inputs.strike
        )
        return intrinsic, intrinsic

    discount = exp(-inputs.risk_free_rate * time)
    if inputs.model is OptionPricingModel.BLACK_76:
        discounted_underlying = discount * inputs.underlying_price
    else:
        discounted_underlying = inputs.underlying_price * exp(
            -inputs.carry_rate * time
        )
    discounted_strike = discount * inputs.strike
    if inputs.option_side is OptionSide.CALL:
        return (
            max(discounted_underlying - discounted_strike, 0.0),
            discounted_underlying,
        )
    return (
        max(discounted_strike - discounted_underlying, 0.0),
        discounted_strike,
    )


def option_greeks(inputs: OptionModelInputs) -> OptionGreeks:
    """Return analytical Greeks; positive time and volatility are required."""

    time = inputs.years_to_expiry
    if time <= 0.0:
        raise ValueError("Greeks are undefined at expiry")
    if inputs.volatility <= 0.0:
        raise ValueError("Greeks require positive volatility")

    d1, d2 = _d1_d2(inputs, time)
    root_time = sqrt(time)
    density = _normal_pdf(d1)
    discount = exp(-inputs.risk_free_rate * time)
    sign = 1.0 if inputs.option_side is OptionSide.CALL else -1.0
    price = option_price(inputs)

    if inputs.model is OptionPricingModel.BLACK_76:
        delta = discount * sign * _normal_cdf(sign * d1)
        gamma = discount * density / (
            inputs.underlying_price * inputs.volatility * root_time
        )
        vega = discount * inputs.underlying_price * density * root_time
        theta = (
            -discount
            * inputs.underlying_price
            * density
            * inputs.volatility
            / (2.0 * root_time)
            + inputs.risk_free_rate * price
        )
        rho = -time * price
    else:
        carry_discount = exp(-inputs.carry_rate * time)
        delta = carry_discount * sign * _normal_cdf(sign * d1)
        gamma = carry_discount * density / (
            inputs.underlying_price * inputs.volatility * root_time
        )
        vega = (
            inputs.underlying_price * carry_discount * density * root_time
        )
        theta = (
            -inputs.underlying_price
            * carry_discount
            * density
            * inputs.volatility
            / (2.0 * root_time)
            - sign
            * inputs.risk_free_rate
            * inputs.strike
            * discount
            * _normal_cdf(sign * d2)
            + sign
            * inputs.carry_rate
            * inputs.underlying_price
            * carry_discount
            * _normal_cdf(sign * d1)
        )
        rho = (
            sign
            * inputs.strike
            * time
            * discount
            * _normal_cdf(sign * d2)
        )
    return OptionGreeks(
        delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho
    )


def solve_implied_volatility(
    inputs: OptionModelInputs,
    *,
    market_price: float,
    lower_bound: float = 0.0,
    upper_bound: float = 5.0,
    price_tolerance: float = 1e-10,
    volatility_tolerance: float = 1e-10,
    max_iterations: int = 128,
) -> float:
    """Solve IV with bounded deterministic bisection.

    The volatility on ``inputs`` is ignored.  Bounds are inclusive and no
    Newton fallback is used, so convergence is replay-stable.
    """

    if (
        not isfinite(market_price)
        or not isfinite(lower_bound)
        or not isfinite(upper_bound)
        or not isfinite(price_tolerance)
        or not isfinite(volatility_tolerance)
        or market_price < 0.0
        or lower_bound < 0.0
        or upper_bound <= lower_bound
        or price_tolerance <= 0.0
        or volatility_tolerance <= 0.0
        or max_iterations < 1
    ):
        raise ImpliedVolatilityError(
            ImpliedVolatilityFailure.INVALID_INPUT,
            "invalid implied-volatility solver input",
        )
    if inputs.years_to_expiry <= 0.0:
        raise ImpliedVolatilityError(
            ImpliedVolatilityFailure.EXPIRED,
            "implied volatility is undefined at or after expiry",
        )

    no_arbitrage_low, no_arbitrage_high = option_price_bounds(inputs)
    if market_price < no_arbitrage_low - price_tolerance or market_price > (
        no_arbitrage_high + price_tolerance
    ):
        raise ImpliedVolatilityError(
            ImpliedVolatilityFailure.PRICE_OUT_OF_BOUNDS,
            "market price violates European no-arbitrage bounds",
        )

    low_price = option_price(_with_volatility(inputs, lower_bound))
    high_price = option_price(_with_volatility(inputs, upper_bound))
    if market_price < low_price - price_tolerance or market_price > (
        high_price + price_tolerance
    ):
        raise ImpliedVolatilityError(
            ImpliedVolatilityFailure.PRICE_OUT_OF_BOUNDS,
            "market price is outside prices implied by volatility bounds",
        )
    if abs(market_price - low_price) <= price_tolerance:
        return lower_bound
    if abs(market_price - high_price) <= price_tolerance:
        return upper_bound

    low = lower_bound
    high = upper_bound
    for _ in range(max_iterations):
        middle = (low + high) / 2.0
        middle_price = option_price(_with_volatility(inputs, middle))
        if (
            abs(middle_price - market_price) <= price_tolerance
            or high - low <= volatility_tolerance
        ):
            return middle
        if middle_price < market_price:
            low = middle
        else:
            high = middle
    raise ImpliedVolatilityError(
        ImpliedVolatilityFailure.NO_CONVERGENCE,
        "implied-volatility solver did not converge within max_iterations",
    )


def _with_volatility(
    inputs: OptionModelInputs, volatility: float
) -> OptionModelInputs:
    return OptionModelInputs(
        model=inputs.model,
        option_side=inputs.option_side,
        underlying_price=inputs.underlying_price,
        strike=inputs.strike,
        risk_free_rate=inputs.risk_free_rate,
        volatility=volatility,
        valuation_time_ns=inputs.valuation_time_ns,
        expiry_time_ns=inputs.expiry_time_ns,
        carry_rate=inputs.carry_rate,
    )


def _d1_d2(inputs: OptionModelInputs, time: float) -> tuple[float, float]:
    variance = inputs.volatility * inputs.volatility
    drift = (
        inputs.risk_free_rate - inputs.carry_rate
        if inputs.model is OptionPricingModel.BLACK_SCHOLES
        else 0.0
    )
    denominator = inputs.volatility * sqrt(time)
    d1 = (
        log(inputs.underlying_price / inputs.strike)
        + (drift + variance / 2.0) * time
    ) / denominator
    return d1, d1 - denominator


def _zero_volatility_price(inputs: OptionModelInputs, time: float) -> float:
    discount = exp(-inputs.risk_free_rate * time)
    if inputs.model is OptionPricingModel.BLACK_76:
        return discount * _intrinsic(
            inputs.option_side, inputs.underlying_price, inputs.strike
        )
    discounted_spot = inputs.underlying_price * exp(
        -inputs.carry_rate * time
    )
    discounted_strike = inputs.strike * discount
    return _intrinsic(
        inputs.option_side, discounted_spot, discounted_strike
    )


def _intrinsic(side: OptionSide, underlying: float, strike: float) -> float:
    sign = 1.0 if side is OptionSide.CALL else -1.0
    return max(sign * (underlying - strike), 0.0)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / _SQRT_TWO))


def _normal_pdf(value: float) -> float:
    return exp(-0.5 * value * value) / _SQRT_TWO_PI


__all__ = [
    "ImpliedVolatilityError",
    "ImpliedVolatilityFailure",
    "OptionGreeks",
    "OptionModelInputs",
    "OptionPricingModel",
    "VolatilitySurfacePoint",
    "VolatilitySurfaceSnapshot",
    "option_greeks",
    "option_price",
    "option_price_bounds",
    "pricing_model_for",
    "solve_implied_volatility",
]
