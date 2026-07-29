"""Source-coverage and account-balance reconciliation proofs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    FinancialReconciliationId,
    Money,
    UnixNanos,
    VenueId,
)

from .facts import FinancialSourceKind
from .ledger import AccountingLedgerView
from .model import LedgerAccountType


class ReconciliationState(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MATCHED = "matched"
    INCOMPLETE = "incomplete"
    MISMATCH = "mismatch"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceCompletenessProof:
    reconciliation_id: FinancialReconciliationId
    venue: VenueId
    account_id: AccountId
    source_kind: FinancialSourceKind
    window_start_ns: UnixNanos
    window_end_ns: UnixNanos
    fact_ids: tuple[FinancialFactId, ...]
    start_cursor: str | None
    end_cursor: str | None
    exhausted: bool
    issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.reconciliation_id, "reconciliation_id")
        _require_identifier(self.venue, "venue")
        _require_identifier(self.account_id, "account_id")
        if self.window_start_ns < 0:
            raise ValueError("window_start_ns cannot be negative")
        if self.window_end_ns <= self.window_start_ns:
            raise ValueError("window_end_ns must follow window_start_ns")
        keys = tuple(str(item) for item in self.fact_ids)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("fact_ids must be unique and sorted")
        for name, cursor in (
            ("start_cursor", self.start_cursor),
            ("end_cursor", self.end_cursor),
        ):
            if cursor is not None and (
                not cursor or cursor != cursor.strip()
            ):
                raise ValueError(f"{name} must be non-empty and trimmed")
        if any(not item or item != item.strip() for item in self.issues):
            raise ValueError("source completeness issues must be trimmed")

    @property
    def state(self) -> ReconciliationState:
        if self.issues or not self.exhausted:
            return ReconciliationState.INCOMPLETE
        return ReconciliationState.MATCHED


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthoritativeBalance:
    venue: VenueId
    account_id: AccountId
    asset: AssetId
    amount: Money
    as_of_ns: UnixNanos
    evidence_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.venue, "venue")
        _require_identifier(self.account_id, "account_id")
        _require_identifier(self.asset, "asset")
        _require_identifier(self.evidence_id, "evidence_id")
        if self.as_of_ns < 0:
            raise ValueError("balance as_of_ns cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class BalanceReconciliationProof:
    reconciliation_id: FinancialReconciliationId
    opening: AuthoritativeBalance
    closing: AuthoritativeBalance
    source_completeness: SourceCompletenessProof
    accepted_movement: Money
    expected_closing: Money
    difference: Money
    ledger_sequence: int
    state: ReconciliationState

    def __post_init__(self) -> None:
        if self.ledger_sequence < 0:
            raise ValueError("ledger_sequence cannot be negative")
        if self.state not in (
            ReconciliationState.MATCHED,
            ReconciliationState.INCOMPLETE,
            ReconciliationState.MISMATCH,
        ):
            raise ValueError("balance proof has unsupported terminal state")


def reconcile_balance(
    ledger: AccountingLedgerView,
    *,
    reconciliation_id: FinancialReconciliationId,
    opening: AuthoritativeBalance,
    closing: AuthoritativeBalance,
    source_completeness: SourceCompletenessProof,
    account_types: tuple[LedgerAccountType, ...] = (
        LedgerAccountType.VENUE_CASH,
        LedgerAccountType.VENUE_INVENTORY,
    ),
) -> BalanceReconciliationProof:
    """Prove opening plus accepted movements against a closing snapshot."""

    _validate_scope(
        reconciliation_id=reconciliation_id,
        opening=opening,
        closing=closing,
        completeness=source_completeness,
    )
    movement = Money(raw=0, scale=opening.amount.scale)
    for transaction in ledger.transactions:
        if not (
            source_completeness.window_start_ns
            <= transaction.effective_time_ns
            < source_completeness.window_end_ns
        ):
            continue
        for posting in transaction.postings:
            account = posting.account
            if (
                account.venue == opening.venue
                and account.account_id == opening.account_id
                and account.asset == opening.asset
                and account.account_type in account_types
            ):
                movement = _add_money(movement, posting.signed_amount)
    expected = _add_money(opening.amount, movement)
    difference = _subtract_money(closing.amount, expected)
    if source_completeness.state is not ReconciliationState.MATCHED:
        state = ReconciliationState.INCOMPLETE
    elif difference.raw == 0:
        state = ReconciliationState.MATCHED
    else:
        state = ReconciliationState.MISMATCH
    return BalanceReconciliationProof(
        reconciliation_id=reconciliation_id,
        opening=opening,
        closing=closing,
        source_completeness=source_completeness,
        accepted_movement=movement,
        expected_closing=expected,
        difference=difference,
        ledger_sequence=ledger.ledger_sequence,
        state=state,
    )


def _validate_scope(
    *,
    reconciliation_id: FinancialReconciliationId,
    opening: AuthoritativeBalance,
    closing: AuthoritativeBalance,
    completeness: SourceCompletenessProof,
) -> None:
    if reconciliation_id != completeness.reconciliation_id:
        raise ValueError("source and balance reconciliation IDs differ")
    if (opening.venue, opening.account_id) != (
        completeness.venue,
        completeness.account_id,
    ):
        raise ValueError("source completeness scope differs from balance scope")
    if (
        opening.venue,
        opening.account_id,
        opening.asset,
    ) != (
        closing.venue,
        closing.account_id,
        closing.asset,
    ):
        raise ValueError("opening and closing balance scopes differ")
    if opening.as_of_ns != completeness.window_start_ns:
        raise ValueError("opening balance does not anchor window start")
    if closing.as_of_ns != completeness.window_end_ns:
        raise ValueError("closing balance does not anchor window end")


def _add_money(first: Money, second: Money) -> Money:
    scale = max(first.scale, second.scale)
    return Money(
        raw=(
            first.raw * 10 ** (scale - first.scale)
            + second.raw * 10 ** (scale - second.scale)
        ),
        scale=scale,
    )


def _subtract_money(first: Money, second: Money) -> Money:
    return _add_money(
        first,
        Money(raw=-second.raw, scale=second.scale),
    )


def _require_identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")


__all__ = [
    "AuthoritativeBalance",
    "BalanceReconciliationProof",
    "ReconciliationState",
    "SourceCompletenessProof",
    "reconcile_balance",
]
