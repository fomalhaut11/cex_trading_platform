# ADR-015 Bounded Execution Stage and Width-One Compatibility

## Status

Accepted for bounded credential-free offline implementation - 2026-08-05.

The project owner confirmed that overlapping and parallel multi-leg execution
is a definite platform requirement and authorized continuation after the
direction was recorded in ADR-011 section 32. This ADR accepts the detailed
contract and migration boundary for T051/A022.

Acceptance authorizes only the width-one compatibility implementation and the
offline evidence needed to prove the Stage boundary. It does not authorize a
parallel dispatcher, Binance or OKX Testnet, production endpoints, credentials
or real-money execution. The existing external-execution gates remain in
force.

Reviewed baseline:

`f222b39`

## Context

ADR-010 defines an immutable 2-to-16-leg economic target. ADR-011 and ADR-012
define one durable Order Group, one exact execution Action at a time and one
finite Risk permit for that Action. T046 composes those contracts into a
single-writer grouped Runtime.

That model is safe for terminal-serial execution, but it cannot express:

- several orders authorized from the same group revision;
- a bounded fan-out whose complete identities exist before its first I/O;
- a Risk decision over every possible partial outcome of that fan-out;
- per-Child UNKNOWN and reconciliation results inside one execution unit;
- fill-driven overlap between a working leader and one or more hedge orders.

Funding Carry may initially use terminal-serial execution. Triangular
arbitrage and option parity have a confirmed need for wider or overlapping
execution. Freezing the production composition root around a permanent
single-Action API would therefore force a later control-plane rewrite.

## Decision

Introduce a bounded immutable `ExecutionStage` between an execution Planner
and per-Child execution:

```text
BasketTargetIntent
  -> Order Group
  -> Execution Planner
  -> ExecutionStage[1..bounded actions]
  -> Portfolio Risk Stage decision and permit
  -> atomic local Stage/Action/Child preparation
  -> bounded per-Child venue I/O
  -> per-Child result vector
  -> reconciliation / next Stage
```

V1 is not removed. Existing terminal-serial behavior becomes an
`ExecutionStage` with one Action and `dispatch_width = 1`.

## Contract

### Identity

`ExecutionStageId` is a deterministic checksum over:

- Order Group identity;
- base group revision;
- exact `ExecutionPlanRef`;
- ordered complete Action checksums;
- declared dispatch width.

`ExecutionStagePermitId` is a deterministic checksum over the exact Stage,
Risk snapshot, policy version, validity and partial-execution envelope.

An Action retains its existing deterministic `GroupActionId`, and a Child
retains `child_order_id_for_action(action_id)`. Venues continue to receive
ordinary individual `OrderRequest` values.

### Bounds

The immutable contract has an independent hard maximum of 16 Actions per
Stage. A deployment may configure a smaller limit. The following are separate
dimensions:

```text
Basket leg count      2..16
Stage width           1..16
Stage dispatch width  1..Stage width
```

A Basket may be advanced by multiple smaller Stages. A Stage may not be used
to bypass per-leg or per-group Child-attempt limits.

### Base revision

Every Action in a Stage references the same `base_group_revision`. OMS
validates all Actions against that revision and prepares the complete Stage as
one journal mutation. Successful preparation advances the group revision once,
regardless of Stage width.

No second preparation may interleave with that mutation. Duplicate Stage,
Action, Child or permit identities fail closed unless replay proves identical
content.

### Risk authority

Basket admission remains distinct from Stage permission. Portfolio Risk
authorizes:

1. the complete exact Stage;
2. every individual Action checksum;
3. the conservative envelope covering any permitted partial-execution subset;
4. a finite authorization generation and validity interval.

An `ExecutionStagePermit` contains the exact per-Action permit evidence needed
by the existing Child guard. An Action permit included in a Stage cannot
authorize an Action outside that Stage.

The width-one implementation derives its Stage decision from the existing
exact Action assessment. For one Action, the only partial outcomes are no fill
and the permitted Action exposure; the existing conservative Action exposure
therefore forms the accepted width-one envelope. Wider envelope calculation
is a separately activated implementation requirement.

### Persistence order

Before the first venue call:

1. Portfolio Risk durably records Stage permission and its Action permits;
2. OMS durably records the complete Stage, permit, every Action and every
   Child request in one journal entry;
3. Runtime performs the immediate platform and Risk liveness checks;
4. Risk durably consumes Stage authority before its first external I/O;
5. each Action authority is consumed immediately before that Child I/O;
6. OMS records every dispatch and result independently.

A failure before step 2 makes no exchange call. A failure after Stage
consumption is recovery evidence and never permits blind recreation of the
Stage under a new identity.

### Single writer and concurrency

OMS, Portfolio Risk and Runtime mutation remain single-writer. A future Stage
dispatcher may perform bounded venue I/O concurrently, but returns results to
the owner thread for ordered state mutation.

No Gateway, callback or worker may mutate Order Group, Risk, Portfolio or
Accounting state directly.

### Result vector and UNKNOWN

Results are retained per Child. A Stage never collapses mixed results into a
false all-or-none outcome. A future result vector must distinguish at least:

- accepted;
- rejected;
- definitely not sent;
- unknown;
- later reconciled terminal evidence.

Any UNKNOWN places the Stage and Order Group into recovery-required control.
Automatic compensation is prohibited until every UNKNOWN Child is reconciled
or an explicit recovery authorization is issued. Cross-venue execution never
claims transactional atomicity.

### Planner and host capability

The Planner proposes an immutable Stage and owns no Risk, operator or I/O
authority. A host publishes a configured maximum Stage width and dispatch
width. A proposal exceeding host capability fails before Risk authorization
or persistence.

The first implementation supports only:

```text
max_stage_width = 1
max_dispatch_width = 1
```

The public Stage contract nevertheless supports the bounded wider form. A
parallel-capable host can later replace only dispatch and wider Risk-envelope
components; it must not change Basket, Portfolio truth, Accounting truth,
individual Gateway contracts or the production composition-root interface.

## State ownership

| State | Single writer | Readers |
|---|---|---|
| Stage/Action/Child preparation and result facts | OMS | Runtime, Risk, Operations |
| Stage permit, generation and consumption | Portfolio Risk Coordinator | Runtime, Operations |
| Venue I/O scheduling | Runtime Stage host | OMS/Risk only through ordered calls |
| Positions and account state | Portfolio | Risk, Strategy, Operations |
| Financial truth | Accounting | Applications, reporting, Operations |

Stage status is execution-control evidence. It is not `HEDGED`, profitable,
economically complete or financially final.

## Journal evolution

The OMS journal adds a Stage-prepared entry while retaining all V1 records.
Replay accepts the ordered mixed-version history without rewriting earlier
records. The Portfolio Risk journal adds Stage-permit issued and consumed
facts while retaining existing Action-permit evidence.

Recovery must reconstruct the same Stage-to-Action-to-Child ownership and must
reject:

- changed Stage content under an existing identity;
- multiple Stage owners for one Action or Child;
- a Stage whose base revision does not match replay order;
- a permit whose Action set or checksums differ from the Stage;
- unsupported or unbounded Stage width.

## Compatibility

The following remain compatibility-frozen:

- `BasketTargetIntent` and Objective metadata;
- `OrderGroupAdmission` and portfolio reservation identity;
- individual `ExecutionAction` and `OrderRequest` meaning;
- existing Binance and future OKX Gateway protocols;
- Portfolio position truth and Accounting financial facts;
- external authorization gates.

Legacy `GroupActionPreparedEntry` replay and direct one-Action preparation
remain supported. New grouped Runtime execution uses the width-one Stage path.

## Rejected alternatives

### Keep the production root single-Action until a strategy needs parallelism

Rejected because the known requirement would later change Planner, Risk, OMS,
journal, recovery and deployment APIs together.

### Put several orders in a new Gateway request

Rejected because venues receive individual orders, have different protocol
capabilities and do not provide cross-venue atomicity.

### Let the Planner submit concurrently

Rejected because the Planner owns neither authority, persistence nor state.

### Treat independent Action permits as a Stage

Rejected because separately authorized Actions do not prove a conservative
partial-execution envelope or one atomic local preparation boundary.

### Enable a parallel dispatcher in the first implementation

Rejected for T051/A022. Width-one migration proves contract compatibility
without adding concurrency risk to the pre-production baseline.

## Consequences

Positive:

- the first Funding Carry loop retains simple serial behavior;
- the production root can depend on one stable Stage interface;
- triangular arbitrage, option parity and fill-driven hedging gain an additive
  evolution path;
- every Action and Child remains auditable and venue-neutral;
- Stage width and Basket size no longer become accidental synonyms.

Costs:

- OMS and Risk journals gain new versioned evidence;
- the grouped Runtime carries Stage and legacy one-Action compatibility during
  migration;
- wider Risk envelope calculation and bounded I/O scheduling still require
  focused implementation and acceptance before activation.

## Acceptance

T051/A022 require credential-free deterministic evidence for:

- deterministic Stage and permit identities;
- malformed, duplicate, stale and over-capacity rejection;
- width-one Planner and Runtime compatibility;
- atomic Stage/Action/Child persistence before I/O;
- Stage and Action permit issuance, validation and consumption;
- mixed legacy/Stage OMS journal replay;
- Risk journal replay and restart invalidation;
- accepted, rejected, definitely-not-sent and UNKNOWN outcomes;
- restart from PREPARED, TRANSMITTING, ACKNOWLEDGED and UNKNOWN evidence;
- unchanged Router/Gateway, Basket, Portfolio and Accounting contracts;
- full offline quality, coverage and architecture-fitness gates.

A022 completion grants no Testnet or production authority.
