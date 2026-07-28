"""Generic decision-snapshot contracts, policy and readiness assessment.

This package owns bounded observation metadata and coherence rules. It does
not own source state, application-specific payloads or runtime coordination.
"""

from .assessment import SnapshotAssessmentResult, assess_snapshot
from .model import (
    CoherenceGroupId,
    CoherenceMeasurement,
    DecisionSnapshotId,
    DecisionSnapshotMetadata,
    DecisionSnapshotPublication,
    ObservationId,
    SnapshotAssessment,
    SnapshotIssue,
    SnapshotIssueCode,
    SnapshotReadiness,
    SnapshotSourceId,
    SourceObservation,
)
from .policy import (
    MAX_COHERENCE_GROUPS,
    MAX_DURATION_NS,
    MAX_POLICY_SOURCES,
    MAX_SOURCES_PER_GROUP,
    CoherenceGroup,
    SnapshotPolicy,
    SourceFreshnessRule,
)

__all__ = [
    "MAX_COHERENCE_GROUPS",
    "MAX_DURATION_NS",
    "MAX_POLICY_SOURCES",
    "MAX_SOURCES_PER_GROUP",
    "CoherenceGroup",
    "CoherenceGroupId",
    "CoherenceMeasurement",
    "DecisionSnapshotId",
    "DecisionSnapshotMetadata",
    "DecisionSnapshotPublication",
    "ObservationId",
    "SnapshotAssessment",
    "SnapshotAssessmentResult",
    "SnapshotIssue",
    "SnapshotIssueCode",
    "SnapshotPolicy",
    "SnapshotReadiness",
    "SnapshotSourceId",
    "SourceFreshnessRule",
    "SourceObservation",
    "assess_snapshot",
]
