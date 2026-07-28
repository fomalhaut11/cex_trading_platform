# ADR-010 Basket Intent Architecture

## Status

Accepted — 2026-07-28.

Accepted by the project owner after a Codex compatibility review against the
current `core`, `strategy`, `runtime`, `risk` and `oms` implementation.

Review evidence:

- `ai_collaboration/topics/funding_arbitrage/41_codex_adr010_compatibility_review.md`;
- `ai_collaboration/topics/funding_arbitrage/90_resolution.md`.

Implementation evidence:

- T027, T028 and A013 completed on 2026-07-28;
- `interfaces/basket_intent_schema.md`;
- `tests/acceptance/test_basket_intents.py`;
- `ai_collaboration/topics/funding_arbitrage/50_codex_adr010_implementation_acceptance.md`.

The implementation passed 397 tests plus 129 subtests with 86.34% branch
coverage. It creates no OMS Order Group, child order or exchange request.

This acceptance authorizes only the generic Basket Intent contracts and
Strategy compatibility work assigned to T027/T028/A013. It does not authorize
Parent/Child OMS, Portfolio Risk, Funding Arbitrage, Testnet or production
trading.

## Context

The current Strategy boundary emits one `PositionTargetIntent`:

```text
one strategy
  -> one instrument target
  -> one Risk decision
  -> one OMS order
```

That remains correct for single-instrument decisions. It is insufficient when
the economic objective exists only as a portfolio transition.

Examples:

```text
Funding carry:
  target Spot BTC = +10
  target Perpetual BTC = -10

Calendar spread:
  target near Future = -5
  target far Future = +5

Option spread with hedge:
  target Call K1 = +10
  target Call K2 = -10
  target Perpetual Delta hedge = application-calculated target
```

Representing these as independent intents allows one leg to pass Risk and
reach Execution before the platform has validated the complete objective.
It also loses one durable identity connecting decision snapshot, Risk,
Parent/Child OMS, recovery and accounting.

ADR-009 established deterministic typed decision snapshots. ADR-010 must
define the venue-neutral strategy output that causally follows such a
snapshot, without embedding order instructions or application policy.

## Decision Summary

Add a generic, immutable and bounded N-leg `BasketTargetIntent` to the
Strategy domain.

The Basket represents one portfolio target objective. Each leg specifies a
canonical account/instrument scope and desired signed target quantity. It is
not an order and contains no order type, time-in-force, limit price, execution
sequence, venue payload or recovery callback.

V1 rules:

```text
2 <= leg_count <= configured_max_legs <= hard_cap
hard_cap = 16
```

Every Basket:

- reuses the existing cross-domain `IntentId` for its Basket identity;
- has unique, deterministically ordered leg identities;
- references the accepted `DecisionSnapshotId`;
- has a mandatory finite validity deadline;
- carries one strategy identity and a versioned objective classification;
- rejects duplicate account/instrument scopes;
- is evaluated as a complete immutable value;
- receives binary whole-Basket `ALLOW` or `REJECT` in V1;
- reaches no child submit until complete Basket Risk approval.

Existing `PositionTargetIntent` remains a first-class public contract and is
not silently converted into a public one-leg Basket.

## 1. Package Topology

Planned files:

```text
src/cex_quant/
  core/
    identifiers.py            # BasketLegId, ObjectiveTypeId;
                              # existing IntentId is reused

  strategy/
    model.py                  # DecisionIntent union remains public
    basket.py                 # Basket contracts and construction policy

  risk/
    portfolio.py              # future ADR-012 consumer

  runtime/
    basket_pipeline.py        # future composition after ADR-011/012
```

Ownership:

| Package | Responsibility |
|---|---|
| `core` | Cross-domain strongly typed Basket and leg identities |
| `strategy.basket` | Venue-neutral target contracts and structural policy |
| application | Select objective, accounts, instruments and target quantities |
| Risk | Assess the complete projected transition |
| OMS | Accept only a separately approved immutable group contract |
| Runtime | Preserve mandatory ordering and identity |

`strategy.basket` may depend on `core`, `instruments` and the accepted
snapshot identity contract. It cannot depend on Risk, OMS, Execution,
applications, runtime or venue adapters.

## 2. Public Contracts

The following is the intended semantic API. Exact names may change during
review, but the invariants are normative.

### 2.1 Identities and current-code compatibility

The current code already defines:

```python
IntentId = NewType("IntentId", str)
```

Both `PositionTargetIntent` and Risk/OMS use `IntentId`. A Basket is another
kind of decision intent, so it reuses this identity instead of introducing a
parallel `BasketIntentId`.

Add to `cex_quant.core`:

```python
BasketLegId = NewType("BasketLegId", str)
ObjectiveTypeId = NewType("ObjectiveTypeId", str)
```

`BasketLegId` and `ObjectiveTypeId` cross Strategy, Risk, OMS, Accounting and
application boundaries. They cannot be interchanged with `IntentId`,
`ClientOrderId` or raw strings at typed public boundaries.

Using the existing `IntentId` preserves:

- one `intent_id` attribute across every `DecisionIntent`;
- the existing `StrategyRuntime` duplicate-ID algorithm;
- current Risk/OMS causation terminology;
- simpler unions and replay tooling.

### 2.2 Leg

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketTargetLeg:
    leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    target_quantity: Quantity
    reason: str = ""
```

Semantics:

- `target_quantity` is the desired final signed canonical position;
- it is not an order quantity;
- zero is valid for closing an existing leg;
- product quantity and contract multiplier semantics remain with Instrument;
- `account_id` is a canonical account identity, not a credential;
- Instrument venue and configured account venue must agree during Risk
  context assembly;
- the reason is bounded diagnostic text, not executable policy.

V1 rejects two legs with the same `(account_id, instrument_id)`. The
application must net them into one target before emitting the Basket.
The same Instrument may appear for different accounts when the configured
strategy scope explicitly permits it.

### 2.3 Basket

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketTargetIntent:
    intent_id: IntentId
    strategy_id: StrategyId
    decision_snapshot_id: DecisionSnapshotId
    objective: ObjectiveTypeRef
    legs: tuple[BasketTargetLeg, ...]
    decision_time_ns: UnixNanos
    valid_until_ns: UnixNanos
    policy_version: int
    reason: str = ""
```

Required invariants:

- Basket, Strategy and Snapshot IDs are non-empty;
- the objective reference is registered and versioned;
- `policy_version` is positive;
- validity is finite and cannot precede decision time;
- leg count is between two and the hard cap;
- configured policy may impose a lower maximum;
- leg IDs are unique;
- legs are in canonical account/instrument order;
- account/instrument scope pairs are unique;
- all public collections are immutable tuples;
- quantities use exact fixed point;
- reasons and all string fields have hard length bounds;
- the Basket contains no secret or venue-native object.

Canonical leg order is the ascending tuple:

```python
(
    str(leg.account_id),
    str(leg.instrument_id.venue),
    leg.instrument_id.kind.value,
    leg.instrument_id.symbol,
)
```

Duplicate `(account_id, instrument_id)` scopes are already rejected, so this
key is unique inside one valid Basket. `leg_id` is not the sort key: leg IDs
may be deterministically derived from the canonical scope, and using them as
the ordering input creates an unnecessary identity/ordering dependency.

The public dataclass rejects non-canonical order. It does not silently mutate
caller input. A named construction helper may sort candidate legs before
creating the immutable public value.

### 2.4 Objective Type evolution

Do not use one central `StrEnum`. A central enum would require core releases
for every new application objective and would make historical renames unsafe.

Use a versioned reference:

```python
@dataclass(frozen=True, slots=True, kw_only=True, order=True)
class ObjectiveTypeRef:
    objective_type_id: ObjectiveTypeId
    version: int
```

Stable IDs use bounded lowercase ASCII namespaces, for example:

```text
carry.open
carry.close
rebalance
calendar_spread.open
```

Rules:

- ID maximum length is 96;
- segments use lowercase letters, digits and underscores;
- dots separate ownership/meaning namespaces;
- version is positive;
- an existing `(id, version)` is never reinterpreted;
- changed semantics require a new version or new ID;
- deprecated references remain decodable for replay;
- aliases may exist only in migration tooling, never in canonical records.

An immutable `ObjectiveTypeRegistry` is built at composition time from
metadata-only definitions. It validates references and ownership. It cannot
store callbacks, import paths, Risk functions or application code.

The objective is classification for policy and audit. It is not an execution
plan, lifecycle state, recovery command or authorization.

### 2.5 Construction policy

Structural hard limits belong to the contract. Deployment limits use:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketIntentPolicy:
    max_legs: int
    max_validity_ns: DurationNanos
    allowed_objectives: tuple[ObjectiveTypeRef, ...]
```

Policy invariants:

- `2 <= max_legs <= 16`;
- validity is positive and below a hard duration cap;
- objective references are registered, unique and deterministically sorted;
- an empty allow-list means no objective is allowed, not “allow all”;
- runtime configuration cannot raise the hard cap.

The Strategy runtime validates construction policy before passing the Basket
to Risk. Risk independently validates identity, expiry, policy version and
complete leg equality.

## 3. Strategy Boundary

The public decision union becomes:

```python
DecisionIntent: TypeAlias = PositionTargetIntent | BasketTargetIntent
```

`StrategyDecision.intents` becomes:

```python
tuple[DecisionIntent, ...]
```

Compatibility rules:

- existing strategies may continue returning only `PositionTargetIntent`;
- existing single-instrument runtime behavior and tests remain unchanged;
- a `PositionTargetIntent` is not wrapped in a one-leg Basket;
- Basket-aware composition is a separate mandatory pipeline path;
- a runtime that is not configured for Basket handling must reject Basket
  output explicitly before Risk, never ignore it or partially process legs.

An application produces the complete Basket in one synchronous decision. It
cannot emit one leg now and attach another later.

### 3.1 Current implementation impact

Current source inspection found:

- `StrategyDecision.intents` is already typed through the `DecisionIntent`
  alias, so its dataclass shape does not change;
- `StrategyRuntime._validate_intents` currently accepts only
  `PositionTargetIntent` and must add an explicit Basket branch;
- duplicate intent checking already uses `set[IntentId]`, which remains valid
  because Basket reuses `IntentId`;
- current `StrategyInput` accepts only canonical market events and
  `FeatureSnapshot`;
- ADR-009 now publishes `DecisionSnapshotPublication[T]`.

The additive Strategy input becomes:

```python
StrategyInput: TypeAlias = (
    CanonicalMarketEvent
    | FeatureSnapshot
    | DecisionSnapshotPublication[object]
)
```

For a decision publication, input scope is `metadata.scope`. Basket output
must reference the same `metadata.snapshot_id`. Existing market-event and
FeatureSnapshot behavior remains unchanged.

The single-leg `TradingPipeline` remains explicitly typed to
`PositionTargetIntent`. It must reject Basket output as unsupported before
calling its single-leg Portfolio/Risk port. A later `basket_pipeline` from
ADR-011/012 handles Basket decisions; the current pipeline must not iterate
Basket legs as independent intents.

### 3.2 Lifecycle boundary

`BasketTargetIntent` is an immutable decision value. It has no mutable
status/state machine.

Its only temporal predicates are:

```text
not_yet_created
valid at evaluation time
expired at evaluation time
```

These are not persisted lifecycle states.

Ownership remains:

| Lifecycle | Owning ADR/domain |
|---|---|
| Strategy instance CREATED/RUNNING/STOPPED/FAILED | Existing Strategy Runtime |
| Basket Risk ALLOW/REJECT and continuous risk action | ADR-012 / Risk |
| Parent/Child execution state | ADR-011 / OMS Order Group |
| PARTIALLY_HEDGED/HEDGED/ACTIVE/CLOSED | ADR-014 / Carry application |

ADR-011 must not add economic Carry states to OMS. ADR-010 must not predefine
Parent/Child status transitions.

## 4. Snapshot Causation

Every Basket requires `decision_snapshot_id`.

The causation chain is:

```text
ordered source observations
  -> DecisionSnapshotId
  -> IntentId (BasketTargetIntent)
  -> Basket Risk decision
  -> OMS OrderGroupId
  -> child ClientOrderIds
  -> execution and financial facts
```

Strategy must not copy all source observations into the Basket. Snapshot
identity provides traceability while Risk receives the authoritative Snapshot
evidence through its context.

Risk rejects:

- unknown Snapshot ID;
- scope mismatch;
- snapshot policy-version mismatch;
- snapshot no longer ready;
- Basket created before or inconsistently with Snapshot;
- Basket expired between Strategy and Risk.

## 5. Identity and Idempotency

Basket and leg IDs are supplied by an explicit deterministic identity policy
or an approved caller. Randomness and wall-clock reads are not hidden inside
the dataclasses.

Required behavior:

- exact replay produces the same Basket and leg identities;
- exact redelivery is idempotent;
- reuse of a Basket ID for changed content is a conflict;
- reuse of a leg ID for different content inside the same Basket is a
  conflict;
- a modified target is a new Basket identity;
- Risk cannot silently edit targets while retaining the original identity.

The exact deterministic ID framing and hashing algorithm must be documented
with implementation. IDs are not authentication tokens.

## 6. Whole-Basket Risk Gate

V1 Risk result is binary:

```text
ALLOW complete identity-equal Basket
REJECT complete Basket with typed reasons
```

There is no:

- per-leg partial approval;
- silent leg deletion;
- silent target resizing;
- approval that arrives after the first child submit.

Mandatory invariant:

```text
No child order is created or submitted until one ALLOW decision covers the
complete, unexpired and identity-equal Basket.
```

If a future Risk engine proposes a modified Basket, it must create a new
explicit proposed-plan identity and return it to the application for
acceptance. That workflow is out of V1 scope.

ADR-012 defines projected portfolio calculations and rejection reasons.

## 7. OMS Boundary

`BasketTargetIntent` never enters an Execution adapter.

After whole-Basket approval, Runtime converts it into the OMS-owned
`ApprovedOrderGroupIntent` defined by ADR-011. OMS then derives bounded child
identities and actions.

Separation:

| Basket Strategy contract | OMS/Execution contract |
|---|---|
| target position | order quantity |
| economic objective | execution plan |
| canonical account/instrument | route and venue request |
| decision expiry | order time-in-force |
| application reason | order lifecycle fact |

Strategy cannot specify parallel/sequential child execution in V1 Basket
contracts. Execution planning belongs to the accepted ADR-011 boundary and
may reference an approved application policy version without embedding a
callback.

## 8. Boundedness

Hard contract bounds:

- 16 legs maximum;
- unique leg and account/instrument keys;
- bounded objective and reason text;
- one finite validity deadline;
- immutable tuple storage;
- positive schema/policy version.

Runtime and deployment add lower operational bounds for:

- Basket intents per Strategy decision;
- admitted non-terminal Order Groups per Strategy/account under ADR-011;
- aggregate legs per decision cycle;
- total encoded size;
- retained identity-conflict history;
- Risk work per cycle.

No unbounded dict or caller-controlled recursive object crosses the public
contract.

## 9. Failure Semantics

| Failure | Required result |
|---|---|
| Fewer than two or more than allowed legs | Reject construction/admission |
| Duplicate leg ID | Reject |
| Duplicate account/instrument scope | Reject |
| Non-canonical leg order | Reject; construction helper may sort before creation |
| Empty/unknown objective type | Reject |
| Missing/unknown Snapshot ID | Reject before OMS |
| Expired Basket | Reject before OMS |
| Strategy scope does not allow account/instrument | Reject |
| Unsupported policy version | Reject |
| Risk identity mismatch | Latch pipeline invariant failure |
| Runtime lacks Basket path | Explicit unsupported-intent rejection |
| Any preflight exception | Fail closed; no child action |

One invalid leg rejects the whole Basket.

## 10. Persistence and Replay

The Strategy decision recorder must persist:

- Basket schema version;
- all identities;
- ordered legs;
- exact fixed-point target quantities;
- versioned objective reference and policy version;
- decision/expiry times;
- Snapshot causation;
- deterministic checksum.

Replay of the same Snapshot and Strategy state must produce an identity-equal
Basket. A persisted Basket is decision evidence, not Risk approval and not
permission to submit after restart.

OMS persists its separately approved Order Group under ADR-011.

## 11. Security and Operations

- no credential, API key or signed venue parameter enters a Basket;
- account IDs are canonical internal identities and are sanitized in external
  operator views according to deployment policy;
- operator HALT prevents new Basket admission and every child action;
- reduce-only recovery is not inferred from `objective_type`;
- expiry and clock health remain mandatory;
- audit views preserve Basket, Snapshot and later Order Group causation;
- malformed or oversized Basket input is rejected before expensive Risk work.

## 12. Compatibility and Migration

This decision is additive.

Unchanged:

- `PositionTargetIntent` fields and behavior;
- existing single-instrument Strategy lifecycle;
- current single-instrument Risk contracts;
- current `OrderRequest`, OMS state and journals;
- current child-order Execution adapters;
- existing Testnet and production authorization boundaries.

Required implementation changes after acceptance:

- add strongly typed IDs;
- add versioned Objective Type contracts and registry;
- add `strategy.basket`;
- extend `StrategyInput`, `DecisionIntent` and runtime validation without
  changing the `StrategyDecision` dataclass shape;
- add explicit unsupported-Basket behavior to single-leg composition;
- add serialization and compatibility tests;
- update package exports and interface documentation.

No old OMS journal migration is required because Basket contracts do not
change existing persistent order records.

## 13. Alternatives Considered

### Two independent `PositionTargetIntent` values

Rejected. It permits split Risk decisions and loses one objective identity.

### `TwoLegIntent`

Rejected. It hard-codes Funding and does not support three-leg or option
portfolios.

### One-leg Basket replaces `PositionTargetIntent`

Rejected. It creates unnecessary migration and weakens the established simple
path.

### Basket contains order types and limit prices

Rejected. It merges Strategy objectives with OMS/Execution mechanism.

### Duplicate instruments always rejected

Rejected as too broad. The same Instrument can be valid across distinct
canonical accounts. V1 rejects duplicate account/instrument pairs.

### Risk may approve individual legs

Rejected. Partial approval can destroy the economic objective before OMS
execution even begins.

### Universal `dict[str, object]`

Rejected. It is unbounded, weakly typed and unsafe for schema evolution.

### Application keeps leg identities privately

Rejected. Risk, OMS, recovery, audit and accounting require stable shared
causation.

### New `BasketIntentId`

Rejected after current-code review. Existing `IntentId` already expresses the
cross-domain decision identity and is used by Strategy, Risk and OMS.

### Central `ObjectiveType` enum

Rejected. Application objective families must evolve without editing one
global enum or reinterpreting historical values.

### Sort legs only by `BasketLegId`

Rejected. It makes canonical ordering depend on an identity that may itself be
derived from leg scope. Canonical account/instrument order is explicit and
semantic-neutral.

## 14. Consequences

### Positive

- makes portfolio objectives explicit and atomic at the decision boundary;
- preserves Strategy/Risk/OMS/Execution separation;
- supports bounded generic N-leg applications;
- creates durable causation without Funding-specific core code;
- keeps existing single-instrument strategies compatible;
- prevents any child submit before complete Basket approval.

### Costs

- adds cross-domain IDs and a Strategy submodule;
- requires Basket-aware Runtime and Risk paths;
- requires schema and identity compatibility tests;
- requires applications to emit final net targets, not ad hoc orders.

### Risks

- a hard cap that is too high can create excessive Risk/OMS work;
- an Objective Type registry can become inconsistent if ownership and version
  rules are not enforced;
- account selection can leak policy into Strategy if configuration ownership
  is not explicit;
- treating target quantities as order quantities would cause incorrect
  execution;
- later execution planning must not mutate the approved economic target.

## 15. Required Tests

### Contract

- empty, whitespace and oversized IDs/text;
- fewer than two and more than 16 legs;
- deployment maximum lower than hard cap;
- duplicate leg IDs and non-canonical account/instrument order;
- duplicate account/instrument pair;
- same Instrument across different accounts;
- zero close targets and mixed signed quantities;
- exact fixed-point preservation;
- expiry boundary and maximum validity;
- objective allow-list and policy version;
- Objective Type format, version, registration and historical replay;
- immutable values and tuples.

### Identity and replay

- deterministic Basket and leg IDs;
- exact duplicate idempotency;
- changed-content ID conflict;
- changed target creates new identity;
- Snapshot causation preserved;
- deterministic serialization/checksum.

### Compatibility

- all existing `PositionTargetIntent` tests unchanged;
- existing single-leg runtime processes single intents identically;
- Strategy Runtime accepts `DecisionSnapshotPublication` additively and
  validates Basket snapshot causation;
- single-leg runtime explicitly rejects Basket output;
- no existing OMS journal schema changes.

### Pipeline invariant

- Risk sees all legs together;
- one invalid leg rejects the whole Basket;
- Risk identity mismatch fails closed;
- expiry between Strategy and Risk rejects;
- no OMS group or child action exists before complete `ALLOW`;
- synthetic two-leg and three-leg inputs use the same public contract.

## 16. Implementation Authorization

The review gate was satisfied on 2026-07-28:

1. Codex inspected the current Intent, Strategy Runtime, core ID, Runtime
   Pipeline and OMS contracts;
2. the existing `IntentId` was retained for compatibility;
3. Objective Type became a versioned registered reference;
4. Basket lifecycle ownership was removed from ADR-010;
5. canonical leg ordering was changed from leg-ID order to
   account/instrument order;
6. the project owner conditionally approved acceptance after these changes;
7. T027, T028 and A013 were assigned.

Authorized implementation scope:

- `BasketLegId`, `ObjectiveTypeId` and versioned Objective Type registry;
- immutable bounded `BasketTargetLeg` and `BasketTargetIntent`;
- construction/admission policy and deterministic identity helpers;
- additive `StrategyInput` and `DecisionIntent` unions;
- Strategy Runtime Basket output and Snapshot causation validation;
- explicit single-leg pipeline rejection of Basket output;
- contract, compatibility, replay and two-/three-leg offline tests.

Not authorized:

- Parent/Child OMS or Order Group lifecycle;
- Basket Portfolio Risk implementation;
- execution plan or child submission;
- Financial Ledger or Carry application;
- Testnet, production or real-money trading.

ADR-011 and ADR-012 may now be drafted. Their implementations remain blocked
until their own ADRs are accepted.

## 17. Resolved Review Decisions

| Question | Accepted decision |
|---|---|
| Account scope | Each leg contains canonical `AccountId` |
| V1 hard cap | 16 legs |
| Validity | `valid_until_ns` is mandatory |
| Duplicate scope | Reject duplicate account/instrument; allow same Instrument across accounts |
| Leg order | Canonical account/instrument order; reject non-canonical public values |
| Risk result | Binary whole-Basket `ALLOW/REJECT` in V1 |
| Objective Type | Versioned registered `ObjectiveTypeRef`, not central enum or raw string |
| Intent identity | Reuse existing `IntentId`; add only `BasketLegId` |
| StrategyDecision | Dataclass shape unchanged; unions and validation expand additively |
| Lifecycle | OMS execution in ADR-011; application economics in ADR-014 |
