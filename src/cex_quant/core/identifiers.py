"""Strong identifiers shared by domain contracts."""

from typing import NewType

AccountId = NewType("AccountId", str)
AssetId = NewType("AssetId", str)
BasketLegId = NewType("BasketLegId", str)
ClientOrderId = NewType("ClientOrderId", str)
CorrelationId = NewType("CorrelationId", str)
EventId = NewType("EventId", str)
ExecutionPermitId = NewType("ExecutionPermitId", str)
ExecutionPlanId = NewType("ExecutionPlanId", str)
ExecutionStageId = NewType("ExecutionStageId", str)
ExecutionStagePermitId = NewType("ExecutionStagePermitId", str)
FeatureId = NewType("FeatureId", str)
FinancialFactId = NewType("FinancialFactId", str)
FinancialObservationId = NewType("FinancialObservationId", str)
FinancialReconciliationId = NewType("FinancialReconciliationId", str)
GroupActionId = NewType("GroupActionId", str)
IntentId = NewType("IntentId", str)
LedgerAccountId = NewType("LedgerAccountId", str)
LedgerPostingId = NewType("LedgerPostingId", str)
LedgerTransactionId = NewType("LedgerTransactionId", str)
MarginScopeId = NewType("MarginScopeId", str)
ObjectiveTypeId = NewType("ObjectiveTypeId", str)
OrderGroupId = NewType("OrderGroupId", str)
PortfolioApprovalId = NewType("PortfolioApprovalId", str)
PortfolioConfirmationId = NewType("PortfolioConfirmationId", str)
PortfolioReconciliationId = NewType("PortfolioReconciliationId", str)
PortfolioReservationId = NewType("PortfolioReservationId", str)
RecoveryAuthorizationId = NewType("RecoveryAuthorizationId", str)
RiskDirectiveId = NewType("RiskDirectiveId", str)
RiskFactorId = NewType("RiskFactorId", str)
PositionId = NewType("PositionId", str)
SpreadRiskId = NewType("SpreadRiskId", str)
StrategyId = NewType("StrategyId", str)
TradeId = NewType("TradeId", str)
AttributionAllocationId = NewType("AttributionAllocationId", str)
VenueId = NewType("VenueId", str)
VenueOrderId = NewType("VenueOrderId", str)

__all__ = [
    "AccountId",
    "AssetId",
    "AttributionAllocationId",
    "BasketLegId",
    "ClientOrderId",
    "CorrelationId",
    "EventId",
    "ExecutionPermitId",
    "ExecutionPlanId",
    "ExecutionStageId",
    "ExecutionStagePermitId",
    "FeatureId",
    "FinancialFactId",
    "FinancialObservationId",
    "FinancialReconciliationId",
    "GroupActionId",
    "IntentId",
    "LedgerAccountId",
    "LedgerPostingId",
    "LedgerTransactionId",
    "MarginScopeId",
    "ObjectiveTypeId",
    "OrderGroupId",
    "PortfolioApprovalId",
    "PortfolioConfirmationId",
    "PortfolioReconciliationId",
    "PortfolioReservationId",
    "PositionId",
    "RecoveryAuthorizationId",
    "RiskDirectiveId",
    "RiskFactorId",
    "SpreadRiskId",
    "StrategyId",
    "TradeId",
    "VenueId",
    "VenueOrderId",
]
