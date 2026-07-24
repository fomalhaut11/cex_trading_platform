"""Venue-neutral instrument identities and product specifications."""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import AssetId, Money, Price, Quantity, UnixNanos, VenueId


class InstrumentKind(StrEnum):
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    OPTION = "option"


class InstrumentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    HALTED = "halted"
    EXPIRED = "expired"
    DELISTED = "delisted"


class ContractValueType(StrEnum):
    LINEAR = "linear"
    INVERSE = "inverse"
    QUANTO = "quanto"


class SettlementType(StrEnum):
    CASH = "cash"
    PHYSICAL = "physical"


class OptionSide(StrEnum):
    CALL = "call"
    PUT = "put"


class ExerciseStyle(StrEnum):
    EUROPEAN = "european"
    AMERICAN = "american"


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentId:
    """Structured canonical identity; `symbol` is venue-native and opaque."""

    venue: VenueId
    kind: InstrumentKind
    symbol: str

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol.strip() != self.symbol:
            raise ValueError("symbol must be a non-empty trimmed string")

    def __str__(self) -> str:
        return f"{self.venue}:{self.kind.value}:{self.symbol}"


@dataclass(frozen=True, slots=True, kw_only=True)
class SpotSpecification:
    """Spot product marker."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PerpetualSpecification:
    settlement_asset: AssetId
    margin_asset: AssetId
    contract_size: Quantity
    contract_size_asset: AssetId
    value_type: ContractValueType


@dataclass(frozen=True, slots=True, kw_only=True)
class FutureSpecification:
    settlement_asset: AssetId
    margin_asset: AssetId
    contract_size: Quantity
    contract_size_asset: AssetId
    value_type: ContractValueType
    expiry_time_ns: UnixNanos
    settlement_type: SettlementType


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionSpecification:
    underlying_id: InstrumentId
    settlement_asset: AssetId
    margin_asset: AssetId
    contract_size: Quantity
    contract_size_asset: AssetId
    strike: Price
    option_side: OptionSide
    exercise_style: ExerciseStyle
    expiry_time_ns: UnixNanos
    settlement_type: SettlementType


InstrumentSpecification = (
    SpotSpecification
    | PerpetualSpecification
    | FutureSpecification
    | OptionSpecification
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Instrument:
    """Tradable product definition independent of venue payload formats."""

    instrument_id: InstrumentId
    base_asset: AssetId
    quote_asset: AssetId
    price_increment: Price
    quantity_increment: Quantity
    status: InstrumentStatus
    specification: InstrumentSpecification
    min_quantity: Quantity | None = None
    min_notional: Money | None = None

    def __post_init__(self) -> None:
        expected = {
            InstrumentKind.SPOT: SpotSpecification,
            InstrumentKind.PERPETUAL: PerpetualSpecification,
            InstrumentKind.FUTURE: FutureSpecification,
            InstrumentKind.OPTION: OptionSpecification,
        }[self.instrument_id.kind]
        if not isinstance(self.specification, expected):
            raise ValueError(
                f"{self.instrument_id.kind.value} requires {expected.__name__}"
            )
        if self.price_increment.raw <= 0 or self.quantity_increment.raw <= 0:
            raise ValueError("price and quantity increments must be positive")
        if self.min_quantity is not None and self.min_quantity.raw < 0:
            raise ValueError("min_quantity cannot be negative")
        if self.min_notional is not None and self.min_notional.raw < 0:
            raise ValueError("min_notional cannot be negative")


__all__ = [
    "ContractValueType",
    "ExerciseStyle",
    "FutureSpecification",
    "Instrument",
    "InstrumentId",
    "InstrumentKind",
    "InstrumentSpecification",
    "InstrumentStatus",
    "OptionSide",
    "OptionSpecification",
    "PerpetualSpecification",
    "SettlementType",
    "SpotSpecification",
]
