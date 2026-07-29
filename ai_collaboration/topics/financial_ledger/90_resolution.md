---
id: AI-20260729-015
title: Financial Ledger and PnL Attribution Resolution
origin: joint
status: IMPLEMENTED_OFFLINE_AWAITING_FINAL_ACCEPTANCE
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - 40_codex_clarification_response.md
  - 41_project_owner_offline_continuation.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - ../carry_application/90_resolution.md
external_share: allowed
sensitivity: public-project
---

# Financial Ledger and PnL Attribution Resolution

## Current Status

`IMPLEMENTED_OFFLINE_AWAITING_FINAL_ACCEPTANCE`

Web GPT approved ADR-013 in principle without architectural redesign. The two
requested non-blocking clarifications have been added. Final acceptance has
not yet been returned. The project owner separately authorized bounded offline
implementation, and T036-T039/A016 are now complete.

## Frozen Baseline Facts

- ADR-012 acceptance is formally closed.
- grouped external execution remains blocked.
- ADR-013 is Proposed.
- no `cex_quant.accounting` package exists.
- actual Funding is authenticated financial evidence, not market Funding rate.
- ledger truth precedes ownership allocation.
- Accounting cannot import Carry.
- economic, observation and posting time have distinct authority and use.
- cross-asset valuation requires an explicit versioned conversion policy and
  evidence.
- ADR-014 formal review waits for ADR-013 ownership/allocation/read-port scope
  alignment.

## Proposed Scope Alignment

Accounting uses a generic, versioned `EconomicOwnerRef`. A future Carry
`ApplicationPositionId` is mapped to that opaque reference outside
Accounting. `UNALLOCATED` remains explicit when evidence is incomplete.

## Clarification Result

- Economic time controls accounting interval membership.
- Observation time records platform receipt/source-coverage evidence.
- Posting time plus ledger sequence controls durable audit order.
- Original-asset ledger facts remain canonical.
- Multi-currency totals are derived through a versioned
  `ValuationPolicyRef` and exact conversion evidence.
- Reporting valuation does not replace ADR-012 Risk valuation policy.

Clarification handoff:

`40_codex_clarification_response.md`

## Pending Final Decision

After Web GPT final review, record:

1. accepted ADR-013 source-fact boundary;
2. ledger invariant and durability decision;
3. reconciliation and allocation decision;
4. time and multi-currency clarification acceptance;
5. implementation authorization or continued block;
6. ADR-014 scope-alignment outcome;
7. exact promoted files and commit.

Until then, approval in principle is not final ADR acceptance.

## Project-Owner Offline Continuation

Because network conditions prevent immediate final Web GPT review, the project
owner authorized bounded offline T036-T039/A016 engineering. This does not
change Web GPT status and does not enable authenticated sources or external
execution.

Authorization record:

`41_project_owner_offline_continuation.md`

## Offline Implementation Result

- immutable financial facts and generic owner references;
- balanced per-asset ledger with deterministic IDs and exact reversals;
- checksummed durable journal, source convergence and restart replay;
- separate source-completeness and balance-reconciliation proofs;
- append-only allocation with explicit unallocated remainder;
- explicit versioned valuation paths and conversion evidence;
- generic PnL attribution views;
- bounded single-writer Accounting handoff and health failure propagation;
- 502 tests, 188 subtests, 85.18% branch coverage, Ruff, strict MyPy and
  secret scan passing.

Handoff:

`50_codex_adr013_offline_implementation_handoff.md`
