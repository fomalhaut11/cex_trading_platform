"""Canonical market facts, validation and market-state interfaces.

Venue adapters decode external payloads into this domain. Option IV, Greeks and
surfaces are not market facts and belong to :mod:`cex_quant.features`.
"""

from .events import (
    AggregateTrade,
    AggressorSide,
    BestBidAsk,
    BookLevel,
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
from .normalization import (
    MarketDataNormalizer,
    MarketEvent,
    NormalizationError,
    NormalizationErrorCode,
    RawMarketMessage,
)
from .state import (
    InstrumentMismatchError,
    L1State,
    L1View,
    MarketStateStatus,
    OrderBookView,
    PartialBookState,
    PartialBookView,
    ReconstructedOrderBook,
    StateBufferOverflowError,
    StateUpdateResult,
    UpdateDisposition,
)
from .validation import (
    MarketDataValidator,
    ValidationCode,
    ValidationIssue,
    ValidationPolicy,
    ValidationResult,
    ValidationSeverity,
)

__all__ = [
    "AggregateTrade",
    "AggressorSide",
    "BestBidAsk",
    "BookLevel",
    "FundingRateUpdate",
    "IndexPriceUpdate",
    "InstrumentMismatchError",
    "KlineUpdate",
    "L1State",
    "L1View",
    "MarkPriceUpdate",
    "MarketDataNormalizer",
    "MarketDataValidator",
    "MarketEvent",
    "MarketStateStatus",
    "MarketTrade",
    "NormalizationError",
    "NormalizationErrorCode",
    "OpenInterestUpdate",
    "OrderBookDelta",
    "OrderBookView",
    "PartialBookFrame",
    "PartialBookState",
    "PartialBookView",
    "RawMarketMessage",
    "ReconstructedOrderBook",
    "StateBufferOverflowError",
    "StateUpdateResult",
    "UpdateDisposition",
    "ValidationCode",
    "ValidationIssue",
    "ValidationPolicy",
    "ValidationResult",
    "ValidationSeverity",
    "VenueOptionAnalyticsUpdate",
]
