---
id: AI-20260728-017
title: ADR-014 Proposed Handoff
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-28
code_baseline: fa0df9e2a015db258457d226c7ed9fa5c689b8eb
supersedes: none
related:
  - ../../../adr/ADR-014-carry-application-boundary.md
  - 86_codex_adr014_current_code_audit.md
external_share: allowed
sensitivity: public-project
---

# Codex Handoff: ADR-014 Proposed

## Review Request

Please review ADR-014 as the Carry Application boundary, not as a Funding
strategy implementation.

Its purpose is to freeze:

- where the application lives;
- which economic state it owns;
- how it consumes platform facts;
- how it emits generic portfolio objectives;
- how it remains unable to bypass Risk, OMS, Accounting or Execution.

Preserve accepted ADR-009 through ADR-011. ADR-012 and ADR-013 remain Proposed
and must be reviewed on their own merits.

Classify findings as:

- **A. ADR-014 design error**: must be corrected before acceptance;
- **B. Implementation/dependency issue**: belongs to the final ADR-012/013
  contracts or later implementation detail;
- **C. Long-term optimization**: useful after the first safe MVP.

No implementation or trading authorization is requested.

## Architecture Conclusion

The proposed placement is:

```text
cex_quant.applications.carry
  -> generic Carry economic aggregate

cex_quant.applications.carry.funding_arbitrage
  -> typed Snapshot, Features and pure economic policy
```

This application consumes immutable platform views and emits only
`BasketTargetIntent`.

```text
Market / Funding / Account / Margin / Feature views
  -> ADR-009 READY FundingCarryDecisionSnapshot
  -> pure Carry strategy
  -> ADR-010 BasketTargetIntent
  -> ADR-012 Portfolio Risk
  -> ADR-011 Order Group and durable execution
  -> ADR-013 Accounting attribution
  -> Carry economic-position view
```

The application cannot issue orders or permits.

## Current-Code Compatibility

No change is needed to:

- `StrategyDecision`;
- `PositionTargetIntent`;
- generic Strategy lifecycle;
- ADR-009 Snapshot metadata/readiness;
- ADR-010 Basket content;
- ADR-011 OMS state;
- child-order Execution adapters.

The current generic Strategy runtime already accepts typed Snapshot
publications and validates exact Basket Snapshot causation.

The application-specific missing contracts are:

- `ApplicationPositionId` and `CarryPairId`;
- `FundingCarryDecisionSnapshot`;
- Carry aggregate/journal;
- economic lifecycle and hedge assessment;
- immutable ownership evidence;
- pure recovery proposals.

## Confirmed Ownership

### Carry application owns

- Spot/perpetual economic-pair metadata;
- entry, exit and expected-return policy;
- the economic application-position lifecycle;
- `PARTIALLY_HEDGED/HEDGED` application assessment;
- relationship among opening, adjustment, recovery and closing objectives;
- economic recovery preference;
- expected-versus-realized application presentation;
- ownership evidence offered to Accounting allocation.

### Carry application does not own

- raw market/Funding/account/margin truth;
- generic Feature state;
- Portfolio Risk approval or action permits;
- execution-plan selection;
- Order Group/child state;
- ledger facts/postings/reconciliation;
- venue I/O or operator authority.

## Orthogonal State Model

ADR-014 avoids one mixed lifecycle enum:

```text
Application lifecycle
  PROPOSED
  OPENING
  ACTIVE
  CLOSING
  CLOSED
  RECOVERY_REQUIRED
  HALTED

Hedge assessment
  UNKNOWN
  UNHEDGED
  PARTIALLY_HEDGED
  HEDGED

Financial finality
  NOT_READY
  PROVISIONAL
  RECONCILED
```

OMS continues to own execution-control state. Risk continues to own exposure
facts, limits and safety directives. Accounting continues to own financial
truth.

`HEDGED` is an application interpretation of authoritative effective
positions using accepted pair conversion and tolerance. It cannot be inferred
from target quantities or OMS fills alone.

## ACTIVE and CLOSED Semantics

`ACTIVE` requires:

- Portfolio-confirmed opening target;
- application hedge state `HEDGED`;
- no unresolved execution outcome;
- no active Risk recovery directive;
- registered ownership evidence;
- ready monitoring inputs and healthy platform state.

It does not mean future Funding or profit is guaranteed.

`CLOSED` means physical/economic close is confirmed with no unresolved group
outcome. Financial state may remain `PROVISIONAL` until ADR-013
reconciliation is complete.

## Snapshot and Feature Boundary

Funding Carry uses distinct typed ADR-009 values rather than one universal
object with optional phase fields:

- an entry value requires Spot/perpetual, mark/index, Funding, account,
  margin and Feature views;
- a position value additionally requires the current application position,
- generic Risk and bounded Order Group views;
- Accounting attribution is a separate performance view so Accounting lag
  cannot block reduce/close/recovery;
- later phase variants require their own exact source schema/policy.

The application assembler validates semantic relationships but does not own
source freshness or mutate source truth.

The following are Features:

- basis;
- expected Funding;
- annualized expected carry/APR;
- fee/slippage/borrow estimates;
- expected net carry;
- Funding reversal signal;
- future option Greeks/volatility surfaces.

Actual Funding and fees are Accounting facts, never Features or market
estimates.

## Objective and Execution Separation

Funding Carry uses generic versioned Objective Types such as:

```text
carry.funding.open@1
carry.funding.rebalance@1
carry.funding.close@1
carry.funding.recover@1
```

The resulting Basket contains complete absolute targets but no execution
method.

```text
ObjectiveTypeRef
  -> deployment Runtime mapping
  -> registered ExecutionPlanRef
  -> generic OMS
```

Strategy cannot select child order sequence, retry UNKNOWN outcomes or call
Execution.

## Ownership and PnL

Absolute account positions may include unrelated inventory. The Carry
position therefore records immutable economic ownership:

```text
proven baseline
  + application-owned contribution
  + other admitted/reserved contributions
  = absolute target
```

Risk owns reservation safety. Accounting owns validation and allocation. If
shared-account Funding cannot be proven, it remains `UNALLOCATED`.

For the first exposure-changing MVP, ADR-014 recommends dedicated/exclusive
account ownership unless a shared-account model is accepted first.

Expected carry is never realized PnL:

```text
expected Funding/APR -> Features
actual Funding/fees -> Accounting ledger
application PnL -> attributed Accounting view + derived valuation
```

## Recovery Separation

```text
OMS recovery:
  determine actual execution outcome

Portfolio Risk recovery:
  enforce safety action

Carry recovery:
  propose economic portfolio target
```

Application proposals such as restore target, reduce, flatten or halt require
a fresh Snapshot and the normal Basket/Risk/OMS gates.

## Restart Boundary

Carry owns a checksummed append-only journal of application lifecycle facts
and exact referenced evidence IDs.

Startup independently replays and reconciles:

- OMS;
- Portfolio/account state;
- Portfolio Risk;
- Accounting;
- Carry application facts.

The application rebuilds hedge/financial views from authoritative sources.
It never overwrites venue truth. Incomplete reconciliation produces
`RECOVERY_REQUIRED` or `HALTED`, not `ACTIVE`.

## First-MVP Boundary

The first Funding Carry increment is:

- one Spot plus one linear perpetual pair;
- generic two-leg Basket;
- dedicated/exclusive ownership or accepted equivalent;
- read-only coherent observation first;
- offline deterministic decisions and simulation;
- full partial/unknown/restart/funding-reversal scenarios;
- no authenticated Testnet without later approval.

More than two legs remains supported by generic platform contracts and does
not require a separate OMS module.

## Expansion Assessment

### N-leg Carry

Additional hedge or option legs use the same Basket, Risk and OMS contracts.
Only application semantics and policies expand.

### Market Making

Market Making owns a different application aggregate but reuses generic
platform infrastructure. It does not inherit Carry state.

### Option spreads

Options reuse N-leg execution and Accounting. Greeks and volatility surfaces
stay in Features; application hedge interpretation may use them.

### Multi-venue

Venue/account identities are supported, but transfer, settlement, credit and
connectivity risk require later accepted policies.

## Proposed Acceptance Boundary

After dependency review and explicit owner acceptance, implementation may
later include:

- identifiers, pair metadata and typed Snapshot/Feature contracts;
- pure read-only Carry decisions;
- application journal, aggregate and ownership evidence;
- accepted ADR-012/013 read-port integration;
- offline lifecycle, recovery, accounting and restart tests.

Still forbidden:

- real action-permit issuance before ADR-012 implementation acceptance;
- grouped external submission until separately unblocked;
- application-written ledger facts;
- authenticated Testnet/production use;
- Funding branches inside generic OMS/Risk/Accounting.

## Review Questions

1. Is the application package boundary correct?
2. Can the current Strategy and Basket contracts remain unchanged?
3. Are lifecycle, hedge and financial states correctly orthogonal?
4. Does Carry own `HEDGED` without taking Risk exposure authority?
5. Is Funding market state correctly external to the application?
6. Is objective-to-execution-plan mapping correctly owned by Runtime?
7. Does ownership evidence solve the absolute-target/pre-existing-inventory
   ambiguity?
8. Is dedicated account ownership appropriate for the first MVP?
9. Are Recovery proposal, Risk directive and OMS recovery clearly separated?
10. Does expected-versus-realized return remain auditable?
11. Does N-leg expansion avoid special OMS modules?
12. Which finding, if any, is an **A-class ADR-014 design error** that must be
    corrected before acceptance?
