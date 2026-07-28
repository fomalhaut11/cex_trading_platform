---
id: AI-20260728-001
title: Web GPT Review of ADR-009
origin: web-gpt
status: REVIEWED
created: 2026-07-28
code_baseline: f1ec204cbbb56ebeba5fc4c597b457086ea35c81
supersedes: none
related:
  - ../../../adr/ADR-009-portfolio-decision-snapshot.md
  - 90_resolution.md
external_share: allowed
sensitivity: public-project
---

# Web GPT Review - Funding Arbitrage Architecture

## Review Target

ADR-009 Portfolio Decision Snapshot Model

## Review Result

Web GPT accepts ADR-009 as the correct first architectural decision for
Funding Arbitrage support.

The purpose of ADR-009 is not only data aggregation, but establishing
deterministic decision input.

Approved conceptual flow:

Source Observations

↓

Portfolio Decision Snapshot

↓

Application Decision

↓

Intent

↓

Risk

↓

OMS

## Key Review Points

### 1. Snapshot is Decision Infrastructure

The snapshot should not be considered a strategy-specific object.

It should become a general decision infrastructure layer.

Future applications:

-   Carry arbitrage
-   Market making
-   Cross exchange arbitrage
-   Portfolio rebalancing

### 2. Event Bus Direction

Current synchronous deterministic architecture is acceptable.

A generic Event Bus should not replace Decision Snapshot.

Reason:

Event distribution does not guarantee:

-   temporal coherence
-   freshness policy
-   ownership boundaries

The system should prioritize:

coherent state \> asynchronous notification

### 3. ADR-009 Acceptance

Accepted design principles:

-   immutable snapshot
-   explicit readiness
-   fail closed
-   source ownership preserved
-   event time / arrival time / monotonic time separation

## Remaining Architecture Gaps For Funding Arbitrage

ADR-009 solves decision consistency.

The following capabilities are still required before implementation.

## ADR-010 Basket Intent Model

Problem:

Funding arbitrage is a portfolio objective.

Example:

OPEN BTC CARRY

contains:

-   BUY Spot BTC
-   SELL BTC Perpetual

The system should avoid representing this as two independent intents.

## ADR-011 Parent Child OMS

Problem:

Multi-leg execution requires lifecycle management.

Required states:

-   CREATED
-   EXECUTING
-   PARTIALLY_HEDGED
-   HEDGED
-   ACTIVE
-   CLOSED

## ADR-012 Portfolio Risk Extension

Risk engine requires portfolio-level checks:

-   net delta
-   basis risk
-   margin utilization
-   liquidation distance
-   legging risk

## ADR-013 Financial Ledger

Need attribution of:

Total PnL

=

Funding income

-   Basis PnL

-   Trading fees

-   Execution cost

## Questions For Codex

1.  Does ADR-009 require any modification after reviewing current
    implementation?

2.  Where should Snapshot infrastructure live?

Possible:

-   src/cex_quant/snapshots/
-   another architecture layer

3.  Should ADR-010\~013 be created before any Funding Arbitrage code?

4.  Are there existing abstractions that already partially solve these
    problems?

5.  Provide recommended ADR order and implementation dependency graph.

## Constraint

Do not implement funding arbitrage code yet.

Only perform architecture validation and planning.
