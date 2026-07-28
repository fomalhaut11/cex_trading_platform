---
id: AI-20260728-015
title: ADR-013 Proposed Handoff
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-28
code_baseline: fa0df9e2a015db258457d226c7ed9fa5c689b8eb
supersedes: none
related:
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - 84_codex_adr013_current_code_audit.md
external_share: allowed
sensitivity: public-project
---

# Codex Handoff: ADR-013 Proposed

## Review Request

Please review ADR-013 as the Financial Ledger and PnL Attribution boundary.

ADR-013 is not a Funding-Arbitrage implementation. It establishes the
financial evidence and accounting foundation required by Funding Carry,
Market Making, option spreads and later applications.

Please preserve accepted ADR-009 through ADR-011 and do not use this review to
redesign their contracts. ADR-012 remains Proposed and grouped external
execution remains hard-blocked.

Classify findings as:

- **A. ADR-013 design error**: must be corrected before acceptance;
- **B. ADR-014 or later concern**: valid, but belongs to the application or a
  later implementation decision;
- **C. Long-term optimization**: useful after the correctness baseline.

No implementation authorization is requested by this handoff.

## Architecture Conclusion

ADR-013 proposes:

```text
Authenticated venue financial evidence
  -> canonical immutable financial facts
  -> balanced append-only multi-asset ledger
  -> source and balance reconciliation
  -> immutable ownership allocation
  -> derived valuation and PnL attribution
```

The domain is independent:

```text
OMS         owns execution lifecycle and child-order facts
Portfolio   owns live balances, positions and account state
Market Data owns Funding-rate and mark observations
Risk        owns exposure authorization
Accounting  owns financial facts, postings and reconciliation
Application owns economic intent and consumes attributed views
```

## Critical Current-Code Findings

### Order state is not fill-level financial truth

The current OMS retains cumulative filled quantity and average price. That is
correct for order control but cannot reproduce:

- every individual fill;
- exact quote settlement;
- commission amount/asset;
- derivative realized settlement PnL;
- venue trade identity.

ADR-013 requires `ExecutionFillFact` rather than reconstructing a ledger from
OMS aggregates.

Economic fact identity is separate from transport observation identity. If
the same commission appears through private stream and authenticated history,
it converges to one `FinancialFactId`, retains both provenance observations
and posts once.

### Funding rate is not Funding income

The existing `FundingRateUpdate` is Market Data. It cannot create a ledger
posting.

Actual Funding receipt/payment requires authenticated account evidence with a
venue transaction identity.

### Balances are reconciliation anchors, not history

Portfolio absolute balances and positions prove current venue state. They
cannot explain why cash changed and cannot replace immutable financial
transactions.

## Proposed Canonical Inputs

```text
FinancialSourceFact
  = ExecutionFillFact
  | AccountCashFlowFact

ObservedFinancialFact
  = canonical economic fact
  + transport provenance/cursor
```

`ExecutionFillFact` includes:

- account, venue, product and instrument identity;
- client/venue order identity and venue trade ID;
- exact last-fill quantity, price and quote amount;
- zero or more commission components with asset identity;
- realized settlement PnL where the venue provides it;
- optional immutable Intent, Order Group and leg causation;
- source time, receive time and source cursor.

`AccountCashFlowFact` covers:

- Funding settlement;
- commission or rebate not attached to a fill;
- realized settlement;
- borrow interest;
- deposit, withdrawal and transfer;
- liquidation or insurance movement;
- explicit venue adjustment.

Each private source message should be parsed once and projected independently
to OMS, Portfolio and Accounting. A versioned source policy must converge
stream/history overlap by venue business key; timestamp proximity never proves
identity, and ambiguous aliasing enters reconciliation mismatch.

## Proposed Ledger Invariant

The ledger is operational double entry and balances independently per asset:

```text
for each transaction and asset:
    sum(posting amounts) == 0
```

Examples:

```text
Funding receipt in USDT
  Dr Venue cash:USDT
  Cr Funding income clearing:USDT

Commission in BNB
  Dr Commission expense:BNB
  Cr Venue cash:BNB

Spot purchase
  Dr Venue inventory:BTC
  Cr Trade clearing:BTC
  Dr Trade clearing:USDT
  Cr Venue cash:USDT
```

Fiat-equivalent or reporting-currency values are derived using explicit marks
and conversion sources. Unlike assets are never added inside the immutable
ledger.

## Durability and Correction

The ledger has one durable writer:

```text
fact journal
  -> deterministic versioned mapping
  -> ledger transaction journal
  -> replayed state/read views
```

Required semantics:

- fsync before publishing ledger state;
- idempotency by immutable source identity;
- transport-independent economic identity and one posting across
  stream/history overlap;
- journal corruption/gaps fail closed;
- no generic “unknown transaction” auto-posting;
- no mutation or deletion of posted facts;
- corrections use an exact reversing transaction plus a new transaction.

Accounting is not inserted into the synchronous order-submit handoff. It uses
a bounded durable side path that may apply backpressure but may never drop
financial evidence.

If the side path cannot retain evidence:

- Accounting health becomes unhealthy;
- new exposure is blocked through Runtime/Risk health;
- query, cancel and recovery remain available.

## Reconciliation

Two different proofs remain explicit:

1. **source completeness**: stream plus authenticated trade/income/transfer
   history proves all source facts in a cursor/window;
2. **balance proof**: opening balances plus all ledger movements equal the
   closing authoritative venue balances, per asset.

An unexplained difference cannot be silently posted as an adjustment.
Startup remains financially unhealthy until the configured reconciliation
window is complete.

## Allocation and PnL

Ledger posting always precedes application allocation.

Direct fills can use Intent, Order Group and leg causation. Account-level
Funding requires complete ownership evidence. Shared-account cash flows that
cannot be proven belong to:

```text
UNALLOCATED
```

They must not be guessed into strategy PnL.

Allocation is itself append-only and correctable by reversal/new evidence.

PnL views separate:

- Funding income/expense;
- realized trading/settlement PnL;
- commissions and rebates;
- borrow interest and other explicit costs;
- unrealized mark and basis change;
- non-PnL transfers.

Immutable cash facts remain separate from derived valuation. Mark-price ticks
do not create ledger entries, and realized settlement is not counted again as
unrealized basis change.

## Expansion Assessment

### Funding Carry

The model records real Funding settlements and exposes attributed components,
while expected Funding/APR remains a Feature rather than realized PnL.

### Market Making

Many fills and rebates use the same fill facts and ledger. Inventory valuation
is derived rather than written into execution state.

### Option spreads

Premium, commission, exercise/assignment and derivative settlement can use
product-specific deterministic mappings. Greeks and volatility surfaces stay
in Features.

### Multi-venue

Ledger accounts include venue/account scope. Transfers remain explicit
non-PnL flows; no global balance is inferred from unrelated account snapshots.

## Proposed Acceptance Boundary

If the architecture is accepted, implementation may later include:

- immutable identifiers and financial-fact contracts;
- complete offline Binance fill and income fixtures;
- one-pass private-event projection;
- deterministic product mappings;
- balanced durable ledger and exact replay;
- reconciliation and bounded durable inbox;
- immutable allocation plus derived valuation/PnL views;
- offline acceptance and failure-injection tests.

Still forbidden until separately authorized:

- authenticated Testnet or production financial ingestion;
- grouped external submission;
- real `ExecutionActionPermit` issuance;
- Funding-Arbitrage application execution.

## Review Questions

1. Is a balanced per-asset operational ledger the correct canonical model?
2. Are fill facts and account cash-flow facts the correct source boundary?
3. Is one-pass private-event parsing with independent projections correct?
4. Are fact identity and transport provenance correctly separated so
   stream/history overlap cannot double post?
5. Should `FinancialFactId` replace the narrower planned `CashFlowId`?
6. Are Accounting and Portfolio ownership sufficiently separated?
7. Is the bounded durable side path correct without weakening order handoff?
8. Are source completeness and per-asset balance proof correctly separated?
9. Should posting precede attribution in all cases?
10. Is `UNALLOCATED` mandatory when shared-account ownership is unproven?
11. Are realized ledger facts and derived valuation separated without PnL
    double-counting?
12. Does the model remain generic for Carry, Market Making and option spreads?
13. Which finding, if any, is an **A-class ADR-013 design error** that must be
    corrected before acceptance?
