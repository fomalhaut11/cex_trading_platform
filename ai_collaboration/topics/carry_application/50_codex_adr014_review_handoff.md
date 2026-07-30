---
id: AI-20260730-002
title: Codex ADR-014 Scope-Aligned Review Handoff
origin: codex
status: READY_FOR_WEB_GPT_REVIEW
created: 2026-07-30
code_baseline: d522b87106c63cc9f5b61b7295746e1925fcc26c
supersedes: none
related:
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - 40_codex_adr014_scope_alignment.md
  - 90_resolution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Codex Handoff: ADR-014 Scope-Aligned Proposal

## Review Request

Please review ADR-014 as an application-boundary decision, not as permission
to implement or trade Funding Arbitrage.

ADR-013 T036-T039/A016 is now implemented offline. Codex rechecked ADR-014
against its actual public interfaces and found no A-class design error.

## Frozen Result

```text
platform immutable views
  -> typed Funding Carry Snapshot
  -> pure Carry economic policy
  -> generic BasketTargetIntent
  -> ADR-012 Portfolio Risk
  -> ADR-011 Order Group
  -> Portfolio/Accounting observations
  -> Carry economic interpretation
```

Carry lives in:

```text
cex_quant.applications.carry
cex_quant.applications.carry.funding_arbitrage
```

It owns economic lifecycle, hedge assessment, expected economics, ownership
declarations and economic recovery proposals. It does not own source market
state, Portfolio positions, Risk authorization, OMS execution facts,
Accounting truth or venue I/O.

## ADR-013 Alignment

Carry maps `ApplicationPositionId` to the generic
`EconomicOwnerRef(application.position@1, owner_id)`.

It consumes immutable:

- `PnlAttributionView`;
- `SourceCompletenessProof`;
- `BalanceReconciliationProof`;
- `ValuationSnapshot`;
- Accounting readiness/progress.

It cannot use mutable `AllocationBook` or create allocations. A durable public
Accounting allocation/query coordinator remains an implementation dependency.
The first MVP therefore retains the dedicated/exclusive account rule.

## Proposed Offline Tasks After Acceptance

```text
T040  Funding market-state view
T041  Carry contracts
T042  typed Snapshot and pure decision policy
T043  aggregate/journal/recovery
T044  Runtime composition with external execution still blocked
A017  offline acceptance
```

## Requested Classification

- A. ADR-014 design error;
- B. dependency/implementation issue;
- C. long-term optimization.

Please confirm whether ADR-014 may move from `Proposed, scope-aligned` to
`Accepted` and whether T040-T044/A017 credential-free offline implementation
may begin.

This request does not authorize grouped external execution, Testnet,
production or real capital.
