"""Exact decimal fixed-point values for trading contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Self


@dataclass(frozen=True, slots=True, kw_only=True)
class FixedPoint:
    """An exact decimal value represented by an integer and decimal scale."""

    raw: int
    scale: int

    def __post_init__(self) -> None:
        if self.scale < 0:
            raise ValueError("scale must be non-negative")

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Parse a decimal string without binary floating-point conversion."""

        try:
            decimal = Decimal(value)
        except InvalidOperation as error:
            raise ValueError(f"invalid decimal value: {value!r}") from error
        if not decimal.is_finite():
            raise ValueError("fixed-point value must be finite")
        sign, digits, exponent = decimal.as_tuple()
        if not isinstance(exponent, int):
            raise ValueError("finite decimal must have an integer exponent")
        scale = max(-exponent, 0)
        raw = int("".join(str(digit) for digit in digits) or "0")
        if exponent > 0:
            raw *= 10**exponent
        if sign:
            raw = -raw
        return cls(raw=raw, scale=scale)

    def as_decimal(self) -> Decimal:
        """Return an exact Decimal representation."""

        return Decimal(self.raw).scaleb(-self.scale)

    def rescale_exact(self, scale: int) -> Self:
        """Return the same value at another scale, rejecting precision loss."""

        if scale < 0:
            raise ValueError("scale must be non-negative")
        difference = scale - self.scale
        if difference >= 0:
            return type(self)(raw=self.raw * 10**difference, scale=scale)
        divisor = 10 ** (-difference)
        quotient, remainder = divmod(abs(self.raw), divisor)
        if remainder:
            raise ValueError("rescale would lose precision")
        if self.raw < 0:
            quotient = -quotient
        return type(self)(raw=quotient, scale=scale)

    def __str__(self) -> str:
        return format(self.as_decimal(), f".{self.scale}f")


@dataclass(frozen=True, slots=True, kw_only=True)
class Price(FixedPoint):
    """Exact price in an instrument's quote convention."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Quantity(FixedPoint):
    """Exact order or position quantity."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Money(FixedPoint):
    """Exact amount; the asset identifier is carried by the enclosing object."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Rate(FixedPoint):
    """Exact externally supplied rate, such as a venue funding rate."""


__all__ = ["FixedPoint", "Money", "Price", "Quantity", "Rate"]
