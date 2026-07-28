# ADR-010 Basket Intent Architecture

## Status

Proposed — ready for architecture review.

This ADR does not authorize implementation. ADR-009 is accepted and its
generic Snapshot Infrastructure may proceed independently.

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

- has one strongly typed Basket identity;
- has unique, deterministically ordered leg identities;
- references the accepted `DecisionSnapshotId`;
- has a mandatory finite validity deadline;
- carries one strategy identity and objective classification;
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
    identifiers.py            # BasketIntentId, BasketLegId

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

### 2.1 Identities

Add to `cex_quant.core`:

```python
BasketIntentId = NewType("BasketIntentId", str)
BasketLegId = NewType("BasketLegId", str)
```

They are used by Strategy, Risk, OMS, Accounting and applications. They
cannot be interchangeable with `IntentId`, `ClientOrderId` or raw strings at
public typed boundaries.

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
    basket_intent_id: BasketIntentId
    strategy_id: StrategyId
    decision_snapshot_id: DecisionSnapshotId
    objective_type: str
    legs: tuple[BasketTargetLeg, ...]
    decision_time_ns: UnixNanos
    valid_until_ns: UnixNanos
    policy_version: int
    reason: str = ""
```

Required invariants:

- Basket, Strategy and Snapshot IDs are non-empty;
- `objective_type` is non-empty, trimmed, bounded metadata;
- `policy_version` is positive;
- validity is finite and cannot precede decision time;
- leg count is between two and the hard cap;
- configured policy may impose a lower maximum;
- leg IDs are unique;
- legs are ordered by `BasketLegId`;
- account/instrument scope pairs are unique;
- all public collections are immutable tuples;
- quantities use exact fixed point;
- reasons and all string fields have hard length bounds;
- the Basket contains no secret or venue-native object.

`objective_type` supports stable classifications such as:

```text
carry.open
carry.close
rebalance
calendar_spread.open
```

It is metadata for policy selection and audit. It is not a Python import path,
callback, expression or executable strategy definition.

### 2.4 Construction policy

Structural hard limits belong to the contract. Deployment limits use:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketIntentPolicy:
    max_legs: int
    max_validity_ns: DurationNanos
    allowed_objective_types: tuple[str, ...]
```

Policy invariants:

- `2 <= max_legs <= 16`;
- validity is positive and below a hard duration cap;
- objective types are unique and deterministically sorted;
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

## 4. Snapshot Causation

Every Basket requires `decision_snapshot_id`.

The causation chain is:

```text
ordered source observations
  -> DecisionSnapshotId
  -> BasketIntentId
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
- active Baskets per Strategy/account;
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
| Unsorted legs | Reject; do not silently reorder public input |
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
- objective type and policy version;
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
- add `strategy.basket`;
- extend `DecisionIntent` and `StrategyDecision` typing;
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
- an objective-type taxonomy can become an uncontrolled string namespace;
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
- duplicate and unsorted leg IDs;
- duplicate account/instrument pair;
- same Instrument across different accounts;
- zero close targets and mixed signed quantities;
- exact fixed-point preservation;
- expiry boundary and maximum validity;
- objective allow-list and policy version;
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
- single-leg runtime explicitly rejects Basket output;
- no existing OMS journal schema changes.

### Pipeline invariant

- Risk sees all legs together;
- one invalid leg rejects the whole Basket;
- Risk identity mismatch fails closed;
- expiry between Strategy and Risk rejects;
- no OMS group or child action exists before complete `ALLOW`;
- synthetic two-leg and three-leg inputs use the same public contract.

## 16. Implementation Gate

No source implementation starts until:

1. Web GPT architecture review is recorded;
2. the project owner accepts, revises or rejects this ADR;
3. status changes from Proposed to Accepted;
4. hard cap, account scope and mandatory expiry are explicitly approved;
5. implementation task and acceptance IDs are assigned.

ADR-011 and ADR-012 remain blocked from implementation until ADR-010 is
accepted. Drafting may proceed only where unresolved ADR-010 choices are
clearly marked.

## 17. Review Questions

1. Should Basket legs explicitly contain canonical `AccountId`, or should
   account routing remain entirely in Runtime policy?
2. Is a hard cap of 16 legs appropriate for V1?
3. Should `valid_until_ns` be mandatory for every Basket?
4. Is rejecting duplicate `(account_id, instrument_id)` while allowing the
   same Instrument across accounts correct?
5. Should callers be required to submit legs already sorted by `BasketLegId`,
   with unsorted tuples rejected?
6. Is binary whole-Basket `ALLOW/REJECT` sufficient for V1?
7. Should `objective_type` remain bounded metadata, or use a centrally
   registered identifier contract?
8. Are the compatibility rules for existing `PositionTargetIntent` strict
   enough?
