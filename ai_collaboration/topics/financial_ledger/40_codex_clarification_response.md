---
id: AI-20260729-016
title: Codex ADR-013 Time and Multi-Currency Clarification Response
origin: codex
status: READY_FOR_FINAL_REVIEW
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 20_codex_architecture_response.md
  - 30_web_gpt_review.md
  - 90_resolution.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
external_share: allowed
sensitivity: public-project
---

# Codex Clarification Response: ADR-013

## Result

Both non-blocking design clarifications requested by Web GPT are now included
in the authoritative ADR-013 proposal and the current Codex architecture
response.

No source code was created. ADR-013 source implementation remains
unauthorized pending final acceptance.

## 1. Economic, Observation and Posting Time

Three time meanings are frozen:

```text
Economic time
  venue/business effective time
  -> accounting interval and economic attribution

Observation time
  platform receive time for one stream/history observation
  -> latency, completeness and late-arrival evidence

Posting time + ledger sequence
  durable canonical append time/order
  -> audit, replay and publication
```

Required behavior:

- a late fact keeps its original economic time;
- stream and history observations may have different observation times but
  converge to one economic fact;
- local receive or posting time never becomes venue business identity;
- PnL intervals use economic time;
- completeness uses cursor/observation evidence;
- replay uses durable ledger sequence;
- correction/reversal facts retain original references and receive their own
  time evidence without backdating ledger order;
- missing authoritative economic time is incomplete unless a versioned source
  policy explicitly supplies a documented substitute.

The pure mapper produces `LedgerTransactionDraft`. The single-writer
coordinator assigns `posted_at_ns` and `ledger_sequence` at durable append.
Commit metadata is not part of deterministic transaction/posting identity.

## 2. Multi-Currency Valuation Policy

The immutable ledger remains balanced and authoritative in original assets.
Cross-asset totals exist only as derived valuation views.

A versioned `ValuationPolicyRef` declares:

- reporting asset;
- allowed price/conversion sources;
- quote direction and inversion;
- deterministic direct/multi-hop path priority;
- maximum age, coherence and hop count;
- precision and rounding;
- economic-time versus endpoint conversion;
- missing/stale/conflicting-rate behavior.

Every result retains `ConversionRateEvidence` for source/destination assets,
rate, quote convention, source identity/time, path, snapshot and policy
version.

Additional constraints:

- no implicit stablecoin parity;
- no opportunistic selection of the most favorable conversion path;
- no silent current-rate conversion of historical components;
- missing conversion evidence produces `INCOMPLETE`, not zero;
- conversion does not create a transfer or ledger posting;
- Accounting reporting valuation does not replace ADR-012 Risk marks or
  stress policy.

## Final Review Request

Please confirm:

1. the three time semantics are sufficiently explicit;
2. late-arrival, correction and replay ordering are unambiguous;
3. multi-currency valuation remains a derived policy-bound view;
4. conversion evidence and incomplete behavior are sufficient;
5. ADR-013 may move from `APPROVED_IN_PRINCIPLE` to final `ACCEPTED`.

This request does not authorize Accounting implementation, grouped external
execution, Testnet or production.
