---
id: AI-20260730-003
title: Project Owner BTC Funding Carry Fast-Track Decision
origin: project-owner
status: ACTIVE
created: 2026-07-30
code_baseline: 0123b6322de80f9fb488b92942ef19b31cdd6512
supersedes: none
related:
  - 70_web_gpt_adr014_final_acceptance.md
  - 90_resolution.md
  - ../../../development/funding_carry_fast_track_plan.md
  - ../../../architecture/kernel_v1_freeze.md
external_share: allowed
sensitivity: public-project
---

# Project Owner BTC Funding Carry Fast-Track Decision

## Decision

Retain all implemented kernel and platform capabilities, but remove non-MVP
platform expansion from the active delivery queue.

The sole active product objective is:

> launch the smallest bounded Binance single-account BTC Funding Carry
> end-to-end loop as quickly as safety and evidence allow.

## Active Scope

- Binance only;
- Spot and USD-M linear perpetual only;
- BTC only;
- one dedicated account;
- fixed configured quantity and explicit risk envelope;
- manual start and operator halt;
- Execution Promotion, Testnet, Operations/Shadow, live readiness and
  controlled micro-live.

## Deferred, Not Deleted

- Application Runtime / SDK Lite;
- general historical Replay platform;
- Paper Exchange/general Fill Model;
- CTA;
- cross-venue arbitrage;
- multi-account operation;
- option execution applications;
- high-frequency Market Making;
- general dashboard/platform UI;
- automatic capital optimization.

The existing code and long-term plans remain in the repository. They are not
active work until after the Fast-Track MVP.

## Active Sequence

```text
T045
  -> T046
  -> A018
  -> A019 (separate Testnet authorization)
  -> T050
  -> A020 (readiness only)
  -> A021 (separate real-money authorization)
```

## Authorization

This decision changes priority, not external authority.

```text
Grouped external execution: blocked
Binance Testnet:            not yet authorized
Real-money trading:         not authorized
Production scaling:         not authorized
```

Promoted engineering plan:

`development/funding_carry_fast_track_plan.md`
