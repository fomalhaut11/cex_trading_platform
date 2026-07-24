"""Feature-engine adapter for the synchronous pipeline port."""

from cex_quant.features import FeatureSnapshot, OnlineFeatureEngine
from cex_quant.market_data import MarketEvent


class FeatureEngineAdapter:
    """Update the engine, then expose its immutable point-in-time snapshot."""

    def __init__(self, engine: OnlineFeatureEngine) -> None:
        self._engine = engine

    def on_event(self, event: MarketEvent) -> FeatureSnapshot:
        self._engine.on_event(event)
        return self._engine.snapshot()


__all__ = ["FeatureEngineAdapter"]
