# ADR-011 Parent Order Group and Multi-leg Execution Model

## Status

Accepted — 2026-07-28.

This ADR authorizes only T029, T030, T031 and offline acceptance A014.
Exposure-changing Order Group submission remains blocked until ADR-012 is
accepted. It authorizes no Funding Arbitrage application, Testnet activity or
production trading.

Review inputs:

- `ai_collaboration/topics/funding_arbitrage/60_web_gpt_adr011_review.md`;
- `ai_collaboration/topics/funding_arbitrage/61_codex_adr011_current_code_audit.md`;
- `ai_collaboration/topics/funding_arbitrage/62_codex_adr011_proposal_handoff.md`;
- `ai_collaboration/topics/funding_arbitrage/63_codex_adr011_review_response.md`;
- the second Web GPT review decisions recorded in section 29;
- accepted ADR-009 and ADR-010;
- the current OMS, Execution, journal and recovery implementation at commit
  `157ee6b4ba7446396ed36d07a55c5727dec6cd5a`.

## Context

ADR-009 defines what independently owned states the system can see
coherently. ADR-010 defines the immutable portfolio target a Strategy wants.

Neither decision authorizes an exchange action.

```text
BasketTargetIntent:
  BTC Spot       target +10
  BTC Perpetual  target -10

Portfolio Risk:
  ALLOW Basket admission
```

Real execution can produce:

```text
Spot filled +10, Perpetual filled 0
```

or:

```text
Spot filled +5, Perpetual filled -10
```

Those are not atomic portfolio transitions. Orders can be partially filled,
rejected, canceled, delayed, duplicated at the transport boundary or left in
an unknown state after a timeout or crash.

The required invariant is:

```text
Basket admission approval != child execution permission
```

ADR-011 must define how one approved economic objective becomes a durable,
bounded and recoverable Parent Order Group without moving Strategy,
Portfolio Risk or application economics into OMS.

## Current-Code Finding That Must Be Resolved

The existing single-order kernel is reusable, but the concrete
`TradingApplication` currently composes:

```text
OMS.create_order
  -> Execution.submit
```

It does not durably call `OMS.mark_submitting` before the external submit and
does not write the immediate submit outcome back into OMS.

If the request reaches the venue and the process crashes before a private
stream event, the journal may contain only `CREATED`.
`reconciliation_candidates()` currently excludes `CREATED`, so the possibly
live order may not be queried at restart.

ADR-011 defines one shared durable execution handoff for both existing
single-leg orders and future Order Group children. It must not create a safer
Basket path while leaving the existing single-order composition ambiguous.

No code is changed by this Proposed ADR.

## Decision Summary

Introduce an OMS-owned Parent Order Group with these principles:

1. A Basket admission approval may create one durable group and nothing else.
2. Every exposure-changing child submit requires a separate finite,
   single-action permit over exact immutable content.
3. One Basket leg may own zero or more child order attempts.
4. Existing `OrderRequest`, `OrderStateMachine`, Execution adapters and child
   reconciliation remain the canonical child-order kernel.
5. OMS publishes a signed fill vector per Basket leg; Portfolio Risk computes
   actual position, Delta, basis, margin and hedge condition.
6. Group control lifecycle, child execution facts and portfolio exposure are
   separate dimensions.
7. Submit intent is persisted before every external call.
8. Any possibly-sent action becomes recovery-required and is queried, never
   blindly resubmitted.
9. Restart replays one ordered OMS journal, reconciles all unresolved
   children, refreshes Portfolio state and requires fresh Risk/operator
   authority before new actions.
10. Order Group execution intent, versioned execution plan, exact execution
    action and canonical child attempt are separate layers.
11. V1 is bounded and single-writer. It introduces no universal Event Bus and
    no hidden autonomous economic retry loop.

## 1. Terminology

### Basket

The immutable `BasketTargetIntent` from ADR-010. It is an economic target and
has no execution state.

### Basket admission

A whole-Basket Risk result that permits creation of a durable Order Group.
Admission is not permission to submit a child.

### Parent Order Group

The OMS aggregate that preserves Basket causation, owns group control state,
maps Basket legs to child attempts and derives a complete immutable group
view.

### Order Group execution intent

The durable OMS intention to move toward one admitted Basket target under one
versioned execution plan. It is represented by the Order Group and its plan
reference. It is not an exchange command or action permission.

### Execution plan

A versioned, immutable policy reference plus bounded parameters describing
how the group may propose actions. It contains no runtime callback, venue
session or Risk authority.

### Execution action

One exact immutable proposed attempt to advance one Basket leg at one group
revision. It is identified by `GroupActionId`. An action contains order
content but no permission and cannot reach Execution without an exact permit.

### Child order attempt

One existing canonical `OrderRequest` and `OrderStateMachine` associated with
exactly one Basket leg and one group action.

### Execution action permit

A fresh, finite authorization bound to one exact execution action at one
exact group revision. It cannot authorize another action or child identity.
ADR-012 owns its Risk issuance semantics.

Required layering:

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> Order Group execution intent
  -> ExecutionPlanRef
  -> ExecutionAction
  -> ExecutionActionPermit
  -> Child Order Attempt
  -> existing ExecutionGateway
```

A changed maker/taker choice, price, quantity or other order content creates a
new `ExecutionAction` and child identity. A bounded technical retransmission
with unchanged content and the same `ClientOrderId` remains the same action
and child attempt.

## 2. Package Topology

Planned after acceptance:

```text
src/cex_quant/
  core/
    identifiers.py              # OrderGroupId, ExecutionPlanId,
                                # GroupActionId, PortfolioApprovalId,
                                # ExecutionPermitId

  oms/
    group_model.py              # admissions, plans, actions, permits, views
    group_state.py              # group control and child mapping
    journal.py                  # version-aware legacy + group facts

  runtime/
    order_group_runtime.py      # single-writer orchestration
    execution_planning.py       # registered plans propose actions only
    execution_handoff.py        # durable-before-I/O shared handoff
    execution_router.py         # account/instrument -> existing gateway

  risk/
    portfolio.py                # future ADR-012 approval/permit issuer
```

Ownership:

| Module | Owns |
|---|---|
| Strategy | Immutable Basket target |
| Portfolio Risk | Basket admission and per-action permit decisions |
| execution plan/planner | Deterministic execution action, no authority |
| OMS | Group/child identity, lifecycle, journal and canonical views |
| Runtime | Ordered calls between Risk, OMS and Execution |
| Execution | One child venue request and normalized immediate result |
| Portfolio | Actual account positions and balances |
| Carry application | Economic `HEDGED/ACTIVE/CLOSED` lifecycle under ADR-014 |

The OMS group package may consume accepted immutable Basket contracts but
cannot depend on a concrete Risk engine, application package, runtime or venue
adapter.

## 3. Identity Chain

Proposed cross-domain IDs:

```text
PortfolioApprovalId
OrderGroupId
ExecutionPlanId
GroupActionId
ExecutionPermitId
```

Existing IDs remain:

```text
DecisionSnapshotId
IntentId
BasketLegId
ClientOrderId
VenueOrderId
```

Required chain:

```text
DecisionSnapshotId
  -> IntentId (Basket)
  -> PortfolioApprovalId (group admission only)
  -> OrderGroupId
  -> ExecutionPlanId + version
  -> BasketLegId
  -> GroupActionId
  -> ExecutionPermitId
  -> ClientOrderId
  -> VenueOrderId
```

V1 rules:

- one `IntentId` may create at most one Order Group;
- exact admission redelivery returns the identity-equal existing group;
- changed admission content with the same identity is a conflict;
- `OrderGroupId` is replay-stable under an explicit identity policy;
- one `GroupActionId` identifies one immutable action;
- one action maps to exactly one child attempt and at most one
  `ClientOrderId`;
- a child belongs to exactly one group and one Basket leg;
- one Basket leg may have multiple child attempts;
- changed order content requires a new action and child identity;
- a technical retransmission keeps the same action, child and
  `ClientOrderId`;
- an unknown child identity cannot be replaced until reconciliation resolves
  its venue state.

Recommended default derivation:

```text
OrderGroupId = hash(IntentId, PortfolioApprovalId)
GroupActionId = hash(OrderGroupId, group_revision, BasketLegId,
                     execution_plan_checksum, action_kind,
                     leg_attempt_sequence)
ClientOrderId = venue-safe deterministic encoding of GroupActionId
```

OMS must also maintain uniqueness by Basket `IntentId`, preventing a second
group when the same Basket is reapproved under a different approval identity.

Hashes are identities, not authentication tokens.

## 4. Group Admission Contract

Proposed semantic contract:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupAdmission:
    approval_id: PortfolioApprovalId
    basket: BasketTargetIntent
    basket_checksum: str
    approved_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int
```

Admission invariants:

- Risk approved the complete identity-equal Basket;
- checksum matches canonical ADR-010 serialization;
- approval and Basket identities are non-empty;
- approval is finite and no longer-lived than the Basket;
- objective and Basket policy remain registered;
- every leg is present and unchanged;
- one accepted admission creates one durable group;
- admission contains no order type, order quantity, sequence or venue
  request;
- admission permits no child creation or submit by itself.

ADR-012 may add typed Risk evidence, but it cannot weaken these invariants.

## 5. Execution Intent, Plan and Action

Strategy specifies final targets only. Group admission creates one durable
execution intent to approach that target. A versioned execution plan then
proposes exact actions.

Proposed reference:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPlanRef:
    execution_plan_id: ExecutionPlanId
    version: int
    parameters_checksum: str
```

The durable group stores only this reference and separately bounded immutable
policy parameters. It cannot store a callback, module path or arbitrary
object.

Runtime composition selects the plan from a bounded registry using accepted
configuration and objective metadata. An unknown plan ID/version, checksum
mismatch or unbounded parameter set fails before group creation. The planner
implementation may live in `runtime.execution_planning`; OMS owns only the
immutable plan evidence and resulting action facts.

V1 group creation takes both admission evidence and the plan reference:

```python
create_group(
    admission: OrderGroupAdmission,
    execution_plan: ExecutionPlanRef,
) -> OrderGroupView
```

The registered plan and its bounded parameters become immutable
`GroupCreated` evidence. Admission still grants no child permission. Changing
the plan in place is unsupported in V1; the group is suspended or closed and
the change requires a future reviewed lifecycle rule.

A planner receives immutable views and proposes at most one V1 child action
per call:

```python
class OrderGroupPlanner(Protocol):
    def propose(
        self,
        group: OrderGroupView,
        portfolio: object,
        now_ns: UnixNanos,
    ) -> ExecutionAction | None: ...
```

The exact Portfolio view becomes typed under ADR-012. Planner I/O, implicit
clock access and exchange calls are prohibited.

Proposed action content:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionAction:
    group_id: OrderGroupId
    expected_group_revision: int
    action_id: GroupActionId
    basket_leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Quantity
    time_in_force: TimeInForce
    limit_price: Price | None
    stop_price: Price | None
    reduce_only: bool
    post_only: bool
    position_side: PositionSide
    execution_plan: ExecutionPlanRef
    created_at_ns: UnixNanos
```

The action:

- references one existing Basket leg;
- uses a positive order quantity, not a final target;
- cannot alter Basket target content;
- is deterministic from explicit inputs;
- is content-checksummed;
- is not an Execution command;
- maps to exactly one child attempt after permission and durable preparation;
- must be replaced by a new `GroupActionId` if maker/taker choice, price,
  quantity or any order content changes.

The relation is:

```text
one Basket leg
  -> zero or more sequential ExecutionActions
      -> exactly one Child Order Attempt per action
```

## 6. Per-Action Permission

Proposed semantic contract owned by the Risk boundary:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionActionPermit:
    permit_id: ExecutionPermitId
    group_id: OrderGroupId
    expected_group_revision: int
    action_id: GroupActionId
    action_checksum: str
    risk_snapshot_id: DecisionSnapshotId
    issued_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int
```

OMS accepts a child submit only when:

- group is `ACTIVE`;
- group revision matches;
- action identity and checksum match exactly;
- Basket leg/account/instrument match admission;
- permit is fresh and unconsumed;
- Basket/group deadline permits an ordinary action;
- operator authority allows the action;
- group and configured child bounds are not exceeded;
- no unresolved identity conflicts exist.

One permit is consumed by and latched to one exact action. It cannot authorize:

- another leg;
- another quantity or price;
- cancel/replace;
- a later group revision;
- a different Portfolio/Risk snapshot;
- a retry with changed content;
- a new action or child attempt.

A bounded transport retransmission is not a new economic action. It uses the
already prepared child, the same latched permit causation, action and
`ClientOrderId`; the permit cannot be detached or consumed by another action.
Retransmission is allowed only if all of these hold:

- transport evidence proves the prior attempt was definitely not sent;
- action content is byte-for-byte identity-equal;
- permit, Basket and group deadlines remain fresh;
- no intervening child, exposure, control or recovery fact invalidated the
  persisted action's retry eligibility;
- operator and runtime health gates are rechecked;
- the configured technical retransmission budget is not exhausted.

The retransmission is journaled as another transport attempt for the same
child. It does not create a new `GroupActionId`, `ClientOrderId` or child.
V1 permits at most one technical retransmission per action.

Basket admission alone fails every one of these checks.

### 6.1 Execution Action and Transmission State

Execution action state is separate from group control and canonical child
order state:

```text
PROPOSED
  -> PREPARED
     -> TRANSMITTING
        -> ACKNOWLEDGED
        -> REJECTED
        -> RETRY_ELIGIBLE -> TRANSMITTING
        -> UNKNOWN
```

- `PROPOSED` has no permit and produces no journal or external effect.
- `PREPARED` means the exact action, permit causation, child mapping and submit
  intent are durable.
- `RETRY_ELIGIBLE` is reachable only with proof that the prior transport
  attempt was not sent.
- `UNKNOWN` means the request may have reached the venue and forces group
  `RECOVERY_REQUIRED`.
- a maker-to-taker change is a new action and child, never a technical
  retransmission.

The existing child enters at least `SUBMITTING` at `PREPARED`. A
definitely-not-sent transport fact does not terminally fail that child while
one permitted technical retransmission remains. Exhaustion, expiry or
operator refusal resolves the child as local `FAILED` without an external
order. Venue lifecycle after acknowledgement continues through the existing
`OrderStateMachine`.

## 7. Durable Group Control Lifecycle

Proposed control lifecycle:

```text
CREATED
   |
   v
ACTIVE <------> SUSPENDED
   |                |
   +-------> RECOVERY_REQUIRED
   |                |
   +------------> CLOSING
                       |
                       v
                     CLOSED
```

Semantics:

### `CREATED`

Admission and group identity are durable. No child submit is allowed.

### `ACTIVE`

The group may request actions and permits. Every external action still
requires its own checks.

### `SUSPENDED`

No new submit is allowed. Existing venue orders may still fill. Query,
reconciliation and safe cancel remain allowed.

### `RECOVERY_REQUIRED`

At least one possibly-sent action, identity conflict, reconciliation conflict,
stream gap or durability condition prevents safe progression. No new submit
is allowed.

### `CLOSING`

No new ordinary child submit is allowed. Live children are canceled or
reconciled. Exposure-reducing recovery actions require explicit ADR-012
permission.

### `CLOSED`

Terminal OMS execution-group state. Every child and external action is
resolved and no venue-working order remains.

`CLOSED` carries one outcome:

```text
TARGET_CONFIRMED
ABORTED
FAILED
```

`TARGET_CONFIRMED` requires fresh Portfolio/Risk evidence, not merely terminal
child orders. `FAILED` cannot hide an unknown or possibly-live child.

## 8. States Deliberately Not Used as Group Control States

### `APPROVED`

Approval is immutable admission provenance, not mutable lifecycle.

### `PARTIALLY_FILLED`

This remains an existing child order state. Group partial progress is derived
from all children.

### `HEDGED`

This requires current product Delta, multipliers, marks, positions and
possibly option Greeks. ADR-012 Portfolio Risk owns the assessment. ADR-014
may use it in Carry economic lifecycle.

### `UNKNOWN`

Unknown is an external-action/child condition. It forces group
`RECOVERY_REQUIRED`.

### `COMPLETED`

The word is ambiguous between “all planned orders terminal,” “portfolio
target reached” and “Carry investment active.” OMS uses `CLOSED` with an
explicit outcome.

## 9. Child and Leg Views

Group state reuses one `OrderStateMachine` per child.

Proposed relation:

```text
OrderGroup
  -> 2..16 admitted Basket legs
      -> 0..bounded child attempts
          -> existing OrderRequest
          -> existing OrderStateMachine
```

Proposed leg view:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupLegView:
    basket_leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    target_quantity: Quantity
    child_order_ids: tuple[ClientOrderId, ...]
    signed_cumulative_filled_delta: Quantity
    signed_working_quantity: Quantity
    unresolved_action_ids: tuple[GroupActionId, ...]
```

OMS derives signed quantities from child side and cumulative fill. It never
calls this field the actual account position.

Portfolio Risk joins:

```text
authoritative current positions
  + group child fill vector
  + Instrument multipliers
  + mark/index prices
  + current option Greeks where applicable
  -> net/gross Delta, basis, margin, liquidation and hedge assessment
```

For Spot/Perpetual, Risk may derive a `+3 BTC` residual. For option spreads,
raw contract quantities cannot be summed as Delta.

## 10. Group Revision and Single-Writer Rule

Each group has a positive monotonically increasing revision. Every accepted
group mutation, child creation, submit outcome, cancel fact and venue update
increments it.

An action and its first permit both bind to the same expected revision. Any
intervening fill, cancel, operator action or recovery event before durable
preparation makes them stale. After preparation, bounded technical
transmission attempts are governed by the persisted action state and cannot
be turned into a changed economic action.

OMS remains single writer. Runtime serializes calls and cannot mutate group
or child state directly.

The group runtime is caller-driven and contains no unbounded internal queue,
implicit retry task or universal hot-path Event Bus.

## 11. Durable-Before-External-Action Handoff

One shared handoff is required:

```text
execution action
  -> fresh action permit
  -> OMS validates exact group revision/content
  -> OMS appends action + child mapping + submit intent
  -> fsync succeeds
  -> operator authority rechecked
  -> ExecutionGateway.submit(existing OrderRequest)
  -> immediate outcome appended to OMS
  -> later venue facts update existing child state
```

OMS should expose an atomic semantic operation comparable to:

```python
prepare_child_submit(
    action: ExecutionAction,
    permit: ExecutionActionPermit,
) -> OrderRequest
```

The returned `OrderRequest` is the first value that may cross to Execution.
Its journal fact must reconstruct both:

- group/action/leg to child identity; and
- child state at least `SUBMITTING`.

If durability fails, no external call occurs and the runtime halts.

The same handoff must wrap the existing single-leg path:

```text
single Position Risk approval
  -> durable order creation + SUBMITTING
  -> gateway submit
  -> immediate result returned to OMS
```

This preserves single-leg behavior while closing the current composition gap.

## 12. Immediate Submit Outcomes

The runtime must report every gateway result to OMS.

| Outcome | OMS/group result |
|---|---|
| Accepted with venue ID | Persist acknowledgement; child remains reconcilable until authoritative lifecycle/fill fact |
| Venue rejection | Persist terminal rejected child with zero or authoritative reported fill |
| Definitely not sent | Persist transport proof; same child becomes `RETRY_ELIGIBLE` for at most one unchanged same-ID retransmission, otherwise local `FAILED` |
| Possibly sent / timeout | Persist unknown action; group enters `RECOVERY_REQUIRED` |
| Malformed response after possible send | Treat as unknown |

An async bridge timeout is unknown because canceling a local future does not
prove the HTTP request was not sent.

The current `SubmitResult` remains an immediate result, not canonical order
lifecycle. ADR-011 may add an OMS journal fact for that result without
changing venue adapters.

## 13. Retry and Replace

V1 rules:

- no automatic creation of a new economic action or child;
- at most one technical retransmission of the already prepared action is
  allowed with the same `ClientOrderId`, only when transport proves the prior
  attempt was not sent;
- retransmission requires identity-equal content, unexpired authority,
  rechecked health/operator gates and persisted `RETRY_ELIGIBLE`;
- possibly-sent actions require read-only query/reconciliation;
- a replacement order receives a new `GroupActionId` and `ClientOrderId`;
- no replacement is created while the prior child is unknown;
- every changed maker/taker, price, quantity or other order choice is a new
  action and child attempt;
- every replacement consumes configured child/action budgets;
- every technical retransmission consumes its separate one-retry V1 budget;
- partial fill plus cancel/replace creates multiple children under the same
  Basket leg.

This permits transport recovery without silently creating a new trading
decision.

## 14. Execution Ordering and Concurrency

The contract is N-leg and does not hard-code Funding or two legs.

Accepted V1 hard rule:

```text
max exposure-changing in-flight child submissions per group = 1
```

This does not mean one child per leg. A planner may:

1. submit a bounded first child;
2. observe partial fill;
3. cancel or wait;
4. request a fresh Portfolio assessment;
5. propose a dynamically sized hedge child;
6. continue under new permits.

Parallel exposure-changing stages require atomic batch permit and recovery
semantics that are not defined here. The schema must not prevent a future
reviewed extension, but V1 does not imply exchange atomicity. Enabling
parallel exposure-changing submits requires a future ADR.

## 15. Multi-venue and Multi-account Routing

An Order Group may contain legs across accounts, products and venues.

Runtime uses a bounded router:

```python
class ExecutionGatewayRouter(Protocol):
    def gateway_for(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
    ) -> ExecutionGateway: ...
```

The router selects an already configured adapter. It cannot alter the
`OrderRequest`, read credentials into OMS or expose venue payloads.

Existing Execution adapters remain child-order oriented and unchanged.
Binance Options network support is still a separate product adapter gate.

## 16. Expiry

- Group admission must occur before Basket/admission expiry.
- Ordinary new child submits stop at Basket/admission expiry.
- Query, reconciliation and cancellation remain allowed after expiry.
- A partially executed expired group becomes `SUSPENDED` or
  `RECOVERY_REQUIRED`.
- Any new hedge/flatten action after expiry requires an explicit fresh
  recovery permit from ADR-012.
- Expiry never converts an unknown child to terminal.

## 17. Operator and Health Boundary

Before every new child submit:

- runtime health must admit the action;
- operator authority is sampled before planning/Risk and immediately before
  the external call;
- `HALTED` blocks new group activation and every new submit;
- `REDUCE_ONLY` requires ADR-012 to prove the exact action reduces permitted
  exposure;
- query and reconciliation remain allowed while halted;
- safe cancellation remains allowed while halted;
- journal, audit, clock or routing failure blocks new external actions.

If HALT occurs after submit intent is durable but before the gateway call, OMS
records definitely-not-sent and Execution is not invoked.

## 18. Journal Evolution

ADR-011 defines one OMS journal, not separate order and group journals.

New facts should include:

```text
GroupCreated
GroupControlChanged
GroupChildSubmitPrepared
ChildTransportAttempted
ChildSubmitOutcome
GroupClosed
```

Existing facts remain:

```text
OrderCreated
OrderSubmitting
CancelRequested
VenueEvent
```

Requirements:

- one global contiguous sequence;
- checksummed canonical records;
- bounded per-record size;
- append/flush/fsync before external action;
- old V1 single-order journals replay unchanged;
- decoder accepts legacy and new record versions;
- a migrated journal may contain historical V1 and new-version records;
- no in-place rewrite of old evidence;
- group/leg/action mapping and child creation share one atomic record;
- journal corruption latches OMS and operator authority fail-closed.

A separate group journal is rejected because a crash between two journal
appends would leave ambiguous group-to-child ownership.

## 19. Restart and Reconciliation

Required startup sequence:

```text
restore operator authority as HALTED
  -> replay legacy orders and group facts
  -> rebuild groups, mappings and child OrderStateMachines
  -> start/buffer private order streams
  -> query every child with a persisted external-action intent
  -> merge REST and stream evidence deterministically
  -> recompute immutable group views
  -> refresh canonical account/position state
  -> ADR-012 reassesses exposure
  -> explicit Risk/operator resume decision
  -> only then allow a new child permit
```

Reconciliation candidates include:

- existing `SUBMITTING`, `OPEN`, `PARTIALLY_FILLED` and `CANCEL_PENDING`;
- every group child with submit intent but no definitive not-sent outcome;
- any action whose immediate outcome is unknown;
- every group already marked `RECOVERY_REQUIRED`.

REST `not found` remains unresolved. It is not proof the order never existed.

No group automatically returns to `ACTIVE` merely because child queries
finished. V1 requires completed reconciliation, fresh Portfolio Risk
assessment and explicit operator resume authorization.

## 20. Database Boundary

A database may implement the append-only journal, immutable evidence store or
query read model.

It is not a second mutable OMS authority.

Recovery truth is:

```text
ordered durable action facts
  + normalized venue order evidence
  + authoritative current Portfolio state
```

A database snapshot cannot silently override a later venue fill or repair a
journal gap.

## 21. Boundedness

Accepted review bounds:

- Basket legs: reuse ADR-010 hard cap 16;
- child attempts per leg: hard cap 8;
- total child orders per group: hard cap 64;
- technical retransmissions per action: hard cap 1;
- unresolved actions per group: configured and fail-closed at capacity;
- exposure-changing in-flight submits per group: hard cap 1;
- active groups per strategy/account: configured;
- retained terminal groups/idempotency digests: bounded and durable;
- group journal record size: bounded and larger than the maximum encoded
  Basket envelope only after explicit review;
- planner work per call and runtime actions per cycle: bounded;
- recovery queries and stream startup buffer: bounded.

Configured limits may be lower than hard limits. These are operational safety
bounds, not limits on an economic portfolio model.

Reaching a capacity limit suspends the group and permits no new submit. It
does not evict an unknown child or forget Basket idempotency.

Terminal group eviction requires durable archive/checkpoint policy. V1 may
fail closed at configured retained-group capacity instead of silently
dropping identity history.

## 22. Failure Matrix

| Failure | Required behavior |
|---|---|
| Basket admission redelivery | Idempotent existing group |
| Changed admission under same ID | Conflict; no action |
| Basket approval without action permit | No child creation or submit |
| Stale group revision before preparation | Reject permit/action |
| Expired permit | Reject before child creation |
| Action/permit checksum mismatch | Reject before child creation |
| Journal append/fsync failure | No external call; latch halted |
| Operator halt before submit | No external call |
| Definitely-not-sent transport failure | Same child may receive one unchanged same-ID technical retransmission; otherwise local terminal failure |
| Possibly-sent failure or timeout | Recovery required; query, no resubmit |
| Immediate venue rejection | Persist terminal child rejection |
| Partial child fill | Update leg fill vector; reassess before next action |
| Fill during cancel | Existing child state machine handles race |
| REST not found | Remain unresolved |
| Venue fill behind local fill | Reconciliation conflict |
| Unknown child at close request | Refuse terminal close |
| Planner error | Suspend group; no external action |
| Risk/feature/Portfolio stale | No action permit |
| Private stream gap | Recovery required |
| Restart | Halt, replay, reconcile, reassess, explicit resume |

## 23. Compatibility

Unchanged:

- `BasketTargetIntent`;
- `PositionTargetIntent`;
- existing `OrderRequest` venue command;
- `OrderStateMachine` child lifecycle;
- Binance submit/cancel/query mapping;
- normalized REST/private-stream child observations;
- existing V1 order journal decoding;
- Strategy/Risk/OMS/Execution ownership.

Required after acceptance:

- additive strong group/action/permit IDs;
- new group contracts and state;
- additive group journal facts and version-aware replay;
- a shared durable execution handoff;
- correction of current single-leg submit composition;
- group runtime and bounded execution router;
- action-permit integration after ADR-012.

Old single-leg orders do not need a synthetic one-leg group. They only adopt
the shared safe submit handoff.

## 24. Security

- no credential enters Basket, group, permit, journal or planner;
- account IDs remain canonical internal identities;
- action and permit text is bounded and contains no arbitrary venue payload;
- action checksums detect content mismatch but do not authenticate operators;
- operator commands remain under the existing mTLS/HMAC/audit boundary;
- unknown execution state is never sanitized into success or failure;
- group/operator views must redact account and venue diagnostic fields under
  deployment policy;
- recovery actions require explicit authorization and audit.

## 25. Alternatives Considered

### Treat Basket `ALLOW` as permission to submit all legs

Rejected. State can change after Risk evaluation and child outcomes are not
atomic.

### Put `PARTIALLY_HEDGED/HEDGED` in Basket

Rejected. Basket is immutable intent, while hedge condition changes with
fills, positions, marks and Greeks.

### Put `HEDGED` directly in OMS group lifecycle

Rejected. OMS owns order facts, not portfolio Delta or option-risk models.

### One child per Basket leg

Rejected. Partial fills, cancel/replace and dynamic hedging require multiple
attempts.

### Pre-create every child at group admission

Rejected. Later quantities and prices may depend on actual earlier fills and
fresh Risk evidence.

### Store order type and sequence in `BasketTargetIntent`

Rejected by ADR-010. It merges economic objective and execution mechanism.

### Separate group journal

Rejected. Cross-journal crash consistency would be ambiguous.

### New Execution adapter for groups

Rejected. Venues still receive individual orders; current child adapters are
the correct boundary.

### Blindly retry unknown requests with a new client ID

Rejected. It can duplicate live exposure.

### Universal group `unhedged_exposure: Quantity`

Rejected. Cross-product and option exposure requires multipliers and Greeks.

### Reuse the synchronous market-event Pipeline as the group state machine

Rejected. A group spans fills, timers, cancels, reconciliation and restart.
A dedicated caller-driven runtime is required, while child submission reuses
the same safe handoff.

## 26. Consequences

### Positive

- makes approval/permission separation explicit;
- preserves exact Basket-to-group-to-child causation;
- reuses tested single-order OMS and Execution adapters;
- supports dynamic N-leg execution without a two-leg assumption;
- makes unknown state and restart first-class;
- gives ADR-012 authoritative fill vectors for exposure calculation;
- closes an existing single-leg durability/composition gap;
- keeps economic Carry lifecycle outside OMS.

### Costs

- adds group IDs, contracts, journal records and runtime orchestration;
- requires journal migration and mixed-version replay tests;
- requires a per-action Portfolio Risk permit;
- requires bounded group retention and operational controls;
- adds more latency because durability and Risk checks precede every action.

### Risks

- group state can become a second Portfolio model if ownership is not
  enforced;
- a planner can accidentally become strategy code if it owns economic targets;
- parallel action semantics can invalidate simple revision rules;
- optional durability would reintroduce crash ambiguity;
- insufficient group/action limits can exhaust memory or journal capacity;
- closing a group based only on child terminal states can misreport success.

## 27. Required Tests After Acceptance

### Approval and permission

- Basket admission creates a group and produces zero exchange calls;
- no action permit means no child;
- permit is exact, finite, single-action and revision-bound at preparation;
- changed action or stale permit fails before journal mutation;
- definitely-not-sent permits at most one same-action, same-child and
  same-`ClientOrderId` technical retransmission;
- retransmission never creates a new economic action;
- operator halt race prevents submit.

### Group and leg model

- generic two-to-16-leg groups;
- zero children at creation;
- multiple children for one Basket leg;
- exact signed cumulative fill vector;
- same contract for Spot/Perpetual and synthetic three-leg option hedge;
- no OMS `HEDGED` calculation.

### Durable handoff

Fault injection at:

```text
before group append
after group append
before child submit-intent append
after submit-intent fsync, before gateway
before send
after send, before response
after response, before outcome append
after outcome append
before private-stream fact
```

Every crash point must reconstruct a state that never blindly duplicates a
possibly-live order.

### Child outcomes

- accepted;
- rejected;
- definitely not sent;
- unknown after send;
- bridge timeout classified unknown;
- partial fill, cancel race and replace;
- multiple unknown children rejected by bounds.

### Restart

- existing V1 single-order journal replay unchanged;
- mixed legacy/group journal replay;
- group-child mapping recovery;
- stream-first buffering plus REST query;
- REST not found remains unresolved;
- group remains recovery-required until fresh Risk/operator resume;
- no automatic submit at startup.

### Compatibility

- existing Position Pipeline behavior remains;
- single-leg concrete composition persists `SUBMITTING` before gateway;
- immediate result returns to OMS;
- Execution adapters still accept unchanged `OrderRequest`;
- current Binance mappings and recovery tests remain green.

### Boundedness

- leg, child, attempt, action, active-group and retention limits;
- oversized group journal record;
- planner/action cycle budget;
- recovery query/buffer bounds;
- fail-closed behavior at every capacity.

## 28. Implementation Dependency

Under this accepted ADR, group contracts, state, journal evolution and the
shared durable execution handoff are assigned to T029-T031.

No exposure-changing group child may reach an Execution adapter until
ADR-012 accepts:

- whole-Basket Portfolio Risk approval;
- per-action permit semantics;
- fresh position/Delta/basis/margin evidence;
- continuous risk and recovery-action policy.

Offline ADR-011 state tests may use synthetic signed permits. Testnet and
production remain separately gated.

## 29. Review Decisions Incorporated

Web GPT resolved the eight requested review questions on 2026-07-28:

| Question | Incorporated decision |
|---|---|
| V1 concurrency | Hard maximum one exposure-changing in-flight submit per group; parallel mode requires a future ADR |
| Definitely-not-sent retry | No new economic action automatically; allow at most one unchanged same-`ClientOrderId` technical retransmission with definite not-sent proof |
| Recovery resume | Completed reconciliation, fresh Portfolio Risk and explicit operator resume are all mandatory |
| Group closure | `TARGET_CONFIRMED` requires fresh authoritative Portfolio/Risk confirmation |
| Implementation sequence | After acceptance, offline group model/journal/state/recovery may proceed; external exposure-changing group submit remains blocked by ADR-012 |
| Identity names | `PortfolioApprovalId` and `ExecutionPermitId` accepted |
| Operational bounds | Hard 16 legs, 8 children per leg and 64 children per group; configured limits may be lower |
| Journal evolution | One ordered mixed-version journal; immutable history is not rewritten in place |

The review also required explicit layering:

```text
Order Group execution intent
  -> ExecutionPlanRef
  -> ExecutionAction
  -> ExecutionActionPermit
  -> Child Order Attempt
```

That layering is incorporated in sections 1, 5 and 6.

## 30. Acceptance Record

The gate was satisfied on 2026-07-28:

1. Web GPT reviewed the Proposed handoff and supplied eight conditional
   decisions plus the Execution Plan/Action distinction.
2. The project owner supplied that review to Codex with an instruction to
   read and act; the review explicitly directs promotion after revision.
3. Codex incorporated every decision before promotion.
4. Interface names and hard bounds are fixed.
5. Mixed-version journal backward compatibility is explicit.
6. ADR-012 dependencies remain outside this ADR.
7. No Parent/Child code was written before acceptance.

Authorized scope after acceptance:

```text
T029  immutable group/plan/action/permit contracts and identifiers
T030  bounded group state, journal, replay and recovery model
T031  shared durable submit handoff and fail-closed group runtime boundary
A014  deterministic offline ADR-011 acceptance
```

T031 must keep exposure-changing Order Group calls from reaching any
Execution adapter until ADR-012 is accepted. Offline synthetic permits may
exercise preparation, state and recovery without granting live execution
authority.

## 31. Implementation Record

T029, T030, T031 and A014 were completed offline on 2026-07-28 in commit
`9c1b0afb09744759b98429f7d8e99542bebd0aa1`.

A post-implementation architecture review kept this ADR accepted and found
implementation gaps rather than design defects. Commit
`c2c306dbe7675076ae200021d2c98f127736f09e` closed them by adding the mandatory
post-durability/pre-I/O safety recheck, definitely-not-sent bridge
classification, configured active-group bounds, durable capacity suspension,
global child-identity collision checks, runtime-level single-writer
enforcement and the missing failure/race tests. No ADR-012 Risk logic or
grouped external execution was introduced.

Implemented modules:

```text
core/identifiers.py
oms/group_model.py
oms/group_codec.py
oms/group_state.py
oms/journal.py
runtime/execution_handoff.py
runtime/order_group_runtime.py
```

The single-leg Pipeline now persists `SUBMITTING` before external I/O and
returns immediate outcomes to OMS. The grouped runtime durably prepares and
replays synthetic children, but its external submission boundary always
raises before an Execution adapter. No ADR-012 Risk calculation or real
permit issuance was added.

The self-contained implementation evidence and test matrix are recorded in
`ai_collaboration/topics/funding_arbitrage/80_codex_adr011_implementation_acceptance.md`.

## 32. Accepted Execution-Stage Evolution Direction

Status: project-owner-approved architecture direction on 2026-08-05. This
clarification does not yet accept a Stage contract, enable parallel dispatch
or authorize any external execution.

The original V1 decision remains valid: it is the conservative N-leg execution
mode with a hard concurrency width of one. Its purpose is durable exact
authority, fresh Portfolio reassessment after each action and bounded UNKNOWN
recovery. Funding Carry may continue to select this mode; no later execution
architecture may make parallel dispatch mandatory for every Basket.

The project owner has now confirmed that bounded overlapping and parallel
multi-leg execution are definite platform requirements. Leg cardinality and
execution concurrency are therefore separate dimensions:

```text
Basket leg count        = 2..16
Execution Stage width   = 1..bounded configured maximum
Stage dispatch width    = 1..Stage width
```

### Stable design principles

1. V1 becomes the width-one case of one unified Stage execution model, not a
   separate legacy execution system.
2. A future planner proposes a bounded Stage containing one or more exact
   `ExecutionAction` values. Stage identity, base group revision and action
   membership are immutable.
3. Funding Carry may use terminal-serial, fill-driven overlapping or bounded
   parallel Stages according to its registered Execution Plan.
4. Portfolio Risk must authorize the complete Stage and a conservative
   partial-execution envelope. Basket admission remains distinct from Stage
   permission.
5. The complete Stage, Action identities and Child identities must be durable
   before the first external request is dispatched.
6. OMS and Runtime state mutation remain single-writer. Only venue I/O may be
   concurrent; callbacks are serialized into canonical state transitions.
7. Each Child retains an independent accepted, rejected, definitely-not-sent,
   partial, terminal or UNKNOWN result. Any unresolved truth is reconciled
   before automatic completion, compensation or replacement.
8. Cross-venue dispatch is best-effort concurrent execution, never an
   all-or-none atomicity claim.
9. `BasketTargetIntent`, Portfolio truth, Accounting truth, individual
   `ExecutionAction`, `OrderRequest` and exact Gateway routing remain reusable
   boundaries.
10. Planner, bounded dispatcher and recovery-decision policies are registered
    components, but none may bypass Risk, OMS, operator authority, durability
    or reconciliation.
11. Existing V1 journal history and width-one behavior require deterministic
    backward-compatible replay and regression coverage.
12. Basket maximum legs and Stage concurrency capacity are independent
    limits. A large Basket may be executed through multiple smaller Stages.

### Required reviewed follow-up

Before implementation, a separate ADR or explicit amendment must define:

- Stage and Stage-permit schemas and deterministic identities;
- base-revision and concurrent Child state semantics;
- partial-execution Risk bounds and permit consumption;
- atomic local persistence before concurrent fan-out;
- result-vector journaling, replay, reconciliation and recovery;
- configured Stage-width bounds and capacity behavior;
- migration, rollback and V1 compatibility acceptance tests.

This confirmed requirement satisfies the scenario and owner-direction parts
of the Kernel v1 change-control trigger. It does not waive the remaining
analysis, migration, test or external-authorization gates.
