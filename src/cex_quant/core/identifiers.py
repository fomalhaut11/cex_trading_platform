"""Strong identifiers shared by domain contracts."""

from typing import NewType

AccountId = NewType("AccountId", str)
AssetId = NewType("AssetId", str)
BasketLegId = NewType("BasketLegId", str)
ClientOrderId = NewType("ClientOrderId", str)
CorrelationId = NewType("CorrelationId", str)
EventId = NewType("EventId", str)
FeatureId = NewType("FeatureId", str)
IntentId = NewType("IntentId", str)
ObjectiveTypeId = NewType("ObjectiveTypeId", str)
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
    "FeatureId",
    "IntentId",
    "ObjectiveTypeId",
    "PositionId",
    "StrategyId",
    "TradeId",
    "VenueId",
    "VenueOrderId",
]
