---
id: AI-20260730-002
title: Web GPT ADR-014 Final Implementation Acceptance
origin: web-gpt
status: ACCEPTED
created: 2026-07-30
code_baseline: 40d10125318ebafc6c9979dc6ee3447c10739657
supersedes: none
related:
  - 30_web_gpt_review.md
  - 60_codex_adr014_offline_implementation_handoff.md
  - 90_resolution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
  - ../../../interfaces/carry_application_schema.md
external_share: allowed
sensitivity: public-project
---

# Web GPT ADR-014 Final Implementation Acceptance

## Final Decision

Web GPT reviewed:

1. `60_codex_adr014_offline_implementation_handoff.md`;
2. `carry_application_schema.md`;
3. `ADR-014-carry-application-boundary.md`.

Final result:

```text
ADR-014 Design:                  ACCEPTED
ADR-014 Offline Implementation: ACCEPTED
T040-T044 / A017:               CLOSED
Architecture redesign:          NOT REQUIRED
```

No implementation issue requiring ADR-014 to be reopened was identified.

## Confirmed Architecture

ADR-014 successfully validates that a real application can use the platform
without introducing Funding-specific branches into the trading kernel:

```text
Application
  -> BasketTargetIntent
  -> Portfolio Risk
  -> OMS
  -> Execution
```

Carry correctly owns:

- economic lifecycle;
- hedge interpretation;
- economic recovery proposals;
- application policy.

Carry correctly does not own:

- Market State;
- Portfolio;
- Risk;
- OMS;
- Accounting;
- Venue I/O.

## Confirmed Implementation Decisions

### Carry emits economic intent, not orders

The application produces generic `BasketTargetIntent`. It cannot issue an
`ExecutionActionPermit`, create a child `OrderRequest`, mutate an OMS
`OrderGroup` or call an Execution gateway.

### Application state is not OMS state

The independent dimensions are accepted:

```text
lifecycle:  PROPOSED / OPENING / ACTIVE / CLOSING / CLOSED
hedge:      UNKNOWN / UNHEDGED / PARTIALLY_HEDGED / HEDGED
financial:  NOT_READY / PROVISIONAL / RECONCILED
```

Portfolio effective positions, not OMS fills alone, determine hedge
interpretation. Order success does not by itself mean the Carry objective is
active or complete.

### Expected economics is not Accounting truth

Funding rate and expected carry remain Market/Feature evidence. Realized
Funding requires authenticated settlement evidence and ADR-013 Accounting.

## Non-Blocking Long-Term Guidance

### Do not create a universal application state machine

Carry may keep a Carry-specific journal and aggregate. Future CTA and Market
Making applications should share stable platform interfaces, not inherit
Carry lifecycle or storage semantics.

Examples:

```text
applications/carry/          Carry position and lifecycle
applications/cta/            CTA-specific state
applications/market_making/  quote session and inventory state
```

### Do not treat Carry as the template for every application

`ApplicationPosition` and Carry lifecycle are appropriate for Carry, but are
not mandatory abstractions for quote-driven or other application families.

## Roadmap Direction

The architecture kernel is now sufficiently stable. The recommended order is:

1. close ADR-014 acceptance;
2. complete minimum grouped Execution Promotion;
3. introduce a small Strategy/Application SDK based on interfaces rather than
   shared state;
4. add Replay and Paper Trading.

The objective is to close the first full runtime loop instead of continuing
to expand the kernel with speculative ADRs.

## Codex Gate Handling

Codex records the following implementation consequence: this review
recommends a future first Testnet Carry loop, but contains no explicit
instruction unblocking grouped external submission or supplying the external
prerequisites. Existing external gates therefore remain in force until the
project owner separately authorizes Testnet activation.
