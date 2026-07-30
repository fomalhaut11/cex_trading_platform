---
id: AI-20260729-008
title: Web GPT Carry Application Review
origin: web-gpt
status: ACCEPTED
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 40_codex_adr014_scope_alignment.md
  - 50_codex_adr014_review_handoff.md
  - ../financial_ledger/30_web_gpt_review.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Web GPT Review: Carry Application

## Architecture Review Decision

```text
ADR-014 Design:             ACCEPTED
Scope:                      APPROVED
Offline implementation:     AUTHORIZED
External execution:         BLOCKED
```

Approved boundaries:

- Carry belongs in `cex_quant.applications.carry`.
- Carry owns economic lifecycle and policy.
- Carry does not own Market State, Portfolio, Risk, OMS, Accounting or Venue
  I/O.
- Carry produces generic `BasketTargetIntent`.
- ADR-012 remains the Risk authorization boundary.
- ADR-011 remains the execution-control boundary.
- ADR-013 remains Accounting truth.

Approved offline tasks:

- T040 Funding market-state view;
- T041 Carry contracts;
- T042 pure economic policy;
- T043 Carry aggregation and recovery;
- T044 Runtime composition without external execution;
- A017 offline acceptance.

Non-blocking implementation clarifications:

- Carry lifecycle states;
- Carry economics versus Risk separation;
- recovery proposal semantics.

No Funding execution, Testnet or production authorization is granted.
