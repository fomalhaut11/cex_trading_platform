---
id: AI-20260729-009
title: Carry Application Resolution
origin: joint
status: PENDING_SCOPE_ALIGNMENT
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - ../financial_ledger/90_resolution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Carry Application Resolution

## Current Status

`PENDING_SCOPE_ALIGNMENT`

The topic has an input and a Codex architecture response. Formal ADR-014
review waits for ADR-013 ownership, allocation and attribution read-port scope
alignment. No acceptance or implementation authority is recorded here.

## Frozen Baseline Facts

- ADR-009 through ADR-012 are Accepted and implemented through their bounded
  offline gates.
- ADR-012 findings A-01 through A-07 are accepted and closed.
- Grouped external execution remains blocked.
- ADR-013 is Financial Ledger and PnL Attribution and remains Proposed.
- ADR-014 is Carry Application Boundary and remains Proposed.
- the ADR-014 design draft is complete, but formal review waits for ADR-013
  scope alignment.
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
