---
id: AI-20260729-015
title: Financial Ledger and PnL Attribution Resolution
origin: joint
status: PENDING_REVIEW
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - ../carry_application/90_resolution.md
external_share: allowed
sensitivity: public-project
---

# Financial Ledger and PnL Attribution Resolution

## Current Status

`PENDING_REVIEW`

ADR-013 has a current input and Codex architecture response. Web GPT has not
yet returned its review. No Accounting implementation authority exists.

## Frozen Baseline Facts

- ADR-012 acceptance is formally closed.
- grouped external execution remains blocked.
- ADR-013 is Proposed.
- no `cex_quant.accounting` package exists.
- actual Funding is authenticated financial evidence, not market Funding rate.
- ledger truth precedes ownership allocation.
- Accounting cannot import Carry.
- ADR-014 formal review waits for ADR-013 ownership/allocation/read-port scope
  alignment.

## Proposed Scope Alignment

Accounting uses a generic, versioned `EconomicOwnerRef`. A future Carry
`ApplicationPositionId` is mapped to that opaque reference outside
Accounting. `UNALLOCATED` remains explicit when evidence is incomplete.

## Pending Decision

After Web GPT review, record:

1. accepted ADR-013 source-fact boundary;
2. ledger invariant and durability decision;
3. reconciliation and allocation decision;
4. PnL/slippage/double-counting corrections, if any;
5. A-class corrections;
6. implementation authorization or continued block;
7. ADR-014 scope-alignment outcome;
8. exact promoted files and commit.

Until then, this file is not an ADR acceptance.
