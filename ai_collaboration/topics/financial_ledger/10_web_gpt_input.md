---
id: AI-20260729-012
title: Financial Ledger and PnL Attribution Architecture Input
origin: web-gpt
status: RECEIVED
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - ../funding_arbitrage/96_web_gpt_adr012_formal_closure.md
  - ../funding_arbitrage/84_codex_adr013_current_code_audit.md
  - ../funding_arbitrage/85_codex_adr013_proposal_handoff.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - ../carry_application/20_codex_architecture_response.md
external_share: allowed
sensitivity: public-project
---

# Topic: Financial Ledger and PnL Attribution

## Background

ADR-012 is formally closed:

```text
Design                  ACCEPTED
Implementation          ACCEPTED
Remediation             CLOSED
Grouped external        BLOCKED
Testnet / Production    NOT AUTHORIZED
```

The committee selected ADR-013 Financial Ledger and PnL Attribution as the
next architecture gate. ADR-014 Carry Application formal review follows
ADR-013 scope alignment.

This topic is a design request. It does not authorize Accounting source code,
Funding Arbitrage, grouped external execution, Testnet or production.

## Architecture Problem

The platform currently knows:

- current OMS order state;
- current venue-reported balances and positions;
- market Funding rate and next settlement time;
- recorded market and execution events.

It does not yet possess authoritative, immutable financial history that can
answer:

- which fill created each asset movement;
- which commission asset and amount were charged;
- whether an actual Funding settlement occurred;
- why a balance changed;
- whether stream and history facts are complete;
- how ledger balances reconcile with the venue;
- which application owns a financial component;
- how realized and marked PnL avoid double counting.

## Committee Requirements

Funding Carry PnL must account for:

```text
trading/settlement PnL
signed Funding settlement
commissions and rebates
borrow interest
other explicit costs
unrealized mark/basis change
```

Expected Funding rate, expected APR and expected slippage remain Features.
Actual Funding and fees require authenticated financial evidence.

## Required ADR-013 Scope

1. canonical fill-level and account cash-flow facts;
2. economic identity distinct from transport observation identity;
3. stream/history convergence without double posting;
4. balanced immutable per-asset ledger;
5. durable bounded ingestion outside the synchronous order-submit path;
6. correction by reversal rather than mutation;
7. source-completeness and balance reconciliation as separate proofs;
8. generic allocation, including explicit `UNALLOCATED`;
9. valuation and PnL attribution without mixing cash facts and marks;
10. Accounting health integration that blocks new exposure but preserves
    query, cancel, reduce and recovery.

## ADR-014 Scope Alignment Question

Accounting must accept economic ownership evidence from Carry without
importing `applications.carry`.

The design must define a generic, versioned `EconomicOwnerRef` boundary.
Carry's future `ApplicationPositionId` may be represented through that
boundary, but Accounting must not understand Carry lifecycle, Funding
objectives or hedge state.

## Required Review Questions

1. Is per-asset double entry the correct canonical ledger invariant?
2. Are `ExecutionFillFact` and `AccountCashFlowFact` the right source union?
3. How should one private message feed OMS, Portfolio and Accounting without
   multiple inconsistent parses?
4. Which exact business keys prevent stream/history double posting?
5. How does the durable side path fail closed without joining the submit
   critical section?
6. What constitutes source completeness versus balance proof?
7. How should shared-account Funding remain `UNALLOCATED` until ownership is
   proven?
8. How should `EconomicOwnerRef` avoid an Accounting-to-Carry dependency?
9. Which PnL components are ledger facts, derived valuation or analytical
   decomposition?
10. Is slippage an explanatory execution-quality component rather than an
    additional cash expense?
11. Which contracts must be frozen before implementation task IDs are
    assigned?

## Frozen Constraints

- Do not reopen ADR-009 through ADR-012.
- Do not implement Funding-specific mapping in the generic ledger.
- Do not infer actual Funding from `FundingRateUpdate`.
- Do not reconstruct individual fills from cumulative OMS quantity and
  average price.
- Do not let applications write ledger transactions.
- Do not treat missing financial evidence as zero.
- Do not authorize external grouped execution, Testnet or production.

## Requested Output

Codex should provide:

- a current-code audit;
- package topology and dependency rules;
- source-fact, ledger, reconciliation, allocation and PnL boundaries;
- proposed immutable public ports;
- ADR-014 ownership alignment;
- explicit implementation and external-authorization gates;
- a Web GPT review-ready architecture response.
