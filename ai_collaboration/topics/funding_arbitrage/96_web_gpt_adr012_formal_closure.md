---
id: AI-20260729-011
title: Web GPT ADR-012 Formal Closure and ADR-013 Transition
origin: web-gpt
status: PROMOTED
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 94_web_gpt_adr012_final_acceptance.md
  - 95_web_gpt_adr012_final_committee_review.md
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
  - ../financial_ledger/10_web_gpt_input.md
external_share: allowed
sensitivity: public-project
---

# Web GPT Formal Closure: ADR-012

## Final State

```text
ADR-012 Design:                 ACCEPTED
ADR-012 Implementation:         ACCEPTED
ADR-012 Remediation:            CLOSED
Grouped External Execution:     BLOCKED
Testnet / Production:           NOT AUTHORIZED
```

A-01 through A-07 are closed. ADR-012 does not need to be reopened.

## Architectural Result

ADR-012 now provides a complete authorization chain:

```text
Application Intent
  -> Portfolio Risk
  -> ExecutionActionPermit
  -> Order Group
  -> future Execution I/O
```

It authorizes a multi-leg economic target in a traceable, invalidatable and
durable way. It does not implement Funding Arbitrage or choose execution
method.

## Confirmed Boundaries

- Risk snapshot validity is bounded by the oldest relevant market, position,
  margin and liquidation evidence.
- Typed invalidation records why authorization was withdrawn.
- Whole-Basket approval reserves explicit position, margin, notional and
  factor-risk resources.
- Portfolio target confirmation does not absorb price or Greeks evaluation.
- Risk consumes, but does not calculate, IV, Greeks or volatility surfaces.
- Permit consumption is durable before any future external I/O.
- `STALE`, `INSUFFICIENT_DATA` and `RECOVERY_REQUIRED` remain distinct from
  economic `REJECT`.

## Transition Order

The committee directs:

1. begin ADR-013 Financial Ledger and PnL Attribution design;
2. align ADR-013 ownership/allocation scope with ADR-014;
3. then perform ADR-014 Carry Application Boundary review;
4. do not implement Funding Arbitrage execution until both ADRs are reviewed
   and accepted.

Grouped external execution, authenticated Testnet and production remain
separate closed gates.
