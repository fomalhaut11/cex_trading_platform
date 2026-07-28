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
ObjectiveTypeId = NewType("ObjectiveTypeId", str)
OrderGroupId = NewType("OrderGroupId", str)
PortfolioApprovalId = NewType("PortfolioApprovalId", str)
PositionId = NewType("PositionId", str)
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
    "ObjectiveTypeId",
    "OrderGroupId",
    "PortfolioApprovalId",
    "PositionId",
    "StrategyId",
    "TradeId",
    "VenueId",
    "VenueOrderId",
]
