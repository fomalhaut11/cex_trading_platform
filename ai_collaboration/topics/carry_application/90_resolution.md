---
id: AI-20260729-009
title: Carry Application Resolution
origin: joint
status: READY_FOR_REVIEW
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - 40_codex_adr014_scope_alignment.md
  - 50_codex_adr014_review_handoff.md
  - ../financial_ledger/90_resolution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Carry Application Resolution

## Current Status

`READY_FOR_REVIEW`

The topic has an input, architecture response and current-code scope-alignment
record. ADR-013 Accounting public contracts are compatible with the proposal.
ADR-014 is ready for formal review. No acceptance or implementation authority
is recorded here.

## Frozen Baseline Facts

- ADR-009 through ADR-012 are Accepted and implemented through their bounded
  offline gates.
- ADR-012 findings A-01 through A-07 are accepted and closed.
- Grouped external execution remains blocked.
- ADR-013 is approved in principle; T036-T039/A016 are complete under
  project-owner offline authority, with final Web GPT acceptance pending.
- ADR-014 is Carry Application Boundary and remains Proposed.
- ADR-014 design and ADR-013 interface scope alignment are complete.
- Carry/Funding source implementation is not yet authorized.

## Numbering Resolution

The phrase “ADR-013 Carry” in the incoming review is normalized to the
repository's stable identifier ADR-014. Existing ADRs are not renumbered.

## Pending Decision

After Web GPT review, record:

1. accepted ADR-014 boundary;
2. required A-class corrections, if any;
3. ADR-013 dependencies;
4. non-blocking long-term items;
5. explicit implementation authorization or continued block;
6. exact promoted files and commit.

Until then, this file must not be interpreted as ADR acceptance.

## Scope Alignment Result

- `ApplicationPositionId` maps to generic `EconomicOwnerRef`;
- Carry consumes `PnlAttributionView`, source/balance proofs and valuation
  views;
- Carry cannot allocate, post or reconcile financial facts;
- a durable public Accounting allocation/query coordinator remains a
  dependency;
- the first MVP retains dedicated/exclusive account ownership;
- T040-T044/A017 are planned but unauthorized.
