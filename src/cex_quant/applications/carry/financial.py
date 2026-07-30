"""Pure projection of ADR-013 evidence into Carry financial readiness."""

from cex_quant.accounting import (
    AccountingLedgerView,
    AttributionCompleteness,
    BalanceReconciliationProof,
    PnlAttributionView,
    ReconciliationState,
    SourceCompletenessProof,
)
from cex_quant.core import AttributionAllocationId

from .model import CarryFinancialState


def assess_carry_financial_state(
    *,
    attribution: PnlAttributionView | None,
    source_proofs: tuple[SourceCompletenessProof, ...],
    balance_proofs: tuple[BalanceReconciliationProof, ...],
    allocation_ids: tuple[AttributionAllocationId, ...],
    ledger: AccountingLedgerView,
) -> CarryFinancialState:
    """Consume Accounting truth without constructing or changing it."""

    if not ledger.healthy or attribution is None:
        return CarryFinancialState.NOT_READY
    if attribution.ledger_sequence != ledger.ledger_sequence:
        return CarryFinancialState.PROVISIONAL
    if (
        not source_proofs
        or not balance_proofs
        or not allocation_ids
        or len(set(allocation_ids)) != len(allocation_ids)
    ):
        return CarryFinancialState.PROVISIONAL
    if any(
        item.state is not ReconciliationState.MATCHED
        for item in source_proofs
    ):
        return CarryFinancialState.PROVISIONAL
    if any(
        item.state is not ReconciliationState.MATCHED
        for item in balance_proofs
    ):
        return CarryFinancialState.PROVISIONAL
    if attribution.completeness is not AttributionCompleteness.COMPLETE:
        return CarryFinancialState.PROVISIONAL
    return CarryFinancialState.RECONCILED


__all__ = ["assess_carry_financial_state"]
