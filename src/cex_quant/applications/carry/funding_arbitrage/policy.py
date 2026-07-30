"""Bounded immutable Funding Carry feature and economic policies."""

from dataclasses import dataclass
from math import isfinite

from cex_quant.core import DurationNanos, Quantity
from cex_quant.strategy import MAX_BASKET_VALIDITY_NS


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryFeaturePolicy:
    estimated_round_trip_cost_rate: float
    funding_periods_per_year: int
    version: int

    def __post_init__(self) -> None:
        if (
            not isfinite(self.estimated_round_trip_cost_rate)
            or self.estimated_round_trip_cost_rate < 0
        ):
            raise ValueError("estimated cost rate must be finite and non-negative")
        if not 1 <= self.funding_periods_per_year <= 24 * 366:
            raise ValueError("funding periods per year is outside bounds")
        if self.version <= 0:
            raise ValueError("feature policy version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryEconomicPolicy:
    target_base_quantity: Quantity
    minimum_entry_net_rate: float
    maximum_entry_abs_basis_rate: float
    exit_net_rate: float
    hedge_tolerance_base_quantity: Quantity
    basket_validity_ns: DurationNanos
    version: int

    def __post_init__(self) -> None:
        if self.target_base_quantity.as_decimal() <= 0:
            raise ValueError("target base quantity must be positive")
        for name, value in (
            ("minimum_entry_net_rate", self.minimum_entry_net_rate),
            (
                "maximum_entry_abs_basis_rate",
                self.maximum_entry_abs_basis_rate,
            ),
            ("exit_net_rate", self.exit_net_rate),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.minimum_entry_net_rate <= self.exit_net_rate:
            raise ValueError("entry threshold must exceed exit threshold")
        if self.maximum_entry_abs_basis_rate < 0:
            raise ValueError("maximum basis rate cannot be negative")
        if self.hedge_tolerance_base_quantity.as_decimal() < 0:
            raise ValueError("hedge tolerance cannot be negative")
        if not 0 < self.basket_validity_ns <= MAX_BASKET_VALIDITY_NS:
            raise ValueError("Basket validity is outside hard bounds")
        if self.version <= 0:
            raise ValueError("economic policy version must be positive")


__all__ = [
    "FundingCarryEconomicPolicy",
    "FundingCarryFeaturePolicy",
]
