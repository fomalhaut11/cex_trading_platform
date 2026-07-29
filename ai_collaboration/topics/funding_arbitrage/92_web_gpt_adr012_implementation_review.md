---
id: AI-20260729-003
title: Web GPT ADR-012 Implementation Review
status: REVIEWED_CONDITIONAL
date: 2026-07-29
references:
  - 91_codex_adr012_implementation_acceptance.md
---

# Web GPT Review: ADR-012 Implementation

## Decision

ADR-012 design remains `Accepted`.

Implementation decision:

`CONDITIONAL ACCEPTANCE`

The review confirms:

- Portfolio Risk remains independent from OMS and Execution;
- the implementation is generic N-leg infrastructure;
- no Funding, Carry, Market Making or Option strategy specialization leaked
  into Risk;
- Portfolio Risk, not OMS, owns economic authorization and permit issuance;
- the immediate execution-guard ordering is correct.

Grouped Testnet and production execution remain forbidden.

## Required Items

| ID | Finding | Required outcome |
|---|---|---|
| A-01 | Risk snapshot freshness | explicit generation, market/Portfolio as-of and bounded validity contract |
| A-02 | material-change semantics | typed invalidation taxonomy rather than an untyped changed flag |
| A-03 | reservation serialization | explicit resource keys and independent/exclusive/shared-capacity semantics |
| A-04 | target confirmation | versioned position-target tolerance instead of exact decimal equality |
| A-05 | options boundary | explicitly preserve Greeks as supplied Feature/Risk-analytics evidence |
| A-06 | execution guard | preserve durable permit consumption before every external side effect |
| A-07 | failure classification | distinguish economic rejection, stale input, insufficient data and recovery |

## Classification

A-01, A-02, A-03, A-04 and A-07 are ADR-012 implementation-strengthening
items.

A-05 and A-06 are confirmation items because the reviewed implementation
already satisfies them.

No finding authorizes Carry/Funding code or reopening ADR-011. ADR-013 design
may continue independently, but grouped external execution remains blocked
until this conditional review is closed and a later Testnet promotion is
explicitly granted.
