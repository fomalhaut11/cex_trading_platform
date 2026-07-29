---
id: AI-20260729-006
title: Carry Application Architecture Input
origin: web-gpt
status: RECEIVED
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - ../funding_arbitrage/94_web_gpt_adr012_final_acceptance.md
  - ../funding_arbitrage/95_web_gpt_adr012_final_committee_review.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
external_share: allowed
sensitivity: public-project
---

# Topic: Carry Application Architecture

## Background

The platform now has an accepted bounded offline execution-authorization
kernel:

```text
ADR-009  coherent decision facts
ADR-010  N-leg economic target
ADR-011  durable N-leg execution control
ADR-012  Portfolio Risk approval and per-action authorization
```

Web GPT accepted and closed ADR-012 implementation findings A-01 through
A-07. Grouped external execution remains blocked.

The next step is application-layer architecture. It is not a request to
implement Funding Arbitrage or to modify the accepted infrastructure
boundaries.

## Proposed Direction from Web GPT

Create a separate collaboration lifecycle:

```text
10_web_gpt_input
  -> 20_codex_architecture_response
  -> 30_web_gpt_review
  -> 90_resolution
```

The first application should exercise the execution-authorization kernel
without becoming a special branch inside Strategy, Risk, OMS, Accounting or
Execution.

## Committee Transition Decision

The final ADR-012 committee review explicitly authorizes ADR-014 design and
asks it to cover four concrete areas.

### Carry position

The application must represent one economic Carry position and the
relationship among its Spot, perpetual and future optional hedge legs.
Economic position state belongs to the application, not the generic Portfolio
state owner.

### Financial cash flows

Actual Funding payments, trading fees, borrow cost and realized PnL
attribution belong to ADR-013 Accounting. They are not Risk values and must
not be inferred from expected Funding Features.

### Workflow

The business workflow must explain:

```text
SEARCH -> OPEN -> HEDGE -> COLLECT_FUNDING -> UNWIND
```

without combining discovery, execution outcome, hedge quality and financial
finality into one ambiguous state enum.

### Basket production

The application emits a generic `BasketTargetIntent`. ADR-012 then performs
Portfolio Risk approval, and ADR-011 owns Order Group execution control.

## Repository Numbering

The review message called the next phase “ADR-013 Carry Application.”
The repository already has stable, cross-referenced decisions:

```text
ADR-013  Financial Ledger and PnL Attribution
ADR-014  Carry Application Boundary
```

This topic preserves those identifiers. “Carry Application design may begin”
is therefore handled as ADR-014 design review. No existing ADR is renumbered.

## Architecture Question

How should the first Carry application compose the accepted platform
capabilities while preserving all ownership and safety boundaries?

## Required Review Areas

1. Where should generic Carry and Funding-specific code live?
2. Which economic state belongs to the application?
3. Which facts remain authoritative in Market Data, Features, Portfolio,
   Risk, OMS and Accounting?
4. What immutable inputs should form a Carry decision snapshot?
5. What is the public output boundary to Strategy/Basket?
6. How does the application observe partial or unknown execution without
   controlling child orders?
7. How should application-position ownership be represented?
8. Which ADR-013 Accounting capability is required before Carry code starts?
9. How should restart, recovery and financial finality remain separate?
10. Can Funding Carry, basis/calendar Carry and future option hedges share the
    same application family without Funding-specific platform branches?

## Frozen Constraints

- Keep grouped external execution blocked.
- Do not reopen ADR-009 through ADR-012.
- Do not move Greeks or volatility surfaces out of Features.
- Do not calculate economic Risk in OMS.
- Do not allow the application to issue an execution permit or venue order.
- Do not infer actual Funding or realized PnL from expected market values.
- Do not create Carry application source code during this proposal phase.

## Requested Output

Codex should:

- audit the current code against this boundary;
- identify reusable and missing contracts;
- show module topology, dependency direction and public ports;
- state the ADR-013/ADR-014 dependency and promotion sequence;
- classify what can be designed now versus what remains implementation-gated;
- provide a review-ready architecture response for Web GPT.
