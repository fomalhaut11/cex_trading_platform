# ADR-012 Portfolio Risk and Grouped Execution Authorization

## Status

Accepted — 2026-07-29.

Web GPT confirmed that ADR-012 Proposal work could start while grouped
external execution remained closed. The project owner agreed. The apparent
ADR-011 blockers in that review were checked against the current branch and
were already closed by the accepted ADR-011 remediation evidence.

Acceptance authorizes T032-T035 and A015 offline work only. It does not
authorize Funding Arbitrage, Testnet or production execution.

Web GPT's implementation review retained this ADR as Accepted and initially
assigned `CONDITIONAL ACCEPTANCE` to the implementation. A-01 through A-07
were remediated or confirmed at implementation commit
`b082af0618e180f98441af5dc6d49c906994a012`.

The focused review on 2026-07-29 accepted and closed all seven findings and
upgraded the ADR-012 implementation to `Accepted`. No ADR reopening was
required. Risk-decision explainability, Risk-model versioning and
audit-oriented Risk evidence remain non-blocking future improvements.
The remediation and final acceptance add no external-execution authority.

The final committee decision on 2026-07-29 formally closed the ADR-012
acceptance process. The next architecture gate is ADR-013 Financial Ledger
and PnL Attribution scope alignment, followed by ADR-014 Carry Application
Boundary review.

Grouped external execution remains hard-blocked by
`GroupedExecutionBlockedError`. Removing that block requires completed
offline acceptance and a later explicit Testnet authorization.

Reviewed baseline:

`a752d3bff06a1b73b1103f543c64a2b6b64d2016`

Review inputs:

- accepted ADR-009 Portfolio Decision Snapshot Model;
- accepted ADR-010 Basket Intent Architecture;
- accepted and implemented ADR-011 Parent Order Group and Multi-leg
  Execution Model;
- current `risk`, `portfolio`, `snapshots`, `features`, `oms` and `runtime`
  source;
- ADR-011 remediation acceptance in
  `ai_collaboration/topics/funding_arbitrage/81_codex_adr011_remediation_acceptance.md`.

## Context

ADR-009 defines coherent typed observations. ADR-010 defines the complete
portfolio target. ADR-011 defines a durable N-leg execution-control aggregate
and one exact action at a time.

The remaining safety question is:

```text
Given current positions, working orders, margin and market conditions,
is the complete target admissible, and is this exact next action safe now?
```

These are different decisions.

Example target:

```text
BTC Spot       target +10
BTC Perpetual  target -10
```

Whole-Basket admission may be safe when both legs are considered together.
After the first child fills, the actual state may instead be:

```text
Spot fill +10
Perpetual fill 0
residual BTC Delta +10
```

An earlier Basket approval cannot authorize the second, third or recovery
action indefinitely. Every exposure-changing action must be assessed against
the latest complete portfolio state.

The system also has to avoid a subtler error:

```text
authoritative account position
  + complete OMS cumulative fills
```

is not generally valid. The account position may already include some or all
of those fills. Adding them again double-counts exposure. ADR-012 therefore
requires explicit execution-coverage evidence between the authoritative
account baseline and the OMS fill overlay.

## Current-Code Findings

### Reusable capabilities

The current repository already provides:

- a stateless deterministic `RiskEngine` for `PositionTargetIntent`;
- exact fixed-point `Price`, `Quantity`, `Money` and `Rate` contracts;
- normalized immutable `AccountSnapshot` values;
- typed `DecisionSnapshotPublication` and readiness evidence;
- system-computed option IV and Greeks in the Feature domain;
- immutable `BasketTargetIntent`;
- immutable `OrderGroupView`, signed per-leg fill vectors and working
  quantities;
- exact `ExecutionAction` checksums and finite `ExecutionActionPermit`;
- durable OMS journal/replay and a durable-before-external-I/O handoff;
- an immediate pre-I/O `ExternalSubmitGuardPort`;
- explicit operator `HALT` and `REDUCE_ONLY` authority.

These capabilities remain first-class and are extended additively.

### Missing capabilities

The repository does not yet have:

- a complete portfolio risk snapshot;
- normalized collateral, margin and liquidation facts;
- an account baseline to OMS execution-coverage watermark;
- portfolio risk-factor projection across Spot, futures and options;
- working-order and reservation exposure;
- whole-Basket approval issuance;
- real per-action permit issuance;
- continuous group risk supervision;
- durable Risk reservation/recovery state;
- typed Risk evidence for group recovery resume and target confirmation;
- a grouped runtime path allowed to reach an Execution adapter.

### Compatibility constraint

The existing single-instrument `RiskEngine` is intentionally stateless and
caller-driven. ADR-012 does not silently replace it, reinterpret its limits or
convert existing single-leg intents into Baskets.

## Decision Summary

Introduce an additive Portfolio Risk domain with five boundaries:

1. Portfolio publishes an execution-consistent position view and normalized
   margin/collateral facts. It calculates no Delta, basis or risk decision.
2. A pure Portfolio Risk engine projects current, target, action and
   conservative working-order exposure from one immutable Risk snapshot.
3. A single-writer Risk coordinator durably owns admission reservations,
   issued evidence and continuous supervision state.
4. OMS continues to own group/action/child truth. It validates immutable Risk
   evidence but calculates no economic risk.
5. Runtime serializes Snapshot, Risk, OMS, operator and Execution calls and
   rechecks Risk authority immediately before external I/O.

The required authorization chain is:

```text
BasketTargetIntent
  -> whole-Basket Portfolio Risk assessment
  -> durable PortfolioApproval + reservation
  -> OMS OrderGroupAdmission
  -> ExecutionAction proposal
  -> current Portfolio Risk snapshot
  -> exact finite ExecutionActionPermit
  -> durable OMS child preparation
  -> immediate Risk/operator/health recheck
  -> existing child ExecutionGateway
```

Basket approval and an action permit remain different evidence:

```text
PortfolioApproval
  permits one durable group admission

ExecutionActionPermit
  permits one exact action at one exact group revision
```

## 1. Terminology

### Authoritative account baseline

A normalized venue position snapshot established by a completed
reconciliation cut. It includes evidence of which OMS execution facts are
already reflected.

### Execution overlay

The exact signed position deltas from OMS cumulative-fill progress strictly
after the baseline's execution-coverage cursor.

### Effective position

```text
effective position
  = reconciled account baseline
  + post-watermark execution overlay
```

It is a Portfolio-owned derived fact, not a Risk-owned position store.

### Working exposure

Potential additional exposure from non-terminal child orders. Working
exposure is separate from filled exposure.

### Portfolio Risk snapshot

One immutable ADR-009-compatible publication containing all required
Portfolio, OMS, market, Feature, margin, policy and health inputs for a Risk
decision.

### Risk factor

A stable economic exposure axis, for example BTC Delta, BTC option Gamma, USD
value or one configured spread/basis set. It is not a strategy name.

### Portfolio approval

Finite evidence that one identity-equal complete Basket passed admission Risk.
It creates a bounded Risk reservation and may admit one Order Group. It
permits no child submit.

### Action permit

Finite evidence that one exact `ExecutionAction` at one group revision passed
current Portfolio Risk. It cannot authorize another action.

### Continuous supervision

Caller-driven re-assessment after material Portfolio, OMS, market, margin,
Feature, policy, health or time changes.

### Risk directive

An immutable constraint or escalation result published by Portfolio Risk.
It never submits, cancels or sizes an order by itself.

## 2. Package Topology

Planned after acceptance:

```text
src/cex_quant/
  core/
    identifiers.py              # additive typed evidence identifiers

  portfolio/
    contracts.py                # existing account truth remains
    exposure.py                 # reconciled baseline + execution overlay view
    margin.py                   # normalized venue margin/collateral facts

  risk/
    model.py                    # existing single-leg contracts remain
    portfolio_model.py          # snapshots, measures, policies, decisions
    portfolio_engine.py         # pure deterministic projections/limits
    portfolio_state.py          # reservations and supervision state
    portfolio_journal.py        # durable Risk evidence and replay

  oms/
    group_model.py              # additive recovery/confirmation evidence

  runtime/
    portfolio_risk_coordinator.py
    basket_pipeline.py
    grouped_execution_handoff.py
```

Final filenames may be adjusted during implementation review. Ownership and
dependency direction are frozen by this ADR.

### Allowed dependencies

```text
portfolio -> core, instruments
risk.portfolio -> core, instruments, portfolio, features, strategy,
                  OMS immutable views
oms.group -> core, instruments, strategy immutable contracts
runtime -> Risk, Portfolio, OMS, operator, health and Execution ports
```

### Prohibited dependencies

- Portfolio must not import Risk or application strategy code.
- OMS must not import a concrete Risk engine.
- Risk must not import Execution adapters or application implementations.
- Execution must not import Portfolio Risk or Basket economics.
- Applications must not issue permits or call Execution directly.
- No module may inspect `strategy == "funding"` or an equivalent application
  discriminator inside generic Risk or OMS.

## 3. Portfolio Position Truth and Execution Coverage

### 3.1 Why `AccountSnapshot + group fill vector` is insufficient

`OrderGroupLegView.signed_cumulative_filled_delta` is an OMS execution fact.
`AccountSnapshot.positions` is an absolute venue fact. Their observation
windows can overlap.

The following is forbidden without coverage evidence:

```text
effective = account quantity + all-time group cumulative fill
```

### 3.2 Reconciled baseline

Portfolio introduces an immutable semantic contract comparable to:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionCoverage:
    reconciliation_id: str
    through_oms_journal_sequence: int
    established_at_ns: UnixNanos


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciledAccountBaseline:
    account: AccountSnapshot
    account_observation_id: ObservationId
    coverage: ExecutionCoverage
```

The baseline may advance only when a reconciliation process proves that:

- the absolute venue positions are complete for the declared account scope;
- all OMS fill facts through the coverage sequence are reflected;
- unresolved or unknown orders have been queried;
- account, venue and instrument identities match;
- the baseline and execution cursor are durable recovery evidence.

An arbitrary private-stream account update is not automatically a new
baseline. A venue-specific adapter may establish a baseline only when it can
prove the same coverage semantics.

### 3.3 Execution overlay

Portfolio consumes cumulative child-fill changes from the ordered OMS journal.
For each child, it applies only the signed incremental change after the
baseline cursor.

Semantic contract:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPositionEffect:
    oms_journal_sequence: int
    client_order_id: ClientOrderId
    account_id: AccountId
    instrument_id: InstrumentId
    signed_fill_delta: Quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionRiskView:
    account_id: AccountId
    instrument_id: InstrumentId
    baseline_quantity: Quantity
    post_baseline_fill_delta: Quantity
    effective_quantity: Quantity
```

Mandatory invariant:

```text
effective_quantity
  == baseline_quantity + post_baseline_fill_delta
```

Duplicate OMS records, cumulative-fill redelivery and replay cannot change the
result. A fill decrease, identity conflict, missing journal range or
reconciliation gap latches the Portfolio view not ready.

### 3.4 Divergence

Portfolio compares its execution-consistent view with later venue account
observations. Unexplained divergence, including manual trading or an external
order not represented in OMS, is explicit.

```text
READY
UNRECONCILED
DIVERGENT
RECOVERY_REQUIRED
```

Only `READY` position views can authorize ordinary grouped actions. Other
states allow query/reconciliation and separately permitted recovery only.

### 3.5 Ownership

Portfolio owns the reconciled baseline, overlay and effective position.

OMS remains the source of child execution facts. Risk reads the immutable
Portfolio result. Risk must not independently replay fills into a second
position store.

## 4. Margin, Collateral and Liquidation Inputs

Portfolio adds normalized venue facts without becoming a Risk calculator.

Semantic contracts include:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class MarginScopeSnapshot:
    account_id: AccountId
    venue: VenueId
    margin_scope: str
    margin_mode: MarginMode
    reporting_asset: AssetId
    equity: Money
    available_margin: Money
    initial_margin: Money
    maintenance_margin: Money
    as_of_ns: UnixNanos
    source_update_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionLiquidationReference:
    account_id: AccountId
    instrument_id: InstrumentId
    liquidation_price: Price | None
    maintenance_margin: Money | None
    as_of_ns: UnixNanos
```

Rules:

- values are venue-supplied or normalized adapter facts with provenance;
- assets and margin scopes are explicit;
- cross and isolated margin are never silently merged;
- missing venue liquidation price remains `None`, never a fabricated zero;
- Spot accounts without borrowing do not require derivative margin fields;
- derivative, margin or borrowing scopes required by policy fail closed when
  missing or stale;
- raw venue payloads do not cross into Portfolio Risk.

Portfolio stores no Funding APR, basis-entry rule or strategy success state.

## 5. Portfolio Risk Snapshot

A Portfolio Risk snapshot uses ADR-009 metadata and readiness semantics.

The original Basket decision snapshot and a later action Risk snapshot are
different causation points:

```text
basket.decision_snapshot_id
  identifies the Strategy decision input

permit.risk_snapshot_id
  identifies the current Portfolio Risk input used for this action
```

They are not required to be equal.

Semantic value:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskSnapshot:
    positions: tuple[PositionRiskView, ...]
    working_orders: tuple[WorkingOrderRiskView, ...]
    groups: tuple[OrderGroupView, ...]
    margins: tuple[MarginScopeSnapshot, ...]
    liquidation_references: tuple[PositionLiquidationReference, ...]
    instruments: tuple[Instrument, ...]
    marks: tuple[RiskMark, ...]
    sensitivities: tuple[InstrumentSensitivity, ...]
    spread_inputs: tuple[SpreadRiskInput, ...]
    active_reservations: tuple[PortfolioRiskReservationView, ...]
    health: HealthReport
```

It is published only when every source required by the selected Risk policy is
ready, fresh, coherent and scope-complete.

The snapshot is bounded and immutable. It contains no network client, mutable
store, callback, database session or raw exchange object.

## 6. Risk Measures and Numeric Semantics

### 6.1 Exact evidence

Public Risk evidence uses exact fixed-point values plus explicit units and
assets. Internal calculations use `Decimal`.

Feature values currently use finite binary floats. At the Risk boundary they
are converted through a documented decimal string representation, then
quantized to a policy-defined scale and rounding mode. The converted value,
scale, unit, Feature reference and source observation are retained in Risk
evidence.

Risk must reject:

- non-finite values;
- unknown or mismatched units;
- unsupported precision;
- silent conversion between assets;
- missing conversion rates for a declared reporting currency.

### 6.2 Instrument sensitivities

Each supported instrument has one registered, versioned Risk model.

```text
Spot
  base-asset Delta and quote notional

Linear future/perpetual
  contract size, mark and base-asset Delta

Inverse future/perpetual
  explicit inverse contract value and mark-dependent Delta

Option
  contract size plus required system-computed Delta/Gamma/Vega Features
```

Quanto and any unsupported settlement convention fail closed.

Venue-published option analytics remain labelled reference market data.
Portfolio Risk consumes system-computed Feature values as authoritative inputs
when policy requires Greeks. Risk does not calculate a volatility surface or
option Greeks inside the Risk module.

### 6.3 Exposure vector

Risk calculates at least:

- signed and absolute position by account/instrument;
- net and gross Delta by configured risk factor;
- notional and concentration by account, strategy, asset and global scope;
- configured option Gamma and Vega;
- realized residual/legging exposure;
- conservative working-order exposure;
- configured spread/basis exposure;
- current and projected margin utilization;
- current and projected liquidation buffer where the model is supported.

Raw quantities from unlike products are never summed as Delta.

### 6.4 Basis and spread risk

Basis is configured as a generic versioned Risk relationship, not inferred
from a Funding strategy name.

Example:

```text
risk set: BTC spot-perpetual basis
members:
  BTC Spot mark        weight -1
  BTC Perpetual mark   weight +1
unit:
  USDT per BTC
```

A `SpreadRiskDefinition` is metadata-only and references known instrument,
mark or Feature identities. Runtime loads an approved registered
implementation. No import path, callback or application object is persisted
in the policy.

Calendar spreads and other configured relationships use the same boundary.
Risk does not decide whether a spread is profitable or whether Funding is
attractive.

### 6.5 Working-order envelope

Risk evaluates three distinct views:

```text
current realized exposure
projected exposure if the proposed target/action completes
conservative exposure if currently working orders fill adversely
```

V1 does not enumerate every fill combination. It uses a conservative bounded
component-wise envelope derived from signed remaining working quantities.
The algorithm is deterministic and linear in the number of positions,
working orders, sensitivities and configured spread sets.

## 7. Portfolio Risk Policy

One immutable versioned policy declares:

- complete account, venue, instrument, asset and risk-factor scope;
- supported instrument Risk model versions;
- required marks, Features, margin and health sources;
- freshness, coherence and clock thresholds;
- per-instrument, per-account, per-strategy and global limits;
- net/gross Delta, notional and concentration limits;
- optional Gamma, Vega and spread/basis limits;
- margin-utilization and liquidation-buffer limits;
- legging/residual exposure limits;
- working-order envelope limits;
- approval and permit maximum lifetimes;
- active reservation and group bounds;
- operator `REDUCE_ONLY` reduction rules.

The policy is data, not executable application code.

Policy changes create a new version. A new version invalidates unconsumed
permits and requires active groups/reservations to be reassessed. Policy
rollback requires explicit operator authorization and audit; version numbers
never move backward silently.

Application configuration may select a registered limit profile. It cannot
weaken platform hard limits or bypass required sources.

## 8. Whole-Basket Admission

### 8.1 Input

Admission receives:

```python
assess_basket(
    basket: BasketTargetIntent,
    risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
    policy: PortfolioRiskPolicy,
) -> BasketPortfolioRiskDecision
```

The pure engine verifies:

- Basket identity, checksum, objective registration and expiry;
- original decision-snapshot causation;
- complete Risk scope and current Risk snapshot readiness;
- active instrument and supported product models;
- current effective positions;
- all active reservations and working exposure in policy scope;
- target projection for every Basket leg while preserving unrelated
  positions;
- current, projected and conservative exposure;
- margin, liquidation and configured spread limits;
- global, strategy, account and concentration limits.

### 8.2 Output

V1 is binary:

```text
ALLOW complete identity-equal Basket
REJECT complete Basket with typed reasons
```

There is no per-leg approval, silent deletion, resizing or target mutation.

An allowed decision contains immutable evidence comparable to:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BasketPortfolioRiskDecision:
    status: PortfolioRiskDecisionStatus
    basket: BasketTargetIntent
    risk_snapshot_id: DecisionSnapshotId
    risk_policy_version: int
    reasons: tuple[PortfolioRiskRejectReason, ...]
    current_exposure: PortfolioExposure
    projected_exposure: PortfolioExposure
    conservative_exposure: PortfolioExposure
    approval: PortfolioApprovalEvidence | None
```

`ALLOW` requires one approval. `REJECT` requires no approval and at least one
typed reason.

### 8.3 Approval evidence

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioApprovalEvidence:
    approval_id: PortfolioApprovalId
    basket_intent_id: IntentId
    basket_checksum: str
    risk_snapshot_id: DecisionSnapshotId
    assessment_checksum: str
    approved_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int
```

The ID is replay-stable over complete canonical content. It is not an
authentication token.

Runtime converts this evidence to the accepted OMS `OrderGroupAdmission`.
OMS validates Basket checksum, identity, expiry and policy version. OMS does
not recalculate Risk.

## 9. Reservations and Approval Races

Without a reservation, two Baskets can both pass against the same available
margin before either group is created.

The Portfolio Risk coordinator therefore owns a bounded reservation for every
allowed admission:

```text
Risk assessment ALLOW
  -> append and fsync approval/reservation evidence
  -> publish PortfolioApprovalEvidence
```

The reservation accounts for the approved target transition and conservative
working exposure. It is keyed by `PortfolioApprovalId`.

Reservation states are:

```text
ACTIVE
ATTACHED_TO_GROUP
RELEASED
EXPIRED
RECOVERY_REQUIRED
```

These are Risk reservation states, not OMS group states.

Rules:

- one approval creates at most one reservation;
- exact redelivery is idempotent;
- changed content with the same ID is a conflict;
- a reservation is included in later admission and action assessments;
- group creation attaches the reservation to the deterministic group;
- fills and current positions do not get added again to the same reserved
  transition;
- group close, rejection before group creation or explicit expiry releases
  the reservation only after durable evidence;
- a crash between approval and group creation leaves a recoverable active
  reservation, not unreserved capacity;
- journal or reconciliation uncertainty moves the reservation to
  `RECOVERY_REQUIRED` and blocks new permits.

## 10. Per-Action Authorization

### 10.1 Input

```python
authorize_action(
    group: OrderGroupView,
    action: ExecutionAction,
    risk_snapshot: DecisionSnapshotPublication[PortfolioRiskSnapshot],
    policy: PortfolioRiskPolicy,
) -> ExecutionActionRiskDecision
```

Risk verifies:

- group, approval, Basket leg, account and instrument identity;
- exact current group revision;
- action checksum and positive bounded order quantity;
- current position reconciliation and OMS execution coverage;
- all unresolved and working orders in policy scope;
- current reservation state;
- current and full-fill action exposure;
- conservative working-order envelope;
- current/projected margin and liquidation limits;
- Basket, group, snapshot and policy freshness;
- runtime Risk health.

Execution ordering, order type, price and quantity proposal remain execution
plan responsibilities. Risk can reject a proposal but does not silently
replace it.

### 10.2 Permit

On `ALLOW`, the coordinator durably issues the existing ADR-011 contract:

```python
ExecutionActionPermit(
    permit_id=...,
    group_id=action.group_id,
    expected_group_revision=action.expected_group_revision,
    action_id=action.action_id,
    action_checksum=execution_action_checksum(action),
    risk_snapshot_id=current_risk_snapshot_id,
    issued_at_ns=...,
    valid_until_ns=...,
    risk_policy_version=...,
)
```

Permit expiry is the earliest of:

- configured permit lifetime;
- Risk snapshot/source validity;
- Basket/admission expiry;
- policy validity;
- any stricter runtime deadline.

An expired, changed, consumed, unknown or no-longer-current permit cannot be
renewed in place. Risk reassesses a new exact action/current revision and
issues new evidence.

### 10.3 Authorization generation

The Risk coordinator owns a monotonically increasing authorization generation
for each affected scope.

Material changes increment the generation and invalidate every unconsumed
permit in that scope:

- fill or working-order change;
- account or margin update;
- mark, Feature or spread-input update;
- group revision/control change;
- reservation change;
- Risk policy change;
- health, clock or operator safety change;
- reconciliation status change.

The permit retains its accepted ADR-011 wire contract. The coordinator
durably maps `permit_id` to its issuance generation.

Immediately before external I/O, the runtime guard must prove:

- permit ID is known and still current in Risk;
- issuance generation still matches;
- group revision/action checksum still match;
- permit is fresh and unconsumed;
- Risk coordinator, Portfolio view, journal, clock, route and operator are
  healthy;
- `HALT`/`REDUCE_ONLY` authority still allows the exact action.

This recheck is in addition to OMS validation during durable preparation.

### 10.4 `REDUCE_ONLY`

An action is Risk-reducing only if it:

- creates no new hard-limit breach;
- makes no existing hard-limit breach worse;
- increases no policy-declared protected exposure measure;
- strictly reduces at least one breached or explicitly targeted measure; and
- remains safe under the conservative working-order envelope.

The decision is tied to the exact action. An exchange `reduceOnly` flag alone
is not proof that a portfolio action reduces Risk.

## 11. Continuous Supervision

Risk supervision is caller-driven and single-writer. It runs after every
material change and at bounded timer deadlines.

Semantic result:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskDirective:
    directive_id: str
    group_id: OrderGroupId
    expected_group_revision: int
    risk_snapshot_id: DecisionSnapshotId
    kind: PortfolioRiskDirectiveKind
    reasons: tuple[PortfolioRiskRejectReason, ...]
    issued_at_ns: UnixNanos
    risk_policy_version: int
```

V1 directive kinds:

```text
CLEAR
BLOCK_NEW_ACTIONS
RECONCILIATION_REQUIRED
RECOVERY_ACTION_REQUIRED
OPERATOR_REVIEW_REQUIRED
```

Risk directives:

- invalidate pending action authority;
- inform Runtime, OMS control, operations and application readers;
- may cause Runtime to request OMS `SUSPENDED` or `RECOVERY_REQUIRED`;
- never mutate OMS directly;
- never create an `ExecutionAction`;
- never call Execution;
- never declare a Carry position `HEDGED` or `ACTIVE`.

Cancellation remains an OMS/Execution action. A safe cancel can proceed under
halt according to ADR-011. Any new exposure-changing hedge or flatten action
still requires a fresh exact permit.

## 12. Recovery and Target Confirmation

### 12.1 Restart

Restart is fail-closed:

```text
HALTED
  -> replay Risk journal
  -> replay OMS journal
  -> query/reconcile unresolved and unknown children
  -> establish Portfolio baselines and execution coverage
  -> rebuild active reservations from approvals and non-terminal groups
  -> obtain fresh market/Feature/margin/account observations
  -> publish a fresh Portfolio Risk snapshot
  -> reassess every active group
  -> explicit operator resume
```

No pre-restart `ExecutionActionPermit` authorizes a new external call by
itself. The immutable permit remains the latched causation for the original
action. A same-ID technical retransmission remains governed by ADR-011 and
requires definitely-not-sent evidence plus a fresh exact recovery
authorization and current Risk/operator validation; it does not issue or bind
a replacement permit.

### 12.2 Recovery resume evidence

ADR-012 defines typed semantics for the current
`recovery_authorization_id` boundary:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupRecoveryAuthorization:
    authorization_id: str
    group_id: OrderGroupId
    expected_group_revision: int
    mode: RecoveryAuthorizationMode
    reconciliation_id: str
    risk_snapshot_id: DecisionSnapshotId
    issued_at_ns: UnixNanos
    valid_until_ns: UnixNanos
    risk_policy_version: int
    action_id: GroupActionId | None = None
    permit_id: ExecutionPermitId | None = None
```

Risk may issue it only when:

- OMS reconciliation is complete;
- no child has an unresolved unknown outcome;
- Portfolio execution coverage includes all reconciled fill facts;
- the fresh Risk snapshot is ready;
- active reservation state is reconstructable;
- the group can safely resume or enter an explicitly constrained recovery
  mode.

`RESUME_GROUP` contains no action/permit identity and grants no child-submit
authority. `RETRANSMIT_DEFINITELY_NOT_SENT` binds the already persisted
action and latched permit; it cannot replace content, identity or permit
causation. A new hedge/flatten action uses a new exact action permit under an
explicit recovery policy.

Explicit operator resume remains separately mandatory. Risk evidence cannot
impersonate operator authority.

### 12.3 Target confirmation

`TARGET_CONFIRMED` close requires typed Portfolio Risk evidence comparable to:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioTargetConfirmation:
    confirmation_id: str
    group_id: OrderGroupId
    expected_group_revision: int
    basket_intent_id: IntentId
    risk_snapshot_id: DecisionSnapshotId
    confirmed_at_ns: UnixNanos
    risk_policy_version: int
```

It confirms only that:

- all children are resolved;
- execution coverage is complete;
- effective positions match the admitted Basket targets under documented
  instrument increments/tolerances;
- no conflicting reservation remains.

It does not declare Funding profitability, Carry `HEDGED`, application
`ACTIVE` or PnL correctness.

## 13. Durable Risk Evidence

The pure Portfolio Risk engine performs no I/O. The coordinator persists
state-changing evidence before publication.

Minimum durable facts:

```text
PortfolioApprovalIssued
PortfolioReservationChanged
ExecutionPermitIssued
PortfolioRiskDirectiveIssued
GroupRecoveryAuthorizationIssued
PortfolioTargetConfirmed
RiskPolicyActivated
```

Requirements:

- append-only, checksummed and globally ordered within the Risk owner;
- canonical bounded serialization;
- flush/fsync before returning an approval, permit or recovery evidence;
- exact replay and idempotent redelivery;
- no in-place rewrite;
- corruption, truncation, append failure, unsupported version or external
  modification latches Risk unhealthy and blocks new authority;
- journal contains no credentials or raw venue payloads;
- old permits are evidence after restart, never live authority.

Risk journal and OMS journal remain separate ownership logs. Runtime recovery
cross-checks their identities; neither journal becomes the other's state
writer.

## 14. State Ownership

| State or evidence | Single writer | Readers |
|---|---|---|
| Venue account positions/balances | Portfolio/Account state | Risk, application |
| Reconciled baseline and execution overlay | Portfolio projection owner | Risk, operations |
| Margin/collateral normalized facts | Portfolio/Account state | Risk, application snapshot |
| Market/Feature values | Existing market/Feature owners | Snapshot, Risk |
| Basket economic target | Strategy/application | Risk, OMS admission |
| Risk policy and active version | Portfolio Risk coordinator | Risk engine, operations |
| Approval reservation | Portfolio Risk coordinator | Runtime, operations |
| Portfolio approval/action permit | Portfolio Risk coordinator | Runtime, OMS, audit |
| Group/action/child control facts | OMS | Risk, Runtime, operations |
| Risk directive | Portfolio Risk coordinator | Runtime, OMS control adapter, application, operations |
| Execution route and external I/O | Runtime/Execution adapter | OMS outcome path |
| Carry `HEDGED/ACTIVE/CLOSED` | Carry application aggregate under ADR-014 | Strategy, operations |
| Funding/fee/PnL ledger | Accounting under ADR-013 | Attribution, operations |

No mutable object crosses these boundaries.

## 15. Runtime Interaction

### 15.1 Basket admission

```text
1. obtain READY application decision snapshot
2. Strategy emits complete BasketTargetIntent
3. validate Basket causation and identity
4. obtain READY Portfolio Risk snapshot
5. pure Risk engine evaluates complete Basket
6. Risk coordinator durably records approval/reservation
7. Runtime creates one OMS OrderGroupAdmission
8. OMS durably creates group
9. Risk reservation attaches to group
10. Runtime may activate group only while Risk/operator/health are current
```

No child is created before step 8. No child is submitted by this flow.

### 15.2 One action

```text
1. planner proposes one exact ExecutionAction from immutable views
2. obtain current READY Portfolio Risk snapshot
3. Risk evaluates action/full-fill/working envelope
4. Risk durably issues exact finite permit
5. OMS validates action/permit and durably prepares SUBMITTING child
6. immediate guard rechecks Risk generation, group, health and operator
7. existing ExecutionGateway submits canonical OrderRequest
8. immediate outcome returns to OMS
9. venue facts update OMS
10. Portfolio updates post-watermark execution overlay
11. Risk invalidates old authority and supervises the new state
```

Steps are serialized for one group in V1. An external call is never made while
a conflicting material Risk update is being applied.

### 15.3 Grouped handoff

The existing shared durable handoff remains the external-I/O boundary. Runtime
adds a grouped adapter that binds:

- `OrderRequest.approval_id` to the latched `ExecutionPermitId`;
- child ID to group/action/permit context;
- `ExternalSubmitGuardPort` to current Risk, operator and health checks;
- immediate outcomes back to the existing OMS group child.

Execution adapters remain child-order oriented and application-neutral.

## 16. Failure Matrix

| Condition | Required result |
|---|---|
| Unknown/stale Risk snapshot | REJECT; no approval/permit |
| Basket identity/scope mismatch | REJECT complete Basket |
| Missing account baseline | REJECT |
| Missing execution coverage or OMS journal range | Portfolio not ready; reconcile |
| Account/OMS divergence | Block new actions; recovery required |
| Duplicate execution effect | Idempotent no-op |
| Changed effect with reused identity | Latch failure |
| Unsupported instrument or margin model | REJECT |
| Missing/invalid required mark or Greek | REJECT |
| Missing currency conversion | REJECT; never silently aggregate |
| Stale margin/liquidation fact | REJECT |
| Exposure, basis, concentration or margin breach | REJECT or typed directive |
| Concurrent approvals exceed capacity | One serialized approval wins; later assessment sees reservation |
| Action/group revision mismatch | No permit or OMS rejection |
| Risk generation changes before I/O | Definitely not sent; no Execution call |
| Permit expired or unknown | No Execution call |
| Risk journal append/fsync failure | Latch Risk unhealthy; no authority |
| OMS journal failure after permit | No Execution call; Risk reservation retained/recovered |
| External result possibly sent | OMS `RECOVERY_REQUIRED`; query, never blind replacement |
| Restart | Old permits invalid; reconcile and reassess |
| Operator HALT | No new approval/action submit; query/reconcile/safe cancel remain |
| Operator REDUCE_ONLY | Only exact Risk-proven reducing actions can proceed |

## 17. Compatibility

### Existing single-leg Risk

- `RiskEngine`, `RiskContext`, `RiskLimits` and `RiskDecision` remain public.
- Existing `PositionTargetIntent` evaluation remains stateless.
- Existing single-leg Pipeline behavior and tests remain unchanged.
- Existing single-leg orders do not create a Portfolio reservation or Order
  Group unless a future separately accepted migration says so.

### Existing OMS and journal

- Current child `OrderRequest`, `OrderStateMachine` and Execution adapters
  remain canonical.
- ADR-011 group journal records replay unchanged.
- Additive recovery/confirmation evidence requires an explicit compatible
  schema version; old records are never rewritten.
- `ExecutionActionPermit` fields remain unchanged.

### Existing Snapshot and Feature domains

- ADR-009 generic Snapshot contracts are reused.
- Feature remains the owner of IV, Greeks and volatility surfaces.
- Risk consumes feature evidence; it does not move analytics into market data
  or duplicate the Feature engine.

## 18. Expansion Safety

### Funding Arbitrage

Funding Carry uses:

- Spot and Perpetual positions mapped to one underlying Delta factor;
- a configured Spot/Perpetual basis risk set;
- margin and liquidation inputs for the derivative account;
- no Funding-specific branch in Risk or OMS.

Funding rate, expected APR, entry/exit economics and `HEDGED/ACTIVE` status
remain application concerns.

### Market Making

The conservative working-order envelope and per-action authorization can be
reused by market making. ADR-012 does not introduce quote-set lifecycle,
inventory skew policy or cancellation strategy. Those remain future
application/execution-plan decisions.

### Option Spreads

Option positions map to underlying Delta and configured Gamma/Vega factors
using Feature values and contract multipliers. A third Delta-hedge leg uses
the same Basket/action boundary. Missing or stale Greeks fail closed.

ADR-012 does not claim full volatility-surface scenario Risk, American option
support or arbitrary nonlinear portfolio simulation. Those are additive
future Risk models behind the same registered interface.

### Multi-venue and multi-account

Every position, margin fact, action and reservation keeps explicit account,
venue, asset and instrument identity. Cross-venue or cross-asset aggregation
requires explicit conversion and policy scope. There is no implicit global
USD conversion.

## 19. Boundedness and Performance

Every deployment policy must be lower than immutable implementation hard caps.
The acceptance review must freeze exact caps for:

- accounts and positions per Risk snapshot;
- working orders and active groups per scope;
- active reservations;
- risk factors and sensitivities per instrument;
- spread/basis definitions;
- rejection reasons and directive history;
- approval and permit maximum lifetime;
- journal record size and record count;
- reconciliation overlay entries.

The pure calculation path must be:

```text
O(positions + working orders + sensitivities + configured spread sets)
```

It may not:

- perform network, filesystem or database I/O;
- enumerate unbounded fill combinations;
- search unbounded history;
- create background retry tasks;
- import application callbacks.

Latency budgets and concrete limits are implementation acceptance evidence,
not guessed production claims in this ADR.

## 20. Security and Operational Controls

- Approval, permit and checksum IDs are integrity/causation identities, not
  authentication tokens.
- Only the composed Risk coordinator may issue live evidence.
- A future cross-process Risk service requires authenticated transport, mTLS,
  replay protection and issuer identity; in-process IDs alone are
  insufficient.
- Risk policy activation and rollback are audited operator actions.
- No API key, secret, cookie or raw signed request enters Risk evidence.
- Runtime validates current operator authority independently of Risk.
- Journal, clock, Portfolio, Risk, OMS, routing or audit failure blocks new
  exposure-changing actions.

## 21. Alternatives Considered

### Treat Basket approval as permission for every child

Rejected. It ignores partial fills, changing margin and stale market state.

### Calculate Risk inside OMS

Rejected. OMS owns execution truth, not Delta, basis, Greeks or margin policy.

### Let Strategy decide whether each next leg is safe

Rejected. Strategy defines economic intent; platform Risk must enforce
portfolio-wide limits across strategies and working orders.

### Add account positions and all OMS fills

Rejected. Overlapping observation windows double-count exposure.

### Use only account positions and ignore recent OMS fills

Rejected. Private account state can lag a partial fill and hide legging Risk.

### Infer basis from a Funding objective type

Rejected. It leaks application semantics into generic Portfolio Risk.

### Put option Greeks in Risk

Rejected. System-computed Greeks remain Features. Risk consumes their values,
quality, unit and lineage.

### Keep Portfolio Risk fully stateless

Rejected for grouped admission. Concurrent approvals require durable
reservations, and restart must reconstruct outstanding authority.

The projection engine remains pure; state belongs to the separate
single-writer coordinator.

### Let a Risk directive submit a hedge automatically

Rejected. A directive constrains or escalates. Execution still requires an
explicit planner action, exact permit, OMS durability and runtime guard.

### Rely only on permit TTL

Rejected. A material fill or margin change can invalidate a still-unexpired
permit. Immediate generation validation is required.

## 22. Consequences

### Positive

- closes the admission-versus-action authorization gap;
- avoids position double-counting with explicit execution coverage;
- prevents concurrent approval overcommit through durable reservations;
- preserves OMS/Risk/Portfolio ownership separation;
- supports generic N-leg, option and multi-venue evolution;
- keeps Funding economics out of platform mechanisms;
- makes restart and recovery authority explicit;
- reuses existing child Execution adapters and durable handoff.

### Costs

- adds a Portfolio execution-overlay/reconciliation view;
- adds normalized margin/collateral contracts;
- adds Risk factor and policy registries;
- adds a durable Risk journal and coordinator;
- requires continuous snapshot assembly and more fail-closed states;
- requires careful latency and memory bounds.

### Risks

- incorrect execution-coverage semantics could undercount or double-count
  positions;
- incorrect contract multipliers or Greek units could misstate exposure;
- conservative working-order envelopes may reject otherwise executable plans;
- margin projection can imply false precision unless model support is explicit;
- reservations can leak capacity if release/recovery evidence is wrong;
- cross-process deployment would require a stronger authenticated issuer
  boundary.

## 23. Required Tests After Acceptance

### Compatibility

- all existing regression and acceptance tests pass;
- existing single-leg Risk decisions are byte/field compatible;
- existing V1/V2 OMS journals replay unchanged;
- `PositionTargetIntent` never enters Basket Risk implicitly;
- grouped external submit remains blocked until the final ADR-012 acceptance
  gate.

### Position coverage

- baseline plus post-watermark fill delta produces exact effective position;
- a fill already reflected in the baseline is not counted twice;
- cumulative partial-fill increases apply only the increment;
- duplicate replay is idempotent;
- missing journal range, decreasing fill or identity conflict fails closed;
- manual/external position divergence requires reconciliation;
- restart rebuilds the same effective positions.

### Whole-Basket admission

- BTC Spot `+10` and BTC Perpetual `-10` project as one complete target;
- no leg can be partially approved;
- unrelated portfolio positions remain in global exposure;
- stale/mismatched original decision snapshot rejects;
- active working orders and reservations affect the decision;
- two serialized approvals cannot spend the same margin capacity;
- exact approval redelivery is idempotent.

### Per-action permit

- Spot fill `+10`, Perpetual fill `0` exposes residual `+10 BTC`;
- Spot fill `+5`, Perpetual fill `-10` exposes residual `-5 BTC`;
- each next action is evaluated against the current residual;
- permit binds exact group, revision, action, checksum, Risk snapshot, policy
  and expiry;
- changed quantity, price, leg or revision rejects;
- material Risk update invalidates an unexpired permit;
- immediate guard failure records definitely-not-sent and calls Execution zero
  times;
- REDUCE_ONLY proves portfolio reduction, not merely an exchange flag.

### Option and generic N-leg

- two option legs plus one Delta hedge aggregate by underlying risk factor;
- contract quantities are not treated as Delta;
- missing/stale/invalid Delta rejects;
- configured Gamma/Vega limits apply with exact units;
- no two-leg assumptions appear in schemas, loops or projections.

### Margin, basis and working exposure

- cross and isolated scopes cannot be mixed;
- missing/stale margin or liquidation inputs fail closed when required;
- unsupported venue margin model rejects;
- explicit currency conversion is required;
- configured Spot/Perpetual basis limits apply without a Funding branch;
- conservative working-order fill envelope catches adverse one-leg fills.

### Supervision and recovery

- each material fact invalidates affected authority;
- directives never call OMS or Execution directly;
- unknown child forces reconciliation/recovery;
- restart invalidates old permits;
- a post-restart same-ID technical retransmission retains the original permit
  causation and requires fresh exact recovery authorization;
- Risk/OMS journal disagreement blocks resume;
- recovery authorization requires complete reconciliation and current Risk;
- explicit operator resume remains required;
- target confirmation requires effective positions at target and no unresolved
  children;
- target confirmation does not create application `HEDGED` state.

### Durability, failure and boundedness

- approval/permit is never returned before Risk fsync;
- Risk journal corruption/append failure latches unhealthy;
- crash at every admission/action handoff point recovers safely;
- policy limits and immutable hard caps reject oversized inputs;
- calculation complexity remains linear under maximum fixtures;
- fault and race tests cover fill, margin, policy, halt and pre-I/O changes.

## 24. Implementation and Promotion Gate

Web GPT review and explicit project-owner acceptance were recorded on
2026-07-29. They authorized:

1. T032-T035 and A015 task assignment;
2. implement Portfolio exposure-coverage and margin facts;
3. implement immutable Risk contracts and the pure projection engine;
4. implement durable reservations, journal, supervision and recovery evidence;
5. integrate exact permit validation with the shared handoff while keeping the
   external grouped route disabled;
6. run complete offline acceptance and architecture boundary review;
7. update authoritative architecture/interface/package documents;
8. request a separate explicit Testnet authorization.

Funding Arbitrage, Financial Ledger, Testnet and production trading remain
outside this ADR.

## 25. Review Questions

Reviewers should answer without redesigning ADR-011:

1. Is the reconciled account baseline plus post-watermark OMS overlay the
   correct position-truth boundary?
2. Is fail-closed behavior correct when execution coverage cannot be proven?
3. Should the pure engine remain separate from a durable single-writer Risk
   coordinator and reservation journal?
4. Does the reservation model correctly prevent concurrent Basket approval
   overcommit?
5. Is a generic risk-factor/spread registry sufficient without Funding-
   specific branches?
6. Is the current/full-fill/conservative-working-envelope model appropriate
   for V1?
7. Should every material update invalidate unconsumed permits through a Risk
   authorization generation checked immediately before external I/O?
8. Are Risk directives correctly constrained to evidence and escalation
   rather than order creation?
9. Are recovery authorization and target confirmation correctly separated
   from operator authority and Carry economic state?
10. Does the proposal preserve existing single-leg Risk and OMS compatibility?
11. Which immutable hard caps must be frozen before implementation?
12. After acceptance, may offline implementation begin while grouped external
    submission remains hard-blocked through final acceptance?
