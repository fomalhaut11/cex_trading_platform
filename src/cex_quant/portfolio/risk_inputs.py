"""Execution-consistent position and normalized margin inputs for Portfolio Risk.

The account baseline states exactly how far it covers the durable OMS journal.
Only execution effects after that watermark may be overlaid.  This prevents
the common and dangerous ``account position + all fills`` double count.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    AssetId,
    ClientOrderId,
    EventId,
    MarginScopeId,
    Money,
    PortfolioReconciliationId,
    Price,
    Quantity,
    Rate,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId
from cex_quant.snapshots import ObservationId

from .contracts import AccountSnapshot

MAX_EXECUTION_EFFECTS_PER_BATCH = 16_384


class PositionRiskReadiness(StrEnum):
    """Whether effective positions are safe to consume."""

    READY = "ready"
    UNRECONCILED = "unreconciled"
    DIVERGENT = "divergent"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionCoverage:
    """Inclusive durable OMS journal watermark represented by a baseline."""

    through_oms_journal_sequence: int

    def __post_init__(self) -> None:
        if self.through_oms_journal_sequence < 0:
            raise ValueError("OMS journal coverage cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciledAccountBaseline:
    """Authoritative absolute account state with explicit execution coverage."""

    reconciliation_id: PortfolioReconciliationId
    observation_id: ObservationId
    account: AccountSnapshot
    coverage: ExecutionCoverage
    reconciled_at_ns: UnixNanos

    def __post_init__(self) -> None:
        _require_id(self.reconciliation_id, name="reconciliation_id")
        _require_id(self.observation_id, name="observation_id")
        if self.reconciled_at_ns < 0:
            raise ValueError("reconciled_at_ns cannot be negative")
        if self.account.as_of_time_ns is None:
            raise ValueError("risk baseline requires account as_of_time_ns")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPositionEffect:
    """One accepted signed fill delta after the account baseline watermark."""

    effect_id: EventId
    oms_journal_sequence: int
    client_order_id: ClientOrderId
    account_id: AccountId
    instrument_id: InstrumentId
    cumulative_filled_quantity: Quantity
    signed_fill_delta: Quantity
    accepted_at_ns: UnixNanos

    def __post_init__(self) -> None:
        _require_id(self.effect_id, name="effect_id")
        _require_id(self.client_order_id, name="client_order_id")
        _require_id(self.account_id, name="account_id")
        if self.oms_journal_sequence <= 0:
            raise ValueError("OMS journal sequence must be positive")
        if self.accepted_at_ns < 0:
            raise ValueError("accepted_at_ns cannot be negative")
        if self.signed_fill_delta.raw == 0:
            raise ValueError("execution effect delta cannot be zero")
        if self.cumulative_filled_quantity.as_decimal() <= 0:
            raise ValueError("cumulative filled quantity must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPositionEffectBatch:
    """A complete scan of one contiguous OMS journal sequence range."""

    from_sequence_exclusive: int
    through_sequence_inclusive: int
    effects: tuple[ExecutionPositionEffect, ...]

    def __post_init__(self) -> None:
        if self.from_sequence_exclusive < 0:
            raise ValueError("batch start cannot be negative")
        if self.through_sequence_inclusive <= self.from_sequence_exclusive:
            raise ValueError("batch must advance the OMS journal watermark")
        if len(self.effects) > MAX_EXECUTION_EFFECTS_PER_BATCH:
            raise ValueError("execution effect batch exceeds hard bound")
        sequences = tuple(item.oms_journal_sequence for item in self.effects)
        if sequences != tuple(sorted(sequences)):
            raise ValueError("execution effects must be journal ordered")
        if len(set(item.effect_id for item in self.effects)) != len(self.effects):
            raise ValueError("execution effect IDs must be unique")
        if any(
            sequence <= self.from_sequence_exclusive
            or sequence > self.through_sequence_inclusive
            for sequence in sequences
        ):
            raise ValueError("execution effect falls outside scanned range")


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentPositionRiskView:
    """Absolute baseline, post-baseline overlay and effective quantity."""

    instrument_id: InstrumentId
    baseline_quantity: Quantity
    post_baseline_fill_delta: Quantity
    effective_quantity: Quantity

    def __post_init__(self) -> None:
        expected = (
            self.baseline_quantity.as_decimal()
            + self.post_baseline_fill_delta.as_decimal()
        )
        if self.effective_quantity.as_decimal() != expected:
            raise ValueError("effective quantity does not match baseline plus overlay")


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountPositionRiskView:
    """Immutable Portfolio Risk position input for one account."""

    account_id: AccountId
    reconciliation_id: PortfolioReconciliationId | None
    observation_id: ObservationId | None
    coverage: ExecutionCoverage
    as_of_ns: UnixNanos
    positions: tuple[InstrumentPositionRiskView, ...]
    readiness: PositionRiskReadiness
    reason: str = ""

    def __post_init__(self) -> None:
        _require_id(self.account_id, name="account_id")
        if self.as_of_ns < 0:
            raise ValueError("position Risk view as_of_ns cannot be negative")
        keys = tuple(str(item.instrument_id) for item in self.positions)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("position views must be unique and canonically ordered")
        if self.readiness is PositionRiskReadiness.READY and self.reason:
            raise ValueError("READY position view cannot carry a reason")
        if (
            self.readiness is PositionRiskReadiness.READY
            and (
                self.reconciliation_id is None
                or self.observation_id is None
            )
        ):
            raise ValueError("READY position view requires baseline evidence")
        if self.readiness is not PositionRiskReadiness.READY and not self.reason:
            raise ValueError("non-ready position view requires a reason")


class MarginMode(StrEnum):
    """Normalized collateral scope semantics."""

    CASH = "cash"
    CROSS = "cross"
    ISOLATED = "isolated"
    PORTFOLIO = "portfolio"


@dataclass(frozen=True, slots=True, kw_only=True)
class CollateralAssetSnapshot:
    asset: AssetId
    total: Money
    available: Money
    borrowed: Money
    accrued_interest: Money
    collateral_value: Money

    def __post_init__(self) -> None:
        _require_id(self.asset, name="asset")
        if any(
            item.as_decimal() < 0
            for item in (
                self.total,
                self.available,
                self.borrowed,
                self.accrued_interest,
                self.collateral_value,
            )
        ):
            raise ValueError("collateral values cannot be negative")
        if self.available.as_decimal() > self.total.as_decimal():
            raise ValueError("available collateral cannot exceed total")


@dataclass(frozen=True, slots=True, kw_only=True)
class MarginScopeSnapshot:
    """Venue-normalized margin facts; no venue payload leaks past adapters."""

    scope_id: MarginScopeId
    observation_id: ObservationId
    account_id: AccountId
    venue: VenueId
    mode: MarginMode
    reporting_asset: AssetId
    equity: Money
    collateral: tuple[CollateralAssetSnapshot, ...]
    initial_margin: Money
    maintenance_margin: Money
    available_margin: Money
    margin_ratio: Rate | None
    as_of_ns: UnixNanos
    source_update_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("scope_id", self.scope_id),
            ("observation_id", self.observation_id),
            ("account_id", self.account_id),
            ("venue", self.venue),
            ("reporting_asset", self.reporting_asset),
            ("source_update_id", self.source_update_id),
        ):
            _require_id(value, name=name)
        assets = tuple(str(item.asset) for item in self.collateral)
        if assets != tuple(sorted(assets)) or len(set(assets)) != len(assets):
            raise ValueError("collateral must be unique and canonically ordered")
        if any(
            item.as_decimal() < 0
            for item in (
                self.initial_margin,
                self.maintenance_margin,
                self.available_margin,
            )
        ):
            raise ValueError("margin values cannot be negative")
        if self.margin_ratio is not None and self.margin_ratio.as_decimal() < 0:
            raise ValueError("margin_ratio cannot be negative")
        if self.as_of_ns < 0:
            raise ValueError("margin as_of_ns cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionLiquidationReference:
    """Venue-provided liquidation reference for one derivative position."""

    observation_id: ObservationId
    account_id: AccountId
    instrument_id: InstrumentId
    liquidation_price: Price | None
    maintenance_margin: Money | None
    as_of_ns: UnixNanos

    def __post_init__(self) -> None:
        _require_id(self.observation_id, name="observation_id")
        _require_id(self.account_id, name="account_id")
        if self.instrument_id.venue == "":
            raise ValueError("instrument venue cannot be empty")
        if (
            self.liquidation_price is not None
            and self.liquidation_price.as_decimal() <= 0
        ):
            raise ValueError("liquidation price must be positive")
        if (
            self.maintenance_margin is not None
            and self.maintenance_margin.as_decimal() < 0
        ):
            raise ValueError("maintenance margin cannot be negative")
        if self.as_of_ns < 0:
            raise ValueError("liquidation reference time cannot be negative")


def _require_id(value: object, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > 128:
        raise ValueError(f"{name} exceeds maximum length 128")


__all__ = [
    "MAX_EXECUTION_EFFECTS_PER_BATCH",
    "AccountPositionRiskView",
    "CollateralAssetSnapshot",
    "ExecutionCoverage",
    "ExecutionPositionEffect",
    "ExecutionPositionEffectBatch",
    "InstrumentPositionRiskView",
    "MarginMode",
    "MarginScopeSnapshot",
    "PositionLiquidationReference",
    "PositionRiskReadiness",
    "ReconciledAccountBaseline",
]
