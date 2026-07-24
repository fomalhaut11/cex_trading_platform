"""Deterministic validation for canonical market facts."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from cex_quant.core import DurationNanos, SchemaVersion, UnixNanos

from .events import (
    BestBidAsk,
    BookLevel,
    FundingRateUpdate,
    OrderBookDelta,
    PartialBookFrame,
    VenueOptionAnalyticsUpdate,
)
from .normalization import MarketEvent

_DEFAULT_MAX_FUTURE_SKEW_NS = DurationNanos(1_000_000_000)


class ValidationSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class ValidationCode(StrEnum):
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    NEGATIVE_TIMESTAMP = "negative_timestamp"
    EVENT_FROM_FUTURE = "event_from_future"
    SOURCE_VENUE_MISMATCH = "source_venue_mismatch"
    CROSSED_BOOK = "crossed_book"
    LOCKED_BOOK = "locked_book"
    UNSORTED_BOOK = "unsorted_book"
    DUPLICATE_BOOK_PRICE = "duplicate_book_price"
    NON_FINITE_ANALYTIC = "non_finite_analytic"
    INVALID_FUNDING_TIME = "invalid_funding_time"


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationIssue:
    code: ValidationCode
    severity: ValidationSeverity
    message: str
    field: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationResult:
    event: MarketEvent
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        """Return false only when at least one error is present."""

        return not any(
            issue.severity is ValidationSeverity.ERROR for issue in self.issues
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationPolicy:
    supported_schema_versions: frozenset[SchemaVersion] = frozenset(
        {SchemaVersion(1)}
    )
    max_future_skew_ns: DurationNanos = _DEFAULT_MAX_FUTURE_SKEW_NS
    locked_book_severity: ValidationSeverity = ValidationSeverity.WARNING

    def __post_init__(self) -> None:
        if not self.supported_schema_versions:
            raise ValueError("at least one schema version must be supported")
        if self.max_future_skew_ns < 0:
            raise ValueError("max_future_skew_ns cannot be negative")


class MarketDataValidator:
    """Apply venue-neutral contract checks without mutating an event."""

    def __init__(self, policy: ValidationPolicy | None = None) -> None:
        self._policy = policy or ValidationPolicy()

    def validate(
        self,
        event: MarketEvent,
        *,
        now_ns: UnixNanos | None = None,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        metadata = event.metadata

        if metadata.schema_version not in self._policy.supported_schema_versions:
            issues.append(
                _error(
                    ValidationCode.UNSUPPORTED_SCHEMA,
                    "event schema version is not supported",
                    "metadata.schema_version",
                )
            )
        if metadata.event_time_ns < 0 or metadata.receive_time_ns < 0:
            issues.append(
                _error(
                    ValidationCode.NEGATIVE_TIMESTAMP,
                    "event and receive timestamps must be non-negative",
                    "metadata",
                )
            )
        if (
            now_ns is not None
            and metadata.event_time_ns
            > now_ns + self._policy.max_future_skew_ns
        ):
            issues.append(
                _error(
                    ValidationCode.EVENT_FROM_FUTURE,
                    "event timestamp exceeds allowed future clock skew",
                    "metadata.event_time_ns",
                )
            )
        if metadata.source.venue != str(event.instrument_id.venue):
            issues.append(
                _error(
                    ValidationCode.SOURCE_VENUE_MISMATCH,
                    "event source venue does not match instrument venue",
                    "metadata.source.venue",
                )
            )

        if isinstance(event, BestBidAsk):
            _validate_top_of_book(event.bid, event.ask, issues, self._policy)
        elif isinstance(event, PartialBookFrame):
            _validate_book(event.bids, event.asks, issues, self._policy)
        elif isinstance(event, OrderBookDelta):
            _validate_side_order(
                event.bids,
                descending=True,
                field="bids",
                issues=issues,
            )
            _validate_side_order(
                event.asks,
                descending=False,
                field="asks",
                issues=issues,
            )
        elif isinstance(event, VenueOptionAnalyticsUpdate):
            _validate_venue_analytics(event, issues)
        elif (
            isinstance(event, FundingRateUpdate)
            and event.next_funding_time_ns is not None
            and event.next_funding_time_ns < metadata.event_time_ns
        ):
            issues.append(
                _error(
                    ValidationCode.INVALID_FUNDING_TIME,
                    "next funding time precedes the event time",
                    "next_funding_time_ns",
                )
            )

        return ValidationResult(event=event, issues=tuple(issues))


def _validate_book(
    bids: tuple[BookLevel, ...],
    asks: tuple[BookLevel, ...],
    issues: list[ValidationIssue],
    policy: ValidationPolicy,
) -> None:
    _validate_side_order(bids, descending=True, field="bids", issues=issues)
    _validate_side_order(asks, descending=False, field="asks", issues=issues)
    if bids and asks:
        _validate_top_of_book(bids[0], asks[0], issues, policy)


def _validate_top_of_book(
    bid: BookLevel,
    ask: BookLevel,
    issues: list[ValidationIssue],
    policy: ValidationPolicy,
) -> None:
    bid_value, ask_value = bid.price.as_decimal(), ask.price.as_decimal()
    if bid_value > ask_value:
        issues.append(
            _error(
                ValidationCode.CROSSED_BOOK,
                "best bid exceeds best ask",
                "bid.price",
            )
        )
    elif bid_value == ask_value:
        issues.append(
            ValidationIssue(
                code=ValidationCode.LOCKED_BOOK,
                severity=policy.locked_book_severity,
                message="best bid equals best ask",
                field="bid.price",
            )
        )


def _validate_side_order(
    levels: tuple[BookLevel, ...],
    *,
    descending: bool,
    field: str,
    issues: list[ValidationIssue],
) -> None:
    prices = [level.price.as_decimal() for level in levels]
    if len(prices) != len(set(prices)):
        issues.append(
            _error(
                ValidationCode.DUPLICATE_BOOK_PRICE,
                "book side contains duplicate price levels",
                field,
            )
        )
    if prices != sorted(prices, reverse=descending):
        issues.append(
            _error(
                ValidationCode.UNSORTED_BOOK,
                "book side does not use canonical price ordering",
                field,
            )
        )


def _validate_venue_analytics(
    event: VenueOptionAnalyticsUpdate,
    issues: list[ValidationIssue],
) -> None:
    fields = ("implied_volatility", "delta", "gamma", "vega", "theta")
    for field in fields:
        value = getattr(event, field)
        if value is not None and not isfinite(value):
            issues.append(
                _error(
                    ValidationCode.NON_FINITE_ANALYTIC,
                    "venue analytic must be finite when supplied",
                    field,
                )
            )


def _error(code: ValidationCode, message: str, field: str) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=ValidationSeverity.ERROR,
        message=message,
        field=field,
    )


__all__ = [
    "MarketDataValidator",
    "ValidationCode",
    "ValidationIssue",
    "ValidationPolicy",
    "ValidationResult",
    "ValidationSeverity",
]
