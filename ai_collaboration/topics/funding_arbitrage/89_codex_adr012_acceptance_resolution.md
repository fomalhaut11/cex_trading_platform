---
id: AI-20260729-001
title: ADR-012 Acceptance Resolution
status: PROMOTED
date: 2026-07-29
promoted_to:
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
---

# ADR-012 Acceptance Resolution

## Decision

Web GPT concluded that the ADR-012 Proposal could start, but grouped external
execution must remain closed. The project owner agreed.

The same review repeated an earlier ADR-011 conditional-acceptance state with
A-01, A-03 and A-06 as blockers. That statement applied to the
pre-remediation implementation. Current-branch evidence shows that all three
were already closed by:

- `81_codex_adr011_remediation_acceptance.md`;
- implementation commit
  `c2c306dbe7675076ae200021d2c98f127736f09e`;
- documentation acceptance commit
  `df2fd83`;
- passing CI run `30351998834`.

ADR-011 therefore remains Accepted and was not reopened.

## Authorized Scope

ADR-012 is Accepted for bounded offline implementation:

| ID | Scope |
|---|---|
| T032 | execution-consistent Portfolio baseline/overlay and normalized margin/liquidation inputs |
| T033 | immutable Portfolio Risk contracts, exact N-leg projection and whole-Basket/action decisions |
| T034 | durable reservation, permit generation, supervision, recovery and confirmation evidence |
| T035 | immediate pre-I/O Portfolio Risk guard integrated with the shared handoff boundary |
| A015 | deterministic offline ADR-012 acceptance |

## Frozen Boundary

Authorized:

```text
Economic Intent
  -> Portfolio Risk approval/reservation
  -> exact ExecutionActionPermit
  -> durable grouped preparation
```

Still forbidden:

- grouped requests reaching an Execution adapter;
- Testnet or production grouped trading;
- Funding Arbitrage application implementation;
- ADR-013 Accounting implementation;
- Risk logic inside OMS;
- strategy-specific branches inside Risk or OMS.

Passing A015 is evidence for a later review. It is not Testnet authority.
