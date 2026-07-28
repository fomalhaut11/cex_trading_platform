from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from cex_quant.core import DurationNanos, MonotonicNanos, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.snapshots import (
    CoherenceGroup,
    CoherenceGroupId,
    ObservationId,
    SnapshotIssueCode,
    SnapshotPolicy,
    SnapshotReadiness,
    SnapshotSourceId,
    SourceFreshnessRule,
    SourceObservation,
    assess_snapshot,
)

SPOT = SnapshotSourceId("spot")
PERP = SnapshotSourceId("perp")
ACCOUNT = SnapshotSourceId("account")
SCOPE = "btc-carry:main"


def rule(
    source_id: SnapshotSourceId,
    *,
    required: bool = True,
    event_age: int = 100,
    arrival_age: int = 50,
    future_skew: int = 5,
) -> SourceFreshnessRule:
    return SourceFreshnessRule(
        source_id=source_id,
        max_event_age_ns=DurationNanos(event_age),
        max_arrival_age_ns=DurationNanos(arrival_age),
        max_future_skew_ns=DurationNanos(future_skew),
        required=required,
    )


def policy(*, account_required: bool = True) -> SnapshotPolicy:
    return SnapshotPolicy(
        source_rules=(
            rule(SPOT),
            rule(PERP),
            rule(ACCOUNT, required=account_required, event_age=500),
        ),
        coherence_groups=(
            CoherenceGroup(
                group_id=CoherenceGroupId("prices"),
                source_ids=(SPOT, PERP),
                max_event_time_skew_ns=DurationNanos(10),
            ),
        ),
        policy_version=1,
    )


def observation(
    source_id: SnapshotSourceId,
    *,
    observation_id: str | None = None,
    scope: str = SCOPE,
    as_of: int = 990,
    accepted: int = 190,
    schema_version: int = 1,
    sequence: int | None = 1,
    value: object | None = None,
) -> SourceObservation[object]:
    return SourceObservation(
        observation_id=ObservationId(
            observation_id or f"{source_id}-{sequence}"
        ),
        source_id=source_id,
        scope=scope,
        as_of_ns=UnixNanos(as_of),
        received_at_ns=UnixNanos(as_of + 1),
        accepted_at_monotonic_ns=MonotonicNanos(accepted),
        schema_version=schema_version,
        source_sequence=sequence,
        value=source_id if value is None else value,
    )


def assess(
    observations: tuple[SourceObservation[object], ...],
    *,
    snapshot_policy: SnapshotPolicy | None = None,
    now: int = 1_000,
    monotonic: int = 200,
    clock: HealthStatus = HealthStatus.HEALTHY,
):
    return assess_snapshot(
        policy=snapshot_policy or policy(),
        observations=observations,
        scope=SCOPE,
        now_ns=UnixNanos(now),
        now_monotonic_ns=MonotonicNanos(monotonic),
        clock_status=clock,
    )


class SnapshotContractTests(unittest.TestCase):
    def test_observation_is_immutable_and_validated(self) -> None:
        item = observation(SPOT)
        with self.assertRaises(FrozenInstanceError):
            item.scope = "other"  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "observation_id"):
            SourceObservation(
                observation_id=ObservationId(" "),
                source_id=SPOT,
                scope=SCOPE,
                as_of_ns=UnixNanos(1),
                received_at_ns=UnixNanos(1),
                accepted_at_monotonic_ns=MonotonicNanos(1),
                schema_version=1,
                value=1,
            )
        with self.assertRaisesRegex(ValueError, "schema_version"):
            observation(SPOT, schema_version=0)
        with self.assertRaisesRegex(ValueError, "source_sequence"):
            observation(SPOT, sequence=-1)

    def test_policy_rejects_duplicate_and_unknown_sources(self) -> None:
        with self.assertRaisesRegex(ValueError, "source rule IDs"):
            SnapshotPolicy(
                source_rules=(rule(SPOT), rule(SPOT)),
                coherence_groups=(),
                policy_version=1,
            )
        with self.assertRaisesRegex(ValueError, "unknown source"):
            SnapshotPolicy(
                source_rules=(rule(SPOT), rule(PERP)),
                coherence_groups=(
                    CoherenceGroup(
                        group_id=CoherenceGroupId("bad"),
                        source_ids=(SPOT, ACCOUNT),
                        max_event_time_skew_ns=DurationNanos(1),
                    ),
                ),
                policy_version=1,
            )

    def test_policy_rejects_unbounded_or_malformed_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two"):
            CoherenceGroup(
                group_id=CoherenceGroupId("one"),
                source_ids=(SPOT,),
                max_event_time_skew_ns=DurationNanos(1),
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            rule(SPOT, event_age=-1)
        with self.assertRaisesRegex(ValueError, "deterministically sorted"):
            SourceFreshnessRule(
                source_id=SPOT,
                max_event_age_ns=DurationNanos(1),
                max_arrival_age_ns=DurationNanos(1),
                max_future_skew_ns=DurationNanos(1),
                supported_schema_versions=(2, 1),
            )
        with self.assertRaisesRegex(ValueError, "at least one"):
            SnapshotPolicy(
                source_rules=(rule(SPOT, required=False),),
                coherence_groups=(),
                policy_version=1,
            )


class SnapshotAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.complete = (
            observation(SPOT, as_of=990),
            observation(PERP, as_of=995),
            observation(ACCOUNT, as_of=980),
        )

    def codes(self, result) -> tuple[SnapshotIssueCode, ...]:
        return tuple(item.code for item in result.assessment.issues)

    def test_complete_coherent_input_is_ready_and_policy_ordered(self) -> None:
        result = assess(tuple(reversed(self.complete)))
        self.assertEqual(
            result.assessment.readiness,
            SnapshotReadiness.READY,
        )
        self.assertEqual(
            tuple(item.source_id for item in result.ordered_observations),
            (SPOT, PERP, ACCOUNT),
        )
        self.assertEqual(result.coherence[0].observed_skew_ns, 5)

    def test_missing_required_and_optional_source(self) -> None:
        required = assess(self.complete[:2])
        self.assertEqual(
            self.codes(required),
            (SnapshotIssueCode.MISSING_SOURCE,),
        )
        optional = assess(
            self.complete[:2],
            snapshot_policy=policy(account_required=False),
        )
        self.assertEqual(optional.assessment.readiness, SnapshotReadiness.READY)

    def test_event_age_and_future_skew_boundaries(self) -> None:
        ready = assess(
            (
                observation(SPOT, as_of=900),
                observation(PERP, as_of=905),
                self.complete[2],
            )
        )
        self.assertEqual(ready.assessment.readiness, SnapshotReadiness.READY)
        ready_future = assess(
            (
                observation(SPOT, as_of=1_000),
                observation(PERP, as_of=1_005),
                self.complete[2],
            )
        )
        self.assertEqual(
            ready_future.assessment.readiness,
            SnapshotReadiness.READY,
        )

        stale = assess(
            (observation(SPOT, as_of=899), *self.complete[1:])
        )
        self.assertIn(SnapshotIssueCode.SOURCE_EVENT_STALE, self.codes(stale))
        future = assess(
            (
                self.complete[0],
                observation(PERP, as_of=1_006),
                self.complete[2],
            )
        )
        self.assertIn(
            SnapshotIssueCode.SOURCE_TIME_FROM_FUTURE,
            self.codes(future),
        )

    def test_arrival_age_and_monotonic_regression(self) -> None:
        at_limit = assess(
            (
                observation(SPOT, accepted=150),
                self.complete[1],
                self.complete[2],
            )
        )
        self.assertEqual(
            at_limit.assessment.readiness,
            SnapshotReadiness.READY,
        )
        stale = assess(
            (
                observation(SPOT, accepted=149),
                self.complete[1],
                self.complete[2],
            )
        )
        self.assertIn(SnapshotIssueCode.SOURCE_ARRIVAL_STALE, self.codes(stale))
        regression = assess(
            (
                observation(SPOT, accepted=201),
                self.complete[1],
                self.complete[2],
            )
        )
        self.assertIn(
            SnapshotIssueCode.MONOTONIC_REGRESSION,
            self.codes(regression),
        )

    def test_clock_and_coherence_fail_closed(self) -> None:
        unhealthy = assess(self.complete, clock=HealthStatus.DEGRADED)
        self.assertEqual(
            self.codes(unhealthy)[0],
            SnapshotIssueCode.CLOCK_UNHEALTHY,
        )
        skewed = assess(
            (
                observation(SPOT, as_of=980),
                observation(PERP, as_of=995),
                self.complete[2],
            )
        )
        self.assertIn(
            SnapshotIssueCode.COHERENCE_SKEW_EXCEEDED,
            self.codes(skewed),
        )
        self.assertEqual(skewed.coherence[0].observed_skew_ns, 15)

    def test_scope_schema_unexpected_and_duplicate_are_explicit(self) -> None:
        invalid = assess(
            (
                observation(SPOT, scope="other"),
                observation(PERP, schema_version=2),
                self.complete[2],
                observation(
                    SnapshotSourceId("extra"),
                    observation_id="extra",
                ),
                observation(SPOT, observation_id="spot-other"),
            )
        )
        codes = self.codes(invalid)
        self.assertIn(SnapshotIssueCode.SCOPE_MISMATCH, codes)
        self.assertIn(SnapshotIssueCode.SCHEMA_UNSUPPORTED, codes)
        self.assertIn(SnapshotIssueCode.UNEXPECTED_SOURCE, codes)
        self.assertIn(SnapshotIssueCode.DUPLICATE_OBSERVATION, codes)

    def test_same_observation_id_across_sources_is_rejected(self) -> None:
        duplicate_id = assess(
            (
                observation(SPOT, observation_id="same"),
                observation(PERP, observation_id="same"),
                self.complete[2],
            )
        )
        self.assertEqual(
            self.codes(duplicate_id)[0],
            SnapshotIssueCode.DUPLICATE_OBSERVATION,
        )


if __name__ == "__main__":
    unittest.main()
