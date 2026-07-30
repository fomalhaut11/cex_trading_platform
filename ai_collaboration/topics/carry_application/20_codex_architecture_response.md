---
id: AI-20260729-007
title: Codex Carry Application Architecture Response
origin: codex
status: SCOPE_ALIGNED_SUPPLEMENTED
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - ../financial_ledger/20_codex_architecture_response.md
  - ../funding_arbitrage/86_codex_adr014_current_code_audit.md
  - ../funding_arbitrage/87_codex_adr014_proposal_handoff.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
  - 40_codex_adr014_scope_alignment.md
  - 50_codex_adr014_review_handoff.md
external_share: allowed
sensitivity: public-project
---

# Codex Architecture Response: Carry Application

## Executive Result

The current platform can host a Carry application additively. Accepted
ADR-009 through ADR-012 do not need redesign.

The correct boundary is:

```text
immutable platform facts
  -> typed Carry decision snapshot
  -> pure Carry economic policy
  -> generic BasketTargetIntent
  -> Portfolio Risk approval
  -> generic Order Group execution control
  -> authoritative Portfolio and Accounting observations
  -> Carry economic-position interpretation
```

Carry belongs in `cex_quant.applications.carry`, with Funding-specific policy
under `cex_quant.applications.carry.funding_arbitrage`.

The ADR-014 draft is complete. ADR-013 ownership, allocation and attribution
read-port scope has since been aligned against implementation baseline
`d522b87106c63cc9f5b61b7295746e1925fcc26c`; see
`40_codex_adr014_scope_alignment.md`. Application implementation remains
unauthorized pending review. Grouped external execution is a separate closed
gate.

## 1. Current-Code Audit

### Reusable without modification

| Current capability | Carry use |
|---|---|
| `snapshots` contracts and `SnapshotCoordinator` | bounded source identity, freshness, coherence and READY publication |
| Feature models/registry/engine | basis, expected Funding, estimated costs, IV, Greeks and volatility surfaces |
| `StrategyRuntime` and `StrategyDecision` | pure synchronous decision evaluation |
| `BasketTargetIntent` | complete two-to-16-leg absolute portfolio target |
| Portfolio Risk engine/coordinator/journal | whole-Basket admission, reservations, action permits and directives |
| OMS Order Group model/journal | parent/child execution facts, partial progress, unknown outcome and recovery |
| execution-consistent Portfolio state | authoritative effective positions and fill-coverage evidence |
| Runtime composition | mandatory assembly of Snapshot, Strategy, Risk, OMS and Execution boundaries |

No `cex_quant.applications` source package exists and no Carry-specific source
contract is implemented. ADR-013 has since added `cex_quant.accounting`; its
exact reusable interfaces and remaining allocation-service dependency are
recorded in `40_codex_adr014_scope_alignment.md`.

### Existing compatibility conclusions

- `PositionTargetIntent` remains unchanged.
- `StrategyDecision` already accepts `BasketTargetIntent`.
- A two-leg Funding target and a three-leg option-spread-plus-Delta-hedge
  target already pass generic Basket acceptance.
- OMS exposes sufficient execution facts without owning `HEDGED` or Carry
  lifecycle.
- Risk consumes Greeks and sensitivities; it does not produce IV, Greeks or
  volatility surfaces.
- `OrderGroupRuntime.submit_prepared_child()` still raises
  `GroupedExecutionBlockedError` before external grouped submission.

## 2. Module Topology

Proposed application packages:

```text
src/cex_quant/applications/
  __init__.py
  carry/
    __init__.py
    identifiers.py
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
      objectives.py
      policy.py
```

Required platform packages remain outside the application:

```text
cex_quant.market_data.state    authoritative market/Funding observations
cex_quant.features             estimates, IV, Greeks and surfaces
cex_quant.snapshots            source coherence and publication metadata
cex_quant.strategy             generic decision and Basket contracts
cex_quant.portfolio            normalized account and effective-position truth
cex_quant.risk                 approval, reservations, permits and directives
cex_quant.oms                  group/action/child execution facts
cex_quant.accounting           financial facts, ledger and PnL attribution
cex_quant.runtime              composition and mandatory gate ordering
cex_quant.execution            venue I/O
```

Dependency rule:

```text
generic platform packages -X-> applications.carry
applications.carry       -X-> execution adapters
applications.carry       -X-> Risk/OMS mutable implementations
runtime                    -> composes application and platform read/write ports
```

The application may import immutable public contracts. Generic platform
packages must not import Funding or Carry implementations.

## 3. State Ownership

### Carry application owns

- `ApplicationPositionId` and `CarryPairId`;
- Spot/perpetual economic-pair metadata;
- entry, rebalance, close and economic-recovery objectives;
- the relationship among objectives belonging to one application position;
- expected-return policy and expected-versus-realized presentation;
- application economic lifecycle;
- application hedge assessment;
- immutable ownership declarations offered to Risk and Accounting;
- its append-only application-fact journal and restart replay.

### Carry application does not own

- raw market, Funding, mark/index, account, margin or position truth;
- Feature computation infrastructure;
- Portfolio Risk approval, reservation or permit issuance;
- execution planning, leg sequencing or child-order retry;
- Order Group and child-order state;
- financial source facts, postings, reconciliation or PnL truth;
- venue I/O, Testnet authority or operator authority.

## 4. Orthogonal Application State

One mixed lifecycle enum would leak OMS and Accounting state into the
application. ADR-014 should retain three dimensions:

```text
Economic lifecycle
  PROPOSED / OPENING / ACTIVE / CLOSING / CLOSED /
  RECOVERY_REQUIRED / HALTED

Hedge assessment
  UNKNOWN / UNHEDGED / PARTIALLY_HEDGED / HEDGED

Financial finality
  NOT_READY / PROVISIONAL / RECONCILED
```

`HEDGED` is an application interpretation of authoritative effective
positions, accepted instrument conversion and tolerance. It is not an OMS
status and is not inferred from child fills alone.

`CLOSED` describes physical/economic closure. It does not imply that all
financial facts have reconciled.

### Workflow-to-state mapping

The committee's business workflow is retained, but it is mapped onto the
orthogonal model instead of becoming one lifecycle enum:

| Business workflow term | Architectural meaning |
|---|---|
| `SEARCH` | stateless candidate discovery over a READY entry snapshot; no Carry position exists yet |
| `OPEN` | emit an opening Basket objective; on admission create/advance the application position to `OPENING` |
| `HEDGE` | observe effective positions while lifecycle remains `OPENING`; hedge assessment may move through `UNHEDGED`, `PARTIALLY_HEDGED` and `HEDGED` |
| `COLLECT_FUNDING` | lifecycle `ACTIVE` with current hedge assessment and monitoring inputs; actual payments remain Accounting facts |
| `UNWIND` | emit a closing Basket objective and move lifecycle to `CLOSING`; OMS owns execution facts |
| completed unwind | lifecycle `CLOSED`; financial finality may still be `PROVISIONAL` |

This prevents `SEARCH`, `HEDGED`, `CARRYING` and `CLOSED` from being placed in
one state field even though they describe different dimensions.

## 5. Typed Snapshot Boundary

Carry should not introduce a universal state object filled with optional
fields. Separate typed values should serve distinct policies, for example:

```text
FundingCarryEntrySnapshot
  market: spot/perpetual bid, ask, depth, mark and index
  funding: latest normalized Funding observation
  account: balances and normalized margin state
  portfolio: execution-consistent effective positions
  features: basis, expected Funding and expected costs
  metadata: exact ADR-009 snapshot identity/readiness

FundingCarryPositionSnapshot
  current Carry position view
  authoritative effective positions
  bounded Order Group read views
  current Risk directive/read view
  current market, margin and Feature evidence
```

Accounting attribution is a separate performance view. Accounting lag or
failure must block new exposure as policy requires, but must not make safe
reduce/close/recovery impossible.

## 6. Public Interaction Contracts

The design should expose immutable public contracts, not concrete
cross-domain service calls:

```python
class CarryDecisionSnapshotPort(Protocol):
    def latest_ready(self, pair_id: CarryPairId) -> DecisionSnapshotPublication: ...

class CarryPositionReadPort(Protocol):
    def get(self, position_id: ApplicationPositionId) -> CarryPositionView: ...

class OrderGroupReadPort(Protocol):
    def get_group(self, group_id: OrderGroupId) -> OrderGroupView: ...

class PortfolioRiskReadPort(Protocol):
    def current_view(self, scope: AccountId) -> PortfolioRiskReadView: ...

class CarryAccountingReadPort(Protocol):
    def pnl_attribution(
        self,
        owner: EconomicOwnerRef,
        interval_start_ns: UnixNanos,
        interval_end_ns: UnixNanos,
    ) -> PnlAttributionView: ...
```

The Carry-specific Protocol names remain proposal-level. ADR-013 public symbols
such as `EconomicOwnerRef` and `PnlAttributionView` are reused as implemented;
ADR-014 does not invent a parallel Accounting model.

The only trade-objective output remains:

```python
StrategyDecision(
    intents=(
        BasketTargetIntent(...),
    ),
)
```

The application cannot call `ExecutionGateway`, construct
`ExecutionActionPermit` or mutate an `OrderGroupStateMachine`.

## 7. Runtime Interaction

### Open

```text
READY Carry entry snapshot
  -> pure Funding policy
  -> carry.funding.open@1 Basket target
  -> ADR-012 whole-Basket Risk admission
  -> Runtime maps ObjectiveType to registered ExecutionPlanRef
  -> ADR-011 Order Group
  -> each future action requires a fresh exact ADR-012 permit
```

### Partial or unknown execution

```text
OMS execution facts
  + execution-consistent Portfolio positions
  + current Risk directive
  -> Carry position snapshot
  -> application hedge assessment and economic recovery proposal
  -> new Snapshot-bound Basket objective
  -> normal Risk and OMS gates
```

The application does not declare that an execution attempt succeeded, retry an
unknown child or choose the next child action.

### Accounting

```text
venue/private financial facts
  -> ADR-013 canonical source facts and balanced ledger
  -> reconciliation and allocation
  -> PnlAttributionView plus reconciliation proofs
  -> Carry expected-versus-realized presentation
```

Expected Funding, APR and estimated cost are Features. Actual Funding,
commissions, realized PnL and reconciled attribution are Accounting facts.

## 8. Ownership and Shared Accounts

Basket targets are absolute account/instrument quantities. They cannot by
themselves prove how much position belongs to one application.

Carry therefore needs immutable ownership evidence:

```text
proven baseline
  + Carry-owned target contribution
  + other admitted/reserved contributions
  = absolute Basket target
```

Risk owns reservation and conflict safety. Carry owns its declared economic
contribution. Accounting validates allocation and keeps ambiguous cash flows
`UNALLOCATED`.

The first exposure-changing Funding MVP should use a dedicated/exclusive
account scope unless a complete shared-account ownership model is separately
accepted.

## 9. ADR-013 Dependency

ADR-013 is not a cosmetic reporting dependency. It supplies:

- fill-level and account-level financial facts;
- actual Funding and fee settlements;
- balanced per-asset ledger invariants;
- source and balance reconciliation;
- application ownership allocation;
- provisional versus reconciled PnL attribution.

ADR-013 ownership/allocation/read-port scope alignment and offline acceptance
are now complete under project-owner authority. ADR-014 is ready for review.
Carry code remains blocked until explicit ADR-014 implementation authority.

Recommended promotion sequence:

```text
1. ADR-012 implementation final acceptance        COMPLETE
2. ADR-013 offline implementation and A016        COMPLETE
3. ADR-013 final Web GPT acceptance                PENDING
4. ADR-014 scope alignment                         COMPLETE
5. ADR-014 boundary review and acceptance          NEXT DESIGN GATE
6. ADR-014 bounded offline implementation          BLOCKED
7. Funding Carry offline scenario acceptance       BLOCKED
8. separate authenticated Testnet authorization    BLOCKED
9. separate production authorization               BLOCKED
```

## 10. Expansion Safety

### Funding and basis/calendar Carry

They share the Carry aggregate, ownership and Accounting boundary. They use
different typed snapshots, features and objective policies.

### N-leg and option hedges

Additional futures/options/Delta hedge legs reuse generic Basket, Risk and
Order Group contracts. No separate multi-leg OMS is needed. IV, Greeks and
volatility surfaces stay in Features.

### Market Making

Market Making should own a different application aggregate. It may reuse the
same generic Snapshot, Risk, OMS and Accounting infrastructure, but it must
not inherit Carry lifecycle or Funding semantics.

### Multi-venue

Existing generic identities can describe multiple venues/accounts. Transfer,
settlement, credit, connectivity and venue-default Risk require later
policies; they must not be hidden inside the first Carry application.

## 11. Frozen Implementation Gates

Before ADR-013/ADR-014 acceptance and required capability completion:

- no `src/cex_quant/applications` source package;
- no Funding-specific branch in Strategy, Risk, OMS or Accounting;
- no application-created execution action or permit;
- no grouped Execution adapter integration;
- no authenticated Testnet or production trading.

Even after bounded offline Carry implementation, grouped external execution
remains blocked until a separate explicit authorization removes the runtime
gate.

## 12. Review Request

Please review this as an application-boundary proposal, not as a request to
reopen ADR-009 through ADR-012.

Classify findings as:

- **A. ADR-014 design error** — must be corrected before acceptance;
- **B. ADR-013 or implementation dependency** — belongs to Accounting or the
  later implementation gate;
- **C. long-term optimization** — non-blocking after the first safe MVP.

Specific questions:

1. Is the package and dependency direction correct?
2. Are lifecycle, hedge assessment and financial finality sufficiently
   independent?
3. Is the application prevented from bypassing Risk, OMS and Execution?
4. Is the absolute-target ownership ambiguity handled at the correct boundary?
5. Is ADR-013 correctly treated as a prerequisite for Carry implementation?
6. Can N-leg options and other Carry families extend without platform-specific
   Funding branches?
