"""Financial facts, ledger, reconciliation and attribution interfaces.

Accounting owns immutable financial evidence and derived reporting views. It
does not own execution, Portfolio state, Risk authorization, or applications.
Only accepted public contracts are exported here; venue parsers and mutable
implementation internals remain in their defining modules.
"""

from cex_quant.core import (
    AttributionAllocationId,
    FinancialFactId,
    FinancialObservationId,
    FinancialReconciliationId,
    LedgerAccountId,
    LedgerPostingId,
    LedgerTransactionId,
)

from .allocation import (
    UNALLOCATED_OWNER,
    AttributionAllocation,
)
from .attribution import (
    AttributionCompleteness,
    PnlAttributionView,
    PnlComponent,
    PnlComponentType,
    build_pnl_attribution,
)
from .facts import (
    MAX_FINANCIAL_COMPONENTS,
    MAX_FINANCIAL_REFERENCE_LENGTH,
    MAX_SOURCE_CURSOR_LENGTH,
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    ExecutionFillFact,
    FillSide,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceFact,
    FinancialSourceKind,
    ObservedFinancialFact,
)
from .ledger import (
    AccountingLedgerView,
    LedgerIngestDisposition,
    LedgerIngestResult,
)
from .mapping import (
    MAX_MAPPING_INSTRUMENTS,
    FinancialMappingError,
    LedgerMappingPolicy,
    UnsupportedFinancialMappingError,
    map_financial_fact,
)
from .model import (
    MAX_LEDGER_MEMO_LENGTH,
    MAX_LEDGER_POSTINGS_PER_TRANSACTION,
    MAX_LEDGER_SOURCE_FACTS,
    LedgerAccount,
    LedgerAccountType,
    LedgerBalance,
    LedgerPosting,
    LedgerTransaction,
    LedgerTransactionDraft,
    LedgerTransactionType,
    validate_per_asset_balance,
)
from .ownership import (
    MAX_OWNER_ID_LENGTH,
    EconomicOwnerRef,
    EconomicOwnerTypeRef,
)
from .reconciliation import (
    AuthoritativeBalance,
    BalanceReconciliationProof,
    ReconciliationState,
    SourceCompletenessProof,
    reconcile_balance,
)
from .valuation import (
    ConversionQuoteConvention,
    ConversionRateEvidence,
    ConversionTimeBasis,
    PositionValuation,
    PositionValueInput,
    ValuationCompleteness,
    ValuationPolicyRef,
    ValuationRoundingMode,
    ValuationSnapshot,
    ValuedAmount,
    build_valuation_snapshot,
    value_amount,
)

__all__ = [
    "MAX_FINANCIAL_COMPONENTS",
    "MAX_FINANCIAL_REFERENCE_LENGTH",
    "MAX_LEDGER_MEMO_LENGTH",
    "MAX_LEDGER_POSTINGS_PER_TRANSACTION",
    "MAX_LEDGER_SOURCE_FACTS",
    "MAX_MAPPING_INSTRUMENTS",
    "MAX_OWNER_ID_LENGTH",
    "MAX_SOURCE_CURSOR_LENGTH",
    "UNALLOCATED_OWNER",
    "AccountCashFlowFact",
    "AccountCashFlowType",
    "AccountingLedgerView",
    "AttributionAllocation",
    "AttributionAllocationId",
    "AttributionCompleteness",
    "AuthoritativeBalance",
    "BalanceReconciliationProof",
    "CashComponent",
    "ConversionQuoteConvention",
    "ConversionRateEvidence",
    "ConversionTimeBasis",
    "EconomicOwnerRef",
    "EconomicOwnerTypeRef",
    "ExecutionFillFact",
    "FillSide",
    "FinancialFactId",
    "FinancialFactMetadata",
    "FinancialFactObservation",
    "FinancialMappingError",
    "FinancialObservationId",
    "FinancialReconciliationId",
    "FinancialSourceFact",
    "FinancialSourceKind",
    "LedgerAccount",
    "LedgerAccountId",
    "LedgerAccountType",
    "LedgerBalance",
    "LedgerIngestDisposition",
    "LedgerIngestResult",
    "LedgerMappingPolicy",
    "LedgerPosting",
    "LedgerPostingId",
    "LedgerTransaction",
    "LedgerTransactionDraft",
    "LedgerTransactionId",
    "LedgerTransactionType",
    "ObservedFinancialFact",
    "PnlAttributionView",
    "PnlComponent",
    "PnlComponentType",
    "PositionValuation",
    "PositionValueInput",
    "ReconciliationState",
    "SourceCompletenessProof",
    "UnsupportedFinancialMappingError",
    "ValuationCompleteness",
    "ValuationPolicyRef",
    "ValuationRoundingMode",
    "ValuationSnapshot",
    "ValuedAmount",
    "build_pnl_attribution",
    "build_valuation_snapshot",
    "map_financial_fact",
    "reconcile_balance",
    "validate_per_asset_balance",
    "value_amount",
]
