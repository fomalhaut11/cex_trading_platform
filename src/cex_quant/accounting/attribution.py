"""Generic PnL projection from allocated ledger facts and valuation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AssetId,
    AttributionAllocationId,
    LedgerPostingId,
    LedgerTransactionId,
    Money,
    UnixNanos,
)
from cex_quant.snapshots import DecisionSnapshotId

from .allocation import AllocationBook
from .ledger import AccountingLedgerView
from .model import LedgerAccountType
from .ownership import EconomicOwnerRef
from .valuation import (
    ConversionRateEvidence,
    ValuationCompleteness,
    ValuationPolicyRef,
    value_amount,
)


class PnlComponentType(StrEnum):
    FUNDING = "funding"
    REALIZED_TRADING = "realized_trading"
    COMMISSION = "commission"
    REBATE = "rebate"
    BORROW_INTEREST = "borrow_interest"
    LIQUIDATION = "liquidation"


class AttributionCompleteness(StrEnum):
    COMPLETE = "complete"
    REALIZED_ONLY = "realized_only"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True, kw_only=True)
class PnlComponent:
    component_type: PnlComponentType
    transaction_id: LedgerTransactionId
    posting_id: LedgerPostingId
    allocation_id: AttributionAllocationId
    original_asset: AssetId
    original_amount: Money
    reporting_amount: Money | None
    conversion_evidence: tuple[ConversionRateEvidence, ...]
    completeness: ValuationCompleteness


@dataclass(frozen=True, slots=True, kw_only=True)
class PnlAttributionView:
    owner: EconomicOwnerRef
    interval_start_ns: UnixNanos
    interval_end_ns: UnixNanos
    reporting_asset: AssetId
    components: tuple[PnlComponent, ...]
    realized_net_pnl: Money | None
    unrealized_change: Money | None
    total_marked_pnl: Money | None
    ledger_sequence: int
    valuation_snapshot_ids: tuple[DecisionSnapshotId, ...]
    completeness: AttributionCompleteness
    issues: tuple[str, ...]


_PNL_ACCOUNT_COMPONENTS: dict[LedgerAccountType, PnlComponentType] = {
    LedgerAccountType.FUNDING_INCOME: PnlComponentType.FUNDING,
    LedgerAccountType.REALIZED_PNL: PnlComponentType.REALIZED_TRADING,
    LedgerAccountType.COMMISSION_EXPENSE: PnlComponentType.COMMISSION,
    LedgerAccountType.REBATE_INCOME: PnlComponentType.REBATE,
    LedgerAccountType.BORROW_INTEREST_EXPENSE: (
        PnlComponentType.BORROW_INTEREST
    ),
    LedgerAccountType.LIQUIDATION_EXPENSE: PnlComponentType.LIQUIDATION,
}


def build_pnl_attribution(
    *,
    owner: EconomicOwnerRef,
    interval_start_ns: UnixNanos,
    interval_end_ns: UnixNanos,
    ledger: AccountingLedgerView,
    allocations: AllocationBook,
    valuation_snapshot_id: DecisionSnapshotId,
    valuation_reference_ns: UnixNanos,
    valuation_policy: ValuationPolicyRef,
    conversion_evidence: tuple[ConversionRateEvidence, ...],
    ledger_complete: bool,
    ownership_complete: bool,
    unrealized_change: Money | None = None,
    valuation_snapshot_ids: tuple[DecisionSnapshotId, ...] = (),
) -> PnlAttributionView:
    """Build a read-only owner view without changing ledger truth."""

    if interval_start_ns < 0 or interval_end_ns <= interval_start_ns:
        raise ValueError("PnL attribution interval is invalid")
    if allocations.ledger_sequence != ledger.ledger_sequence:
        raise ValueError("allocation book and ledger sequence differ")
    transaction_by_id = {
        item.transaction_id: item for item in ledger.transactions
    }
    posting_by_id = {
        posting.posting_id: posting
        for transaction in ledger.transactions
        for posting in transaction.postings
    }
    components: list[PnlComponent] = []
    conversion_complete = True
    total = Money(raw=0, scale=valuation_policy.output_scale)
    for allocation in allocations.records_for_owner(owner):
        transaction = transaction_by_id[allocation.transaction_id]
        if not (
            interval_start_ns
            <= transaction.effective_time_ns
            < interval_end_ns
        ):
            continue
        posting = posting_by_id[allocation.posting_id]
        component_type = _PNL_ACCOUNT_COMPONENTS.get(
            posting.account.account_type
        )
        if component_type is None:
            continue
        economic_amount = Money(
            raw=-allocation.signed_amount.raw,
            scale=allocation.signed_amount.scale,
        )
        valued = value_amount(
            original_asset=allocation.asset,
            original_amount=economic_amount,
            valuation_snapshot_id=valuation_snapshot_id,
            reference_time_ns=valuation_reference_ns,
            policy=valuation_policy,
            evidence=conversion_evidence,
        )
        if valued.reporting_amount is None:
            conversion_complete = False
        else:
            total = _add_money(total, valued.reporting_amount)
        components.append(
            PnlComponent(
                component_type=component_type,
                transaction_id=allocation.transaction_id,
                posting_id=allocation.posting_id,
                allocation_id=allocation.allocation_id,
                original_asset=allocation.asset,
                original_amount=economic_amount,
                reporting_amount=valued.reporting_amount,
                conversion_evidence=valued.evidence,
                completeness=valued.completeness,
            )
        )
    issues: list[str] = []
    if not ledger_complete:
        issues.append("ledger evidence is incomplete")
    if not ownership_complete:
        issues.append("ownership evidence is incomplete")
    if not conversion_complete:
        issues.append("valuation evidence is incomplete")
    evidence_complete = not issues
    realized = total if evidence_complete else None
    if unrealized_change is not None:
        unrealized_change = unrealized_change.rescale_exact(
            max(unrealized_change.scale, valuation_policy.output_scale)
        )
    marked = (
        _add_money(realized, unrealized_change)
        if realized is not None and unrealized_change is not None
        else None
    )
    if not evidence_complete:
        completeness = AttributionCompleteness.INCOMPLETE
    elif unrealized_change is None:
        completeness = AttributionCompleteness.REALIZED_ONLY
    else:
        completeness = AttributionCompleteness.COMPLETE
    snapshot_ids = tuple(sorted(set(valuation_snapshot_ids), key=str))
    return PnlAttributionView(
        owner=owner,
        interval_start_ns=interval_start_ns,
        interval_end_ns=interval_end_ns,
        reporting_asset=valuation_policy.reporting_asset,
        components=tuple(components),
        realized_net_pnl=realized,
        unrealized_change=unrealized_change,
        total_marked_pnl=marked,
        ledger_sequence=ledger.ledger_sequence,
        valuation_snapshot_ids=snapshot_ids,
        completeness=completeness,
        issues=tuple(issues),
    )


def _add_money(first: Money, second: Money) -> Money:
    scale = max(first.scale, second.scale)
    return Money(
        raw=(
            first.raw * 10 ** (scale - first.scale)
            + second.raw * 10 ** (scale - second.scale)
        ),
        scale=scale,
    )


__all__ = [
    "AttributionCompleteness",
    "PnlAttributionView",
    "PnlComponent",
    "PnlComponentType",
    "build_pnl_attribution",
]
