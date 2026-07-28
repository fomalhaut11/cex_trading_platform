---
id: AI-20260728-016
title: ADR-014 Current-Code Audit
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-28
code_baseline: fa0df9e2a015db258457d226c7ed9fa5c689b8eb
supersedes: none
related:
  - ../../../adr/ADR-014-carry-application-boundary.md
  - 85_codex_adr013_proposal_handoff.md
external_share: allowed
sensitivity: public-project
---

# ADR-014 Current-Code Audit

## Audit Result

The repository's generic contracts can host a Carry application additively,
but the application domain itself does not exist.

No redesign of accepted ADR-009 through ADR-011 is needed:

- the generic Snapshot coordinator can publish a typed Carry value;
- `StrategyRuntime` can consume that publication;
- `StrategyDecision` already supports `BasketTargetIntent`;
- Basket identity supports 2-to-16 legs and exact Snapshot causation;
- OMS Order Group views expose the execution facts an application needs.

The missing work is an explicit economic application aggregate and its
read-only interaction with Platform Risk, OMS, Portfolio and Accounting.

Funding application implementation remains blocked because ADR-012 and
ADR-013 are Proposed and grouped external execution is disabled.

## Existing Reusable Boundaries

### Snapshot

ADR-009 implementation already provides:

```text
bounded latest source observations
  -> freshness/coherence assessment
  -> pure application assembler
  -> READY typed publication
```

The application needs only a small strongly typed entry/position Snapshot
union and semantic assemblers. It does not need a global Event Bus or an
untyped universal state vector with optional phase fields.

Accounting attribution remains a separate performance view. It cannot be a
mandatory source for reduce, close or recovery decisions because Accounting
failure must halt new exposure without trapping an existing position.

### Strategy

The current Strategy contract:

- is pure and synchronous;
- receives immutable Market/Feature/Snapshot input;
- can emit zero or more immutable decision intents;
- supports both the existing single-leg intent and Basket;
- validates Basket Snapshot identity and Objective policy.

Therefore:

- `StrategyDecision` does not need modification;
- `PositionTargetIntent` remains unaffected;
- Funding Carry should not create a new order-producing Strategy API.

### Basket

`BasketTargetIntent` already expresses the complete economic objective:

```text
BTC Spot absolute target +10
BTC Perpetual absolute target -10
```

It deliberately has no order type, TIF, leg ordering, retry or API payload.
The Funding application must use this generic N-leg contract even when its
first MVP has two legs.

### OMS

The accepted ADR-011 implementation exposes:

- Order Group identity/revision/control state;
- per-leg target and cumulative/working quantity;
- child/action facts;
- unknown and recovery state;
- exact Snapshot/Intent/approval causation.

OMS correctly does not expose:

- net Delta;
- basis profitability;
- Carry `HEDGED` or `ACTIVE`;
- Funding economics.

Those omissions are correct boundaries, not missing OMS features.

## Missing Application Contracts

There is no `cex_quant.applications` package and no:

- `ApplicationPositionId` or `CarryPairId`;
- Spot/perpetual economic-pair validation;
- typed Carry decision snapshot;
- Carry economic-position aggregate;
- application lifecycle and hedge assessment;
- position-ownership evidence for Accounting allocation;
- pure economic recovery proposal;
- Carry application journal and restart replay.

## Missing Platform Inputs

The application must not implement local substitutes for these gaps:

| Missing capability | Correct owner |
|---|---|
| latest normalized Funding market view | Market Data state |
| normalized margin/liquidation view | Portfolio/account state |
| effective positions with fill coverage cursor | ADR-012 Portfolio Risk input |
| whole-Basket approval/action permit | ADR-012 Risk |
| actual Funding/fee settlement | ADR-013 Accounting |
| attribution and financial reconciliation | ADR-013 Accounting |
| grouped external submission | Runtime + OMS + Execution after authorization |

The existing `FundingRateUpdate` market event is reusable, but no independent
latest Funding state owner currently publishes it as an ADR-009 source view.

## State-Ownership Finding

The previously discussed sequence:

```text
PARTIALLY_HEDGED
HEDGED
ACTIVE
CLOSED
```

mixes different dimensions.

ADR-014 proposes:

```text
Application lifecycle:
  PROPOSED / OPENING / ACTIVE / CLOSING / CLOSED /
  RECOVERY_REQUIRED / HALTED

Economic hedge assessment:
  UNKNOWN / UNHEDGED / PARTIALLY_HEDGED / HEDGED

Financial finality:
  NOT_READY / PROVISIONAL / RECONCILED
```

This preserves formal `PARTIALLY_HEDGED/HEDGED` application states without
leaking them into OMS or Portfolio Risk.

Hedge assessment uses authoritative effective positions, multipliers, fresh
marks/Greeks and accepted tolerance. OMS fills alone are not sufficient.

## Ownership Finding

Basket targets are absolute account/instrument quantities. An application
cannot assume the entire venue position belongs to it.

The Carry aggregate therefore needs immutable ownership evidence:

```text
proven baseline
  + Carry-owned target contribution
  + other admitted/reserved contributions
  = absolute Basket target
```

ADR-012 owns reservation/conflict safety. ADR-014 owns the Carry position's
economic ownership declaration. ADR-013 Accounting validates allocation and
keeps ambiguous shared-account cash flows `UNALLOCATED`.

The first exposure-changing MVP should use a dedicated/exclusive account scope
unless a complete shared-account ownership model is accepted first.

## Recovery Finding

Three authorities must remain separate:

```text
OMS:
  determine what was submitted/acknowledged/unknown

Portfolio Risk:
  suspend, cancel, reduce or flatten for safety

Carry application:
  propose the preferred economic target
```

A Carry recovery preference becomes a new Snapshot-bound Basket objective and
must pass normal Risk and OMS gates. It is never an order, permit or retry.

## Proposed Topology

```text
cex_quant.applications.carry
  model/state/journal/ownership/recovery

cex_quant.applications.carry.funding_arbitrage
  model/snapshot/features/strategy/objectives/policy

cex_quant.market_data.state.funding
  authoritative Funding market view

cex_quant.runtime
  application coordination and mandatory platform gates
```

Generic platform modules must not import Carry implementation.

## Compatibility Assessment

ADR-014 is additive:

- no change to `StrategyDecision`;
- no change to `PositionTargetIntent`;
- no Funding field in Basket;
- no `HEDGED` state in OMS;
- no application lifecycle in Portfolio Risk;
- no application-written ledger transactions;
- no multi-leg venue adapter;
- no weakening of the existing single-leg pipeline/handoff.

Future Market Making and option applications can own different aggregates
while reusing Snapshot, Basket, Risk, OMS and Accounting.

## Implementation Blockers

No Carry application code should start before:

1. ADR-012 and ADR-013 review corrections are resolved;
2. ADR-009 through ADR-014 are compatible and Accepted;
3. required Portfolio Risk and Accounting implementations pass acceptance;
4. Carry identifiers, state ownership and public read ports are frozen;
5. read-only/offline scenario tests are approved;
6. grouped external execution is separately unblocked.

Testnet and production remain independent later gates.
