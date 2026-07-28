"""Pure deterministic readiness assessment for decision snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from cex_quant.core import MonotonicNanos, UnixNanos
from cex_quant.observability import HealthStatus

from .model import (
    CoherenceMeasurement,
    SnapshotAssessment,
    SnapshotIssue,
    SnapshotIssueCode,
    SnapshotReadiness,
    SnapshotSourceId,
    SourceObservation,
)
from .policy import SnapshotPolicy


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotAssessmentResult:
    assessment: SnapshotAssessment
    coherence: tuple[CoherenceMeasurement, ...]
    ordered_observations: tuple[SourceObservation[object], ...]


def assess_snapshot(
    *,
    policy: SnapshotPolicy,
    observations: tuple[SourceObservation[object], ...],
    scope: str,
    now_ns: UnixNanos,
    now_monotonic_ns: MonotonicNanos,
    clock_status: HealthStatus,
) -> SnapshotAssessmentResult:
    """Assess latest observations without mutating source or runtime state."""

    if not scope or scope != scope.strip():
        raise ValueError("scope must be non-empty and trimmed")
    if now_ns < 0:
        raise ValueError("now_ns cannot be negative")
    if now_monotonic_ns < 0:
        raise ValueError("now_monotonic_ns cannot be negative")

    issues: list[SnapshotIssue] = []
    if clock_status is not HealthStatus.HEALTHY:
        issues.append(
            SnapshotIssue(
                code=SnapshotIssueCode.CLOCK_UNHEALTHY,
                source_ids=(),
                reason=f"clock status is {clock_status.value}",
            )
        )

    by_source: dict[SnapshotSourceId, SourceObservation[object]] = {}
    duplicate_sources: set[SnapshotSourceId] = set()
    known_sources = set(policy.source_ids)
    unexpected: dict[SnapshotSourceId, SourceObservation[object]] = {}
    seen_observation_ids: dict[str, SourceObservation[object]] = {}
    duplicate_observation_sources: set[SnapshotSourceId] = set()

    for observation in observations:
        prior_id = seen_observation_ids.get(str(observation.observation_id))
        if prior_id is not None:
            duplicate_observation_sources.update(
                (prior_id.source_id, observation.source_id)
            )
        else:
            seen_observation_ids[str(observation.observation_id)] = observation

        if observation.source_id not in known_sources:
            unexpected[observation.source_id] = observation
            continue
        if observation.source_id in by_source:
            duplicate_sources.add(observation.source_id)
            continue
        by_source[observation.source_id] = observation

    if duplicate_observation_sources:
        issues.append(
            SnapshotIssue(
                code=SnapshotIssueCode.DUPLICATE_OBSERVATION,
                source_ids=tuple(
                    sorted(duplicate_observation_sources, key=str)
                ),
                reason="observation ID was reused in the assessment input",
            )
        )

    for source_id in sorted(unexpected, key=str):
        issues.append(
            SnapshotIssue(
                code=SnapshotIssueCode.UNEXPECTED_SOURCE,
                source_ids=(source_id,),
                reason="source is not declared by the snapshot policy",
            )
        )

    for rule in policy.source_rules:
        source_id = rule.source_id
        if source_id in duplicate_sources:
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.DUPLICATE_OBSERVATION,
                    source_ids=(source_id,),
                    reason="multiple observations were supplied for one source",
                )
            )
        current_observation = by_source.get(source_id)
        if current_observation is None:
            if rule.required:
                issues.append(
                    SnapshotIssue(
                        code=SnapshotIssueCode.MISSING_SOURCE,
                        source_ids=(source_id,),
                        reason="required source observation is missing",
                    )
                )
            continue
        if current_observation.scope != scope:
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.SCOPE_MISMATCH,
                    source_ids=(source_id,),
                    reason="observation scope does not match coordinator scope",
                )
            )
        if (
            current_observation.schema_version
            not in rule.supported_schema_versions
        ):
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.SCHEMA_UNSUPPORTED,
                    source_ids=(source_id,),
                    reason=(
                        "observation schema version is not accepted by policy"
                    ),
                )
            )

        if current_observation.as_of_ns > now_ns:
            future_skew = current_observation.as_of_ns - now_ns
            if future_skew > rule.max_future_skew_ns:
                issues.append(
                    SnapshotIssue(
                        code=SnapshotIssueCode.SOURCE_TIME_FROM_FUTURE,
                        source_ids=(source_id,),
                        reason="source event time exceeds future-skew limit",
                    )
                )
        elif (
            now_ns - current_observation.as_of_ns > rule.max_event_age_ns
        ):
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.SOURCE_EVENT_STALE,
                    source_ids=(source_id,),
                    reason="source event age exceeds policy limit",
                )
            )

        if (
            now_monotonic_ns
            < current_observation.accepted_at_monotonic_ns
        ):
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.MONOTONIC_REGRESSION,
                    source_ids=(source_id,),
                    reason="current monotonic time precedes source acceptance",
                )
            )
        elif (
            now_monotonic_ns
            - current_observation.accepted_at_monotonic_ns
            > rule.max_arrival_age_ns
        ):
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.SOURCE_ARRIVAL_STALE,
                    source_ids=(source_id,),
                    reason="source arrival age exceeds policy limit",
                )
            )

    coherence: list[CoherenceMeasurement] = []
    for group in policy.coherence_groups:
        group_observations = tuple(
            by_source.get(source_id) for source_id in group.source_ids
        )
        if any(item is None for item in group_observations):
            continue
        event_times = tuple(
            item.as_of_ns
            for item in group_observations
            if item is not None
        )
        observed_skew = max(event_times) - min(event_times)
        coherence.append(
            CoherenceMeasurement(
                group_id=group.group_id,
                observed_skew_ns=observed_skew,
            )
        )
        if observed_skew > group.max_event_time_skew_ns:
            issues.append(
                SnapshotIssue(
                    code=SnapshotIssueCode.COHERENCE_SKEW_EXCEEDED,
                    source_ids=group.source_ids,
                    reason="coherence group event-time skew exceeds limit",
                )
            )

    ordered_observations = tuple(
        by_source[source_id]
        for source_id in policy.source_ids
        if source_id in by_source
    )
    readiness = (
        SnapshotReadiness.READY
        if not issues
        else SnapshotReadiness.NOT_READY
    )
    return SnapshotAssessmentResult(
        assessment=SnapshotAssessment(
            readiness=readiness,
            issues=tuple(issues),
            policy_version=policy.policy_version,
        ),
        coherence=tuple(coherence),
        ordered_observations=ordered_observations,
    )


__all__ = ["SnapshotAssessmentResult", "assess_snapshot"]
