"""Immutable contracts for deterministic pre-trade risk assessment."""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import Money, Price, Quantity, StrategyId, UnixNanos
from cex_quant.features import FeatureQuality
from cex_quant.instruments import Instrument
from cex_quant.observability import HealthStatus
from cex_quant.strategy import PositionTargetIntent


class RiskDecisionStatus(StrEnum):
    """Binary outcome: an intent is either approved or rejected."""

    ALLOW = "allow"
    REJECT = "reject"


class RiskRejectReason(StrEnum):
    """Stable machine-readable rejection reasons."""

    INTENT_EXPIRED = "intent_expired"
    INTENT_FROM_FUTURE = "intent_from_future"
    STRATEGY_MISMATCH = "strategy_mismatch"
    INSTRUMENT_MISMATCH = "instrument_mismatch"
    INSTRUMENT_NOT_ACTIVE = "instrument_not_active"
    CLOCK_UNHEALTHY = "clock_unhealthy"
    REFERENCE_PRICE_MISSING = "reference_price_missing"
    REFERENCE_PRICE_INVALID = "reference_price_invalid"
    MARKET_DATA_MISSING = "market_data_missing"
    MARKET_DATA_STALE = "market_data_stale"
    FEATURE_DATA_MISSING = "feature_data_missing"
    FEATURE_DATA_STALE = "feature_data_stale"
    FEATURE_DATA_INVALID = "feature_data_invalid"
    STRATEGY_POSITION_LIMIT = "strategy_position_limit"
    GLOBAL_POSITION_LIMIT = "global_position_limit"
    STRATEGY_NOTIONAL_LIMIT = "strategy_notional_limit"
    GLOBAL_NOTIONAL_LIMIT = "global_notional_limit"
    STRATEGY_INTENT_RATE_LIMIT = "strategy_intent_rate_limit"
    GLOBAL_INTENT_RATE_LIMIT = "global_intent_rate_limit"
    UNSUPPORTED_NOTIONAL_MODEL = "unsupported_notional_model"


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskLimits:
    """Exposure, rate, and freshness limits for one evaluation policy.

    Notional caps are denominated in the instrument's quote/reference asset.
    ``None`` disables only that exposure or rate cap; health and freshness
    checks remain fail-closed.
    """

    max_abs_strategy_position: Quantity | None = None
    max_abs_global_position: Quantity | None = None
    max_strategy_notional: Money | None = None
    max_global_notional: Money | None = None
    max_strategy_intents_per_window: int | None = None
    max_global_intents_per_window: int | None = None
    intent_rate_window_ns: int = 1_000_000_000
    max_market_data_age_ns: int = 1_000_000_000
    max_feature_data_age_ns: int = 1_000_000_000
    require_fresh_features: bool = True

    def __post_init__(self) -> None:
        fixed_limits = (
            self.max_abs_strategy_position,
            self.max_abs_global_position,
            self.max_strategy_notional,
            self.max_global_notional,
        )
        if any(value is not None and value.raw < 0 for value in fixed_limits):
            raise ValueError("exposure limits must be non-negative")
        count_limits = (
            self.max_strategy_intents_per_window,
            self.max_global_intents_per_window,
        )
        if any(value is not None and value < 0 for value in count_limits):
            raise ValueError("intent rate limits must be non-negative")
        if self.intent_rate_window_ns <= 0:
            raise ValueError("intent_rate_window_ns must be positive")
        if self.max_market_data_age_ns < 0:
            raise ValueError("max_market_data_age_ns must be non-negative")
        if self.max_feature_data_age_ns < 0:
            raise ValueError("max_feature_data_age_ns must be non-negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskContext:
    """Complete point-in-time input to an evaluation; contains no I/O."""

    now_ns: UnixNanos
    strategy_id: StrategyId
    instrument: Instrument
    current_strategy_position: Quantity
    current_global_position: Quantity
    reference_price: Price | None
    market_data_as_of_ns: UnixNanos | None
    feature_data_as_of_ns: UnixNanos | None
    feature_data_valid_until_ns: UnixNanos | None
    feature_quality: FeatureQuality | None
    clock_status: HealthStatus
    strategy_intents_in_window: int = 0
    global_intents_in_window: int = 0

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id cannot be empty")
        if self.strategy_intents_in_window < 0:
            raise ValueError("strategy_intents_in_window cannot be negative")
        if self.global_intents_in_window < 0:
            raise ValueError("global_intents_in_window cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskDecision:
    """Immutable assessment result; ALLOW carries no rejection reasons."""

    status: RiskDecisionStatus
    intent: PositionTargetIntent
    reasons: tuple[RiskRejectReason, ...]
    projected_strategy_position: Quantity
    projected_global_position: Quantity
    projected_strategy_notional: Money | None
    projected_global_notional: Money | None

    def __post_init__(self) -> None:
        if self.status is RiskDecisionStatus.ALLOW and self.reasons:
            raise ValueError("ALLOW decision cannot carry rejection reasons")
        if self.status is RiskDecisionStatus.REJECT and not self.reasons:
            raise ValueError("REJECT decision requires at least one reason")

    @property
    def allowed(self) -> bool:
        return self.status is RiskDecisionStatus.ALLOW


__all__ = [
    "RiskContext",
    "RiskDecision",
    "RiskDecisionStatus",
    "RiskLimits",
    "RiskRejectReason",
]
