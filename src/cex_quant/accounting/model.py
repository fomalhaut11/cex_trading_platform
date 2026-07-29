"""Balanced immutable ledger contracts for ADR-013."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    LedgerAccountId,
    LedgerPostingId,
    LedgerTransactionId,
    Money,
    UnixNanos,
    VenueId,
)

MAX_LEDGER_POSTINGS_PER_TRANSACTION = 64
MAX_LEDGER_SOURCE_FACTS = 64
MAX_LEDGER_MEMO_LENGTH = 512


class LedgerAccountType(StrEnum):
    VENUE_CASH = "venue_cash"
    VENUE_INVENTORY = "venue_inventory"
    TRADE_CLEARING = "trade_clearing"
    FUNDING_INCOME = "funding_income"
    COMMISSION_EXPENSE = "commission_expense"
    REBATE_INCOME = "rebate_income"
    BORROW_INTEREST_EXPENSE = "borrow_interest_expense"
    REALIZED_PNL = "realized_pnl"
    TRANSFER_CLEARING = "transfer_clearing"
    LIQUIDATION_EXPENSE = "liquidation_expense"
    INSURANCE_CLEARING = "insurance_clearing"
    ADJUSTMENT_CLEARING = "adjustment_clearing"


class LedgerTransactionType(StrEnum):
    SPOT_FILL = "spot_fill"
    DERIVATIVE_FILL = "derivative_fill"
    FUNDING = "funding"
    COMMISSION = "commission"
    REBATE = "rebate"
    BORROW_INTEREST = "borrow_interest"
    REALIZED_SETTLEMENT = "realized_settlement"
    TRANSFER = "transfer"
    LIQUIDATION = "liquidation"
    INSURANCE = "insurance"
    VENUE_ADJUSTMENT = "venue_adjustment"
    REVERSAL = "reversal"


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerAccount:
    ledger_account_id: LedgerAccountId
    venue: VenueId
    account_id: AccountId
    account_type: LedgerAccountType
    asset: AssetId

    def __post_init__(self) -> None:
        for name, value in (
            ("ledger_account_id", self.ledger_account_id),
            ("venue", self.venue),
            ("account_id", self.account_id),
            ("asset", self.asset),
        ):
            _require_identifier(value, name=name)


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerPosting:
    posting_id: LedgerPostingId
    account: LedgerAccount
    signed_amount: Money
    memo: str = ""

    def __post_init__(self) -> None:
        _require_identifier(self.posting_id, name="posting_id")
        if self.signed_amount.raw == 0:
            raise ValueError("ledger posting amount cannot be zero")
        if self.memo != self.memo.strip():
            raise ValueError("ledger posting memo must be trimmed")
        if len(self.memo) > MAX_LEDGER_MEMO_LENGTH:
            raise ValueError("ledger posting memo exceeds maximum length")

    @property
    def asset(self) -> AssetId:
        return self.account.asset


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerTransactionDraft:
    transaction_id: LedgerTransactionId
    source_fact_ids: tuple[FinancialFactId, ...]
    transaction_type: LedgerTransactionType
    postings: tuple[LedgerPosting, ...]
    effective_time_ns: UnixNanos
    mapping_policy_version: int
    reverses_transaction_id: LedgerTransactionId | None = None

    def __post_init__(self) -> None:
        _validate_transaction_fields(
            transaction_id=self.transaction_id,
            source_fact_ids=self.source_fact_ids,
            postings=self.postings,
            effective_time_ns=self.effective_time_ns,
            mapping_policy_version=self.mapping_policy_version,
            reverses_transaction_id=self.reverses_transaction_id,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerTransaction:
    transaction_id: LedgerTransactionId
    source_fact_ids: tuple[FinancialFactId, ...]
    transaction_type: LedgerTransactionType
    postings: tuple[LedgerPosting, ...]
    effective_time_ns: UnixNanos
    posted_at_ns: UnixNanos
    ledger_sequence: int
    mapping_policy_version: int
    reverses_transaction_id: LedgerTransactionId | None = None

    def __post_init__(self) -> None:
        _validate_transaction_fields(
            transaction_id=self.transaction_id,
            source_fact_ids=self.source_fact_ids,
            postings=self.postings,
            effective_time_ns=self.effective_time_ns,
            mapping_policy_version=self.mapping_policy_version,
            reverses_transaction_id=self.reverses_transaction_id,
        )
        if self.posted_at_ns < 0:
            raise ValueError("posted_at_ns cannot be negative")
        if self.ledger_sequence <= 0:
            raise ValueError("ledger_sequence must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerBalance:
    account: LedgerAccount
    balance: Money


def validate_per_asset_balance(postings: tuple[LedgerPosting, ...]) -> None:
    totals: defaultdict[AssetId, Decimal] = defaultdict(Decimal)
    for posting in postings:
        totals[posting.asset] += posting.signed_amount.as_decimal()
    unbalanced = tuple(
        sorted(
            (str(asset), total)
            for asset, total in totals.items()
            if total != 0
        )
    )
    if unbalanced:
        raise ValueError(f"ledger transaction is not balanced per asset: {unbalanced}")


def _validate_transaction_fields(
    *,
    transaction_id: LedgerTransactionId,
    source_fact_ids: tuple[FinancialFactId, ...],
    postings: tuple[LedgerPosting, ...],
    effective_time_ns: UnixNanos,
    mapping_policy_version: int,
    reverses_transaction_id: LedgerTransactionId | None,
) -> None:
    _require_identifier(transaction_id, name="transaction_id")
    if not source_fact_ids or len(source_fact_ids) > MAX_LEDGER_SOURCE_FACTS:
        raise ValueError("source_fact_ids count is outside bounds")
    source_keys = tuple(str(item) for item in source_fact_ids)
    if source_keys != tuple(sorted(source_keys)) or len(set(source_keys)) != len(
        source_keys
    ):
        raise ValueError("source_fact_ids must be unique and sorted")
    if len(postings) < 2 or len(postings) > MAX_LEDGER_POSTINGS_PER_TRANSACTION:
        raise ValueError("ledger posting count is outside bounds")
    posting_ids = tuple(str(item.posting_id) for item in postings)
    if len(set(posting_ids)) != len(posting_ids):
        raise ValueError("ledger posting IDs must be unique")
    if effective_time_ns < 0:
        raise ValueError("effective_time_ns cannot be negative")
    if mapping_policy_version <= 0:
        raise ValueError("mapping_policy_version must be positive")
    if reverses_transaction_id is not None:
        _require_identifier(
            reverses_transaction_id,
            name="reverses_transaction_id",
        )
        if reverses_transaction_id == transaction_id:
            raise ValueError("transaction cannot reverse itself")
    validate_per_asset_balance(postings)


def _require_identifier(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")


__all__ = [
    "MAX_LEDGER_MEMO_LENGTH",
    "MAX_LEDGER_POSTINGS_PER_TRANSACTION",
    "MAX_LEDGER_SOURCE_FACTS",
    "LedgerAccount",
    "LedgerAccountType",
    "LedgerBalance",
    "LedgerPosting",
    "LedgerTransaction",
    "LedgerTransactionDraft",
    "LedgerTransactionType",
    "validate_per_asset_balance",
]
