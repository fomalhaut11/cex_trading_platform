"""Deterministic Accounting identity derivation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

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

from .model import LedgerAccountType, LedgerTransactionType


def deterministic_ledger_account_id(
    *,
    venue: VenueId,
    account_id: AccountId,
    account_type: LedgerAccountType,
    asset: AssetId,
) -> LedgerAccountId:
    return LedgerAccountId(
        "ledger-account-"
        + _digest(
            {
                "venue": str(venue),
                "account_id": str(account_id),
                "account_type": account_type.value,
                "asset": str(asset),
            }
        )
    )


def deterministic_ledger_transaction_id(
    *,
    source_fact_ids: tuple[FinancialFactId, ...],
    transaction_type: LedgerTransactionType,
    effective_time_ns: UnixNanos,
    mapping_policy_version: int,
    posting_specs: Sequence[tuple[LedgerAccountId, AssetId, Money, str]],
    reverses_transaction_id: LedgerTransactionId | None = None,
) -> LedgerTransactionId:
    return LedgerTransactionId(
        "ledger-transaction-"
        + _digest(
            {
                "source_fact_ids": [str(item) for item in source_fact_ids],
                "transaction_type": transaction_type.value,
                "effective_time_ns": int(effective_time_ns),
                "mapping_policy_version": mapping_policy_version,
                "postings": [
                    {
                        "ledger_account_id": str(account_id),
                        "asset": str(asset),
                        "raw": amount.raw,
                        "scale": amount.scale,
                        "memo": memo,
                    }
                    for account_id, asset, amount, memo in posting_specs
                ],
                "reverses_transaction_id": (
                    None
                    if reverses_transaction_id is None
                    else str(reverses_transaction_id)
                ),
            }
        )
    )


def deterministic_ledger_posting_id(
    transaction_id: LedgerTransactionId,
    index: int,
) -> LedgerPostingId:
    if index < 0:
        raise ValueError("posting index cannot be negative")
    value = {
        "transaction_id": str(transaction_id),
        "index": index,
    }
    return LedgerPostingId(
        f"ledger-posting-{_digest(value)}"
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "deterministic_ledger_account_id",
    "deterministic_ledger_posting_id",
    "deterministic_ledger_transaction_id",
]
