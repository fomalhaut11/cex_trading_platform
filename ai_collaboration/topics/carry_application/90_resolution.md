---
id: AI-20260729-009
title: Carry Application Resolution
origin: joint
status: ACCEPTED_OFFLINE_IMPLEMENTATION_CLOSED
created: 2026-07-29
code_baseline: 40d10125318ebafc6c9979dc6ee3447c10739657
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - 40_codex_adr014_scope_alignment.md
  - 50_codex_adr014_review_handoff.md
  - 60_codex_adr014_offline_implementation_handoff.md
  - 70_web_gpt_adr014_final_acceptance.md
  - ../financial_ledger/90_resolution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Carry Application Resolution

## Current Status

`ACCEPTED_OFFLINE_IMPLEMENTATION_CLOSED`

Web GPT accepted ADR-014, approved its scope and authorized T040-T044/A017
credential-free offline implementation. That implementation and A017 are now
complete. ADR-013 Accounting public contracts are compatible with the
accepted boundary.

Web GPT completed the final implementation review without requesting an
architecture redesign or reopening ADR-014. T040-T044/A017 are accepted and
closed.

## Frozen Baseline Facts

- ADR-009 through ADR-012 are Accepted and implemented through their bounded
  offline gates.
- ADR-012 findings A-01 through A-07 are accepted and closed.
- Grouped external execution remains blocked.
- ADR-013 is approved in principle; T036-T039/A016 are complete under
  project-owner offline authority, with final Web GPT acceptance pending.
- ADR-014 Carry Application Boundary is Accepted.
- ADR-014 design and ADR-013 interface scope alignment are complete.
- T040-T044/A017 offline implementation is accepted and closed.
- Funding execution, grouped external submission, Testnet and production
  remain blocked.

## Numbering Resolution

The phrase “ADR-013 Carry” in the incoming review is normalized to the
repository's stable identifier ADR-014. Existing ADRs are not renumbered.

## Review Resolution

No A-class architecture correction was requested. The accepted implementation
must make lifecycle transitions, the economics/Risk separation and recovery
proposal semantics explicit and testable.

## Scope Alignment Result

- `ApplicationPositionId` maps to generic `EconomicOwnerRef`;
- Carry consumes `PnlAttributionView`, source/balance proofs and valuation
  views;
- Carry cannot allocate, post or reconcile financial facts;
- a durable public Accounting allocation/query coordinator remains a
  dependency;
- the first MVP retains dedicated/exclusive account ownership;
- T040-T044/A017 are complete offline.

## Implementation Resolution

- T040 publishes a bounded authoritative latest `FundingView`.
- T041 provides immutable Carry IDs, pair, lifecycle and ownership contracts.
- T042 assembles exact typed decision Snapshots and emits only generic
  `BasketTargetIntent` through pure economic policy.
- T043 persists application facts before publishing Carry state, replays the
  journal and keeps recovery proposals distinct from OMS recovery and Risk
  permits.
- T044 composes Snapshot plus Strategy only. Its public result is permanently
  `external_execution_blocked=True`.
- A017 validates two-leg open/close, UNKNOWN restart recovery, independent
  physical/financial finality and generic three-leg compatibility.

No source module enables Funding execution, grouped external submission,
Testnet or production.

## Long-Term Guidance

- do not create one universal application journal or state machine;
- do not make Carry lifecycle mandatory for CTA or Market Making;
- share stable application protocols, not family-specific mutable state;
- prioritize the first complete execution/runtime loop before speculative
  kernel expansion.

The next planned sequence is T045/T046/A018 Execution Promotion, separately
authorized A019 Testnet, T047 Application Runtime / SDK Lite, T048 historical
Replay and T049 Paper Exchange. Testnet remains a separate explicit
authorization gate.
