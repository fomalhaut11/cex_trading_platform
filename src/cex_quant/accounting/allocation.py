"""Append-only ownership allocation over immutable ledger postings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from cex_quant.core import (
    AssetId,
    AttributionAllocationId,
    LedgerPostingId,
    LedgerTransactionId,
    Money,
)

from .ledger import AccountingLedgerView
from .model import LedgerPosting, LedgerTransaction
from .ownership import EconomicOwnerRef, EconomicOwnerTypeRef

UNALLOCATED_OWNER = EconomicOwnerRef(
    owner_type=EconomicOwnerTypeRef(name="unallocated", version=1),
    owner_id="unallocated",
)


class AllocationError(ValueError):
    pass


class AllocationIdentityConflictError(AllocationError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributionAllocation:
    allocation_id: AttributionAllocationId
    transaction_id: LedgerTransactionId
    posting_id: LedgerPostingId
    owner: EconomicOwnerRef
    signed_amount: Money
    asset: AssetId
    policy_version: int
    evidence_ids: tuple[str, ...]
    reverses_allocation_id: AttributionAllocationId | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("allocation_id", self.allocation_id),
            ("transaction_id", self.transaction_id),
            ("posting_id", self.posting_id),
            ("asset", self.asset),
        ):
            _require_identifier(value, name)
        if self.signed_amount.raw == 0:
            raise ValueError("allocation amount cannot be zero")
        if self.policy_version <= 0:
            raise ValueError("allocation policy_version must be positive")
        if not self.evidence_ids:
            raise ValueError("allocation requires ownership evidence")
        if self.evidence_ids != tuple(sorted(self.evidence_ids)):
            raise ValueError("allocation evidence_ids must be sorted")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("allocation evidence_ids must be unique")
        for item in self.evidence_ids:
            _require_identifier(item, "evidence_id")
        if self.reverses_allocation_id is not None:
            _require_identifier(
                self.reverses_allocation_id,
                "reverses_allocation_id",
            )
            if self.reverses_allocation_id == self.allocation_id:
                raise ValueError("allocation cannot reverse itself")


def create_allocation(
    *,
    transaction_id: LedgerTransactionId,
    posting_id: LedgerPostingId,
    owner: EconomicOwnerRef,
    signed_amount: Money,
    asset: AssetId,
    policy_version: int,
    evidence_ids: tuple[str, ...],
    reverses_allocation_id: AttributionAllocationId | None = None,
) -> AttributionAllocation:
    canonical_evidence = tuple(sorted(evidence_ids))
    payload = {
        "transaction_id": str(transaction_id),
        "posting_id": str(posting_id),
        "owner": owner.canonical,
        "amount_raw": signed_amount.raw,
        "amount_scale": signed_amount.scale,
        "asset": str(asset),
        "policy_version": policy_version,
        "evidence_ids": list(canonical_evidence),
        "reverses_allocation_id": (
            None
            if reverses_allocation_id is None
            else str(reverses_allocation_id)
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return AttributionAllocation(
        allocation_id=AttributionAllocationId(
            "allocation-" + hashlib.sha256(encoded).hexdigest()
        ),
        transaction_id=transaction_id,
        posting_id=posting_id,
        owner=owner,
        signed_amount=signed_amount,
        asset=asset,
        policy_version=policy_version,
        evidence_ids=canonical_evidence,
        reverses_allocation_id=reverses_allocation_id,
    )


class AllocationBook:
    """Validate allocations without changing Accounting financial totals."""

    def __init__(
        self,
        ledger: AccountingLedgerView,
        *,
        records: tuple[AttributionAllocation, ...] = (),
    ) -> None:
        self._ledger_sequence = ledger.ledger_sequence
        self._postings: dict[
            LedgerPostingId,
            tuple[LedgerTransaction, LedgerPosting],
        ] = {
            posting.posting_id: (transaction, posting)
            for transaction in ledger.transactions
            for posting in transaction.postings
        }
        self._records: dict[
            AttributionAllocationId,
            AttributionAllocation,
        ] = {}
        self._record_order: list[AttributionAllocationId] = []
        self._posting_records: dict[
            LedgerPostingId,
            list[AttributionAllocationId],
        ] = {}
        self._reversals: dict[
            AttributionAllocationId,
            AttributionAllocationId,
        ] = {}
        for record in records:
            self.append(record)

    @property
    def ledger_sequence(self) -> int:
        return self._ledger_sequence

    @property
    def records(self) -> tuple[AttributionAllocation, ...]:
        return tuple(self._records[item] for item in self._record_order)

    def append(self, allocation: AttributionAllocation) -> bool:
        prior = self._records.get(allocation.allocation_id)
        if prior is not None:
            if prior != allocation:
                raise AllocationIdentityConflictError(
                    "same allocation identity has changed content"
                )
            return False
        try:
            transaction, posting = self._postings[allocation.posting_id]
        except KeyError:
            raise AllocationError(
                f"unknown ledger posting: {allocation.posting_id}"
            ) from None
        if transaction.transaction_id != allocation.transaction_id:
            raise AllocationError(
                "allocation transaction does not own the posting"
            )
        if posting.asset != allocation.asset:
            raise AllocationError("allocation asset differs from posting")
        if allocation.owner == UNALLOCATED_OWNER:
            raise AllocationError(
                "UNALLOCATED is a remainder, not ownership evidence"
            )
        self._validate_reversal(allocation)
        self._validate_posting_total(posting, allocation)
        self._records[allocation.allocation_id] = allocation
        self._record_order.append(allocation.allocation_id)
        self._posting_records.setdefault(allocation.posting_id, []).append(
            allocation.allocation_id
        )
        if allocation.reverses_allocation_id is not None:
            self._reversals[
                allocation.reverses_allocation_id
            ] = allocation.allocation_id
        return True

    def records_for_owner(
        self,
        owner: EconomicOwnerRef,
    ) -> tuple[AttributionAllocation, ...]:
        return tuple(item for item in self.records if item.owner == owner)

    def unallocated(self, posting_id: LedgerPostingId) -> Money:
        try:
            _, posting = self._postings[posting_id]
        except KeyError:
            raise KeyError(f"unknown ledger posting: {posting_id}") from None
        total = Money(raw=0, scale=posting.signed_amount.scale)
        for allocation_id in self._posting_records.get(posting_id, ()):
            total = _add_money(
                total,
                self._records[allocation_id].signed_amount,
            )
        return _subtract_money(posting.signed_amount, total)

    def _validate_reversal(
        self,
        allocation: AttributionAllocation,
    ) -> None:
        reversed_id = allocation.reverses_allocation_id
        if reversed_id is None:
            return
        original = self._records.get(reversed_id)
        if original is None:
            raise AllocationError(
                "allocation reversal precedes or references unknown evidence"
            )
        if reversed_id in self._reversals:
            raise AllocationError("allocation was reversed more than once")
        if (
            original.transaction_id,
            original.posting_id,
            original.owner,
            original.asset,
        ) != (
            allocation.transaction_id,
            allocation.posting_id,
            allocation.owner,
            allocation.asset,
        ):
            raise AllocationError(
                "allocation reversal scope differs from original"
            )
        if allocation.signed_amount != Money(
            raw=-original.signed_amount.raw,
            scale=original.signed_amount.scale,
        ):
            raise AllocationError(
                "allocation reversal is not the exact economic inverse"
            )
        if allocation.policy_version < original.policy_version:
            raise AllocationError(
                "allocation reversal cannot use an older policy"
            )

    def _validate_posting_total(
        self,
        posting: LedgerPosting,
        allocation: AttributionAllocation,
    ) -> None:
        total = allocation.signed_amount
        for allocation_id in self._posting_records.get(posting.posting_id, ()):
            total = _add_money(
                total,
                self._records[allocation_id].signed_amount,
            )
        normalized_posting, normalized_total = _normalize_money(
            posting.signed_amount,
            total,
        )
        if normalized_total.raw == 0:
            return
        if (normalized_total.raw > 0) != (normalized_posting.raw > 0):
            raise AllocationError(
                "allocation total has opposite sign to ledger posting"
            )
        if abs(normalized_total.raw) > abs(normalized_posting.raw):
            raise AllocationError("allocation total exceeds ledger posting")


def _normalize_money(first: Money, second: Money) -> tuple[Money, Money]:
    scale = max(first.scale, second.scale)
    return (
        first.rescale_exact(scale),
        second.rescale_exact(scale),
    )


def _add_money(first: Money, second: Money) -> Money:
    normalized_first, normalized_second = _normalize_money(first, second)
    return Money(
        raw=normalized_first.raw + normalized_second.raw,
        scale=normalized_first.scale,
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
    "UNALLOCATED_OWNER",
    "AllocationBook",
    "AllocationError",
    "AllocationIdentityConflictError",
    "AttributionAllocation",
    "create_allocation",
]
