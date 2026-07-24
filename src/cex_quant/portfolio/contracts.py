"""Immutable account, balance, and position contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    AssetId,
    Money,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind


class PositionAccounting(StrEnum):
    """Cost convention of a normalized position."""

    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"
    OPTION = "option"
    QUANTO = "quanto"


@dataclass(frozen=True, slots=True, kw_only=True)
class Balance:
    """Absolute balance in one asset.

    ``total`` must equal ``available + locked`` numerically. Differing decimal
    scales are permitted because comparison is performed exactly.
    """

    asset: AssetId
    total: Money
    available: Money
    locked: Money

    def __post_init__(self) -> None:
        if not self.asset:
            raise ValueError("asset cannot be empty")
        values = (self.total, self.available, self.locked)
        if any(value.as_decimal() < 0 for value in values):
            raise ValueError("balance amounts cannot be negative")
        if self.total.as_decimal() != (
            self.available.as_decimal() + self.locked.as_decimal()
        ):
            raise ValueError("total must equal available plus locked")


@dataclass(frozen=True, slots=True, kw_only=True)
class Position:
    """Absolute normalized position with venue-supplied accounting values.

    Quantity is signed: positive is long, negative is short. Cost basis is
    non-negative and realized PnL is signed. The state container deliberately
    does not derive either value or perform mark-to-market valuation.
    """

    instrument_id: InstrumentId
    accounting: PositionAccounting
    quantity: Quantity
    cost_basis: Money
    realized_pnl: Money
    pnl_asset: AssetId
    average_entry_price: Price | None = None

    def __post_init__(self) -> None:
        if not self.pnl_asset:
            raise ValueError("pnl_asset cannot be empty")
        if self.accounting is PositionAccounting.QUANTO:
            raise NotImplementedError("quanto position accounting is not implemented")
        kind = self.instrument_id.kind
        derivative_kinds = {InstrumentKind.PERPETUAL, InstrumentKind.FUTURE}
        mismatch = (
            (
                self.accounting is PositionAccounting.SPOT
                and kind is not InstrumentKind.SPOT
            )
            or (
                self.accounting
                in {PositionAccounting.LINEAR, PositionAccounting.INVERSE}
                and kind not in derivative_kinds
            )
            or (
                self.accounting is PositionAccounting.OPTION
                and kind is not InstrumentKind.OPTION
            )
        )
        if mismatch:
            raise ValueError("position accounting does not match instrument kind")
        if self.cost_basis.as_decimal() < 0:
            raise ValueError("cost_basis cannot be negative")
        if self.quantity.raw != 0 and self.average_entry_price is None:
            raise ValueError("non-flat position requires average_entry_price")
        if (
            self.average_entry_price is not None
            and self.average_entry_price.as_decimal() <= 0
        ):
            raise ValueError("average_entry_price must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountUpdate:
    """Atomic normalized venue update containing absolute entity values."""

    venue_update_id: str
    account_id: AccountId
    venue: VenueId
    event_time_ns: UnixNanos
    balances: tuple[Balance, ...] = ()
    positions: tuple[Position, ...] = ()
    sequence: int | None = None

    def __post_init__(self) -> None:
        if (
            not self.venue_update_id
            or self.venue_update_id.strip() != self.venue_update_id
        ):
            raise ValueError("venue_update_id must be non-empty and trimmed")
        if not self.account_id:
            raise ValueError("account_id cannot be empty")
        if not self.venue:
            raise ValueError("venue cannot be empty")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence cannot be negative")
        balance_keys = [balance.asset for balance in self.balances]
        if len(balance_keys) != len(set(balance_keys)):
            raise ValueError("update contains duplicate balance assets")
        position_keys = [position.instrument_id for position in self.positions]
        if len(position_keys) != len(set(position_keys)):
            raise ValueError("update contains duplicate instruments")
        if any(
            position.instrument_id.venue != self.venue
            for position in self.positions
        ):
            raise ValueError("position venue does not match update venue")


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountSnapshot:
    """Immutable, deterministically ordered account-state projection."""

    account_id: AccountId
    venue: VenueId
    balances: tuple[Balance, ...]
    positions: tuple[Position, ...]
    as_of_time_ns: UnixNanos | None
    sequence: int | None


__all__ = [
    "AccountSnapshot",
    "AccountUpdate",
    "Balance",
    "Position",
    "PositionAccounting",
]
