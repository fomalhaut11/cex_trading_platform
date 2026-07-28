"""Bounded freshness and coherence policies for decision snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from cex_quant.core import DurationNanos

from .model import (
    CoherenceGroupId,
    SnapshotSourceId,
    _require_text,
)

MAX_POLICY_SOURCES = 64
MAX_COHERENCE_GROUPS = 32
MAX_SOURCES_PER_GROUP = 32
MAX_DURATION_NS = 7 * 24 * 60 * 60 * 1_000_000_000


def _require_duration(value: DurationNanos, *, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    if value > MAX_DURATION_NS:
        raise ValueError(f"{name} exceeds hard safety limit")


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceFreshnessRule:
    source_id: SnapshotSourceId
    max_event_age_ns: DurationNanos
    max_arrival_age_ns: DurationNanos
    max_future_skew_ns: DurationNanos
    required: bool = True
    supported_schema_versions: tuple[int, ...] = (1,)

    def __post_init__(self) -> None:
        _require_text(
            str(self.source_id),
            name="source_id",
            maximum=128,
        )
        _require_duration(self.max_event_age_ns, name="max_event_age_ns")
        _require_duration(
            self.max_arrival_age_ns,
            name="max_arrival_age_ns",
        )
        _require_duration(
            self.max_future_skew_ns,
            name="max_future_skew_ns",
        )
        if not self.supported_schema_versions:
            raise ValueError("supported_schema_versions cannot be empty")
        if any(item <= 0 for item in self.supported_schema_versions):
            raise ValueError("supported schema versions must be positive")
        if len(set(self.supported_schema_versions)) != len(
            self.supported_schema_versions
        ):
            raise ValueError("supported schema versions must be unique")
        if tuple(sorted(self.supported_schema_versions)) != (
            self.supported_schema_versions
        ):
            raise ValueError(
                "supported schema versions must be deterministically sorted"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class CoherenceGroup:
    group_id: CoherenceGroupId
    source_ids: tuple[SnapshotSourceId, ...]
    max_event_time_skew_ns: DurationNanos

    def __post_init__(self) -> None:
        _require_text(str(self.group_id), name="group_id", maximum=128)
        if len(self.source_ids) < 2:
            raise ValueError("coherence group requires at least two sources")
        if len(self.source_ids) > MAX_SOURCES_PER_GROUP:
            raise ValueError("coherence group exceeds source hard limit")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("coherence group source_ids must be unique")
        for source_id in self.source_ids:
            _require_text(
                str(source_id),
                name="source_id",
                maximum=128,
            )
        _require_duration(
            self.max_event_time_skew_ns,
            name="max_event_time_skew_ns",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotPolicy:
    source_rules: tuple[SourceFreshnessRule, ...]
    coherence_groups: tuple[CoherenceGroup, ...]
    policy_version: int

    def __post_init__(self) -> None:
        if not self.source_rules:
            raise ValueError("source_rules cannot be empty")
        if len(self.source_rules) > MAX_POLICY_SOURCES:
            raise ValueError("source_rules exceed hard safety limit")
        if len(self.coherence_groups) > MAX_COHERENCE_GROUPS:
            raise ValueError("coherence_groups exceed hard safety limit")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        if not any(item.required for item in self.source_rules):
            raise ValueError("at least one source rule must be required")

        source_ids = tuple(item.source_id for item in self.source_rules)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source rule IDs must be unique")
        group_ids = tuple(item.group_id for item in self.coherence_groups)
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("coherence group IDs must be unique")

        known = set(source_ids)
        for group in self.coherence_groups:
            unknown = tuple(
                source_id
                for source_id in group.source_ids
                if source_id not in known
            )
            if unknown:
                raise ValueError(
                    "coherence group references unknown source IDs: "
                    + ", ".join(map(str, unknown))
                )

    @property
    def source_ids(self) -> tuple[SnapshotSourceId, ...]:
        return tuple(item.source_id for item in self.source_rules)


__all__ = [
    "MAX_COHERENCE_GROUPS",
    "MAX_DURATION_NS",
    "MAX_POLICY_SOURCES",
    "MAX_SOURCES_PER_GROUP",
    "CoherenceGroup",
    "SnapshotPolicy",
    "SourceFreshnessRule",
]
