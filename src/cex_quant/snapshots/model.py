"""Immutable contracts for coherent application decision inputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, NewType, TypeVar

from cex_quant.core import MonotonicNanos, UnixNanos

SnapshotSourceId = NewType("SnapshotSourceId", str)
ObservationId = NewType("ObservationId", str)
DecisionSnapshotId = NewType("DecisionSnapshotId", str)
CoherenceGroupId = NewType("CoherenceGroupId", str)

T_co = TypeVar("T_co", covariant=True)

MAX_ID_LENGTH = 128
MAX_SCOPE_LENGTH = 256
MAX_REASON_LENGTH = 512


def _require_text(value: str, *, name: str, maximum: int) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}")


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceObservation(Generic[T_co]):
    """One immutable source view with explicit time and provenance."""

    observation_id: ObservationId
    source_id: SnapshotSourceId
    scope: str
    as_of_ns: UnixNanos
    received_at_ns: UnixNanos
    accepted_at_monotonic_ns: MonotonicNanos
    schema_version: int
    value: T_co
    source_sequence: int | None = None

    def __post_init__(self) -> None:
        _require_text(
            str(self.observation_id),
            name="observation_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(
            str(self.source_id),
            name="source_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(self.scope, name="scope", maximum=MAX_SCOPE_LENGTH)
        if self.as_of_ns < 0:
            raise ValueError("as_of_ns cannot be negative")
        if self.received_at_ns < 0:
            raise ValueError("received_at_ns cannot be negative")
        if self.accepted_at_monotonic_ns < 0:
            raise ValueError("accepted_at_monotonic_ns cannot be negative")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")
        if self.source_sequence is not None and self.source_sequence < 0:
            raise ValueError("source_sequence cannot be negative")


class SnapshotReadiness(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


class SnapshotIssueCode(StrEnum):
    MISSING_SOURCE = "missing_source"
    UNEXPECTED_SOURCE = "unexpected_source"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    SCOPE_MISMATCH = "scope_mismatch"
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    SOURCE_SEQUENCE_REGRESSION = "source_sequence_regression"
    SOURCE_TIME_FROM_FUTURE = "source_time_from_future"
    SOURCE_EVENT_STALE = "source_event_stale"
    SOURCE_ARRIVAL_STALE = "source_arrival_stale"
    COHERENCE_SKEW_EXCEEDED = "coherence_skew_exceeded"
    CLOCK_UNHEALTHY = "clock_unhealthy"
    MONOTONIC_REGRESSION = "monotonic_regression"
    SOURCE_VALUE_INVALID = "source_value_invalid"


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotIssue:
    code: SnapshotIssueCode
    source_ids: tuple[SnapshotSourceId, ...]
    reason: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("snapshot issue source_ids must be unique")
        for source_id in self.source_ids:
            _require_text(
                str(source_id),
                name="source_id",
                maximum=MAX_ID_LENGTH,
            )
        _require_text(
            self.reason,
            name="reason",
            maximum=MAX_REASON_LENGTH,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotAssessment:
    readiness: SnapshotReadiness
    issues: tuple[SnapshotIssue, ...]
    policy_version: int

    def __post_init__(self) -> None:
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        if self.readiness is SnapshotReadiness.READY and self.issues:
            raise ValueError("READY assessment cannot contain issues")
        if self.readiness is SnapshotReadiness.NOT_READY and not self.issues:
            raise ValueError("NOT_READY assessment requires at least one issue")


@dataclass(frozen=True, slots=True, kw_only=True)
class CoherenceMeasurement:
    group_id: CoherenceGroupId
    observed_skew_ns: int

    def __post_init__(self) -> None:
        _require_text(
            str(self.group_id),
            name="group_id",
            maximum=MAX_ID_LENGTH,
        )
        if self.observed_skew_ns < 0:
            raise ValueError("observed_skew_ns cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionSnapshotMetadata:
    snapshot_id: DecisionSnapshotId
    scope: str
    snapshot_sequence: int
    assembled_at_ns: UnixNanos
    assembled_at_monotonic_ns: MonotonicNanos
    policy_version: int
    observation_ids: tuple[ObservationId, ...]
    coherence: tuple[CoherenceMeasurement, ...]

    def __post_init__(self) -> None:
        _require_text(
            str(self.snapshot_id),
            name="snapshot_id",
            maximum=MAX_ID_LENGTH,
        )
        _require_text(self.scope, name="scope", maximum=MAX_SCOPE_LENGTH)
        if self.snapshot_sequence <= 0:
            raise ValueError("snapshot_sequence must be positive")
        if self.assembled_at_ns < 0:
            raise ValueError("assembled_at_ns cannot be negative")
        if self.assembled_at_monotonic_ns < 0:
            raise ValueError("assembled_at_monotonic_ns cannot be negative")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        if not self.observation_ids:
            raise ValueError("observation_ids cannot be empty")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("observation_ids must be unique")
        for observation_id in self.observation_ids:
            _require_text(
                str(observation_id),
                name="observation_id",
                maximum=MAX_ID_LENGTH,
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionSnapshotPublication(Generic[T_co]):
    """A typed application value with its complete decision evidence."""

    metadata: DecisionSnapshotMetadata
    assessment: SnapshotAssessment
    value: T_co

    def __post_init__(self) -> None:
        if self.assessment.readiness is not SnapshotReadiness.READY:
            raise ValueError("only READY snapshots can be published")
        if self.metadata.policy_version != self.assessment.policy_version:
            raise ValueError("metadata and assessment policy versions differ")


__all__ = [
    "CoherenceGroupId",
    "CoherenceMeasurement",
    "DecisionSnapshotId",
    "DecisionSnapshotMetadata",
    "DecisionSnapshotPublication",
    "ObservationId",
    "SnapshotAssessment",
    "SnapshotIssue",
    "SnapshotIssueCode",
    "SnapshotReadiness",
    "SnapshotSourceId",
    "SourceObservation",
]
