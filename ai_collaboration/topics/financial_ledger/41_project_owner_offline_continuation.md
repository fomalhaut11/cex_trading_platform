---
id: AI-20260729-017
title: Project Owner ADR-013 Offline Continuation
origin: project-owner
status: AUTHORIZED_OFFLINE
created: 2026-07-29
code_baseline: beb078ac8441479cad63f7a11a0f2965baa0800c
supersedes: none
related:
  - 30_web_gpt_review.md
  - 40_codex_clarification_response.md
  - 90_resolution.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
external_share: allowed
sensitivity: public-project
---

# Project Owner Offline Continuation: ADR-013

## Context

Web GPT approved ADR-013 in principle and requested two non-blocking
clarifications. Codex completed those clarifications, but network conditions
prevent immediate Web GPT document upload and final review.

The project owner instructed Codex to continue work and aggregate results for
later review.

## Authorized Scope

Continue bounded, deterministic, credential-free offline engineering:

```text
T036  Accounting identifiers and immutable financial facts
T037  Balanced ledger, deterministic mapping, journal and replay
T038  Reconciliation, allocation, valuation and PnL read views
T039  Bounded durable financial-fact handoff and health boundary
A016  Offline Accounting acceptance and restart/failure scenarios
```

## Status Semantics

This record is project-owner authorization for offline engineering. It is not
a fabricated Web GPT final acceptance and does not change the external review
record.

ADR-013 remains:

```text
Web GPT design status:       APPROVED_IN_PRINCIPLE
Offline implementation:      PROJECT_OWNER_AUTHORIZED
External grouped execution:  BLOCKED
Authenticated Testnet:       NOT_AUTHORIZED
Production:                  NOT_AUTHORIZED
```

## Forbidden Scope

- no authenticated financial-history calls;
- no live private-stream Accounting activation;
- no grouped external order submission;
- no Funding Arbitrage or Carry execution;
- no Testnet or production credentials;
- no weakening of ADR-009 through ADR-012;
- no Accounting dependency on Carry implementations.

Results must remain separately reviewable and be summarized for Web GPT when
network access permits.
