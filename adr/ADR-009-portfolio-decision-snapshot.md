# ADR-009 Portfolio Decision Snapshot Model

## Status

Accepted — 2026-07-28.

Accepted by the project owner after Web GPT architecture review and Codex
repository verification.

Review evidence:

- `ai_collaboration/topics/funding_arbitrage/31_web_gpt_adr009_review.md`;
- `ai_collaboration/topics/funding_arbitrage/40_codex_adr009_review_response.md`;
- `ai_collaboration/topics/funding_arbitrage/90_resolution.md`.

This acceptance authorizes implementation of the generic Snapshot
Infrastructure described by this ADR. It does not authorize Funding Arbitrage
application code, Basket execution, Testnet or production trading.

## Context

The current runtime processes one canonical market event at a time. Existing
state owners publish immutable views:

- market-state engines publish L1 or order-book views;
- the feature engine publishes `FeatureSnapshot`;
- the Portfolio/Account engine publishes `AccountSnapshot`;
- health owners publish `HealthReport`;
- clock monitoring publishes health and offset evidence.

This is sufficient for deterministic single-instrument decisions. It is not
sufficient for a portfolio application that must relate observations from
multiple instruments, accounts and update cadences.

For example, a Funding Carry decision may require:

```text
Spot executable price
Perpetual executable price
Perpetual mark/index price
Funding rate and next funding time
Spot balance and position
Perpetual position and margin
Features
Clock and connector health
```

These values cannot arrive physically at the same instant. “Latest” alone is
unsafe: one value may be fresh while another is stale, delayed, invalid or
from a different account scope.

The system needs a deterministic logical decision snapshot without:

- moving ownership away from existing state engines;
- introducing a generic hot-path Event Bus;
- creating one universal object with optional fields for every strategy;
- allowing application code to read mutable state;
- using database transactions as live trading state;
- hiding timestamp skew or source quality.

## Decision Summary

Add a narrow, venue-neutral `cex_quant.snapshots` package containing common
observation metadata, readiness policy and deterministic assessment contracts.

Each concrete application continues to define its own typed decision snapshot.
For example:

```text
cex_quant.applications.carry.funding_arbitrage.CarryDecisionSnapshot
```

Runtime owns a single-writer coordinator per application scope. The
coordinator retains only the latest bounded source observations, evaluates the
accepted policy, invokes a pure application assembler and publishes an
immutable snapshot only when every mandatory gate is ready.

The snapshot is a derived decision input. It is not authoritative market,
account, feature, order or financial state.

## 1. Terminology

### Source view

An immutable value published by an authoritative state owner, such as
`L1View`, `FeatureSnapshot`, `AccountSnapshot` or `HealthReport`.

### Source observation

A source view plus common identity, scope, time, sequence and provenance
metadata used for freshness and coherence assessment.

### Application decision snapshot

A typed immutable object containing exactly the inputs required by one
application. It contains source references and assessment metadata.

### Coherence group

A named set of sources whose event times must fall within a configured maximum
skew. Different source groups may use different skew and freshness policies.

### Readiness

The result of evaluating completeness, identity, health, freshness, monotonic
age and coherence. A trading application receives only a `READY` snapshot.

## 2. Package Topology

The planned package boundary is:

```text
src/cex_quant/
  snapshots/
    __init__.py
    model.py
    policy.py
    assessment.py

  applications/
    carry/
      funding_arbitrage/
        snapshot.py

  runtime/
    snapshot_coordinator.py
```

Responsibilities:

| Package | Responsibility |
|---|---|
| `snapshots` | Generic source stamps, policy, issue codes, readiness and metadata |
| authoritative state packages | Own and publish their immutable source views |
| application snapshot module | Define typed inputs and pure assembly for one application |
| `runtime.snapshot_coordinator` | Serialize source delivery, retain bounded latest observations and publish ready snapshots |
| recorder | Persist accepted snapshot evidence through a bounded side channel |
| strategy | Consume typed immutable snapshots; perform no I/O |
| risk | Independently recheck required snapshot identity and readiness |

`snapshots` depends only on `core` and minimal public health types. It cannot
depend on market data, portfolio, features, strategy, risk, OMS, applications,
runtime or venue adapters.

Applications may depend on `snapshots` and public domain views. Applications
cannot depend on runtime or venue adapters. Runtime may depend on both.

## 3. Common Public Contracts

The following is the intended semantic API. Exact Python naming can change
during implementation review, but any change must preserve the invariants.

### 3.1 Identities

```python
SnapshotSourceId
ObservationId
DecisionSnapshotId
CoherenceGroupId
```

These are strongly typed identifiers. Public APIs do not interchange them as
arbitrary strings.

### 3.2 Source observation

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SourceObservation(Generic[T_co]):
    observation_id: ObservationId
    source_id: SnapshotSourceId
    scope: str
    as_of_ns: UnixNanos
    received_at_ns: UnixNanos
    accepted_at_monotonic_ns: MonotonicNanos
    schema_version: int
    value: T_co
    source_sequence: int | None = None
```

Invariants:

- IDs and scope are non-empty and trimmed;
- schema version is positive;
- source sequence is non-negative when present;
- `as_of_ns` is the externally comparable time of the underlying fact or
  immutable state view;
- `received_at_ns` is the UTC receive/publication time;
- `accepted_at_monotonic_ns` is process-local and used only for live elapsed
  time;
- `value` is an immutable typed source view;
- source-native payloads cannot be used as `value`;
- one observation contains one bounded view, not an unbounded history.

`accepted_at_monotonic_ns` is meaningless across process restarts and must
never be compared between processes.

### 3.3 Policy

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SourceFreshnessRule:
    source_id: SnapshotSourceId
    max_event_age_ns: DurationNanos
    max_arrival_age_ns: DurationNanos
    max_future_skew_ns: DurationNanos
    required: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class CoherenceGroup:
    group_id: CoherenceGroupId
    source_ids: tuple[SnapshotSourceId, ...]
    max_event_time_skew_ns: DurationNanos


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotPolicy:
    source_rules: tuple[SourceFreshnessRule, ...]
    coherence_groups: tuple[CoherenceGroup, ...]
    policy_version: int
```

Policy invariants:

- source IDs are unique and deterministically ordered;
- coherence-group IDs are unique;
- every coherence source has a source rule;
- every group has at least two distinct sources;
- all durations are non-negative and below configured hard safety limits;
- required source count is bounded;
- policy version is positive.

One global skew threshold is rejected. Price sources, funding state and
account/margin state have different cadences. Example:

```text
executable_price_group:
  Spot BBA
  Perpetual BBA
  tight maximum skew

derivative_reference_group:
  Perpetual mark
  Perpetual index
  separate maximum skew

funding:
  independent maximum event age

account_margin:
  independent maximum event and arrival age
```

### 3.4 Readiness and issues

```python
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


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotAssessment:
    readiness: SnapshotReadiness
    issues: tuple[SnapshotIssue, ...]
    policy_version: int
```

Issues use stable machine-readable codes. They are deterministically ordered
by policy source/group order and then issue code.

`READY` requires no issues. `NOT_READY` requires at least one issue. The first
implementation does not deliver a “degraded but tradable” snapshot. A future
degraded mode requires a new explicit ADR or policy version.

### 3.5 Published metadata

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CoherenceMeasurement:
    group_id: CoherenceGroupId
    observed_skew_ns: DurationNanos


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
```

Observation IDs follow deterministic policy order. Snapshot sequence is
strictly increasing within one coordinator instance and scope.

Snapshot identity is supplied by an explicit deterministic identity policy
using scope, sequence, policy version and ordered observation IDs. The ADR
does not mandate a hash algorithm.

## 4. Time Semantics

Freshness and coherence use different clocks for different questions.

### Event freshness

```text
event_age = now_unix_ns - observation.as_of_ns
```

This detects venue or source facts that were already old when received. It
requires healthy wall-clock evidence. A future timestamp beyond the configured
future-skew allowance is not ready.

### Local arrival freshness

```text
arrival_age =
    now_monotonic_ns - observation.accepted_at_monotonic_ns
```

This detects a locally silent source without relying on wall-clock duration.
Monotonic regression is immediately not ready.

### Coherence

For each coherence group:

```text
observed_skew =
    max(source.as_of_ns) - min(source.as_of_ns)
```

Only sources named in the group participate. Funding or account state cannot
silently widen or weaken the executable-price group threshold.

### Snapshot time

`assembled_at_ns` is the injected UTC assembly time. It is not presented as
the event time of every source. Every source keeps its own `as_of_ns`.

The architecture does not claim physical simultaneity.

## 5. Coordinator and Assembly

### 5.1 Runtime coordinator

One coordinator instance owns one declared application scope, such as a Carry
pair and account set.

It:

- is called by one serialized runtime writer;
- accepts only configured source IDs;
- retains at most one latest observation per configured source in v1;
- rejects conflicting reuse of an observation ID;
- rejects source-sequence regression where sequence exists;
- evaluates readiness with injected UTC, monotonic and clock-health inputs;
- does no network, filesystem or database I/O;
- invokes the typed application assembler only after generic readiness is
  `READY`;
- publishes at most one snapshot per ordered observation-ID fingerprint;
- increments a deterministic local snapshot sequence;
- exposes the latest assessment for monitoring.

V1 does not retain unbounded histories or search backward for a “better”
timestamp alignment. If latest observations exceed a coherence threshold, it
waits for new data.

Any future bounded history/time-matching algorithm requires explicit limits,
selection rules and deterministic replay tests.

### 5.2 Application assembler

The application owns a pure typed assembler. Example:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CarrySnapshotInputs:
    spot_bba: SourceObservation[L1View]
    perpetual_bba: SourceObservation[L1View]
    perpetual_mark: SourceObservation[MarkPriceView]
    funding: SourceObservation[FundingView]
    spot_account: SourceObservation[AccountSnapshot]
    perpetual_account: SourceObservation[AccountSnapshot]
    margin: SourceObservation[MarginSnapshot]
    features: SourceObservation[FeatureSnapshot]
    health: SourceObservation[HealthReport]


class CarrySnapshotAssembler:
    def build(
        self,
        *,
        inputs: CarrySnapshotInputs,
        metadata: DecisionSnapshotMetadata,
    ) -> CarryDecisionSnapshot: ...
```

The assembler:

- verifies application identities and instrument/account relationships;
- performs no I/O;
- cannot change authoritative source state;
- cannot weaken generic readiness;
- uses no raw venue payload;
- returns a frozen, slotted, keyword-only typed snapshot;
- performs any application-specific validation not expressible by generic
  source freshness or coherence rules.

Application validation failure returns a typed not-ready result to runtime. It
does not invoke Strategy.

## 6. Feature and Account Treatment

### Features

`FeatureSnapshot` contains values with individual feature metadata. A wrapper
must not hide required-feature quality or use a misleading newest timestamp.

An application must either:

1. treat each required feature as a logical source; or
2. wrap one Feature snapshot using the oldest required feature `as_of_ns`
   while preserving all per-feature metadata.

Missing, `DEGRADED`, `INVALID` or expired required features remain fail-closed
according to application/Risk policy.

### Accounts and margin

An `AccountSnapshot` with no authoritative `as_of_time_ns` is incomplete for a
trading decision. Account and margin scopes must match the accounts selected
for the Basket.

The snapshot layer does not calculate balances, margin or liquidation. Those
remain Portfolio/Account responsibilities.

### Health

Required connector, private-stream, clock, OMS-recovery and operator health
must be healthy before publication. Health inclusion in a typed application
snapshot does not replace the mandatory runtime health gate.

## 7. State Ownership

| State or value | Owner | Snapshot-layer role |
|---|---|---|
| Market state | Market State Engine | Read immutable view only |
| Funding state | Funding State owner introduced with implementation | Read immutable view only |
| Feature state | Online Feature Engine | Read immutable view only |
| Account/position state | Portfolio/Account Engine | Read immutable view only |
| Margin/collateral state | Portfolio/Account Engine | Read immutable view only |
| Health state | Owning component/health aggregator | Read immutable report only |
| Latest source observations | Runtime coordinator | Bounded references for one application scope |
| Readiness assessment | Runtime coordinator | Derived, replace-only |
| Application decision snapshot | Runtime coordinator using pure application assembler | Immutable published decision input |
| Strategy state | Application strategy instance | Consumes snapshot |
| Risk decision | Risk Engine | Independently validates snapshot reference/readiness |

The coordinator is not a second writer for any source state.

## 8. Strategy and Risk Boundary

Strategy receives a typed application snapshot, not a mutable state service:

```python
def on_snapshot(
    snapshot: CarryDecisionSnapshot,
) -> tuple[DecisionIntent, ...]: ...
```

Every decision intent records the `DecisionSnapshotId` or an equivalent
causation reference. This creates traceability from:

```text
source observations
  -> decision snapshot
  -> strategy intent
  -> risk decision
  -> OMS state
```

Risk must reject:

- unknown snapshot identity;
- a non-ready snapshot;
- policy-version mismatch;
- intent/snapshot scope mismatch;
- snapshot expiry between Strategy and Risk;
- any additional portfolio-risk violation.

Snapshot readiness is necessary but not sufficient for Risk approval.

## 9. Failure Semantics

The following outcomes are fail-closed for new decisions:

| Failure | Required behavior |
|---|---|
| Missing required source | No snapshot publication |
| Stale event time | No snapshot publication |
| Stale local arrival | No snapshot publication |
| Excessive coherence skew | No snapshot publication |
| Unhealthy or unknown clock | No snapshot publication |
| Monotonic regression | Latch unhealthy; no publication |
| Source sequence regression | Reject update and report not ready |
| Observation-ID conflict | Latch coordinator failure |
| Unsupported schema | No publication |
| Application identity mismatch | No publication |
| Assembler exception | Latch application/coordinator failure |
| Recorder side-channel overflow | Explicit health degradation/halt policy; no silent loss |

A prior ready snapshot may remain available for diagnostics but cannot be
silently reused for a new trading decision after current readiness becomes
not ready.

## 10. Recording, Replay and Restart

### Recording

Recorder evidence contains:

- snapshot metadata;
- ordered observation IDs;
- policy version;
- coherence measurements;
- application payload schema version;
- deterministic payload/checksum.

Recording uses a bounded side channel. No blocking filesystem I/O is added to
the core decision transition.

### Replay

Offline replay injects:

- source observations in declared order;
- UTC and monotonic replay clocks;
- clock health;
- the same policy version;
- deterministic identity policy.

The same input sequence must produce the same readiness assessments, snapshot
payloads and causation chain.

### Restart

Coordinator memory is rebuildable, not durable authority. On restart:

1. coordinator starts empty and not ready;
2. process-local monotonic timestamps from the prior process are discarded;
3. source owners recover/reconcile independently;
4. fresh or replayed observations repopulate the coordinator;
5. a new ready snapshot is required before Strategy runs.

Persisted pre-restart snapshots are evidence, not permission to resume
trading.

## 11. Boundedness

Each coordinator has immutable construction-time limits:

- maximum configured sources;
- maximum coherence groups;
- maximum sources per group;
- one latest observation per source in v1;
- maximum metadata and reason lengths;
- maximum observation-reference count;
- maximum published snapshot payload size at the recorder boundary.

No dictionary with arbitrary source IDs crosses the application public
contract. Typed application input fields or bounded deterministic tuples are
used.

## 12. Compatibility

This decision is additive.

It does not change:

- canonical market event contracts;
- existing per-instrument state engines;
- `FeatureSnapshot`;
- `AccountSnapshot`;
- the current single-instrument Strategy input path;
- current Risk, OMS or Execution contracts;
- existing persistent journals.

The existing single-instrument pipeline remains operational. A later ADR and
implementation task may add an adapter that publishes typed decision
snapshots alongside it.

No existing `snapshot()` method is redefined. “Snapshot” in this ADR means a
correlated application decision input, not an order-book REST snapshot or OMS
reconciliation snapshot.

## 13. Alternatives Considered

### Generic hot-path Event Bus

Rejected for this need. It distributes events but does not itself create
coherent state, freshness policy or single-writer ownership. It would also
weaken explicit ordering and backpressure.

### Portfolio module owns all market and feature state

Rejected. Portfolio owns account, position, collateral and valuation state,
not canonical market or feature state.

### Universal decision snapshot

Rejected. A single object with optional Spot, Futures, Options, account,
margin and strategy fields becomes an untyped dumping ground and couples
unrelated applications.

### Application reads all state services directly

Rejected. It produces inconsistent read timing, hidden I/O and difficult
replay.

### Database transaction snapshot

Rejected for live decisions. Database records are evidence and recovery
inputs, not the hot-path source of truth.

### UTC time only

Rejected. Wall time is needed for cross-source event comparison, but local
silence and elapsed duration require monotonic time.

### Retain unbounded history and choose closest observations

Rejected. It violates bounded-memory and makes selection/replay semantics
complex. V1 uses latest-only observations and waits when skew is excessive.

### Put all snapshot contracts in `core`

Rejected. Core would acquire policy and readiness concerns. The narrow
`snapshots` package keeps the dependency explicit while still depending only
on foundational types.

## 14. Consequences

### Positive

- preserves current state ownership;
- makes cross-source freshness and skew explicit;
- supports Funding and future N-leg applications;
- keeps application snapshots strongly typed;
- preserves deterministic synchronous processing;
- adds no venue leakage or blocking I/O;
- provides a reproducible causation chain.

### Costs

- adds a new public package and policy schema;
- requires adapters from existing state views into source observations;
- requires explicit clock, health and scope wiring;
- adds snapshot recording and replay fixtures;
- requires every application to define a typed snapshot contract.

### Risks

- poorly chosen skew thresholds can reject too much or admit incoherent data;
- using newest rather than oldest required feature time can hide stale inputs;
- treating persisted snapshots as restart authority would be unsafe;
- generic snapshot utilities could expand into a dumping ground unless package
  scope remains narrow.

## 15. Required Documentation Changes After Acceptance

If accepted, implementation changes must update:

- `architecture/module_topology.md`;
- `architecture/state_ownership.md`;
- `architecture/state_management.md`;
- `architecture/time_synchronization.md`;
- a new `interfaces/decision_snapshot_schema.md`;
- `development/coding_conventions.md` if generic type rules require it;
- package `__init__.py` responsibility and explicit `__all__`;
- testing and replay documentation.

The accepted ADR is the authority; this proposed file does not change those
documents yet.

## 16. Required Tests

### Contract tests

- invalid IDs, scopes, versions and durations;
- duplicate source/group IDs;
- coherence group with missing or duplicate members;
- unbounded policy construction;
- deterministic issue ordering;
- immutable values and tuples.

### Readiness tests

- every required source missing independently;
- event-time stale and future-skew cases;
- arrival stale using monotonic time;
- monotonic regression;
- source-sequence regression;
- exact threshold boundaries;
- multiple coherence groups with different thresholds;
- clock unknown/degraded/unhealthy;
- unsupported schema and scope mismatch.

### Coordinator tests

- one writer and re-entrant/concurrent rejection;
- duplicate observation idempotency;
- conflicting observation-ID reuse;
- exactly one publication per observation fingerprint;
- deterministic sequence and source order;
- bounded retained observations;
- assembler exception latching;
- prior snapshot not reused after readiness loss.

### Replay and restart tests

- identical inputs produce identical snapshot payload/digest;
- different arrival order follows the documented caller order;
- restart begins not ready;
- prior-process monotonic values are never reused;
- replay clocks reproduce freshness outcomes;
- corrupt recorded snapshot evidence fails explicitly.

### Application acceptance

- Funding Spot/Perpetual executable-price skew;
- slower funding source using its own age rule;
- Spot and Perpetual account scope mismatch;
- missing margin state;
- feature quality/freshness failure;
- healthy snapshot delivered to Strategy and referenced by Risk/intent;
- synthetic three-source application proving no two-source assumption.

## 17. Implementation Authorization

The architecture-review gate was satisfied on 2026-07-28:

1. Web GPT accepted the architecture direction;
2. Codex verified the review against the current repository;
3. the project owner accepted this ADR;
4. the public package and dependency boundaries in this ADR were retained;
5. implementation tasks T025, T026 and acceptance A012 were assigned.

Authorized implementation scope:

- generic `cex_quant.snapshots` contracts, policy and assessment;
- deterministic runtime snapshot coordinator;
- bounded recording/replay evidence for generic decision snapshots;
- contract, readiness, coordinator, replay, restart and synthetic typed-
  application tests;
- required documentation and explicit package exports.

Not authorized by this ADR:

- `applications/carry/funding_arbitrage` implementation;
- Basket Intent, Parent/Child OMS, Portfolio Risk or Financial Ledger code;
- Testnet multi-leg execution;
- production or real-money trading.

ADR-010 may now be drafted and reviewed independently. Its implementation
remains unauthorized until ADR-010 is accepted.

## 18. Review Questions

External review should answer:

1. Is a narrow generic `snapshots` package preferable to placing common
   contracts in `core`, `portfolio` or `runtime`?
2. Is latest-only source retention sufficient for v1, with excessive skew
   causing wait/fail-closed?
3. Are separate event-age, arrival-age and coherence-skew checks necessary and
   correctly assigned to UTC versus monotonic clocks?
4. Should v1 have only `READY` and `NOT_READY`, prohibiting degraded-but-
   tradable snapshots?
5. Is the division between generic snapshot assessment and application-typed
   assembly sufficiently strict?
6. Should every intent require a `DecisionSnapshotId` causation reference?
7. Are restart semantics appropriately fail-closed?
8. Which fields or ownership rules remain underspecified before acceptance?
