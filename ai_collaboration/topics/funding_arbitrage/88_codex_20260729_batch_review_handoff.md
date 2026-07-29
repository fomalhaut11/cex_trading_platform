---
id: AI-20260728-018
title: ADR-012 to ADR-014 Batch Review Handoff
origin: codex
status: SUPERSEDED
created: 2026-07-28
code_baseline: fa0df9e2a015db258457d226c7ed9fa5c689b8eb
supersedes: none
related:
  - 83_codex_adr012_proposal_handoff.md
  - 85_codex_adr013_proposal_handoff.md
  - 87_codex_adr014_proposal_handoff.md
  - 96_web_gpt_adr012_formal_closure.md
  - ../financial_ledger/20_codex_architecture_response.md
external_share: allowed
sensitivity: public-project
---

# Codex Handoff: 2026-07-29 Architecture Review Batch

## Supersession Notice

This batch entry is closed. ADR-012 acceptance is formally complete, and the
current next review entry is
`../financial_ledger/20_codex_architecture_response.md`.

## Purpose

This is the single entry point for the 2026-07-29 Web GPT/project-owner
review.

The batch contains three Proposed ADRs:

```text
ADR-012
  Portfolio Risk and Grouped Execution Authorization

ADR-013
  Financial Ledger and PnL Attribution

ADR-014
  Carry Application Boundary
```

ADR-009, ADR-010 and ADR-011 are already Accepted and implemented within their
bounded offline acceptance scopes. Do not reopen them unless a new proposal
contains a direct compatibility error.

No document in this batch authorizes implementation, Testnet, production or
external grouped submission.

## Recommended Review Order

Review in this order:

1. `83_codex_adr012_proposal_handoff.md`;
2. `85_codex_adr013_proposal_handoff.md`;
3. `87_codex_adr014_proposal_handoff.md`.

Each handoff is self-contained because Web GPT cannot inspect the local
repository.

Use the corresponding current-code audits for additional evidence:

```text
82 -> ADR-012 audit
84 -> ADR-013 audit
86 -> ADR-014 audit
```

The formal ADRs contain the complete contracts, invariants, alternatives and
test gates.

## Frozen Foundation

```text
ADR-009
  decides what coherent facts the system sees

ADR-010
  decides what economic target the system wants

ADR-011
  controls uncertain N-leg execution facts
```

Implemented boundary:

```text
READY Decision Snapshot
  -> BasketTargetIntent
  -> OrderGroupAdmission
  -> Order Group + ExecutionPlanRef
  -> ExecutionAction
  -> synthetic permit for offline tests
  -> durable child attempt
  -X-> grouped external Execution
```

The final block remains active.

## ADR-012 Summary

ADR-012 decides whether a Basket or one exact execution action is safe.

```text
authoritative account baseline
  + OMS fill overlay strictly after a proven coverage cursor
  -> effective position
  -> generic exposure/margin projection
  -> durable Basket reservation/approval
  -> exact current action permit
  -> continuous Risk directive
```

Critical rule:

`AccountSnapshot` and all cumulative OMS fills must not be added without a
proven coverage boundary; the same fill may already be present in the venue
snapshot.

Risk does not:

- create child orders;
- decide Funding profitability;
- declare Carry `HEDGED/ACTIVE`;
- own OMS recovery facts;
- contain application-specific branches.

## ADR-013 Summary

ADR-013 decides how financial facts become auditable ledger and PnL evidence.

```text
fill-level and account cash-flow facts
  -> append-only balanced per-asset ledger
  -> source completeness and balance reconciliation
  -> immutable allocation
  -> derived valuation/PnL attribution
```

Critical rules:

- OMS cumulative fill/average price is not a financial ledger;
- Funding market rate is not an actual Funding settlement;
- absolute Portfolio balances are reconciliation anchors, not transaction
  history;
- private-stream and history observations of one economic component converge
  to one transport-independent financial fact and one posting;
- every ledger transaction balances independently per asset;
- ledger posting precedes strategy/application allocation;
- ambiguous shared-account Funding remains `UNALLOCATED`;
- Accounting cannot block the synchronous submit handoff, but financial
  evidence may never be dropped.

## ADR-014 Summary

ADR-014 decides where Carry economic semantics live.

```text
cex_quant.applications.carry.funding_arbitrage
  consumes typed immutable platform views
  owns Carry economic state
  emits BasketTargetIntent
  cannot call Execution or issue permits
```

Critical rules:

- `StrategyDecision` and generic Basket do not change;
- Funding market state remains Market Data;
- basis/expected Funding/APR/cost estimates remain Features;
- actual Funding/fees remain Accounting;
- objective-to-Execution-plan mapping remains Runtime configuration;
- OMS, Risk and Accounting cannot branch on Funding/Carry;
- N-leg expansion uses the existing generic platform, not separate OMS
  modules.

Carry state is orthogonal:

```text
lifecycle:
  PROPOSED / OPENING / ACTIVE / CLOSING / CLOSED /
  RECOVERY_REQUIRED / HALTED

hedge:
  UNKNOWN / UNHEDGED / PARTIALLY_HEDGED / HEDGED

financial:
  NOT_READY / PROVISIONAL / RECONCILED
```

## Cross-ADR Ownership Matrix

| State or decision | Owner |
|---|---|
| coherent source readiness | Snapshot coordinator/policy |
| Basket economic target | Strategy/application |
| effective positions and margin facts | Portfolio inputs under ADR-012 |
| exposure projection and safety authority | Portfolio Risk |
| group/action/child execution facts | OMS |
| venue submission | Execution adapter through Runtime handoff |
| fill/cash-flow facts and ledger | Accounting |
| financial allocation/PnL truth | Accounting |
| Carry lifecycle and hedge interpretation | Carry application |
| operator halt/resume authority | Operations control |

## Cross-ADR Safety Invariants

All three proposals must preserve:

1. Basket approval is not action permission.
2. Recovery preference is not action permission.
3. Objective Type is not authorization.
4. UNKNOWN venue outcome is not a retryable failure.
5. Application state is not Portfolio/account truth.
6. OMS fills alone do not prove effective exposure.
7. Funding rate does not prove cash settlement.
8. Expected APR is not realized PnL.
9. No generic module imports or branches on Funding application code.
10. No grouped child reaches external Execution before accepted Risk
    implementation and separate authorization.

## Requested Finding Classification

For each ADR, classify feedback as:

- **A. Current ADR design error** - must be corrected before acceptance;
- **B. Another ADR or implementation concern** - valid but belongs outside
  this decision;
- **C. Long-term optimization** - useful after the correctness baseline.

Please identify the exact ADR and section for every A-class finding.

## Requested Decision

For each ADR independently, return one:

```text
ACCEPT

ACCEPT WITH REQUIRED CORRECTIONS
  -> list exact A-class corrections

REVISE
  -> list architecture blockers
```

Acceptance of a design does not mean its implementation is complete.

After Web GPT review, the project owner will decide whether to:

- accept each ADR;
- request corrections;
- assign implementation and offline acceptance task IDs.

## Current Authorization

```text
ADR-012: Proposed
ADR-013: Proposed
ADR-014: Proposed

Portfolio Risk implementation: not authorized
Accounting implementation: not authorized
Carry application implementation: not authorized
real grouped action permits: blocked
grouped external submission: blocked
authenticated Testnet: separately gated
production: not authorized
```
