---
id: AI-20260728-003
title: ADR-010 Current-Code Compatibility Review
origin: codex
status: REVIEWED
created: 2026-07-28
code_baseline: 617f4dea38fd5669c067ebeb0c50482c12cf418d
supersedes: none
related:
  - ../../../adr/ADR-010-basket-intent-architecture.md
  - ../../../src/cex_quant/core/identifiers.py
  - ../../../src/cex_quant/strategy/model.py
  - ../../../src/cex_quant/strategy/runtime.py
  - ../../../src/cex_quant/runtime/pipeline.py
external_share: allowed
sensitivity: public-project
---

# ADR-010 Current-Code Compatibility Review

## Verdict

ADR-010 required revision before acceptance. The revised ADR is compatible
with the current code and has been accepted under the project owner's
conditional instruction.

This review authorizes generic Basket contracts and Strategy compatibility
only. It does not authorize OMS Order Groups, Portfolio Risk, Funding
Arbitrage or any exchange execution.

## Evidence Inspected

Codex inspected the current implementation rather than relying only on the
planning document:

- `cex_quant.core.identifiers`;
- `cex_quant.strategy.model`;
- `cex_quant.strategy.runtime`;
- `cex_quant.runtime.pipeline`;
- `cex_quant.oms.model`;
- ADR-009 Snapshot contracts and coordinator;
- current Strategy and order interface documentation.

## 1. Intent Model Compatibility

### Current fact

`PositionTargetIntent` already has:

```text
intent_id: IntentId
strategy_id: StrategyId
instrument_id: InstrumentId
target_quantity: Quantity
decision_time_ns
valid_until_ns
```

It is an immutable target, not an order.

### Revision

`BasketTargetIntent` now follows the same target semantics:

- reuse `IntentId`;
- preserve `strategy_id`, target quantities and explicit decision time;
- require Snapshot causation and finite expiry;
- add bounded ordered legs;
- contain no order type, price, time-in-force or execution sequencing.

The earlier proposed `BasketIntentId` was removed. It duplicated the existing
cross-domain `IntentId` and complicated union validation without adding
semantic safety.

## 2. Core Identifier Compatibility

### Current fact

`core.identifiers` uses lightweight `NewType` identities shared across domain
boundaries, including `IntentId`, `AccountId`, `ClientOrderId` and
`StrategyId`.

### Revision

ADR-010 adds only identities that do not already exist:

```text
BasketLegId
ObjectiveTypeId
```

`IntentId` remains the identity of both single-leg and Basket intents.

## 3. StrategyDecision and StrategyRuntime

### Current fact

`StrategyDecision` already declares:

```python
intents: tuple[DecisionIntent, ...]
```

Its dataclass shape does not need to change. Today, however:

- `DecisionIntent` aliases only `PositionTargetIntent`;
- `StrategyRuntime._validate_intents` rejects every other type;
- duplicate detection uses `set[IntentId]`;
- `StrategyInput` accepts only canonical market events and
  `FeatureSnapshot`;
- `TradingPipeline` is structurally single-leg.

### Revision

Implementation must:

1. extend `DecisionIntent` with `BasketTargetIntent`;
2. keep the `StrategyDecision` dataclass unchanged;
3. extend runtime validation with an explicit Basket branch;
4. preserve duplicate detection through the common `IntentId`;
5. accept ADR-009 `DecisionSnapshotPublication` additively;
6. validate that Basket `decision_snapshot_id` matches the delivered input;
7. make the current single-leg pipeline reject Basket output before its
   single-leg Portfolio/Risk ports.

It must not iterate Basket legs as independent intents.

## 4. Objective Type Long-Term Evolution

The original raw `str objective_type` plus allow-list was insufficient:

- one central enum would block application-owned evolution;
- raw strings could be silently reinterpreted;
- `policy_version` is not an objective schema version.

ADR-010 now uses:

```text
ObjectiveTypeId + positive version = ObjectiveTypeRef
```

Definitions are metadata-only and registered at composition. Historical
references are immutable; changed semantics require a new version or ID.
Registry entries cannot contain callbacks or import paths.

## 5. Basket Lifecycle Boundary

`BasketTargetIntent` has no mutable lifecycle. It is a decision value that is
valid or expired when evaluated.

Lifecycle ownership:

| Concern | Owner |
|---|---|
| Strategy CREATED/RUNNING/STOPPED/FAILED | Existing Strategy Runtime |
| Basket Risk ALLOW/REJECT | ADR-012 / Risk |
| Parent/Child execution status | ADR-011 / OMS |
| PARTIALLY_HEDGED/HEDGED/ACTIVE/CLOSED | ADR-014 / Carry application |

This prevents ADR-010 from pre-empting the ADR-011 state machine.

## 6. Leg Ordering

The original rule sorted by `BasketLegId`. That creates an unnecessary
dependency because leg IDs may be derived from leg scope.

The revised canonical key is:

```text
account_id
instrument venue
instrument kind
instrument symbol
```

The public immutable contract rejects non-canonical ordering. A named
construction helper may sort candidates before construction. Execution order
is not inferred from tuple order; it belongs to ADR-011.

## 7. Accepted Scope

The project owner's instruction was:

```text
inspect current code
revise the four named compatibility areas
then accept ADR-010
```

Those conditions are satisfied. ADR-010 is Accepted with:

- explicit AccountId per leg;
- V1 hard cap of 16;
- mandatory finite expiry;
- canonical account/instrument ordering;
- versioned Objective Type references;
- binary whole-Basket Risk result;
- common IntentId;
- no Basket lifecycle.

## 8. Required Implementation

Assigned work:

```text
T027 Basket IDs, Objective Type registry, contracts and policy
T028 Strategy input/output compatibility and single-leg rejection
A013 Offline contract, replay, two-leg and three-leg acceptance
```

No implementation may create child orders or exchange requests.

## 9. Non-Claims

This review does not:

- define Parent/Child OMS states;
- implement portfolio-level Risk;
- define execution sequencing or compensation;
- implement Financial Ledger;
- implement Carry/Funding strategy;
- authorize Testnet or production trading.
