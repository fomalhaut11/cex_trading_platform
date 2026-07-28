from __future__ import annotations

import unittest
from dataclasses import dataclass
from threading import Thread

from cex_quant.core import DurationNanos, MonotonicNanos, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    ObservationDisposition,
    ObservationIdentityConflictError,
    SnapshotCoordinator,
    SnapshotCoordinatorFailedError,
    SnapshotCoordinatorStatus,
    SnapshotWriterViolationError,
)
from cex_quant.snapshots import (
    CoherenceGroup,
    CoherenceGroupId,
    DecisionSnapshotMetadata,
    DecisionSnapshotPublication,
    ObservationId,
    SnapshotIssueCode,
    SnapshotPolicy,
    SnapshotReadiness,
    SnapshotSourceId,
    SourceFreshnessRule,
    SourceObservation,
)

PRICE_A = SnapshotSourceId("price-a")
PRICE_B = SnapshotSourceId("price-b")
ACCOUNT = SnapshotSourceId("account")
SCOPE = "synthetic-three-source"


def make_policy() -> SnapshotPolicy:
    rules = tuple(
        SourceFreshnessRule(
            source_id=source_id,
            max_event_age_ns=DurationNanos(100),
            max_arrival_age_ns=DurationNanos(100),
            max_future_skew_ns=DurationNanos(5),
        )
        for source_id in (PRICE_A, PRICE_B, ACCOUNT)
    )
    return SnapshotPolicy(
        source_rules=rules,
        coherence_groups=(
            CoherenceGroup(
                group_id=CoherenceGroupId("prices"),
                source_ids=(PRICE_A, PRICE_B),
                max_event_time_skew_ns=DurationNanos(10),
            ),
        ),
        policy_version=7,
    )


def source(
    source_id: SnapshotSourceId,
    *,
    sequence: int = 1,
    as_of: int = 990,
    accepted: int = 190,
    observation_id: str | None = None,
    value: int | None = None,
) -> SourceObservation[object]:
    return SourceObservation(
        observation_id=ObservationId(
            observation_id or f"{source_id}-{sequence}"
        ),
        source_id=source_id,
        scope=SCOPE,
        as_of_ns=UnixNanos(as_of),
        received_at_ns=UnixNanos(as_of + 1),
        accepted_at_monotonic_ns=MonotonicNanos(accepted),
        schema_version=1,
        value=sequence if value is None else value,
        source_sequence=sequence,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class SyntheticDecisionInput:
    first: int
    second: int
    account: int
    snapshot_id: str


class SyntheticAssembler:
    def build(
        self,
        *,
        observations: tuple[SourceObservation[object], ...],
        metadata: DecisionSnapshotMetadata,
    ) -> SyntheticDecisionInput:
        values = tuple(int(item.value) for item in observations)
        if len(values) != 3:
            raise ValueError("synthetic application requires three sources")
        return SyntheticDecisionInput(
            first=values[0],
            second=values[1],
            account=values[2],
            snapshot_id=str(metadata.snapshot_id),
        )


class FailingAssembler:
    def build(
        self,
        *,
        observations: tuple[SourceObservation[object], ...],
        metadata: DecisionSnapshotMetadata,
    ) -> SyntheticDecisionInput:
        del observations, metadata
        raise RuntimeError("assembler failed")


class EvidenceCollector:
    def __init__(self) -> None:
        self.items: list[
            DecisionSnapshotPublication[SyntheticDecisionInput]
        ] = []

    def publish(
        self,
        publication: DecisionSnapshotPublication[SyntheticDecisionInput],
    ) -> None:
        self.items.append(publication)


class FailingEvidencePort:
    def publish(
        self,
        publication: DecisionSnapshotPublication[SyntheticDecisionInput],
    ) -> None:
        del publication
        raise RuntimeError("evidence queue full")


def coordinator(
    *,
    assembler: SyntheticAssembler | FailingAssembler | None = None,
    evidence_port: EvidenceCollector | FailingEvidencePort | None = None,
    max_seen: int = 16,
) -> SnapshotCoordinator[SyntheticDecisionInput]:
    return SnapshotCoordinator(
        scope=SCOPE,
        policy=make_policy(),
        assembler=assembler or SyntheticAssembler(),
        evidence_port=evidence_port,
        max_seen_observation_ids=max_seen,
    )


def populate(
    target: SnapshotCoordinator[SyntheticDecisionInput],
    *,
    sequence: int = 1,
) -> None:
    for item in (
        source(PRICE_A, sequence=sequence, as_of=990),
        source(PRICE_B, sequence=sequence, as_of=995),
        source(ACCOUNT, sequence=sequence, as_of=985),
    ):
        target.accept(item)


def evaluate(
    target: SnapshotCoordinator[SyntheticDecisionInput],
    *,
    now: int = 1_000,
    monotonic: int = 200,
):
    return target.evaluate(
        now_ns=UnixNanos(now),
        now_monotonic_ns=MonotonicNanos(monotonic),
        clock_status=HealthStatus.HEALTHY,
    )


class SnapshotCoordinatorTests(unittest.TestCase):
    def test_three_source_application_publishes_in_policy_order(self) -> None:
        evidence = EvidenceCollector()
        target = coordinator(evidence_port=evidence)
        populate(target)

        result = evaluate(target)

        self.assertEqual(result.assessment.readiness, SnapshotReadiness.READY)
        self.assertIsNotNone(result.publication)
        assert result.publication is not None
        self.assertEqual(
            result.publication.value,
            SyntheticDecisionInput(
                first=1,
                second=1,
                account=1,
                snapshot_id=str(result.publication.metadata.snapshot_id),
            ),
        )
        self.assertEqual(len(evidence.items), 1)
        self.assertEqual(target.view().snapshot_sequence, 1)

    def test_missing_source_starts_not_ready_and_restart_is_empty(self) -> None:
        first = coordinator()
        first.accept(source(PRICE_A))
        self.assertEqual(
            evaluate(first).assessment.readiness,
            SnapshotReadiness.NOT_READY,
        )
        populate(first)
        self.assertIsNotNone(evaluate(first).publication)

        restarted = coordinator()
        view = restarted.view()
        self.assertEqual(view.retained_sources, 0)
        self.assertEqual(view.snapshot_sequence, 0)
        self.assertIsNone(evaluate(restarted).publication)

    def test_same_fingerprint_publishes_once_and_new_source_advances(self) -> None:
        target = coordinator()
        populate(target)
        first = evaluate(target)
        repeated = evaluate(target)
        self.assertIsNotNone(first.publication)
        self.assertIsNone(repeated.publication)

        target.accept(source(ACCOUNT, sequence=2, as_of=996))
        second = evaluate(target)
        self.assertIsNotNone(second.publication)
        assert first.publication is not None
        assert second.publication is not None
        self.assertEqual(second.publication.metadata.snapshot_sequence, 2)
        self.assertNotEqual(
            first.publication.metadata.snapshot_id,
            second.publication.metadata.snapshot_id,
        )

    def test_replay_produces_same_publication_identity_and_value(self) -> None:
        first = coordinator()
        second = coordinator()
        for target in (first, second):
            populate(target)
        left = evaluate(first)
        right = evaluate(second)
        self.assertEqual(left.publication, right.publication)

    def test_prior_publication_is_not_reused_after_readiness_loss(self) -> None:
        target = coordinator()
        populate(target)
        self.assertIsNotNone(evaluate(target).publication)
        stale = evaluate(target, now=1_200, monotonic=400)
        self.assertEqual(stale.assessment.readiness, SnapshotReadiness.NOT_READY)
        self.assertIsNone(stale.publication)
        self.assertIsNotNone(target.view().latest_publication)

    def test_duplicate_is_idempotent_and_conflict_latches_failure(self) -> None:
        target = coordinator()
        item = source(PRICE_A)
        self.assertEqual(
            target.accept(item),
            ObservationDisposition.APPLIED,
        )
        self.assertEqual(
            target.accept(item),
            ObservationDisposition.DUPLICATE,
        )
        with self.assertRaises(ObservationIdentityConflictError):
            target.accept(source(PRICE_A, observation_id="price-a-1", value=9))
        self.assertEqual(
            target.view().status,
            SnapshotCoordinatorStatus.FAILED,
        )
        with self.assertRaises(SnapshotCoordinatorFailedError):
            evaluate(target)

    def test_sequence_regression_blocks_until_newer_input(self) -> None:
        target = coordinator()
        populate(target, sequence=2)
        self.assertIsNotNone(evaluate(target).publication)

        disposition = target.accept(source(PRICE_A, sequence=1))
        self.assertEqual(disposition, ObservationDisposition.OUT_OF_ORDER)
        rejected = evaluate(target)
        self.assertEqual(
            rejected.assessment.issues[-1].code,
            SnapshotIssueCode.SOURCE_SEQUENCE_REGRESSION,
        )

        target.accept(source(PRICE_A, sequence=3, as_of=996))
        recovered = evaluate(target)
        self.assertEqual(
            recovered.assessment.readiness,
            SnapshotReadiness.READY,
        )
        self.assertIsNotNone(recovered.publication)

    def test_seen_identity_memory_is_bounded(self) -> None:
        target = coordinator(max_seen=3)
        populate(target)
        for sequence in range(2, 8):
            target.accept(source(ACCOUNT, sequence=sequence))
        self.assertEqual(target.view().retained_observation_ids, 3)
        self.assertEqual(target.view().retained_sources, 3)

    def test_non_owner_thread_is_rejected(self) -> None:
        target = coordinator()
        errors: list[BaseException] = []

        def mutate() -> None:
            try:
                target.accept(source(PRICE_A))
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=mutate)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], SnapshotWriterViolationError)
        self.assertEqual(target.view().retained_sources, 0)

    def test_assembler_and_evidence_failure_latch(self) -> None:
        for target in (
            coordinator(assembler=FailingAssembler()),
            coordinator(evidence_port=FailingEvidencePort()),
        ):
            with self.subTest(target=target):
                populate(target)
                with self.assertRaises(SnapshotCoordinatorFailedError):
                    evaluate(target)
                self.assertEqual(
                    target.view().status,
                    SnapshotCoordinatorStatus.FAILED,
                )
                self.assertEqual(target.view().snapshot_sequence, 0)


if __name__ == "__main__":
    unittest.main()
