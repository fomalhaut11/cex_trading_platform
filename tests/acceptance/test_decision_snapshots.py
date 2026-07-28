"""Offline acceptance scenarios for coherent decision snapshots."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from cex_quant.core import DurationNanos, MonotonicNanos, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.runtime import SnapshotCoordinator
from cex_quant.snapshots import (
    CoherenceGroup,
    CoherenceGroupId,
    DecisionSnapshotMetadata,
    ObservationId,
    SnapshotIssueCode,
    SnapshotPolicy,
    SnapshotReadiness,
    SnapshotSourceId,
    SourceFreshnessRule,
    SourceObservation,
)

SCOPE = "acceptance:three-source"
SPOT = SnapshotSourceId("spot-bba")
PERP = SnapshotSourceId("perp-bba")
ACCOUNT = SnapshotSourceId("account")


@dataclass(frozen=True, slots=True, kw_only=True)
class ThreeSourceDecisionInput:
    spot: int
    perpetual: int
    account: int


class ThreeSourceAssembler:
    def build(
        self,
        *,
        observations: tuple[SourceObservation[object], ...],
        metadata: DecisionSnapshotMetadata,
    ) -> ThreeSourceDecisionInput:
        del metadata
        values = tuple(int(item.value) for item in observations)
        if len(values) != 3:
            raise ValueError("three source input is incomplete")
        return ThreeSourceDecisionInput(
            spot=values[0],
            perpetual=values[1],
            account=values[2],
        )


def policy() -> SnapshotPolicy:
    return SnapshotPolicy(
        source_rules=tuple(
            SourceFreshnessRule(
                source_id=source_id,
                max_event_age_ns=DurationNanos(100),
                max_arrival_age_ns=DurationNanos(100),
                max_future_skew_ns=DurationNanos(5),
            )
            for source_id in (SPOT, PERP, ACCOUNT)
        ),
        coherence_groups=(
            CoherenceGroup(
                group_id=CoherenceGroupId("executable-prices"),
                source_ids=(SPOT, PERP),
                max_event_time_skew_ns=DurationNanos(10),
            ),
        ),
        policy_version=1,
    )


def observation(
    source_id: SnapshotSourceId,
    *,
    sequence: int,
    event_time: int,
) -> SourceObservation[object]:
    return SourceObservation(
        observation_id=ObservationId(f"{source_id}:{sequence}"),
        source_id=source_id,
        scope=SCOPE,
        as_of_ns=UnixNanos(event_time),
        received_at_ns=UnixNanos(event_time + 1),
        accepted_at_monotonic_ns=MonotonicNanos(900 + sequence),
        schema_version=1,
        source_sequence=sequence,
        value=sequence,
    )


def coordinator() -> SnapshotCoordinator[ThreeSourceDecisionInput]:
    return SnapshotCoordinator(
        scope=SCOPE,
        policy=policy(),
        assembler=ThreeSourceAssembler(),
        max_seen_observation_ids=8,
    )


class DecisionSnapshotAcceptanceTests(unittest.TestCase):
    def evaluate(
        self,
        target: SnapshotCoordinator[ThreeSourceDecisionInput],
        *,
        now: int = 1_000,
        monotonic: int = 1_000,
    ):
        return target.evaluate(
            now_ns=UnixNanos(now),
            now_monotonic_ns=MonotonicNanos(monotonic),
            clock_status=HealthStatus.HEALTHY,
        )

    def test_missing_skewed_then_coherent_inputs_publish_once(self) -> None:
        target = coordinator()
        target.accept(observation(SPOT, sequence=1, event_time=990))
        missing = self.evaluate(target)
        self.assertEqual(
            missing.assessment.readiness,
            SnapshotReadiness.NOT_READY,
        )
        self.assertIsNone(missing.publication)

        target.accept(observation(PERP, sequence=1, event_time=970))
        target.accept(observation(ACCOUNT, sequence=1, event_time=980))
        skewed = self.evaluate(target)
        self.assertIn(
            SnapshotIssueCode.COHERENCE_SKEW_EXCEEDED,
            tuple(item.code for item in skewed.assessment.issues),
        )
        self.assertIsNone(skewed.publication)

        target.accept(observation(PERP, sequence=2, event_time=995))
        ready = self.evaluate(target)
        self.assertEqual(
            ready.assessment.readiness,
            SnapshotReadiness.READY,
        )
        self.assertIsNotNone(ready.publication)
        assert ready.publication is not None
        self.assertEqual(
            ready.publication.value,
            ThreeSourceDecisionInput(spot=1, perpetual=2, account=1),
        )
        self.assertIsNone(self.evaluate(target).publication)

    def test_replay_is_deterministic_and_restart_requires_new_inputs(self) -> None:
        observations = (
            observation(SPOT, sequence=1, event_time=990),
            observation(PERP, sequence=1, event_time=995),
            observation(ACCOUNT, sequence=1, event_time=980),
        )
        publications = []
        for _ in range(2):
            target = coordinator()
            for item in observations:
                target.accept(item)
            publications.append(self.evaluate(target).publication)
        self.assertEqual(publications[0], publications[1])

        restarted = coordinator()
        result = self.evaluate(restarted)
        self.assertEqual(
            result.assessment.readiness,
            SnapshotReadiness.NOT_READY,
        )
        self.assertIsNone(result.publication)


if __name__ == "__main__":
    unittest.main()
