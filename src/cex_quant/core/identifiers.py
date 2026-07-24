"""Strong identifiers shared by domain contracts."""

from typing import NewType

AccountId = NewType("AccountId", str)
AssetId = NewType("AssetId", str)
ClientOrderId = NewType("ClientOrderId", str)
CorrelationId = NewType("CorrelationId", str)
EventId = NewType("EventId", str)
FeatureId = NewType("FeatureId", str)
IntentId = NewType("IntentId", str)
PositionId = NewType("PositionId", str)
StrategyId = NewType("StrategyId", str)
TradeId = NewType("TradeId", str)
VenueId = NewType("VenueId", str)
VenueOrderId = NewType("VenueOrderId", str)

__all__ = [
    "AccountId",
    "AssetId",
    "ClientOrderId",
    "CorrelationId",
    "EventId",
    "FeatureId",
    "IntentId",
    "PositionId",
    "StrategyId",
    "TradeId",
    "VenueId",
    "VenueOrderId",
]

