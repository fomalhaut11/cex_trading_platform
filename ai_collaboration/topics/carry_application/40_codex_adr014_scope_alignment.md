---
id: AI-20260730-001
title: Codex ADR-014 Scope Alignment Against ADR-013 Implementation
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-30
code_baseline: d522b87106c63cc9f5b61b7295746e1925fcc26c
supersedes: none
related:
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - 50_codex_adr014_review_handoff.md
  - 90_resolution.md
  - ../financial_ledger/50_codex_adr013_offline_implementation_handoff.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Codex ADR-014 Scope Alignment

## Result

ADR-014 remains architecturally valid after inspection of the implemented
ADR-013 contracts. No redesign of ADR-009 through ADR-013 is required.

The formal review dependency is now satisfied at the interface-design level:

```text
ADR-013 immutable public contracts
  -> exact Carry Accounting read boundary
  -> explicit ownership mapping
  -> ADR-014 ready for review
```

This result is design evidence only. It does not accept ADR-014, authorize
Carry source code or open grouped external execution.

## Current-Code Findings

### Directly reusable

| Need | Current contract |
|---|---|
| coherent typed input | `DecisionSnapshotPublication` and `SnapshotCoordinator` |
| pure strategy output | existing `StrategyDecision` |
| N-leg objective | `BasketTargetIntent` |
| execution observation | immutable `OrderGroupView` |
| effective position truth | `AccountPositionRiskView` |
| Risk observation | immutable ADR-012 decisions, reservations and directives |
| Accounting owner identity | `EconomicOwnerRef` |
| PnL read model | `PnlAttributionView` |
| financial completeness | `AttributionCompleteness` |
| source proof | `SourceCompletenessProof` |
| balance proof | `BalanceReconciliationProof` |
| reporting valuation | `ValuationSnapshot` |
| Accounting progress | `AccountingLedgerView` |

### Still missing

- latest authoritative Funding state owner;
- `cex_quant.applications` and Carry contracts;
- Carry fact journal and replay;
- typed Carry snapshot assemblers and policy;
- Runtime application composition;
- a durable public Accounting allocation coordinator/query repository;
- grouped external execution authorization.

## Exact Accounting Boundary

One application position maps to a generic Accounting owner:

```python
EconomicOwnerRef(
    owner_type=EconomicOwnerTypeRef(
        name="application.position",
        version=1,
    ),
    owner_id=str(application_position_id),
)
```

Carry may consume:

- `PnlAttributionView`;
- `SourceCompletenessProof`;
- `BalanceReconciliationProof`;
- `ValuationSnapshot`;
- sanitized `AccountingLedgerView` readiness/progress.

Carry may not:

- import or mutate `AllocationBook`;
- call `create_allocation`;
- construct allocation results;
- ingest a financial fact;
- append/reverse a ledger transaction;
- select a conversion rate;
- declare reconciliation from its own lifecycle.

The application durably records `CarryLegOwnership`. Runtime supplies this
application evidence to a generic Accounting integration adapter. Accounting
owns the resulting `AttributionAllocation` and may keep the remainder
`UNALLOCATED`.

## State Promotion Rule

`CarryFinancialState.RECONCILED` requires:

```text
SourceCompletenessProof.state == MATCHED
and BalanceReconciliationProof.state == MATCHED
and PnlAttributionView.completeness == AttributionCompleteness.COMPLETE
and allocation evidence is durable/recoverable
and Accounting health is healthy
```

Physical closure and financial finality remain independent.

## Public Application Boundary

After acceptance, `cex_quant.applications.carry.__init__` should export only
immutable application contracts:

- strong IDs;
- Carry pair and position views;
- lifecycle, hedge and financial-state enums;
- ownership declarations;
- recovery proposals;
- immutable journal facts or fact views.

It should not export:

- journal file handles/coordinators;
- mutable aggregate internals;
- Runtime adapters;
- Risk/OMS/Accounting implementations;
- venue clients or execution functions.

`cex_quant.applications.carry.funding_arbitrage.__init__` should export only:

- Funding Carry pair/policy;
- typed Snapshot values and assembler;
- versioned Objective registrations;
- pure feature/decision functions.

## Proposed Implementation Work

```text
T040  latest Funding market-state owner
T041  Carry IDs, pair, position and ownership contracts
T042  typed Snapshot, Feature, Objective and pure decision policy
T043  Carry aggregate, journal, replay and recovery proposal
T044  Runtime read-port composition; Basket output remains offline-blocked
A017  offline Carry decision/lifecycle/restart/accounting-boundary acceptance
```

No task may enable authenticated Testnet, production or grouped external
execution.

## Findings Classification

### A. ADR-014 design errors

None found.

### B. Dependency or implementation issues

1. ADR-013 final Web GPT acceptance is pending.
2. Accounting has immutable allocation contracts and replayable allocation
   records, but no durable public allocation coordinator/query repository.
3. Market Data has `FundingRateUpdate` events but no latest Funding state
   owner for ADR-009 snapshots.
4. Carry source domain and application journal do not exist.
5. Grouped external execution remains hard-blocked.

### C. Long-term optimizations

- shared-account interval allocation beyond the dedicated-account MVP;
- multi-venue transfer/credit/settlement risk;
- option overlays and multi-hop hedges;
- application journal compaction and archival services;
- portfolio-wide capital optimization.

## Review Readiness

ADR-014 may now be reviewed against the actual Accounting public boundary.
The design remains Proposed until Web GPT review and explicit project-owner
acceptance.
