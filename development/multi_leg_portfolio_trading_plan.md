# Multi-Leg Portfolio Trading Development Plan

Status: In progress — ADR-009/010/011 accepted; ADR-011 offline foundation
complete; application blocked by ADR-012 through ADR-014

Created: 2026-07-27

Planning baseline: `e5e5bc4c7788e61d91b413ece498bbcc9449d0ec`

First validating application: Funding Arbitrage

Production authorization: None

ADR progress: ADR-009 accepted on 2026-07-28; generic Snapshot Infrastructure
tasks T025/T026 and acceptance A012 are complete. ADR-010 was accepted after
current-code compatibility review; T027/T028/A013 are complete. ADR-011 was
accepted after incorporating the second Web GPT review; T029-T031/A014 are
complete for bounded offline implementation. ADR-012 through ADR-014 remain
blocked by their declared dependencies, and external exposure-changing group
submission is not authorized.

## 1. Purpose

This plan defines how the existing single-instrument trading foundation can be
extended to support bounded, generic N-leg portfolio objectives.

It is not a Funding-specific implementation plan. Funding Arbitrage is the
first application used to validate the generic capability. The same platform
primitives should later support:

- spot/perpetual carry;
- triangular arbitrage;
- calendar spreads;
- option spreads and hedged option portfolios;
- cross-venue arbitrage;
- market-making hedge groups.

This document is a development plan, not an accepted public contract. Exact
contracts, state machines and ownership become authoritative only after the
planned ADRs are accepted and the affected `interfaces/` and `architecture/`
documents are updated.

## 2. Design Position

The existing architecture remains valid:

```text
Market Data -> State -> Features -> Strategy -> Risk -> OMS -> Execution
```

Multi-leg support extends each relevant boundary without allowing an
application to bypass it:

```text
Per-instrument market states ----+
Feature states ------------------+
Account/position states ---------+--> Typed application snapshot
Health/clock states -------------+              |
                                                v
                                     Application Strategy
                                                |
                                                v
                                      Basket Target Intent
                                                |
                                                v
                                       Portfolio Risk
                                                |
                                                v
                                  OMS Parent Order Group
                                                |
                                                v
                                Child Order Execution Ports
                                                |
                                                v
                                            Exchanges

Fills / account / funding / fee facts
                    |
                    v
          Financial Ledger and Attribution
```

The platform owns reliable facts and generic execution mechanisms. The
application owns the economic objective and the definition of strategy
success.

## 3. Responsibilities: Policy Versus Mechanism

| Concern | Owner |
|---|---|
| Select instruments and direction | Application strategy |
| Define entry, exit and economic success | Application strategy |
| Define desired leg targets | Application strategy |
| Publish authoritative market facts | Market State owners |
| Publish authoritative balances and positions | Portfolio/Account owners |
| Assemble an application-specific typed snapshot | Application snapshot assembler, serialized by runtime |
| Approve the complete projected portfolio transition | Portfolio Risk |
| Own individual order truth | Existing OMS order state |
| Own parent/child execution-group truth | OMS order-group state |
| Communicate with a venue | Execution adapters |
| Decide application recovery policy | Application policy constrained by Risk |
| Persist actual execution and cash-flow facts | OMS and Financial Ledger |
| Determine whether a Carry position is hedged/active | Carry application aggregate |
| Calculate and attribute strategy PnL | Accounting plus application attribution |

The core must not contain Funding APR thresholds, basis-entry rules or
strategy-specific profit criteria.

## 4. Proposed Package Topology

The proposed target layout is:

```text
src/cex_quant/
  core/
    ids.py                         # new bounded-domain identities only

  instruments/                    # unchanged ownership
  market_data/                    # unchanged venue-neutral facts
  features/                       # registered scalar/derived information

  strategy/
    model.py                       # existing single-leg contracts remain
    basket.py                      # generic BasketTargetIntent contracts

  portfolio/
    contracts.py                  # existing account/position truth remains
    margin.py                      # normalized collateral/margin snapshots
    valuation.py                  # explicit portfolio valuation contracts

  risk/
    model.py                       # existing single-leg contracts remain
    portfolio.py                   # BasketRiskContext and BasketRiskDecision

  oms/
    model.py                       # existing child order contracts remain
    order_group.py                 # generic parent/child state and views
    order_group_journal.py         # durable group facts and replay

  execution/
    gateway.py                     # remains child-order oriented
    adapters/                      # remains venue-specific

  accounting/
    __init__.py
    cash_flow.py                   # funding, commissions and other cash flows
    ledger.py                      # durable, idempotent financial records
    attribution.py                 # strategy/application PnL projections

  applications/
    __init__.py
    carry/
      __init__.py
      funding_arbitrage/
        __init__.py
        model.py                   # CarryPair and CarryPosition aggregate
        snapshot.py                # typed CarryDecisionSnapshot
        features.py                # basis and expected-carry registrations
        strategy.py                # pure entry/exit portfolio policy
        risk_policy.py             # carry-specific limits via Risk protocols
        recovery_policy.py         # application response to group facts

  runtime/
    pipeline.py                    # existing single-leg pipeline remains
    basket_pipeline.py             # mandatory basket preflight and dispatch
    order_group_orchestrator.py    # serialized OMS/execution coordination
    application.py                 # composition root
```

The final filenames may change during ADR review. Package responsibilities and
dependency direction are the important constraints.

## 5. Dependency Rules

### 5.1 Allowed dependencies

In this diagram, `A -> B` means package A may import public contracts from B:

```text
instruments -> core
market_data -> instruments, core
features -> market_data/state views, instruments, core
portfolio -> instruments, core
strategy -> instruments, features, core
risk -> strategy, portfolio, features, instruments, core
oms -> instruments, core
execution -> OMS public order contracts, instruments, core
accounting -> canonical OMS/portfolio facts, instruments, core
applications -> strategy, portfolio, features, risk protocols,
                accounting views, instruments, core
runtime -> applications and every domain port needed for composition
```

The diagram is conceptual; the exact Python imports follow these rules:

1. `core` depends on no business package.
2. `strategy.basket` may depend on `core` and `instruments`, but not Risk,
   OMS, Execution, runtime or venue adapters.
3. `risk.portfolio` may depend on public strategy, instrument, feature and
   portfolio contracts.
4. `oms.order_group` must not depend on the concrete Risk engine. Runtime
   converts an allowed risk result into an OMS-owned approved group contract,
   matching the existing single-order pattern.
5. `execution` remains unaware of applications and parent-group economics. It
   submits, cancels and queries canonical child orders.
6. `accounting` consumes canonical facts and identities, never raw Binance
   payloads.
7. `applications` may depend on public domain contracts, but never on
   `runtime` or a venue adapter.
8. `runtime` is the only composition root and may depend on applications and
   domain ports.
9. No application can call an execution adapter directly.
10. No mutable state crosses a package boundary.

### 5.2 Prohibited structures

Do not create:

```text
TwoLegOms
ThreeLegOms
FourLegOms
strategy/funding.py
applications/carry/binance_client.py
dict[str, object] Basket payloads
unbounded child-order collections
application-owned copies of venue position truth
```

## 6. Generic N-Leg Boundary

The new public capability is bounded N-leg, not a special two-leg path.

The planned invariant is:

```text
2 <= number_of_legs <= configured_max_legs <= hard_safety_cap
```

The exact configured and hard limits are decided by ADR-010. Every collection
also requires limits for:

- active groups;
- active children per account;
- retained group history;
- journal record size;
- recovery work per cycle;
- pending execution actions;
- per-group lifetime.

Existing single-leg `PositionTargetIntent` remains supported. It is not
silently converted into a public one-leg Basket. Internally, implementation
may reuse common helpers as long as the current contract and behavior remain
unchanged.

## 7. Proposed Public Contracts

Basket contracts in section 7.2 follow accepted ADR-010. OMS, Risk,
Accounting and application contracts remain drafts until their owning ADRs
are accepted.

### 7.1 Core identities

Accepted ADR-010 reuses existing `IntentId` and adds:

```python
BasketLegId
ObjectiveTypeId
```

Later ADRs may add:

```python
OrderGroupId
ExecutionPlanId
GroupActionId
PortfolioApprovalId
ExecutionPermitId
CashFlowId
LedgerEntryId
ApplicationPositionId
```

They must follow existing immutable typed-ID conventions. They cannot be raw
interchangeable strings at public boundaries.

### 7.2 Strategy boundary

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketTargetLeg:
    leg_id: BasketLegId
    account_id: AccountId
    instrument_id: InstrumentId
    target_quantity: Quantity
    reason: str = ""


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
```

Required invariants:

- leg count is bounded;
- leg IDs are unique;
- legs use canonical account/instrument ordering;
- duplicate account/instrument scopes are rejected;
- instrument identities are canonical;
- target quantities are exact fixed point;
- the intent contains no account secret, order type, time-in-force, venue
  request or adapter object;
- expiry cannot precede decision time;
- Objective Type is a versioned registered reference, not a runtime import
  path or executable code.

The strategy output type may become:

```python
DecisionIntent = PositionTargetIntent | BasketTargetIntent
```

The existing `PositionTargetIntent` API and tests remain valid.

### 7.3 Snapshot boundary

There should not be one untyped universal snapshot containing optional fields
for every strategy. Each application defines a typed decision snapshot.

Shared observation metadata may use:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationStamp:
    source_id: str
    as_of_ns: UnixNanos
    receive_time_ns: UnixNanos
    quality: SnapshotQuality
    version: int
```

The Carry application can define:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CarryDecisionSnapshot:
    pair: CarryPair
    spot_view: ExecutableMarketView
    perpetual_view: ExecutableMarketView
    funding_view: FundingView
    account_view: AccountSnapshot
    margin_view: MarginSnapshot
    feature_view: FeatureSnapshot
    health: HealthReport
    assembled_at_ns: UnixNanos
    maximum_observed_skew_ns: int
    quality: SnapshotQuality
```

The assembler:

- owns only bounded latest references needed for its application;
- never becomes the authority for market or account truth;
- is called serially by runtime;
- preserves every source timestamp;
- rejects missing, stale, invalid or excessive-skew inputs;
- produces deterministic results under replay.

Common snapshot metadata should be extracted into a generic package only if
ADR-009 establishes a stable cross-application contract. Application-specific
fields stay in the application.

### 7.4 Portfolio Risk boundary

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketRiskContext:
    now_ns: UnixNanos
    intent: BasketTargetIntent
    current_portfolio: PortfolioSnapshot
    projected_legs: tuple[ProjectedLeg, ...]
    market_and_feature_quality: SnapshotQuality
    margin: MarginSnapshot
    clock_status: HealthStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class BasketRiskDecision:
    status: RiskDecisionStatus
    intent: BasketTargetIntent
    reasons: tuple[PortfolioRiskRejectReason, ...]
    projected_exposure: PortfolioExposure
```

V1 should prefer binary `ALLOW` or `REJECT` for Basket admission. Silent
per-leg modification can break the economic objective and identity
guarantees. If Risk proposes a modified Basket in the future, it must return
a new explicitly identified approved plan and the application must accept it
before group creation.

The mandatory invariant is:

```text
An identity-equal whole-Basket admission is required to create one group,
but that admission grants no permission to submit a child.

Every exposure-changing child submit requires a fresh finite permit covering
the exact Execution Action, group revision, Risk snapshot and expiry.
```

### 7.5 OMS boundary

Accepted ADR-011 makes OMS own a durable execution-control group independent
of the concrete Risk implementation:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupAdmission:
    approval_id: PortfolioApprovalId
    basket: BasketTargetIntent
    basket_checksum: str
    approved_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderGroupView:
    order_group_id: OrderGroupId
    source_intent_id: IntentId
    approval_id: PortfolioApprovalId
    revision: int
    status: OrderGroupStatus
    legs: tuple[OrderGroupLegView, ...]
    unresolved_action_ids: tuple[GroupActionId, ...]
    created_at_ns: UnixNanos
    last_transition_ns: UnixNanos
    recovery_reason: str
```

Generic OMS status must use execution-neutral language:

```text
CREATED
  -> ACTIVE <-> SUSPENDED
       |
       v
     RECOVERY_REQUIRED

ACTIVE / SUSPENDED
  -> CLOSING
  -> CLOSED
```

`PARTIALLY_FILLED` remains a child-order state. `UNKNOWN` is a child/action
condition that forces the group into `RECOVERY_REQUIRED`. `HEDGED` and
`PARTIALLY_HEDGED` are Portfolio Risk or Carry classifications derived from
authoritative positions, child fills, marks, multipliers and, when relevant,
Greeks. They are not OMS group control states.

OMS must expose facts, not decide whether the economic arbitrage succeeded.
One Basket leg maps to zero or more bounded child-order attempts; it is not a
one-leg-to-one-child contract.

### 7.6 OMS service port

Accepted ADR-011 defines a caller-driven, single-writer runtime. A versioned
Execution Plan proposes exact actions but grants no authority. Risk grants
one finite, single-action permit for one exact action:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPlanRef:
    execution_plan_id: ExecutionPlanId
    version: int
    parameters_checksum: str


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


class OrderGroupRuntime(Protocol):
    def create_group(
        self,
        admission: OrderGroupAdmission,
        execution_plan: ExecutionPlanRef,
    ) -> OrderGroupView: ...

    def propose_next_actions(
        self,
        order_group_id: OrderGroupId,
    ) -> tuple[ExecutionAction, ...]: ...

    def prepare_child_submit(
        self,
        action: ExecutionAction,
        permit: ExecutionActionPermit,
    ) -> OrderRequest: ...

    def apply_child_fact(
        self,
        order_group_id: OrderGroupId,
        event: OrderEvent,
    ) -> OrderGroupView: ...

    def snapshot(
        self,
        order_group_id: OrderGroupId,
    ) -> OrderGroupView: ...
```

`prepare_child_submit` must validate exact identity, checksum, group revision,
expiry, operator state and configured bounds, then atomically persist the
group/action/child mapping plus child submit intent before returning an
`OrderRequest` for any external call.

All returned actions and collections are bounded and deterministically
ordered. Action generation must be idempotent across retries and restarts.
An unknown result prohibits blind replacement until venue reconciliation
resolves the original child identity. V1 permits at most one
exposure-changing in-flight submit per group. A definitely-not-sent transport
failure may receive at most one unchanged technical retransmission using the
same action, child and `ClientOrderId`; changed order content creates a new
action and child attempt.

Execution ordering may require parallel-ready sets, linear stages or dynamic
hedge sizing from actual fills. ADR-011 defines a versioned execution-plan
contract without embedding application callbacks inside durable OMS records.

### 7.7 Execution boundary

Existing single-order interfaces remain:

```python
submit(OrderRequest)
cancel(CancelRequest)
query(OrderQuery)
```

The order-group orchestrator invokes these ports for child actions. Execution
adapters must not receive a `CarryPosition`, `BasketRiskContext` or application
object.

This preserves venue isolation and avoids duplicating Spot/Perpetual/Options
adapter code for every application.

### 7.8 Accounting boundary

Potential canonical cash-flow contract:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CashFlow:
    cash_flow_id: CashFlowId
    account_id: AccountId
    asset: AssetId
    amount: Money
    type: CashFlowType
    event_time_ns: UnixNanos
    instrument_id: InstrumentId | None
    client_order_id: ClientOrderId | None
    application_position_id: ApplicationPositionId | None
    venue_reference: str
    schema_version: int
```

`CashFlowType` distinguishes:

- trade settlement;
- trading commission;
- funding settlement;
- borrow interest;
- transfer;
- withdrawal;
- adjustment.

The ledger requires an idempotency key, exact fixed-point amounts, explicit
asset denomination, provenance and reconciliation status.

Accounting must not block the order-state hot path. Durable handoff and
failure policy must be decided explicitly; losing financial evidence cannot
be treated as success.

## 8. Application Interfaces

### 8.1 Carry application input

The Funding application consumes only its typed immutable snapshot:

```python
class CarryStrategy(Protocol):
    @property
    def strategy_id(self) -> StrategyId: ...

    def on_snapshot(
        self,
        snapshot: CarryDecisionSnapshot,
    ) -> tuple[BasketTargetIntent, ...]: ...
```

It performs no network, filesystem, database or adapter I/O.

### 8.2 Carry position aggregate

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CarryPositionView:
    position_id: ApplicationPositionId
    pair: CarryPair
    source_intent_id: IntentId
    order_group_ids: tuple[OrderGroupId, ...]
    target_legs: tuple[BasketTargetLeg, ...]
    actual_legs: tuple[ActualLeg, ...]
    status: CarryPositionStatus
    expected_carry: FeatureValue
    opened_at_ns: UnixNanos | None
    last_reconciled_ns: UnixNanos
```

Possible application statuses:

```text
PROPOSED
  -> OPENING
  -> PARTIALLY_HEDGED
  -> HEDGED
  -> ACTIVE
  -> CLOSING
  -> CLOSED

OPENING / PARTIALLY_HEDGED / CLOSING
  -> RECOVERY_REQUIRED
  -> HALTED
```

Actual legs are reconciled from OMS fills and authoritative Portfolio/Account
positions. The application aggregate cannot independently overwrite actual
venue holdings.

### 8.3 Recovery policy

The application may choose among allowed economic responses:

- wait within a bounded hedge timeout;
- resize the unfilled hedge using actual fills;
- cancel remaining children;
- request reduce-only unwind;
- request operator intervention.

Risk approves the permitted envelope. OMS performs and records the actions.
The application cannot submit an adapter request directly.

## 9. Runtime Interaction

The planned basket pipeline is:

```text
1. health gate
2. obtain valid typed application snapshot
3. strategy produces zero or more bounded Basket intents
4. validate intent schema and identity
5. build complete Portfolio Risk context
6. evaluate the whole Basket
7. reject entire Basket on any failure
8. convert allowed decision into OMS-owned approved group intent
9. durably create parent group and child identities
10. request bounded next actions from OMS
11. dispatch child actions through existing Execution ports
12. feed submit/query/cancel/fill facts back to OMS
13. publish immutable group facts to Risk, application and accounting
```

Steps 1–8 occur before any child reaches Execution.

Runtime owns serialization and assembly. It does not own economic state,
canonical orders or venue positions.

## 10. State Ownership Additions

| State | Single writer | Readers | Recovery authority |
|---|---|---|---|
| Per-instrument market state | Existing Market State owner | Features, snapshot assembler | Market replay/resync |
| Funding state | Funding state owner defined by ADR-009 | Carry snapshot assembler, monitoring | Market replay/refetch |
| Margin/collateral state | Portfolio/Account Engine | Risk, application snapshot | REST/private-stream reconciliation |
| Application decision snapshot | Application snapshot assembler | Strategy, Risk, recorder | Rebuilt from source states |
| Basket risk state | Risk Engine | OMS gate, operations | Re-evaluation from durable intent and snapshots where allowed |
| Parent order-group state | OMS | Risk, application, operations | OMS group journal plus venue reconciliation |
| Carry position aggregate | Carry application owner | Strategy, Risk, accounting | Application journal plus OMS/Portfolio reconciliation |
| Financial ledger | Accounting Engine | Attribution, operations, audit | Ledger replay and venue reconciliation |

No state has two writers. Derived application views never replace source
authority.

## 11. Compatibility and Migration

### 11.1 What remains unchanged

- current Market Event schemas;
- existing per-instrument state engines;
- `PositionTargetIntent`;
- current single-instrument `RiskContext` and `RiskDecision`;
- current `OrderRequest`, `OrderEvent`, `OrderView` and state machine;
- authenticated Binance child-order adapters;
- existing single-leg runtime behavior;
- current test and recovery evidence.

### 11.2 Additive extensions

- new typed IDs;
- new Basket strategy contracts;
- new portfolio-risk contracts;
- new OMS group state and journal;
- new account/margin adapters and snapshots;
- new accounting domain;
- new application hierarchy;
- new basket runtime composition.

### 11.3 Migration rule

No existing public contract changes until:

1. the owning ADR is accepted;
2. compatibility tests are written;
3. package exports are updated explicitly;
4. persistent schema versioning is defined;
5. old journal replay remains supported or a migration tool is accepted.

The existing single-leg pipeline remains the regression reference while the
new basket path is developed.

## 12. Planned ADR Sequence

| ADR | Decision required before implementation |
|---|---|
| ADR-009 Portfolio Snapshot Model | Source ownership, freshness, skew, quality and typed application assembly |
| ADR-010 Basket Intent Architecture | Generic bounded N-leg schema, identity, limits and single-leg compatibility |
| ADR-011 Parent Order Group and Multi-leg Execution Model | Generic group lifecycle, per-action permission, execution plan, durable handoff, journal, partial/unknown/recovery |
| ADR-012 Portfolio Risk Extension | Whole-basket preflight, exposure models and continuous supervision |
| ADR-013 Financial Ledger Model | Cash-flow authority, idempotency, reconciliation and PnL attribution |
| ADR-014 Carry Application Boundary | Application package ownership, public API and prohibited dependencies |

ADR-010 and ADR-011 must explicitly avoid two-leg-only contracts.

## 13. Development Workstreams

Task IDs will be assigned only after the relevant ADR is accepted.

### Workstream M1 — Snapshot and source state

- Funding state owner;
- mark/index/executable-price views;
- Binance account and margin normalization;
- typed Carry snapshot assembler;
- freshness/skew/quality gates;
- deterministic replay.

Depends on ADR-009.

### Workstream M2 — Basket contracts

- core identities;
- generic bounded leg and Basket intent;
- strategy output union;
- validation and serialization;
- single-leg compatibility tests.

Depends on ADR-010.

### Workstream M3 — OMS order groups

- approved group contract;
- group state machine;
- deterministic child identities;
- journal and replay;
- next-action protocol;
- partial, unknown, cancel and recovery handling;
- runtime orchestrator.

Depends on ADR-011 and M2.

### Workstream M4 — Portfolio Risk

- projected portfolio;
- net/gross exposure;
- product Delta;
- basis and legging risk;
- margin and liquidation inputs;
- complete Basket preflight;
- continuous risk action protocol.

Depends on ADR-012, M1 and M2.

### Workstream M5 — Financial Ledger

- canonical cash-flow types;
- Binance funding/commission/account sources;
- idempotent durable ledger;
- REST/private-stream reconciliation;
- PnL attribution and invariants.

Depends on ADR-013 and M1.

### Workstream M6 — Carry application

- CarryPair metadata;
- registered basis and expected-carry features;
- CarryPosition aggregate;
- pure strategy;
- risk/recovery policies;
- application composition.

Depends on ADR-014 and M1–M5.

### Workstream M7 — Acceptance

- generic N-leg contract/state tests;
- Funding two-leg scenarios;
- at least one synthetic three-leg scenario proving the core is not hard-coded
  to two legs;
- restart/reconciliation matrix;
- bounded-memory and latency tests;
- Testnet only after independent authorization.

Depends on M1–M6.

## 14. Test and Acceptance Matrix

### 14.1 Compatibility

- all existing regression and acceptance tests continue to pass;
- old OMS journals replay unchanged;
- existing single-leg submissions do not create an Order Group;
- existing Risk rejection still prevents OMS and Execution.

### 14.2 Generic N-leg invariants

- reject fewer than two legs;
- reject more than configured or hard maximum legs;
- reject duplicate leg IDs;
- preserve deterministic leg ordering;
- reject unbounded or malformed policies;
- approve/reject the whole Basket before any child submit;
- create stable parent and child IDs across retry/restart;
- never submit an unknown-state child again before reconciliation.

### 14.3 Two-leg Funding validation

- complete coherent snapshot;
- stale/skewed source rejection;
- both legs risk-approved before first submit;
- partial first leg and dynamically sized hedge;
- second-leg failure;
- funding reversal;
- margin deterioration;
- fee/funding/PnL reconciliation;
- restart during every non-terminal group state.

### 14.4 Synthetic three-leg validation

Use an offline deterministic application fixture, not a production strategy:

```text
Leg A -> Leg B -> Leg C
```

Verify:

- all three identities and risk projections;
- bounded staged activation;
- failure at each stage;
- partial fills on more than one leg;
- recovery and cancel behavior;
- journal replay;
- no two-leg assumptions in schemas or loops.

This test proves generic platform structure without claiming triangular
arbitrage support.

### 14.5 Accounting

- duplicate venue cash flow is idempotent;
- funding and commission remain separate types;
- asset denominations never mix silently;
- attribution components reconcile to ledger totals;
- missing or conflicting financial evidence is explicit;
- ledger failure cannot be reported as successful accounting.

## 15. Operational and Security Gates

Before Testnet:

- bounded group, child and recovery queues;
- aggregate health for snapshot, group OMS, account state and ledger;
- operator halt blocks new groups and children;
- reduce-only recovery requires an explicit approved path;
- credentials remain adapter-only;
- no application state or journal contains secrets;
- mTLS/operator audit controls cover group recovery commands;
- restart, slow storage, full storage, disconnect and clock-failure tests pass.

Before production review:

- target-host latency and soak evidence;
- live account/margin and funding reconciliation;
- ledger backup and retention;
- group-level incident runbook;
- manual recovery exercise;
- branch protection and required CI;
- explicit production go/no-go review.

## 16. Documentation Deliverables

When the ADRs are accepted, update:

- `architecture/module_topology.md`;
- `architecture/state_ownership.md`;
- `architecture/system_architecture.md`;
- `interfaces/order_schema.md`;
- a new Basket intent schema;
- a new portfolio-risk schema;
- a new cash-flow/ledger schema;
- package `__init__.py` responsibilities and `__all__`;
- `development/tasks.md`;
- `development/testing_strategy.md`;
- deployment, recovery and incident runbooks.

This plan alone does not authorize those contract changes.

## 17. Exit Criteria

The generic multi-leg core is complete only when:

1. ADR-009 through ADR-014 are accepted;
2. all new public contracts and ownership are documented;
3. existing single-leg behavior remains compatible;
4. complete Basket admission precedes group creation, and every
   exposure-changing child submit has its own exact finite Risk permit;
5. parent/child state is durable and restart-safe;
6. generic N-leg bounds are enforced;
7. Funding two-leg and synthetic three-leg acceptance pass;
8. account, margin and ledger facts reconcile;
9. branch coverage and existing CI gates pass;
10. no Testnet or production authorization is inferred from offline success.

## 18. Immediate Next Step

T029, T030, T031 and A014 are complete. The next architecture task is to
draft and review ADR-012 against the immutable per-leg fill/working vectors
and exact action-permit validation boundary. External group submission
remains blocked until ADR-012 is accepted and its implementation tasks are
explicitly authorized.

Do not create Funding Arbitrage application code. Basket decision contracts
and the bounded offline OMS Order Group foundation are complete. Portfolio
Risk, Financial Ledger and Carry implementation remain blocked by their
owning ADRs.
