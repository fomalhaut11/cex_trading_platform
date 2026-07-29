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
FeatureId = NewType("FeatureId", str)
GroupActionId = NewType("GroupActionId", str)
IntentId = NewType("IntentId", str)
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
VenueId = NewType("VenueId", str)
VenueOrderId = NewType("VenueOrderId", str)

__all__ = [
    "AccountId",
    "AssetId",
    "BasketLegId",
    "ClientOrderId",
    "CorrelationId",
    "EventId",
    "ExecutionPermitId",
    "ExecutionPlanId",
    "FeatureId",
    "GroupActionId",
    "IntentId",
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
