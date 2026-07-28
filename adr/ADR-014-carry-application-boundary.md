# ADR-014 Carry Application Boundary

## Status

Proposed - 2026-07-28.

This ADR is prepared for the 2026-07-29 batch architecture review. It changes
no source contract and grants no Funding Arbitrage, Testnet or production
authorization.

Reviewed baseline:

`fa0df9e2a015db258457d226c7ed9fa5c689b8eb`

ADR-014 may be reviewed while ADR-012 and ADR-013 are Proposed, but it cannot
be accepted as an implementation authorization until their final accepted
contracts are compatible with this boundary. Carry application code starts
only after ADR-009 through ADR-014 are Accepted and the required platform
capabilities are implemented and accepted.

## Context

Funding Arbitrage is the first application that exercises the complete
portfolio trading platform:

```text
coherent multi-source state
  -> portfolio objective
  -> portfolio Risk admission
  -> uncertain N-leg execution
  -> authoritative account state
  -> financial reconciliation and attribution
```

It must not become:

- `strategy/funding.py`;
- a special two-order Execution adapter;
- a Funding branch inside OMS or Risk;
- an owner of venue market, position or ledger truth;
- a shortcut around grouped execution authorization.

The platform already has or proposes the generic layers:

```text
ADR-009  coherent typed decision snapshots
ADR-010  bounded N-leg economic targets
ADR-011  durable parent Order Group execution control
ADR-012  Portfolio Risk admission and action authorization
ADR-013  financial facts, ledger and PnL attribution
```

ADR-014 defines the application boundary that composes those capabilities
without taking ownership away from them.

## Current-Code Findings

### Reusable generic strategy contract

`StrategyRuntime` already:

- accepts `DecisionSnapshotPublication[object]`;
- invokes a pure synchronous `Strategy`;
- permits `BasketTargetIntent`;
- requires Basket output to reference the exact input `DecisionSnapshotId`;
- validates Objective registration and deployment policy;
- preserves existing `PositionTargetIntent` behavior.

`StrategyDecision` already supports a tuple of generic `DecisionIntent`.
Funding Carry does not require a new strategy output wrapper or a change to
the single-leg intent.

### Reusable snapshot infrastructure

`SnapshotCoordinator` already:

- retains one bounded latest observation per declared source;
- evaluates source freshness, arrival age, future skew and coherence;
- publishes only `READY` immutable typed values;
- provides deterministic identity and replay behavior;
- delegates semantic assembly to a pure application `SnapshotAssembler`.

ADR-014 needs a typed Carry value and assembler. It does not need a generic
Event Bus or a universal Portfolio snapshot with optional application fields.

### Generic Basket intent is complete

`BasketTargetIntent` already contains:

- complete 2-to-16-leg absolute account/instrument targets;
- a stable versioned `ObjectiveTypeRef`;
- exact Snapshot causation;
- deterministic canonical leg identity/order;
- bounded validity and deployment policy.

Funding Carry must use this contract. It must not introduce a two-leg-only
intent or embed child order types, leg order or retry policy into the Basket.

### Generic OMS facts are sufficient as inputs

`OrderGroupView` exposes:

- source Intent and Portfolio approval identity;
- immutable execution-plan reference;
- group revision and execution-control status;
- per-leg target, signed cumulative fills and working quantity;
- child/action outcome and unknown/recovery evidence.

This is sufficient for the Carry application to observe execution progress.
It does not tell whether the position is economically hedged, profitable or
active, and must not be extended to do so.

### Missing application domain

There is no `cex_quant.applications` package and no:

- `ApplicationPositionId`;
- Carry pair definition;
- typed Carry decision snapshot;
- Carry position aggregate;
- economic lifecycle and hedge assessment;
- application ownership registration;
- application recovery proposal;
- application journal/replay boundary.

### Platform dependencies are not complete

The current external single-leg pipeline explicitly rejects Basket intents.
ADR-011 grouped external submission remains blocked. ADR-012 and ADR-013 are
Proposed, not implemented.

The current system also lacks accepted implementations for:

- normalized margin/liquidation source views;
- a state owner that publishes the latest Funding market view;
- Portfolio Risk admission/action permits;
- financial settlement/fee ledger and allocation.

ADR-014 design cannot turn those missing platform capabilities into
application-owned substitutes.

## Decision Summary

Add:

```text
cex_quant.applications.carry
cex_quant.applications.carry.funding_arbitrage
```

The Carry application owns:

1. Carry instrument-pair and application-position identity;
2. application-specific typed decision snapshots and semantic assembly;
3. pure entry, exit and economic recovery policy;
4. the Carry economic-position aggregate;
5. application lifecycle, hedge assessment and ownership evidence;
6. consumption of immutable Risk, OMS, Portfolio and Accounting views;
7. application-level expected-versus-realized performance presentation.

It does not own:

- market, Funding, account, position or margin source truth;
- generic Feature storage;
- Basket approval or execution permission;
- execution-plan selection, child order creation or submission;
- Order Group, child order or recovery truth;
- ledger transactions or PnL source truth;
- operator authority.

## 1. Terminology

### Carry family

Applications that seek economic return from financing, Funding, term
structure or related basis while managing a hedged portfolio.

### Funding Carry application

The first Carry application, relating a Spot leg and a perpetual leg for the
same economic underlying. Its first MVP is two-leg, but it uses the generic
N-leg platform.

### Carry pair

Immutable application metadata that relates the economic underlying, Spot
instrument, perpetual instrument, account scopes and contract conversion
rules.

### Carry decision snapshot

An immutable `READY` application value assembled from authoritative source
views under ADR-009. It is decision evidence, not a state owner.

### Carry position

A durable application aggregate representing one economic Carry objective
across opening, active management and closing. It references platform facts
but does not copy or replace them.

### Lifecycle state

The application control phase such as opening, active or closing.

### Hedge assessment

The application's economic interpretation of current authoritative exposure
relative to its Carry target and accepted tolerance.

### Ownership evidence

Immutable evidence relating an `ApplicationPositionId` to economic position
quantities and financial allocation scope. It does not create venue position
truth or edit the ledger.

### Recovery proposal

A pure application recommendation to restore or flatten an economic target.
It is not an OMS action, Risk permit, cancel command or Execution request.

## 2. Package Topology

The target boundary is:

```text
src/cex_quant/
  applications/
    __init__.py
    carry/
      __init__.py
      model.py
      state.py
      journal.py
      ownership.py
      recovery.py
      funding_arbitrage/
        __init__.py
        model.py
        snapshot.py
        features.py
        strategy.py
        objectives.py
        policy.py

  market_data/
    state/
      funding.py

  runtime/
    carry_application_runtime.py
    basket_pipeline.py
    application.py
```

Exact filenames may change after review; the ownership boundaries may not.

Responsibilities:

| Package | Responsibility |
|---|---|
| `applications.carry.model` | Generic Carry identifiers, lifecycle and read views |
| `applications.carry.state` | Durable economic-position aggregate |
| `applications.carry.journal` | Application facts, replay and revision evidence |
| `applications.carry.ownership` | Application position/leg ownership evidence |
| `applications.carry.recovery` | Pure economic recovery proposals |
| `funding_arbitrage.model` | Spot/perpetual relation and hedge semantics |
| `funding_arbitrage.snapshot` | Typed input and pure semantic assembler |
| `funding_arbitrage.features` | Application feature definitions/calculators |
| `funding_arbitrage.strategy` | Pure entry/exit target policy |
| `funding_arbitrage.objectives` | Versioned Objective Type registrations |
| `funding_arbitrage.policy` | Bounded economic thresholds/configuration |
| `market_data.state.funding` | Authoritative latest normalized Funding market view |
| `runtime` | Single-writer orchestration and mandatory platform gates |

The Funding state owner belongs to Market Data because Funding rate, interval
and next settlement time are market facts. The application may consume its
immutable `FundingView`; it may not become the source of truth.

## 3. Dependency Direction

Allowed:

```text
applications
  -> core identifiers/fixed-point types
  -> public instrument contracts
  -> public Market/Portfolio/Feature/Snapshot views
  -> Strategy Basket contracts
  -> public OMS/Risk/Accounting read views

runtime
  -> applications and every platform service port

generic platform domains
  -> no application implementation
```

Forbidden:

- Applications cannot import venue adapters.
- Applications cannot call Execution gateways.
- Applications cannot instantiate or mutate an OMS Order Group.
- Applications cannot issue `ExecutionActionPermit`.
- Applications cannot append ledger transactions or corrections.
- OMS, Risk and Accounting cannot branch on strategy name, Carry type or
  Funding Objective ID.
- `market_data`, `portfolio`, `risk`, `oms` and `accounting` cannot import
  `applications.carry`.
- Application callbacks cannot perform I/O or read mutable service state.

## 4. Identities

Add strong identifiers only after acceptance:

```text
ApplicationPositionId
CarryPairId
CarryOwnershipId
CarryApplicationFactId
```

Existing identities remain authoritative:

```text
StrategyId
DecisionSnapshotId
IntentId
BasketLegId
PortfolioApprovalId
OrderGroupId
GroupActionId
LedgerTransactionId
AttributionAllocationId
```

`ApplicationPositionId` identifies an economic application aggregate. It is
not interchangeable with:

- a venue `PositionId`;
- a Basket `IntentId`;
- an `OrderGroupId`;
- an accounting allocation;
- a strategy instance.

One Carry position may reference several opening, adjustment, recovery and
closing Intents/Order Groups over its lifetime.

## 5. Carry Pair Contract

The semantic contract is:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryPair:
    pair_id: CarryPairId
    underlying_asset_id: AssetId
    spot_account_id: AccountId
    spot_instrument_id: InstrumentId
    perpetual_account_id: AccountId
    perpetual_instrument_id: InstrumentId
    quantity_conversion_policy_ref: str
    schema_version: int
```

Validation must prove:

- Spot leg has Spot instrument kind;
- perpetual leg has a supported perpetual instrument kind;
- both instruments represent the configured economic underlying;
- account/venue/instrument references are internally consistent;
- quantity conversion and contract multiplier policy is explicit;
- fixed-point scales and bounds are supported;
- identity is deterministic from immutable semantic content;
- no API client, callback or executable import path is persisted.

Symbol string similarity is not sufficient proof of a shared underlying.

## 6. Typed Decision Snapshot

### 6.1 Values

Do not create one object with optional fields for every application phase.
Funding Carry defines a small typed union with a shared immutable market
component:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryMarketInputs:
    pair: FundingCarryPair
    spot_market: ExecutableMarketView
    perpetual_market: ExecutableMarketView
    mark_and_index: PerpetualReferenceView
    funding: FundingView
    account: CarryAccountView
    margin: MarginView
    features: FeatureSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryEntrySnapshot:
    market: FundingCarryMarketInputs


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryPositionSnapshot:
    market: FundingCarryMarketInputs
    application_position: CarryPositionView
    portfolio_risk: PortfolioRiskReadView
    order_groups: tuple[OrderGroupView, ...]


FundingCarryDecisionSnapshot = (
    FundingCarryEntrySnapshot | FundingCarryPositionSnapshot
)


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryPerformanceView:
    application_position: CarryPositionView
    accounting: ApplicationAttributionView
```

Entry does not pretend that an application position already exists.
Monitoring, close and recovery require explicit current application, Risk and
bounded Order Group views. Accounting attribution is a separate performance
view: Accounting delay or failure must not prevent a reduce/close/recovery
decision. Later phases may add another strongly typed variant with its own
exact source policy; they do not add loosely optional fields to a universal
object.

The outer
`DecisionSnapshotPublication[FundingCarryDecisionSnapshot]` supplies:

- Snapshot identity;
- source observation identity;
- source and assembly times;
- coherence measurements;
- readiness assessment and policy version.

The typed value does not duplicate generic Snapshot metadata.

### 6.2 Source authority

Each value is an immutable source-owner projection:

| Value | Authority |
|---|---|
| Spot/perpetual executable market | Market state |
| Mark/index | Market state |
| Funding rate/next time | Funding market-state owner |
| balances/positions | Portfolio/account state |
| margin/liquidation inputs | Portfolio/account state |
| basis/expected carry/cost estimates | Features |
| Portfolio Risk exposure/directive | ADR-012 Risk read view |
| actual Funding/fees/PnL | ADR-013 Accounting view |
| Carry lifecycle/hedge state | Carry application aggregate |

### 6.3 Pure semantic assembler

The assembler:

- receives only the ordered immutable observations and Snapshot metadata;
- verifies exact expected source types;
- verifies pair, account, underlying and instrument relationships;
- rejects an incoherent mix of application-position revisions;
- returns one immutable typed value;
- performs no I/O and owns no source state;
- is deterministic under replay.

Generic freshness/skew/readiness stays in ADR-009 `SnapshotCoordinator`.
Application semantic validation does not recreate it.

### 6.4 Different decision policies may use different sources

Entry, active monitoring, recovery and close decisions do not necessarily
have identical freshness or source requirements.

ADR-014 permits separate versioned Snapshot policies/scopes, for example:

```text
carry.<pair>.entry
carry.<pair>.monitor
carry.<pair>.recovery
carry.<pair>.close
```

All exposure-changing output still requires a `READY` snapshot and later
independent ADR-012 authorization.

## 7. Feature Boundary

The following are Features, not canonical market facts or ledger facts:

- executable Spot/perpetual basis;
- normalized hedge ratio;
- expected Funding income;
- annualized expected carry/APR;
- estimated commissions and slippage;
- borrow-cost estimate;
- expected net carry;
- Funding reversal signal;
- option Greeks and volatility surfaces for future Carry variants.

Raw Funding rate and next Funding time remain Market Data. Actual Funding
settlement remains Accounting.

Application-specific feature calculators may live under
`applications.carry.funding_arbitrage.features`, but they:

- implement public Feature contracts;
- run through the generic Feature engine;
- publish immutable `FeatureSnapshot` values;
- do not become an alternative Feature store;
- cannot read venues or submit actions.

Expected carry/APR is a decision estimate. It must never be displayed as
realized strategy PnL.

## 8. Objective Types and Strategy Output

Funding Carry registers stable versioned Objective Types, for example:

```text
carry.funding.open@1
carry.funding.rebalance@1
carry.funding.close@1
carry.funding.recover@1
```

Names are metadata and routing keys, not permission.

The pure strategy:

```text
READY FundingCarryDecisionSnapshot
  + immutable Carry position view
  + versioned economic policy
  -> zero or more BasketTargetIntent
```

Every Basket:

- contains the complete absolute account/instrument target;
- references the exact input `DecisionSnapshotId`;
- uses the generic 2-to-16-leg contract;
- is deterministic under replay;
- contains no order type, TIF, leg order, retry or venue API parameter.

The current `StrategyDecision` contract remains unchanged.

## 9. Execution-Plan Boundary

Application Strategy decides the economic target. It does not decide how the
target is transmitted.

```text
ObjectiveTypeRef
  -> deployment Runtime mapping
  -> registered ExecutionPlanRef
  -> OMS execution planning
```

The mapping is versioned deployment configuration outside the Basket.

The application may publish economic constraints as accepted immutable
policy data, but it may not:

- construct an `ExecutionAction`;
- choose a first child dynamically inside Strategy;
- specify a Funding-only OMS callback;
- bypass group admission;
- retry an UNKNOWN action;
- convert a recovery proposal directly into an order.

OMS and Execution remain application-neutral.

## 10. Carry Position Aggregate

### 10.1 Aggregate view

The semantic read view is:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CarryPositionView:
    application_position_id: ApplicationPositionId
    strategy_id: StrategyId
    pair_id: CarryPairId
    revision: int
    lifecycle: CarryLifecycle
    hedge_state: CarryHedgeState
    financial_state: CarryFinancialState
    opening_snapshot_id: DecisionSnapshotId
    latest_snapshot_id: DecisionSnapshotId
    intent_ids: tuple[IntentId, ...]
    order_group_ids: tuple[OrderGroupId, ...]
    leg_ownership: tuple[CarryLegOwnership, ...]
    last_transition_ns: UnixNanos
    recovery_reason: str
```

References are bounded. Long history remains in the application journal,
OMS/Risk/Accounting journals and operational archives.

The generic Carry view stores only `CarryPairId`; it cannot import a
Funding-specific pair type. A Funding application composes the generic view
with its own `FundingCarryPair` in the typed decision Snapshot.

### 10.2 Orthogonal state dimensions

Do not create one enum that conflates execution, economic exposure and
financial reconciliation.

Application lifecycle:

```text
PROPOSED
OPENING
ACTIVE
CLOSING
CLOSED
RECOVERY_REQUIRED
HALTED
```

Economic hedge assessment:

```text
UNKNOWN
UNHEDGED
PARTIALLY_HEDGED
HEDGED
```

Financial finality:

```text
NOT_READY
PROVISIONAL
RECONCILED
```

OMS continues to own:

```text
OrderGroupStatus
ExecutionActionState
child-order state
```

Risk continues to own:

```text
exposure snapshot
limit decisions
admission reservation
action permit
risk directive
```

Accounting continues to own:

```text
financial fact
ledger posting
source reconciliation
allocation
attribution view
```

### 10.3 Meaning of hedge state

`PARTIALLY_HEDGED` and `HEDGED` are formal application states, but they are
derived from authoritative Portfolio/Risk exposure and the application pair's
accepted hedge tolerance.

They are not derived only from OMS fill quantity.

The calculation must use:

- authoritative effective positions under ADR-012 cursor semantics;
- instrument multipliers and quantity conversion;
- working/unresolved exposure when relevant;
- fixed-point, versioned tolerances;
- fresh marks/Greeks for products whose Delta is price dependent.

For linear Spot/perpetual MVP, base-equivalent Delta may be sufficient. Future
option Carry must use accepted option Delta/Greek inputs without changing OMS.

`UNKNOWN` is mandatory when any required exposure, mark, multiplier, cursor or
quality input is unresolved.

### 10.4 Meaning of ACTIVE

`ACTIVE` requires all configured application conditions:

- opening target is confirmed from authoritative Portfolio state;
- hedge state is `HEDGED`;
- no unresolved OMS outcome blocks economic certainty;
- no Risk recovery/liquidation directive is active;
- ownership evidence is registered;
- required monitoring Snapshot sources are ready;
- required control-state health permits continued application operation.

`ACTIVE` does not mean future Funding is guaranteed or PnL is positive.
Accounting readiness changes financial state and the new-exposure health gate;
it cannot block an existing position's close or safety recovery.

### 10.5 Meaning of CLOSED

`CLOSED` means the configured economic close target is confirmed and every
linked opening/adjustment/closing group has no unresolved exposure-changing
outcome.

Final PnL may still be `PROVISIONAL` until ADR-013 source and balance
reconciliation is complete. Closing physical exposure and final financial
reconciliation are separate dimensions.

## 11. Application Fact Journal

Carry economic lifecycle must survive restart.

The application owns an append-only, checksummed, bounded single-writer
journal of application facts such as:

```text
CarryPositionCreated
CarryIntentLinked
CarryOrderGroupLinked
CarryOwnershipRegistered
CarryLifecycleChanged
CarryRecoveryRequired
CarryPositionHalted
CarryPositionClosed
```

Each fact includes:

- `CarryApplicationFactId`;
- `ApplicationPositionId`;
- expected prior and new application revision;
- exact referenced Snapshot/Intent/Group/Risk/Accounting evidence IDs;
- event and recorded times;
- policy/schema version;
- bounded reason.

The journal:

- does not copy Order Group child events;
- does not copy Portfolio positions as authority;
- does not create Risk approval;
- does not contain ledger postings;
- never treats replay order as venue source truth;
- fails closed on corruption, gaps or incompatible policy.

Derived hedge and financial states may be rebuilt from source views. Durable
lifecycle transitions record the evidence that justified the change.

## 12. Position Ownership and Allocation

### 12.1 Absolute Basket target versus owned contribution

`BasketTargetIntent` contains absolute account/instrument targets. A Carry
position needs separate ownership evidence so it does not claim unrelated
pre-existing inventory.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CarryLegOwnership:
    ownership_id: CarryOwnershipId
    application_position_id: ApplicationPositionId
    account_id: AccountId
    instrument_id: InstrumentId
    baseline_quantity: Quantity
    intended_owned_delta: Quantity
    effective_from_ns: UnixNanos
    source_snapshot_id: DecisionSnapshotId
    policy_version: int
```

The opening target must satisfy:

```text
absolute target
  = proven baseline
  + application-owned target contribution
  + other admitted/reserved contributions
```

ADR-012 owns reservation and portfolio-conflict safety. ADR-014 owns the Carry
position's economic ownership declaration.

### 12.2 Accounting interaction

The application emits immutable ownership evidence to an Accounting allocation
port. It cannot write ledger transactions or force an allocation result.

Accounting:

- validates evidence and scope;
- allocates direct group/leg fills when causation is complete;
- allocates account-level Funding only when ownership is complete;
- retains `UNALLOCATED` when evidence is ambiguous;
- publishes immutable attribution views back to the application.

### 12.3 First-MVP account rule

The first exposure-changing Funding Carry MVP requires either:

1. a dedicated account/subaccount and exclusive instrument ownership; or
2. a previously accepted complete shared-account ownership/allocation model.

It must not infer ownership from strategy labels or balance differences.

## 13. Recovery Boundary

### 13.1 Three different recovery authorities

```text
OMS recovery
  resolves unknown transmission/order facts

Portfolio Risk recovery
  directs suspend/cancel/reduce/flatten for safety

Carry application recovery
  proposes the economically preferred portfolio target
```

They must remain separate.

### 13.2 Application recovery proposal

A pure Carry recovery policy may propose:

```text
WAIT_FOR_FACT_RECONCILIATION
RESTORE_CARRY_TARGET
REDUCE_TO_SAFE_HEDGE
FLATTEN_TO_BASELINE
HALT_FOR_OPERATOR
```

The output references a fresh decision Snapshot and explains the economic
preference. Any exposure-changing proposal must become a new
`BasketTargetIntent`, pass ADR-012 admission, receive a new Order Group where
required and obtain per-action permits.

### 13.3 Forbidden recovery behavior

The application must never:

- resubmit an `UNKNOWN` child;
- mutate an existing Order Group to match a new economic target;
- issue a child order or permit;
- declare a venue outcome from a timeout;
- override a Risk emergency directive;
- assume that closing one leg restores safety;
- mark `HEDGED` from target quantities without actual position proof.

## 14. Runtime Interaction

Runtime remains the composition and single-writer authority.

### 14.1 Opening flow

```text
authoritative source views
  -> SnapshotCoordinator
  -> READY FundingCarryDecisionSnapshot
  -> pure Carry strategy
  -> BasketTargetIntent
  -> ADR-012 whole-Basket admission
  -> Runtime objective-to-plan mapping
  -> ADR-011 Order Group creation
  -> per-action Risk authorization
  -> durable OMS handoff
  -> child Execution adapter
```

The Carry position observes immutable facts and changes application state only
after durable evidence exists.

### 14.2 Partial execution

```text
Order Group child facts
  + reconciled Portfolio effective positions
  + Portfolio Risk exposure view
  -> Carry hedge assessment
```

Examples:

```text
Spot target +10, actual +10
Perpetual target -10, actual 0
  -> CarryHedgeState.UNHEDGED or PARTIALLY_HEDGED by accepted tolerance

Spot target +10, actual +5
Perpetual target -10, actual -10
  -> negative residual Delta, not OMS failure semantics
```

Risk may independently suspend/flatten before the application next decides.

### 14.3 Funding reversal

```text
new Funding market view
  -> Feature update
  -> READY monitoring/close Snapshot
  -> pure exit decision
  -> new close Basket target
  -> normal Risk and OMS path
```

No special Funding instruction enters OMS.

### 14.4 Accounting

```text
fill and account financial facts
  -> ADR-013 ledger/reconciliation/allocation
  -> immutable application attribution view
  -> Carry financial state/performance view
```

The application cannot derive realized Funding from the market rate.

## 15. Restart and Reconciliation

Startup sequence:

1. validate configuration, Objective registry, pair metadata and policies;
2. replay OMS, Portfolio, Risk, Accounting and Carry journals independently;
3. query/reconcile venue orders, positions, balances and financial history;
4. rebuild effective positions and unresolved Order Group facts;
5. rebuild Carry hedge/financial assessment from authoritative read views;
6. publish `READY` Snapshots only after source policies pass;
7. require configured operator resumption before new exposure.

On disagreement:

```text
venue/account truth
  + exact source cursors
  outrank stale derived application views
```

The Carry journal never overwrites venue facts. Unresolved disagreement moves
the application to `RECOVERY_REQUIRED` or `HALTED`, not silently to `ACTIVE`.

## 16. Failure Matrix

| Failure | Application behavior |
|---|---|
| Missing/stale Spot or perpetual view | no READY decision Snapshot |
| Missing/stale Funding view | no entry/monitor decision requiring Funding |
| Funding sign reversal | evaluate close/reduce through normal Basket path |
| Account/margin source stale | no new exposure; Risk may direct recovery |
| Snapshot scope/identity mismatch | reject strategy output |
| Basket admission rejected | remain at prior lifecycle; record decision evidence |
| One leg partially filled | recompute hedge state from authoritative exposure |
| Child outcome UNKNOWN | `RECOVERY_REQUIRED`; do not retry economically |
| Risk permit expired | no submit; request fresh assessment |
| Risk emergency directive | obey platform safety control; application cannot override |
| Application journal append fails | halt application before state publication |
| OMS journal/recovery unhealthy | no new application exposure |
| Accounting lag but evidence retained | PnL provisional; health policy may limit new exposure |
| Accounting evidence cannot be retained | platform unhealthy for new exposure |
| Financial attribution ambiguous | keep `UNALLOCATED`; never guess |
| Restart reconciliation incomplete | no `ACTIVE` promotion or new exposure |
| Policy/schema incompatible on replay | halt for migration/operator review |

## 17. First Funding Carry MVP

The first application increment is deliberately narrow:

- Binance Spot plus linear perpetual for one economic underlying;
- one configured account ownership model;
- two Basket legs through the generic N-leg contract;
- fixed-point quantities and explicit contract conversion;
- read-only coherent Snapshot and Feature observation first;
- offline deterministic strategy decisions;
- simulated grouped execution and failure injection;
- actual Funding, fee and PnL reconciliation only after ADR-013 capability;
- authenticated Testnet only after separate authorization.

Excluded from the first exposure-changing MVP:

- cross-venue transfers and settlement latency;
- shared-account allocation without accepted evidence;
- automatic capital optimization across many Carry pairs;
- portfolio leverage optimization;
- options, calendar spreads or triangular arbitrage application code;
- production credentials and live capital.

These exclusions do not narrow the generic platform contracts.

## 18. Expansion Safety

### More than two legs

The application always emits generic `BasketTargetIntent`. Adding a hedge leg,
collateral hedge or option overlay does not require a new OMS module.

New application-specific pair/basket semantics and Feature/Risk policies are
required, but the platform lifecycle remains N-leg.

### Market Making

Market Making should use its own application aggregate and typed snapshots.
It can reuse Basket, OMS, Risk and Accounting without importing Carry
lifecycle states.

### Option spreads

Option applications use the same generic Snapshot/Basket/OMS/Risk/Accounting
boundaries. Greeks and volatility surfaces remain Features. Hedge state may
use option Delta but OMS still sees only actions/orders.

### Calendar and basis spreads

They may reuse `applications.carry` when their economic lifecycle and
ownership semantics truly match. They must not be forced into Funding-specific
pair fields or policies.

### Multi-venue Carry

Venue/account identity already exists in Basket legs and ledger accounts.
Multi-venue execution additionally requires accepted transfer, connectivity,
credit and settlement-risk policies; it is not enabled by this ADR alone.

## 19. Compatibility

- Existing single-leg `TradingPipeline` remains unchanged.
- Existing `PositionTargetIntent` remains unchanged.
- Existing `StrategyDecision` remains unchanged.
- Existing `StrategyRuntime` can host the pure Carry strategy.
- ADR-009 Snapshot contracts remain generic.
- ADR-010 Basket remains 2-to-16-leg and application-neutral.
- ADR-011 OMS remains execution-control only.
- ADR-012 Risk remains generic and never declares Carry `HEDGED`.
- ADR-013 Accounting remains ledger authority and never imports Carry.
- Execution adapters remain child-order and venue specific, not
  application specific.

The new basket/runtime composition is additive and cannot weaken the existing
single-leg durable handoff.

## 20. Boundedness and Performance

Accepted implementation must define hard/deployment caps for:

- active/retained Carry positions;
- linked Intent and Order Group references per position;
- application facts per journal segment;
- pair and Objective registrations;
- ownership records per account/instrument;
- Snapshot source and coherence policy;
- recovery proposals and retries;
- reason/metadata size.

Application policy runs synchronously with deterministic bounded inputs. It
performs no network, disk or unbounded collection work.

Journal/archive retention may compact closed aggregates only after immutable
source evidence remains externally auditable.

## 21. Security and Operations

- No credential enters an application model, journal or AI collaboration
  document.
- Application configuration references account IDs, not API keys.
- Strategy callbacks receive no connector/session object.
- Objective Type is not authorization.
- Application state is not operator authority.
- Manual resume/halt/flatten actions require the accepted operations control
  path and durable audit evidence.
- Secrets remain environment/secret-manager inputs at venue composition.

## 22. Alternatives Considered

### Put Funding logic in `strategy/funding.py`

Rejected. It hides application state, ownership, recovery and accounting
interaction inside a callback and encourages direct platform coupling.

### Add Funding-specific fields to Basket

Rejected. Basket represents a generic economic portfolio target.

### Add `HEDGED` to OMS

Rejected. OMS does not own authoritative portfolio Delta or application
tolerance.

### Let Portfolio Risk own Carry lifecycle

Rejected. Risk owns safety decisions, not entry economics, future Funding
expectation or application business completion.

### Infer application state only from two order fills

Rejected. Orders can be partial/unknown and venue positions can include other
activity or already reflect fills under a reconciliation cursor.

### Let Carry write ledger entries

Rejected. Applications provide ownership evidence and consume attribution;
Accounting owns financial truth.

### Build a two-leg Binance adapter

Rejected. Venues expose child-order APIs. Cross-leg uncertainty belongs to
generic Runtime, OMS and Risk control.

### Use one combined lifecycle enum

Rejected. Execution status, hedge assessment, application lifecycle and
financial finality change independently.

### Add a generic Event Bus

Rejected for this requirement. Caller-driven single-writer orchestration and
typed immutable views already provide deterministic ordering.

### Treat expected APR as realized PnL

Rejected. Expected carry is a Feature; realized Funding and fees require
authenticated Accounting facts.

## 23. Consequences

### Positive

- Funding Carry validates all generic platform layers without contaminating
  them;
- N-leg expansion does not require per-strategy OMS modules;
- economic success remains distinct from order and Risk state;
- application state survives restart with exact evidence references;
- shared-account ambiguity is visible instead of guessed;
- expected and realized return remain auditable;
- Market Making and option applications can reuse platform contracts while
  owning different application aggregates.

### Costs

- one new application domain and durable journal are required;
- runtime must coordinate more typed read views;
- ownership/allocation needs explicit evidence;
- lifecycle and hedge state require careful operator presentation;
- read-only, simulation, Testnet and production must remain separate gates.

### Risks

- duplicated source truth if application facts copy Portfolio/OMS state;
- hidden strategy branches in generic Risk/OMS routing;
- stale Snapshot use after lifecycle changes;
- falsely declaring `HEDGED` from order fills alone;
- shared-account PnL misallocation;
- Recovery proposals being mistaken for execution permission;
- accidental live activation before ADR-012/013 acceptance.

Mitigation is enforced dependency direction, immutable evidence identity,
orthogonal states, offline failure tests and explicit promotion gates.

## 24. Required Tests After Acceptance

### Contracts

- deterministic `CarryPairId`, `ApplicationPositionId` and fact identity;
- Spot/perpetual underlying and product validation;
- explicit multiplier/quantity conversion;
- Objective registration/versioning;
- bounded metadata and reference collections;
- no credentials or executable callbacks in persisted contracts.

### Snapshot

- correct typed assembly from Spot, perpetual, mark/index, Funding, account,
  margin, Features and application read views;
- missing, stale, future, wrong-scope and excessive-skew rejection;
- Funding market view cannot be replaced by Accounting settlement;
- semantic mismatch between pair/instrument/account rejected;
- deterministic replay publication and Snapshot causation.

### Strategy

- read-only observation emits no Basket;
- profitable entry emits exact two-leg absolute targets;
- close emits exact baseline/flat targets;
- Funding reversal generates a new close objective;
- existing `PositionTargetIntent` behavior remains unchanged;
- no order type/leg order leaks into Basket;
- same Snapshot/config produces identical decision.

### Application aggregate

- opening, active, closing and closed lifecycle;
- `UNKNOWN/UNHEDGED/PARTIALLY_HEDGED/HEDGED` from authoritative exposure;
- positive and negative residual Delta;
- unresolved cursor/mark/Greek produces `UNKNOWN`;
- closed physical exposure with provisional financial state;
- revision conflict and duplicate fact handling;
- journal crash boundaries, corruption, replay and migration failure.

### Platform boundaries

- Carry cannot call Execution or issue permits;
- OMS/Risk/Accounting do not import or branch on Carry;
- Execution plan mapping remains Runtime configuration;
- one Basket leg can have multiple child attempts;
- UNKNOWN child never creates an application retry order;
- Risk directive outranks recovery preference;
- single-leg pipeline/handoff remains unchanged.

### Ownership and Accounting

- baseline plus owned delta equals absolute target;
- unrelated pre-existing position is not claimed;
- direct group/leg allocation;
- dedicated account Funding allocation;
- shared ambiguous Funding remains `UNALLOCATED`;
- expected APR never appears as realized PnL;
- final attribution reconciles Funding, trading, fees and valuation without
  double-counting.

### Scenario acceptance

- Spot +10 / perpetual -10 fully hedged open;
- Spot +10 / perpetual 0 partial execution;
- Spot +5 / perpetual -10 reverse residual;
- reject/expire before first child;
- one leg rejected after another fills;
- child submission UNKNOWN and restart recovery;
- margin deterioration during opening;
- Funding sign reversal while active;
- operator halt and safe recovery;
- close exposure before final Accounting reconciliation;
- three-leg option spread plus Delta hedge demonstrates generic N-leg
  platform compatibility without importing Funding Carry.

## 25. Implementation and Promotion Gate

This Proposed ADR authorizes no code.

After Web GPT review, dependency compatibility and explicit project-owner
acceptance:

1. assign implementation and acceptance task IDs;
2. implement IDs, Carry pair and typed Snapshot/Feature contracts;
3. implement pure read-only decision observation;
4. implement application journal, aggregate and ownership evidence;
5. integrate only accepted ADR-012/013 read ports;
6. add offline strategy, lifecycle, recovery and attribution tests;
7. run full regression, static, branch-coverage and architecture-boundary
   gates;
8. publish application interfaces and acceptance handoff;
9. request separate authorization before authenticated Testnet.

Exposure-changing Funding Carry remains forbidden until:

- ADR-009 through ADR-014 are Accepted;
- their implementation acceptances are complete;
- grouped external execution is explicitly unblocked;
- Accounting and Risk startup reconciliation are healthy;
- operations/runbook and kill-switch tests pass;
- the project owner separately authorizes Testnet.

Production remains a later independent gate.

## 26. Review Questions

1. Is `cex_quant.applications.carry.funding_arbitrage` the correct boundary?
2. Is a separate application aggregate necessary beyond pure Strategy state?
3. Are lifecycle, hedge assessment and financial finality correctly
   orthogonal?
4. Should Carry own `PARTIALLY_HEDGED/HEDGED` while Risk owns exposure facts
   and safety directives?
5. Is the Funding market-state owner correctly placed outside the
   application?
6. Can current `StrategyDecision` and generic Basket contracts remain
   unchanged?
7. Is Runtime objective-to-Execution-plan mapping correctly separated from
   Strategy?
8. Does ownership evidence correctly distinguish absolute target from the
   Carry-owned contribution?
9. Is dedicated/exclusive account ownership an appropriate first-MVP gate?
10. Are application recovery proposals sufficiently separated from OMS
    recovery and Risk authority?
11. Are actual Funding/fees and expected carry correctly separated?
12. Does the boundary support future N-leg Carry, Market Making and option
    applications without creating application branches in platform modules?
