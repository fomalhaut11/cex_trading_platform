"""Funding Carry pair and exact linear quantity-conversion contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import gcd

from cex_quant.core import AccountId, AssetId, Quantity
from cex_quant.instruments import (
    ContractValueType,
    Instrument,
    InstrumentId,
    InstrumentKind,
    PerpetualSpecification,
)

from ..identifiers import (
    CarryPairId,
    deterministic_carry_pair_id,
)

MAX_CONVERSION_POLICY_REF_LENGTH = 128


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryPair:
    pair_id: CarryPairId
    underlying_asset_id: AssetId
    spot_account_id: AccountId
    spot_instrument_id: InstrumentId
    perpetual_account_id: AccountId
    perpetual_instrument_id: InstrumentId
    spot_base_units_per_quantity: Quantity
    perpetual_base_units_per_quantity: Quantity
    quantity_conversion_policy_ref: str
    schema_version: int

    def __post_init__(self) -> None:
        for name, value in (
            ("pair_id", self.pair_id),
            ("underlying_asset_id", self.underlying_asset_id),
            ("spot_account_id", self.spot_account_id),
            ("perpetual_account_id", self.perpetual_account_id),
        ):
            _require_id(value, name=name)
        if self.spot_instrument_id.kind is not InstrumentKind.SPOT:
            raise ValueError("Funding Carry spot leg must be SPOT")
        if (
            self.perpetual_instrument_id.kind
            is not InstrumentKind.PERPETUAL
        ):
            raise ValueError("Funding Carry derivative leg must be PERPETUAL")
        if self.spot_base_units_per_quantity.raw <= 0:
            raise ValueError("spot quantity conversion must be positive")
        if self.perpetual_base_units_per_quantity.raw <= 0:
            raise ValueError("perpetual quantity conversion must be positive")
        _require_text(
            self.quantity_conversion_policy_ref,
            name="quantity_conversion_policy_ref",
            maximum=MAX_CONVERSION_POLICY_REF_LENGTH,
        )
        if self.schema_version <= 0:
            raise ValueError("Funding Carry schema version must be positive")


def create_funding_carry_pair(
    *,
    underlying_asset_id: AssetId,
    spot_account_id: AccountId,
    spot_instrument: Instrument,
    perpetual_account_id: AccountId,
    perpetual_instrument: Instrument,
    quantity_conversion_policy_ref: str,
    schema_version: int = 1,
) -> FundingCarryPair:
    """Validate instrument metadata before persisting only stable references."""

    if spot_instrument.instrument_id.kind is not InstrumentKind.SPOT:
        raise ValueError("Funding Carry spot instrument must be SPOT")
    if (
        perpetual_instrument.instrument_id.kind
        is not InstrumentKind.PERPETUAL
    ):
        raise ValueError("Funding Carry derivative must be PERPETUAL")
    if (
        spot_instrument.base_asset != underlying_asset_id
        or perpetual_instrument.base_asset != underlying_asset_id
    ):
        raise ValueError("Funding Carry instruments have different underlying")
    specification = perpetual_instrument.specification
    if not isinstance(specification, PerpetualSpecification):
        raise ValueError("Funding Carry requires perpetual specification")
    if specification.value_type is not ContractValueType.LINEAR:
        raise ValueError("first Funding Carry MVP requires a linear perpetual")
    if specification.contract_size_asset != underlying_asset_id:
        raise ValueError(
            "perpetual contract size must be expressed in the underlying"
        )
    spot_multiplier = Quantity.from_str("1")
    perpetual_multiplier = specification.contract_size
    payload = {
        "perpetual_account_id": str(perpetual_account_id),
        "perpetual_base_units_per_quantity": _fixed(perpetual_multiplier),
        "perpetual_instrument_id": _instrument(
            perpetual_instrument.instrument_id
        ),
        "quantity_conversion_policy_ref": quantity_conversion_policy_ref,
        "schema_version": schema_version,
        "spot_account_id": str(spot_account_id),
        "spot_base_units_per_quantity": _fixed(spot_multiplier),
        "spot_instrument_id": _instrument(spot_instrument.instrument_id),
        "underlying_asset_id": str(underlying_asset_id),
    }
    return FundingCarryPair(
        pair_id=deterministic_carry_pair_id(payload),
        underlying_asset_id=underlying_asset_id,
        spot_account_id=spot_account_id,
        spot_instrument_id=spot_instrument.instrument_id,
        perpetual_account_id=perpetual_account_id,
        perpetual_instrument_id=perpetual_instrument.instrument_id,
        spot_base_units_per_quantity=spot_multiplier,
        perpetual_base_units_per_quantity=perpetual_multiplier,
        quantity_conversion_policy_ref=quantity_conversion_policy_ref,
        schema_version=schema_version,
    )


def base_to_instrument_quantity(
    base_quantity: Quantity,
    *,
    base_units_per_quantity: Quantity,
) -> Quantity:
    """Convert base units exactly, rejecting non-terminating decimal ratios."""

    if base_units_per_quantity.raw <= 0:
        raise ValueError("quantity conversion multiplier must be positive")
    numerator = base_quantity.raw * 10**base_units_per_quantity.scale
    denominator = 10**base_quantity.scale * base_units_per_quantity.raw
    common = gcd(abs(numerator), denominator)
    numerator //= common
    denominator //= common
    twos = 0
    fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("quantity conversion is not an exact decimal")
    scale = max(twos, fives)
    raw = numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    return Quantity(raw=raw, scale=scale)


def quantity_to_base(
    quantity: Quantity,
    *,
    base_units_per_quantity: Quantity,
) -> Quantity:
    value = quantity.as_decimal() * base_units_per_quantity.as_decimal()
    return Quantity.from_str(format(Decimal(value), "f"))


def _fixed(value: Quantity) -> dict[str, int]:
    return {"raw": value.raw, "scale": value.scale}


def _instrument(value: InstrumentId) -> dict[str, str]:
    return {
        "kind": value.kind.value,
        "symbol": value.symbol,
        "venue": str(value.venue),
    }


def _require_id(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")


def _require_text(
    value: str,
    *,
    name: str,
    maximum: int,
) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}")


__all__ = [
    "MAX_CONVERSION_POLICY_REF_LENGTH",
    "FundingCarryPair",
    "base_to_instrument_quantity",
    "create_funding_carry_pair",
    "quantity_to_base",
]
