"""Single-writer bounded coordination of typed decision snapshots."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from threading import get_ident
from typing import Generic, Protocol, TypeVar

from cex_quant.core import MonotonicNanos, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.snapshots import (
    DecisionSnapshotId,
    DecisionSnapshotMetadata,
    DecisionSnapshotPublication,
    ObservationId,
    SnapshotAssessment,
    SnapshotIssue,
    SnapshotIssueCode,
    SnapshotPolicy,
    SnapshotReadiness,
    SnapshotSourceId,
    SourceObservation,
    assess_snapshot,
)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class ObservationDisposition(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"


class SnapshotCoordinatorStatus(StrEnum):
    ACTIVE = "active"
    FAILED = "failed"


class SnapshotCoordinatorError(RuntimeError):
    """Base class for coordinator failures."""


class SnapshotWriterViolationError(SnapshotCoordinatorError):
    """A non-owner thread attempted to mutate or assess coordinator state."""


class UnexpectedSnapshotSourceError(SnapshotCoordinatorError):
    """An observation source is not declared by the coordinator policy."""


class ObservationIdentityConflictError(SnapshotCoordinatorError):
    """An observation ID was reused for different immutable content."""


class SnapshotCoordinatorFailedError(SnapshotCoordinatorError):
    """The coordinator has latched a terminal failure."""

    def __init__(self, cause: BaseException) -> None:
        self.cause = cause
        super().__init__(
            f"snapshot coordinator failed with {type(cause).__name__}: {cause}"
        )


class SnapshotAssembler(Protocol[T_co]):
    """Pure application adapter from ordered source views to a typed value."""

    def build(
        self,
        *,
        observations: tuple[SourceObservation[object], ...],
        metadata: DecisionSnapshotMetadata,
    ) -> T_co: ...


class SnapshotEvidencePort(Protocol[T_contra]):
    """Non-blocking bounded publication port for snapshot evidence."""

    def publish(
        self,
        publication: DecisionSnapshotPublication[T_contra],
    ) -> None: ...


class SnapshotIdentityPolicy(Protocol):
    def create(
        self,
        *,
        scope: str,
        snapshot_sequence: int,
        policy_version: int,
        observation_ids: tuple[ObservationId, ...],
    ) -> DecisionSnapshotId: ...


class Sha256SnapshotIdentityPolicy:
    """Stable content-framed identity suitable for deterministic replay."""

    def create(
        self,
        *,
        scope: str,
        snapshot_sequence: int,
        policy_version: int,
        observation_ids: tuple[ObservationId, ...],
    ) -> DecisionSnapshotId:
        payload = json.dumps(
            {
                "observation_ids": [str(item) for item in observation_ids],
                "policy_version": policy_version,
                "scope": scope,
                "snapshot_sequence": snapshot_sequence,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return DecisionSnapshotId(hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotCoordinatorResult(Generic[T]):
    assessment: SnapshotAssessment
    publication: DecisionSnapshotPublication[T] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotCoordinatorView(Generic[T]):
    status: SnapshotCoordinatorStatus
    scope: str
    policy_version: int
    configured_sources: int
    retained_sources: int
    retained_observation_ids: int
    snapshot_sequence: int
    last_assessment: SnapshotAssessment | None
    latest_publication: DecisionSnapshotPublication[T] | None
    failure_type: str | None
    failure_message: str | None


class SnapshotCoordinator(Generic[T]):
    """Retain latest bounded observations and publish coherent typed inputs."""

    def __init__(
        self,
        *,
        scope: str,
        policy: SnapshotPolicy,
        assembler: SnapshotAssembler[T],
        identity_policy: SnapshotIdentityPolicy | None = None,
        evidence_port: SnapshotEvidencePort[T] | None = None,
        max_seen_observation_ids: int = 4096,
    ) -> None:
        if not scope or scope != scope.strip():
            raise ValueError("scope must be non-empty and trimmed")
        if max_seen_observation_ids < len(policy.source_rules):
            raise ValueError(
                "max_seen_observation_ids cannot be below source count"
            )
        self._scope = scope
        self._policy = policy
        self._assembler = assembler
        self._identity_policy = (
            identity_policy or Sha256SnapshotIdentityPolicy()
        )
        self._evidence_port = evidence_port
        self._max_seen_observation_ids = max_seen_observation_ids
        self._writer_thread_id = get_ident()
        self._latest: dict[
            SnapshotSourceId, SourceObservation[object]
        ] = {}
        self._seen: OrderedDict[
            ObservationId, SourceObservation[object]
        ] = OrderedDict()
        self._source_issues: dict[SnapshotSourceId, SnapshotIssue] = {}
        self._last_fingerprint: tuple[ObservationId, ...] | None = None
        self._snapshot_sequence = 0
        self._last_assessment: SnapshotAssessment | None = None
        self._latest_publication: DecisionSnapshotPublication[T] | None = None
        self._failure: BaseException | None = None

    def accept(
        self,
        observation: SourceObservation[object],
    ) -> ObservationDisposition:
        """Accept one configured observation or reject it explicitly."""

        self._assert_writer()
        self._raise_if_failed()
        if observation.source_id not in set(self._policy.source_ids):
            raise UnexpectedSnapshotSourceError(
                f"source {observation.source_id!s} is not configured"
            )

        prior = self._seen.get(observation.observation_id)
        if prior is not None:
            if prior != observation:
                error = ObservationIdentityConflictError(
                    "observation_id was reused for different content"
                )
                self._failure = error
                raise error
            return ObservationDisposition.DUPLICATE

        current = self._latest.get(observation.source_id)
        if (
            current is not None
            and current.source_sequence is not None
            and (
                observation.source_sequence is None
                or observation.source_sequence <= current.source_sequence
            )
        ):
            self._source_issues[observation.source_id] = SnapshotIssue(
                code=SnapshotIssueCode.SOURCE_SEQUENCE_REGRESSION,
                source_ids=(observation.source_id,),
                reason="source sequence did not advance",
            )
            self._remember(observation)
            return ObservationDisposition.OUT_OF_ORDER

        self._latest[observation.source_id] = observation
        self._source_issues.pop(observation.source_id, None)
        self._remember(observation)
        return ObservationDisposition.APPLIED

    def evaluate(
        self,
        *,
        now_ns: UnixNanos,
        now_monotonic_ns: MonotonicNanos,
        clock_status: HealthStatus,
    ) -> SnapshotCoordinatorResult[T]:
        """Assess current inputs and publish at most one new typed snapshot."""

        self._assert_writer()
        self._raise_if_failed()
        assessed = assess_snapshot(
            policy=self._policy,
            observations=tuple(self._latest.values()),
            scope=self._scope,
            now_ns=now_ns,
            now_monotonic_ns=now_monotonic_ns,
            clock_status=clock_status,
        )
        assessment = assessed.assessment
        if self._source_issues:
            ordered_pending = tuple(
                self._source_issues[source_id]
                for source_id in self._policy.source_ids
                if source_id in self._source_issues
            )
            assessment = SnapshotAssessment(
                readiness=SnapshotReadiness.NOT_READY,
                issues=assessment.issues + ordered_pending,
                policy_version=self._policy.policy_version,
            )
        self._last_assessment = assessment
        if assessment.readiness is not SnapshotReadiness.READY:
            return SnapshotCoordinatorResult(
                assessment=assessment,
                publication=None,
            )

        observation_ids = tuple(
            item.observation_id for item in assessed.ordered_observations
        )
        if observation_ids == self._last_fingerprint:
            return SnapshotCoordinatorResult(
                assessment=assessment,
                publication=None,
            )

        next_sequence = self._snapshot_sequence + 1
        metadata = DecisionSnapshotMetadata(
            snapshot_id=self._identity_policy.create(
                scope=self._scope,
                snapshot_sequence=next_sequence,
                policy_version=self._policy.policy_version,
                observation_ids=observation_ids,
            ),
            scope=self._scope,
            snapshot_sequence=next_sequence,
            assembled_at_ns=now_ns,
            assembled_at_monotonic_ns=now_monotonic_ns,
            policy_version=self._policy.policy_version,
            observation_ids=observation_ids,
            coherence=assessed.coherence,
        )
        try:
            value = self._assembler.build(
                observations=assessed.ordered_observations,
                metadata=metadata,
            )
            publication = DecisionSnapshotPublication(
                metadata=metadata,
                assessment=assessment,
                value=value,
            )
            if self._evidence_port is not None:
                self._evidence_port.publish(publication)
        except BaseException as error:
            self._failure = error
            raise SnapshotCoordinatorFailedError(error) from error

        self._snapshot_sequence = next_sequence
        self._last_fingerprint = observation_ids
        self._latest_publication = publication
        return SnapshotCoordinatorResult(
            assessment=assessment,
            publication=publication,
        )

    def view(self) -> SnapshotCoordinatorView[T]:
        """Return immutable diagnostics without granting trading permission."""

        failure = self._failure
        return SnapshotCoordinatorView(
            status=(
                SnapshotCoordinatorStatus.ACTIVE
                if failure is None
                else SnapshotCoordinatorStatus.FAILED
            ),
            scope=self._scope,
            policy_version=self._policy.policy_version,
            configured_sources=len(self._policy.source_rules),
            retained_sources=len(self._latest),
            retained_observation_ids=len(self._seen),
            snapshot_sequence=self._snapshot_sequence,
            last_assessment=self._last_assessment,
            latest_publication=self._latest_publication,
            failure_type=None if failure is None else type(failure).__name__,
            failure_message=None if failure is None else str(failure),
        )

    def _remember(self, observation: SourceObservation[object]) -> None:
        self._seen[observation.observation_id] = observation
        if len(self._seen) > self._max_seen_observation_ids:
            self._seen.popitem(last=False)

    def _assert_writer(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise SnapshotWriterViolationError(
                "snapshot coordinator may only be used by its owner thread"
            )

    def _raise_if_failed(self) -> None:
        if self._failure is not None:
            raise SnapshotCoordinatorFailedError(
                self._failure
            ) from self._failure


__all__ = [
    "ObservationDisposition",
    "ObservationIdentityConflictError",
    "Sha256SnapshotIdentityPolicy",
    "SnapshotAssembler",
    "SnapshotCoordinator",
    "SnapshotCoordinatorError",
    "SnapshotCoordinatorFailedError",
    "SnapshotCoordinatorResult",
    "SnapshotCoordinatorStatus",
    "SnapshotCoordinatorView",
    "SnapshotEvidencePort",
    "SnapshotIdentityPolicy",
    "SnapshotWriterViolationError",
    "UnexpectedSnapshotSourceError",
]
