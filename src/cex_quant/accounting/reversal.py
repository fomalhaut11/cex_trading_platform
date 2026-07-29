"""Deterministic compensating transactions for immutable ledger history."""

from __future__ import annotations

from cex_quant.core import FinancialFactId, Money, UnixNanos

from .identifiers import (
    deterministic_ledger_posting_id,
    deterministic_ledger_transaction_id,
)
from .model import (
    LedgerPosting,
    LedgerTransaction,
    LedgerTransactionDraft,
    LedgerTransactionType,
)


def create_reversal_draft(
    original: LedgerTransaction,
    *,
    correction_fact_id: FinancialFactId,
    effective_time_ns: UnixNanos,
    mapping_policy_version: int,
) -> LedgerTransactionDraft:
    """Create an exact economic inverse without mutating the original entry."""

    if original.transaction_type is LedgerTransactionType.REVERSAL:
        raise ValueError("a reversal transaction cannot itself be reversed")
    source_fact_ids = (correction_fact_id,)
    posting_specs = tuple(
        (
            posting.account.ledger_account_id,
            posting.asset,
            Money(
                raw=-posting.signed_amount.raw,
                scale=posting.signed_amount.scale,
            ),
            f"reversal:{original.transaction_id}",
        )
        for posting in original.postings
    )
    transaction_id = deterministic_ledger_transaction_id(
        source_fact_ids=source_fact_ids,
        transaction_type=LedgerTransactionType.REVERSAL,
        effective_time_ns=effective_time_ns,
        mapping_policy_version=mapping_policy_version,
        posting_specs=posting_specs,
        reverses_transaction_id=original.transaction_id,
    )
    postings = tuple(
        LedgerPosting(
            posting_id=deterministic_ledger_posting_id(
                transaction_id,
                index,
            ),
            account=original_posting.account,
            signed_amount=amount,
            memo=memo,
        )
        for index, (original_posting, (_, _, amount, memo)) in enumerate(
            zip(original.postings, posting_specs, strict=True)
        )
    )
    return LedgerTransactionDraft(
        transaction_id=transaction_id,
        source_fact_ids=source_fact_ids,
        transaction_type=LedgerTransactionType.REVERSAL,
        postings=postings,
        effective_time_ns=effective_time_ns,
        mapping_policy_version=mapping_policy_version,
        reverses_transaction_id=original.transaction_id,
    )


__all__ = ["create_reversal_draft"]
