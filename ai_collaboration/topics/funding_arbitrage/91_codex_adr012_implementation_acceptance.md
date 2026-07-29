---
id: AI-20260729-002
title: ADR-012 Implementation Acceptance Handoff
status: READY_FOR_REVIEW
date: 2026-07-29
code_baseline: 69297d52e764822a1bdd60a23a9b7fca8446a520
references:
  - 89_codex_adr012_acceptance_resolution.md
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
---

# Codex Handoff: ADR-012 Offline Implementation Acceptance

## Result

T032, T033, T034, T035 and A015 are locally complete at:

`69297d52e764822a1bdd60a23a9b7fca8446a520`

This is offline implementation evidence. Grouped external submission remains
hard-blocked and no Testnet or production authority is claimed.

## T032: Execution-Consistent Portfolio Inputs

Implemented:

- `ExecutionCoverage`;
- `ReconciledAccountBaseline`;
- `ExecutionPositionEffect` and complete journal-range batches;
- single-writer `ExecutionConsistentPositionState`;
- baseline plus post-watermark overlay;
- cumulative-fill increment validation;
- exact batch redelivery;
- coverage-gap, identity-conflict and divergence fail-closed states;
- normalized collateral, margin-scope and liquidation-reference contracts.

The baseline explicitly states the inclusive OMS journal watermark it covers.
Only later fill increments are overlaid, so a fill already included in the
account snapshot is not counted twice.

## T033: Pure N-leg Portfolio Risk

`PortfolioRiskEngine` is stateless and deterministic. It consumes immutable
ADR-009 publications and:

- preserves unrelated portfolio positions;
- replaces all Basket leg targets as one economic decision;
- aggregates unlike instruments only through configured Risk factors;
- consumes externally supplied, exact, unit-labelled option
  Delta/Gamma/Vega;
- models Spot, linear/inverse derivatives and options;
- fails closed for Quanto or unregistered models;
- projects current, target and conservative working-order exposure;
- checks exact gross notional, factor, Greek, spread, margin and liquidation
  limits;
- returns one binary whole-Basket ALLOW/REJECT result;
- binds each action permit to exact group, revision, action checksum, current
  Risk snapshot, policy and expiry.

There is no Funding, Carry, two-leg or strategy-name branch.

## T034: Durable Authority and Recovery

`PortfolioRiskCoordinator` and its checksummed JSONL journal own:

- fsync-before-publication approval reservations;
- exact idempotency and identity conflict detection;
- scope and margin-capacity serialization;
- ACTIVE, ATTACHED_TO_GROUP, RELEASED, EXPIRED and RECOVERY_REQUIRED states;
- per-permit issuance authorization generation;
- invalidation on any caller-declared material fact change;
- durable one-time pre-I/O permit consumption;
- restart invalidation of every unconsumed pre-restart permit;
- semantic Risk directives that call neither OMS nor Execution;
- typed group recovery authorization;
- typed Portfolio target confirmation.

Recovery authorization requires reconciled Portfolio inputs, a reconstructable
attached reservation and no unresolved UNKNOWN child. Target confirmation
requires a closing group, resolved children and effective positions equal to
the full Basket target.

## T035: Shared Runtime Boundary

`PortfolioRiskExecutionGuard` composes:

```text
durable SUBMITTING
  -> platform/operator immediate guard
  -> exact current Risk generation/action/group check
  -> durable permit consumption
  -> future external I/O boundary
```

The guard is additive. `OrderGroupRuntime.submit_prepared_child()` still
raises `GroupedExecutionBlockedError`, with explicit Testnet authorization
named as the next possible promotion gate.

## A015 Evidence

The offline suite covers:

- exact baseline/overlay and no double count;
- cumulative partial fills, exact replay, missing coverage and divergence;
- BTC Spot `+10` plus BTC Perpetual `-10` whole-Basket admission;
- residual `+10 BTC` after the Spot leg and a Delta-neutral next action;
- exact permit binding and group revision changes;
- working-order and configured basis/spread rejection;
- two option legs plus one Delta hedge through the generic N-leg loop;
- configured Delta/Gamma/Vega units and limits;
- normalized margin and liquidation readiness;
- serialized reservations and exact redelivery;
- journal corruption/append failure;
- material-change and restart permit invalidation;
- typed recovery/target confirmation;
- external grouped execution still unreachable.

Local verification:

- 462 tests passed;
- 39 isolated acceptance tests passed;
- 141 subtests passed;
- strict MyPy passed for 100 source files;
- Ruff passed for `src`, `tests` and `tools`;
- compileall and the high-confidence secret scan passed;
- branch coverage is 85.12%, above the 85% gate.
- documentation head `1a86b84cee50cbe9c57dcb719bdb66aec31ee008`
  passed all remote CI jobs in GitHub Actions run `30431970845`.

## Review Request

Review without reopening ADR-011:

1. Does T032 prevent baseline/fill double counting and fail closed on missing
   execution coverage?
2. Does T033 keep Risk generic across Funding, Market Making and Option
   Spreads?
3. Does T034 keep OMS, Risk, Portfolio and application ownership separate?
4. Does T035 provide the correct future handoff abstraction while leaving
   external grouped execution closed?
5. Are any findings:
   - A. ADR-012 implementation errors;
   - B. ADR-013/ADR-014 concerns;
   - C. long-term optimizations?
