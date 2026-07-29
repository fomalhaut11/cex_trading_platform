---
id: AI-20260728-014
title: ADR-013 Current-Code Audit
origin: codex
status: REFERENCE
created: 2026-07-28
code_baseline: fa0df9e2a015db258457d226c7ed9fa5c689b8eb
supersedes: none
related:
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - 83_codex_adr012_proposal_handoff.md
  - ../financial_ledger/20_codex_architecture_response.md
external_share: allowed
sensitivity: public-project
---

# ADR-013 Current-Code Audit

## Status Notice

This audit is retained as historical evidence for its recorded code baseline.
The current ADR-013 review entry is
`../financial_ledger/20_codex_architecture_response.md`.

## Audit Result

The repository has enough execution, Portfolio and Recorder infrastructure to
add Accounting as a separate domain, but it does not yet have authoritative
financial transaction history.

The current code answers:

- what the latest order state is;
- what the latest venue-reported balances and positions are;
- what the market Funding rate is;
- what market and execution events were recorded.

It does not answer:

- which individual fill created a financial effect;
- which asset and amount were charged as commission;
- whether an actual Funding settlement occurred;
- why an account balance changed;
- whether all financial source records were ingested;
- how realized PnL reconciles to immutable source evidence;
- which application owns a shared account-level cash flow.

ADR-013 must therefore add Accounting without converting OMS, Portfolio,
Market Data or Recorder into an implicit ledger.

## Existing Module Findings

### OMS

The canonical OMS order event carries:

```text
venue_update_id
client_order_id
order status
cumulative filled quantity
average fill price
```

This is correct for order lifecycle and restart recovery. It is not sufficient
for Accounting:

- a cumulative quantity overlaps prior updates;
- an average price loses the exact fill sequence;
- commission asset and amount are absent;
- derivative realized settlement PnL is absent;
- one order can produce several venue trade IDs.

Accounting must consume individual financial facts, not infer them from the
current OMS aggregate.

### Binance private normalization

Existing Spot and Futures fixtures already include a venue trade ID and
last-fill quantity/price. The current private-order normalizer projects these
messages to `OrderReconciliationSnapshot` and intentionally drops
accounting-specific detail.

Required additive work after acceptance:

- preserve the existing OMS projection;
- normalize fill financial facts with venue trade identity;
- add complete commission, commission-asset, quote amount and realized-PnL
  fixtures;
- normalize authenticated income/transfer history for non-fill cash flows;
- parse each private message once, then fan out typed projections.

### Market Data

`FundingRateUpdate` contains market Funding information such as rate and next
Funding time. It is not proof of account settlement.

Posting it as income would be a correctness defect. An actual Funding
cash-flow fact must come from an authenticated account/private-stream or
history source with an account-scoped venue transaction ID.

### Portfolio

Portfolio stores authoritative absolute balances and positions, including
venue-reported cost basis and realized PnL where available.

Those values are necessary reconciliation anchors, but they are not an
immutable transaction history. A balance difference cannot safely identify
Funding, a fee, transfer, liquidation or manual adjustment.

### Recorder

Recorder owns canonical market/event evidence and replay. It does not own:

- ledger accounts and balanced postings;
- account financial source completeness;
- immutable corrections/reversals;
- economic ownership allocation;
- PnL attribution.

Extending Recorder into Accounting would merge unrelated ownership and
recovery semantics.

### Runtime and durability

ADR-011 established a durable-before-external-I/O order handoff. Accounting is
not part of that synchronous submit critical section.

However, financial evidence cannot be best-effort telemetry. The accepted
implementation must use a bounded durable side path:

```text
private financial fact
  -> durable Accounting inbox/journal
  -> ledger transaction
  -> reconciliation and derived views
```

If Accounting cannot durably retain evidence, the platform must become
unhealthy for new exposure while query, cancel and recovery remain available.

## Missing Domain

There is currently no `cex_quant.accounting` package.

The minimum independent topology is:

```text
cex_quant.accounting
  identifiers
  facts
  ledger
  journal
  mapping
  reconciliation
  allocation
  valuation
  pnl
  service
```

Dependency direction:

```text
Exchange private adapter
  -> canonical financial facts
  -> Accounting

OMS group/leg identity --------\
Portfolio snapshots ------------> Accounting read-side inputs
Market marks/features ----------/

Accounting
  -> immutable ledger/reconciliation facts
  -> derived PnL views
  -> Runtime health
```

Accounting must not submit/cancel orders, issue Risk permits, mutate Portfolio
truth or contain Funding-Arbitrage strategy logic.

## Identity Finding

The planning baseline mentioned a generic `CashFlowId`. That name is too
narrow because fill facts are also authoritative financial inputs.

ADR-013 proposes:

- `FinancialObservationId`;
- `FinancialFactId`;
- `LedgerTransactionId`;
- `LedgerPostingId`;
- `LedgerAccountId`;
- `FinancialReconciliationId`;
- `AttributionAllocationId`.

Venue business IDs remain mandatory economic identity. Transport observation
identity is separate so private-stream/history overlap converges to one
financial fact and cannot double post. Internal IDs provide canonical
immutable references, provenance and idempotency.

## Ledger Model Finding

A single signed cash-flow table is insufficient for:

- Spot trades exchanging two assets;
- fees charged in base, quote or a third asset;
- Futures settlement and margin movements;
- transfers between account locations;
- exact source-to-account reconciliation.

The appropriate operational invariant is per-asset double entry:

```text
for every ledger transaction and asset:
    sum(posting amounts for that asset) == 0
```

Unlike assets are never summed together without an explicit derived valuation
and conversion source.

## Attribution Finding

Ledger truth must precede application allocation.

Direct fill causation can use immutable Intent, Order Group and leg identities.
Account-level Funding can be allocated only when ownership evidence is
complete. A shared-account cash flow without such evidence must remain
`UNALLOCATED`; guessing would make strategy PnL look complete while corrupting
auditability.

## Compatibility Assessment

ADR-013 can be additive:

- existing order projections and tests remain unchanged;
- Portfolio remains the owner of live position/account state;
- Market Data continues to publish Funding-rate observations;
- OMS remains the owner of execution facts;
- Recorder remains a recorder, not a ledger;
- ADR-012 can consume Accounting health without depending on strategy PnL;
- ADR-014 can consume attributed read views after Accounting is accepted and
  implemented.

## Implementation Blockers

No ADR-013 code should start before explicit acceptance.

Before implementation, review must freeze:

1. canonical source-fact schemas and idempotency keys;
2. supported venue/product mapping rules;
3. ledger account registry and per-asset balance invariant;
4. journal and durable-inbox capacity policy;
5. source-completeness and balance-reconciliation equations;
6. allocation evidence and `UNALLOCATED` behavior;
7. valuation sources and PnL component definitions;
8. failure behavior that blocks new exposure without blocking recovery.

Authenticated Testnet and production ingestion remain later, separately
authorized gates.
