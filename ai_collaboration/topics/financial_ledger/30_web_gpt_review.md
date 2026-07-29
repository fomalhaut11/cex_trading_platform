---
id: AI-20260729-014
title: Web GPT Financial Ledger and PnL Review
origin: web-gpt
status: APPROVED_IN_PRINCIPLE
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 40_codex_clarification_response.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
external_share: allowed
sensitivity: public-project
---

# Web GPT Review: Financial Ledger and PnL Attribution

## Decision

ADR-013 Financial Ledger and PnL Attribution is approved in principle.

No architectural redesign is required.

## Accepted Boundaries

- Accounting is an independent domain.
- Ledger does not import Carry.
- Funding rate is not a financial fact.
- Actual Funding settlement requires authenticated account evidence.
- OMS state is not ledger truth.
- Portfolio state is not transaction history.

## Non-Blocking Clarifications Required

Before final acceptance, add:

1. Economic/Observation/Posting time semantics;
2. multi-currency valuation-policy boundary.

These are design clarifications, not architectural redesign findings.

## Authorization State

```text
ADR-013 design:                 APPROVED_IN_PRINCIPLE
ADR-013 source implementation:  NOT_AUTHORIZED
Grouped external execution:     BLOCKED
Testnet / Production:           NOT_AUTHORIZED
```

Final acceptance is required before source implementation.
