"""Immutable contracts for online, system-computed features."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import NewType

from cex_quant.core import EventId, FeatureId, UnixNanos

FeatureVersion = NewType("FeatureVersion", int)


class FeatureQuality(StrEnum):
    """Consumer-facing quality of a computed value."""

    GOOD = "good"
    DEGRADED = "degraded"
    INVALID = "invalid"


class FeatureOrigin(StrEnum):
    """Whether system calculation used venue-published reference analytics."""

    SYSTEM_COMPUTED = "system_computed"
    SYSTEM_COMPUTED_WITH_VENUE_REFERENCE = (
        "system_computed_with_venue_reference"
    )


@dataclass(frozen=True, slots=True, kw_only=True, order=True)
class FeatureRef:
    """Stable identity of one versioned feature definition."""

    feature_id: FeatureId
    version: FeatureVersion

    def __post_init__(self) -> None:
        if not self.feature_id:
            raise ValueError("feature_id cannot be empty")
        if self.version < 1:
            raise ValueError("feature version must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureOutput:
    """Result returned by feature calculation code before lineage is attached."""

    value: float
    unit: str
    quality: FeatureQuality = FeatureQuality.GOOD
    valid_until_ns: UnixNanos | None = None

    def __post_init__(self) -> None:
        if not self.unit:
            raise ValueError("feature unit cannot be empty")
        if self.quality is not FeatureQuality.INVALID and not isfinite(self.value):
            raise ValueError("non-invalid feature values must be finite")


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureMetadata:
    """Validity and reproducibility metadata attached by the engine."""

    ref: FeatureRef
    scope: str
    as_of_ns: UnixNanos
    computed_at_ns: UnixNanos
    triggering_event_id: EventId
    dependency_refs: tuple[FeatureRef, ...]
    origin: FeatureOrigin = FeatureOrigin.SYSTEM_COMPUTED
    venue_reference_event_ids: tuple[EventId, ...] = ()
    valid_until_ns: UnixNanos | None = None

    def __post_init__(self) -> None:
        if not self.scope:
            raise ValueError("feature scope cannot be empty")
        if self.valid_until_ns is not None and self.valid_until_ns < self.as_of_ns:
            raise ValueError("valid_until_ns cannot precede as_of_ns")
        if self.dependency_refs != tuple(sorted(self.dependency_refs)):
            raise ValueError("dependency_refs must be sorted")
        if self.venue_reference_event_ids != tuple(
            sorted(set(self.venue_reference_event_ids))
        ):
            raise ValueError(
                "venue_reference_event_ids must be unique and sorted"
            )
        has_references = bool(self.venue_reference_event_ids)
        if has_references != (
            self.origin
            is FeatureOrigin.SYSTEM_COMPUTED_WITH_VENUE_REFERENCE
        ):
            raise ValueError("feature origin must agree with reference lineage")


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureValue:
    """An immutable scalar feature value with explicit unit and lineage."""

    value: float
    unit: str
    quality: FeatureQuality
    metadata: FeatureMetadata


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureSnapshot:
    """Deterministically ordered point-in-time engine state."""

    scope: str
    values: tuple[FeatureValue, ...]

    def get(self, ref: FeatureRef) -> FeatureValue | None:
        return next((value for value in self.values if value.metadata.ref == ref), None)


__all__ = [
    "FeatureMetadata",
    "FeatureOrigin",
    "FeatureOutput",
    "FeatureQuality",
    "FeatureRef",
    "FeatureSnapshot",
    "FeatureValue",
    "FeatureVersion",
]
