---
id: AI-20260729-018
title: Codex ADR-013 Offline Implementation Handoff
origin: codex
status: READY_FOR_FINAL_REVIEW
created: 2026-07-29
code_baseline: pending-commit
supersedes: none
related:
  - 30_web_gpt_review.md
  - 40_codex_clarification_response.md
  - 41_project_owner_offline_continuation.md
  - 90_resolution.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
external_share: allowed
sensitivity: public-project
---

# Codex ADR-013 Offline Implementation Handoff

## Decision Status

Web GPT status remains `APPROVED_IN_PRINCIPLE`; final acceptance is pending
because the review document cannot currently be uploaded. The project owner
authorized credential-free offline T036-T039/A016 work. This handoff records
the result without fabricating final committee acceptance.

## Implemented Boundary

```text
normalized authenticated financial evidence
  -> bounded runtime handoff
  -> immutable financial fact convergence
  -> deterministic balanced ledger
  -> durable journal and restart replay
  -> reconciliation / allocation
  -> valuation / PnL read views
```

T036 provides strong Accounting identifiers, immutable fill/account cash-flow
facts, separate economic/observation/posting time and opaque versioned
economic-owner references.

T037 provides per-asset double-entry balance, deterministic policy-versioned
transaction/posting IDs, checksummed JSONL durability, duplicate
stream/history convergence, contiguous replay, single-writer mutation and
exact append-only reversal transactions.

T038 keeps source completeness distinct from balance proof, preserves explicit
unallocated ownership, uses append-only allocation reversal/replacement,
requires deterministic conversion paths and exact rate evidence, and derives
Funding, realized settlement, commissions, rebates, interest and liquidation
PnL from ledger account semantics. Transfers are excluded from trading PnL.

T039 creates the Accounting ledger on its worker thread, bounds inbox capacity
and queue age, never reports failed persistence as success, and exposes
overflow/expiry/storage failure as unhealthy so aggregate runtime authority
can block new exposure.

## Acceptance Evidence

A016 covers:

- Spot buy and Perpetual hedge-leg financial facts;
- actual authenticated-style Funding settlement and fees;
- private-stream/authenticated-history observation convergence;
- durable restart replay;
- source-completeness and USDT balance proof;
- generic Carry-shaped owner allocation without importing Carry;
- explicit BTC/USDT valuation evidence;
- realized net PnL `50.00 USDT`;
- marked total PnL `650.00 USDT`;
- persistence failure, overflow, corruption and invariant rejection.

Validation result:

```text
pytest:             502 passed
unittest subtests:  188 passed
branch coverage:    85.18% (minimum 85%)
Ruff:               passed
strict MyPy:        passed, 115 source files
secret scan:        passed
```

## Boundary Audit

- Accounting does not import Carry or Funding applications.
- Funding rate/forecast is not accepted as a financial fact.
- OMS state is not ledger truth.
- Portfolio snapshots are reconciliation/valuation inputs, not transaction
  history.
- IV, Greeks and volatility surfaces remain Feature-owned.
- reporting valuation does not replace ADR-012 Risk marks.
- no grouped external route, authenticated Testnet source or production path
  was enabled.

## Pending Review

When Web GPT connectivity returns, review this handoff together with
`40_codex_clarification_response.md`. Final acceptance may promote ADR-013;
until then, authenticated ingestion, Carry/Funding execution, Testnet,
production and grouped external execution remain blocked.
