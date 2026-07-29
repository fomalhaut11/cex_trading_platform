"""Immutable canonical financial source facts for ADR-013.

Facts represent authenticated economic evidence. They do not mutate a ledger,
Portfolio, Risk, OMS, or an application.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from cex_quant.core import (
    AccountId,
    AssetId,
    BasketLegId,
    ClientOrderId,
    FinancialFactId,
    FinancialObservationId,
    IntentId,
    Money,
    OrderGroupId,
    Price,
    Quantity,
    TradeId,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId

MAX_FINANCIAL_COMPONENTS = 16
MAX_FINANCIAL_REFERENCE_LENGTH = 512
MAX_SOURCE_CURSOR_LENGTH = 4_096
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FinancialSourceKind(StrEnum):
    PRIVATE_STREAM = "private_stream"
    AUTHENTICATED_HISTORY = "authenticated_history"
    RECONCILIATION = "reconciliation"


class FillSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class AccountCashFlowType(StrEnum):
    FUNDING = "funding"
    COMMISSION = "commission"
    REBATE = "rebate"
    BORROW_INTEREST = "borrow_interest"
    REALIZED_SETTLEMENT = "realized_settlement"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    LIQUIDATION = "liquidation"
    INSURANCE = "insurance"
    VENUE_ADJUSTMENT = "venue_adjustment"


@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialFactMetadata:
    fact_id: FinancialFactId
    venue: VenueId
    account_id: AccountId
    venue_reference: str
    effective_time_ns: UnixNanos
    schema_version: int

    def __post_init__(self) -> None:
        _require_identifier(self.fact_id, name="fact_id")
        _require_identifier(self.venue, name="venue")
        _require_identifier(self.account_id, name="account_id")
        _require_text(
            self.venue_reference,
            name="venue_reference",
            maximum=MAX_FINANCIAL_REFERENCE_LENGTH,
        )
        if self.effective_time_ns < 0:
            raise ValueError("effective_time_ns cannot be negative")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialFactObservation:
    observation_id: FinancialObservationId
    fact_id: FinancialFactId
    source_kind: FinancialSourceKind
    observed_at_ns: UnixNanos
    payload_fingerprint: str
    source_cursor: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.observation_id, name="observation_id")
        _require_identifier(self.fact_id, name="fact_id")
        if self.observed_at_ns < 0:
            raise ValueError("observed_at_ns cannot be negative")
        if not _SHA256_PATTERN.fullmatch(self.payload_fingerprint):
            raise ValueError("payload_fingerprint must be lowercase SHA-256")
        if self.source_cursor is not None:
            _require_text(
                self.source_cursor,
                name="source_cursor",
                maximum=MAX_SOURCE_CURSOR_LENGTH,
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class CashComponent:
    asset: AssetId
    signed_amount: Money

    def __post_init__(self) -> None:
        _require_identifier(self.asset, name="asset")
        if self.signed_amount.raw == 0:
            raise ValueError("cash component amount cannot be zero")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionFillFact:
    metadata: FinancialFactMetadata
    instrument_id: InstrumentId
    client_order_id: ClientOrderId
    venue_order_id: VenueOrderId
    venue_trade_id: TradeId
    side: FillSide
    fill_quantity: Quantity
    fill_price: Price
    quote_asset: AssetId
    quote_amount: Money
    commission: tuple[CashComponent, ...] = ()
    realized_pnl: tuple[CashComponent, ...] = ()
    intent_id: IntentId | None = None
    order_group_id: OrderGroupId | None = None
    basket_leg_id: BasketLegId | None = None

    def __post_init__(self) -> None:
        if self.instrument_id.venue != self.metadata.venue:
            raise ValueError("fill instrument venue does not match fact venue")
        _require_identifier(self.client_order_id, name="client_order_id")
        _require_identifier(self.venue_order_id, name="venue_order_id")
        _require_identifier(self.venue_trade_id, name="venue_trade_id")
        _require_identifier(self.quote_asset, name="quote_asset")
        if self.fill_quantity.as_decimal() <= 0:
            raise ValueError("fill_quantity must be positive")
        if self.fill_price.as_decimal() <= 0:
            raise ValueError("fill_price must be positive")
        if self.quote_amount.as_decimal() <= 0:
            raise ValueError("quote_amount must be positive")
        _validate_components(self.commission, name="commission")
        _validate_components(self.realized_pnl, name="realized_pnl")
        for name, value in (
            ("intent_id", self.intent_id),
            ("order_group_id", self.order_group_id),
            ("basket_leg_id", self.basket_leg_id),
        ):
            if value is not None:
                _require_identifier(value, name=name)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountCashFlowFact:
    metadata: FinancialFactMetadata
    cash_flow_type: AccountCashFlowType
    component: CashComponent
    instrument_id: InstrumentId | None = None

    def __post_init__(self) -> None:
        if (
            self.instrument_id is not None
            and self.instrument_id.venue != self.metadata.venue
        ):
            raise ValueError("cash-flow instrument venue does not match fact venue")


FinancialSourceFact: TypeAlias = ExecutionFillFact | AccountCashFlowFact


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservedFinancialFact:
    fact: FinancialSourceFact
    observation: FinancialFactObservation

    def __post_init__(self) -> None:
        if self.observation.fact_id != self.fact.metadata.fact_id:
            raise ValueError("observation fact_id does not match financial fact")


def _validate_components(
    components: tuple[CashComponent, ...],
    *,
    name: str,
) -> None:
    if len(components) > MAX_FINANCIAL_COMPONENTS:
        raise ValueError(f"{name} exceeds maximum component count")
    assets = tuple(str(component.asset) for component in components)
    if assets != tuple(sorted(assets)) or len(set(assets)) != len(assets):
        raise ValueError(f"{name} components must be unique and sorted by asset")


def _require_identifier(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")


def _require_text(value: str, *, name: str, maximum: int) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}")


__all__ = [
    "MAX_FINANCIAL_COMPONENTS",
    "MAX_FINANCIAL_REFERENCE_LENGTH",
    "MAX_SOURCE_CURSOR_LENGTH",
    "AccountCashFlowFact",
    "AccountCashFlowType",
    "CashComponent",
    "ExecutionFillFact",
    "FillSide",
    "FinancialFactMetadata",
    "FinancialFactObservation",
    "FinancialSourceFact",
    "FinancialSourceKind",
    "ObservedFinancialFact",
]
