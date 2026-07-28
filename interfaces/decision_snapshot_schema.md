# Decision Snapshot Schema

Status: Accepted by ADR-009; implemented by T025/T026

## Purpose

The Snapshot Infrastructure creates deterministic, immutable decision inputs
from independently owned source states. It does not claim physical
simultaneity and does not become a second authority for market, feature,
account or health state.

## Public Packages

```text
cex_quant.snapshots
  SourceObservation
  SourceFreshnessRule
  CoherenceGroup
  SnapshotPolicy
  SnapshotAssessment
  DecisionSnapshotMetadata
  DecisionSnapshotPublication
  assess_snapshot

cex_quant.runtime
  SnapshotCoordinator
  SnapshotAssembler
  SnapshotEvidencePort
  SnapshotIdentityPolicy
```

## Observation

`SourceObservation[T]` contains:

- typed observation and source identities;
- application scope;
- source fact `as_of_ns`;
- UTC receive/publication time;
- process-local monotonic acceptance time;
- schema version and optional source sequence;
- one immutable, canonical typed source view.

Raw venue payloads and unbounded histories are prohibited.

## Readiness

A publication requires:

- every required source;
- matching scope and supported schema;
- healthy clock;
- event age within its source rule;
- arrival age within its source rule;
- no excessive future timestamp;
- no monotonic regression;
- every coherence group within its own skew threshold;
- no pending source-sequence regression;
- successful application-specific assembly.

V1 publishes only `READY`. It has no degraded-but-tradable state.

## Ordering and Identity

Source rules and coherence groups are ordered tuples. Published observation
IDs follow policy source order. One coordinator publishes at most once for an
unchanged ordered observation-ID fingerprint.

The default identity is a SHA-256 digest over a canonical framing of:

```text
scope
snapshot_sequence
policy_version
ordered observation IDs
```

The hash is an identity mechanism, not a secret or authentication primitive.

## Ownership and Restart

- authoritative state remains with each source engine;
- Runtime owns one `SnapshotCoordinator` per declared application scope;
- the coordinator retains at most one latest observation per configured
  source and a bounded observation-ID conflict cache;
- the application owns a pure typed assembler;
- a bounded, non-blocking `SnapshotEvidencePort` receives publications;
- a restarted coordinator begins empty and `NOT_READY`;
- persisted pre-restart snapshots are evidence, not trading permission.

## Failure Semantics

Missing, stale, skewed or unhealthy inputs return a typed `NOT_READY`
assessment without publication.

Observation-ID conflict, assembler failure or evidence-port failure latches
the coordinator failed. Source sequence regression rejects that update and
blocks publication until a newer valid source observation arrives.

## Compatibility

The schema is additive. It does not change the current single-instrument
Strategy, Risk, OMS, Execution or persistent journal contracts.
