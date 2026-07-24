"""Immutable inputs, contexts and decision intents for strategies."""

from dataclasses import dataclass
from typing import TypeAlias

from cex_quant.core import IntentId, Quantity, StrategyId, UnixNanos
from cex_quant.features import FeatureSnapshot
from cex_quant.instruments import InstrumentId
from cex_quant.market_data import (
    AggregateTrade,
    BestBidAsk,
    FundingRateUpdate,
    IndexPriceUpdate,
    KlineUpdate,
    MarketTrade,
    MarkPriceUpdate,
    OpenInterestUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)

CanonicalMarketEvent: TypeAlias = (
    AggregateTrade
    | BestBidAsk
    | FundingRateUpdate
    | IndexPriceUpdate
    | KlineUpdate
    | MarketTrade
    | MarkPriceUpdate
    | OpenInterestUpdate
    | OrderBookDelta
    | PartialBookFrame
    | VenueOptionAnalyticsUpdate
)
StrategyInput: TypeAlias = CanonicalMarketEvent | FeatureSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyContext:
    """One deterministically numbered input delivered to a strategy."""

    strategy_id: StrategyId
    input_scope: str
    input_sequence: int
    input: StrategyInput

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id cannot be empty")
        if not self.input_scope or self.input_scope.strip() != self.input_scope:
            raise ValueError("input_scope must be non-empty and trimmed")
        if self.input_sequence < 1:
            raise ValueError("input_sequence must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionTargetIntent:
    """A desired signed position for risk to assess and OMS to realize.

    This is a decision, not an order. It deliberately contains no venue,
    order type, time-in-force or exchange identifier.
    """

    intent_id: IntentId
    strategy_id: StrategyId
    instrument_id: InstrumentId
    target_quantity: Quantity
    decision_time_ns: UnixNanos
    valid_until_ns: UnixNanos | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.intent_id:
            raise ValueError("intent_id cannot be empty")
        if not self.strategy_id:
            raise ValueError("strategy_id cannot be empty")
        if (
            self.valid_until_ns is not None
            and self.valid_until_ns < self.decision_time_ns
        ):
            raise ValueError("valid_until_ns cannot precede decision_time_ns")


DecisionIntent: TypeAlias = PositionTargetIntent


__all__ = [
    "CanonicalMarketEvent",
    "DecisionIntent",
    "PositionTargetIntent",
    "StrategyContext",
    "StrategyInput",
]
