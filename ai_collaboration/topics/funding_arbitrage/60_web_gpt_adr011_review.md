# Web GPT Review: ADR-011 Parent Order Group and Multi-leg Execution

Date: 2026-07-28

Source: Web GPT architecture review supplied by the project owner

## Core Warning

```text
Basket Approval != Execution Permission
```

ADR-010 answers what portfolio state the system wants to reach. A whole-Basket
Risk `ALLOW` means the economic transition is admissible. It does not mean
that any child order may be submitted without an OMS-owned execution plan and
state transition.

Example target:

```text
BTC Spot       +10
BTC Perpetual  -10
```

Possible execution fact A:

```text
Spot filled:       +10
Perpetual filled:    0
Current exposure:  +10 BTC unhedged
```

Possible execution fact B:

```text
Perpetual filled:  -10
Spot filled:        +5
Current exposure:   -5 BTC unhedged
```

ADR-011 must therefore explain how one approved economic objective remains
safe and recoverable under partial fill, rejection, timeout, disconnect,
unknown result and process restart.

## Requested ADR Name

```text
ADR-011 Parent Order Group and Multi-leg Execution Model
```

The decision is broader than ordinary single-order management.

## Required Review Questions

### 1. Identity Chain

Define and preserve:

```text
IntentId
  -> approved Basket identity
  -> OrderGroupId
  -> ChildOrderId / ClientOrderId
```

The review must determine which domain creates each identity, how it remains
stable across retry and restart, and what constitutes an identity conflict.

### 2. Execution State

Basket remains an immutable Strategy decision and owns no execution
lifecycle.

OMS should evaluate a group lifecycle such as:

```text
CREATED
APPROVED
EXECUTING
PARTIALLY_FILLED
HEDGED
COMPLETED
FAILED
UNKNOWN
RECOVERY_REQUIRED
```

These names are review input, not automatically accepted final states. Codex
must compare them with the current OMS model and separate:

- durable order/execution facts;
- derived hedge/exposure condition;
- application economic lifecycle.

### 3. Leg Execution and Exposure

OMS needs a complete, queryable group view:

```text
spot:
  target: +10
  filled: +10

perpetual:
  target: -10
  filled: -7
```

The system must be able to derive current residual or unhedged exposure
without mutating the approved Basket target.

Codex must decide which facts belong to OMS and which exposure calculation
belongs to Portfolio Risk under ADR-012.

### 4. Restart Recovery

After process restart, reconstruction should use:

```text
durable OMS journal
  + exchange order query/private-stream facts
  + canonical account/position state
  -> current Order Group view and next safe action
```

The design must fail closed when external state is unknown. It cannot blindly
resubmit a child whose prior submission may have reached the exchange.

## Requested Codex Work

Do not implement ADR-011 yet.

First inspect the current:

- OMS model and state machine;
- `OrderRequest` and approval causation;
- Execution adapter contracts;
- durable OMS journal;
- restart replay and reconciliation kernel;
- runtime OMS/execution adapters;
- operator halt and recovery boundaries.

Then produce:

1. a current-code compatibility review;
2. `ADR-011 Parent Order Group and Multi-leg Execution Model` with status
   `Proposed`;
3. explicit questions requiring Web GPT and project-owner review before
   acceptance.

## Architecture Sequence

```text
ADR-009: what the system can coherently see
ADR-010: what portfolio state the system wants
ADR-011: how an approved objective enters an uncertain market
ADR-012: whether the evolving portfolio remains safe
ADR-013: how financial outcomes are recorded and explained
ADR-014: how Carry application economics use those capabilities
```

## Current Maturity Assessment

| Capability | Status |
|---|---|
| Market Data | Implemented |
| State Model | Implemented |
| Decision Snapshot | ADR-009 complete |
| Decision Intent | ADR-010 complete |
| Execution Group | Pending ADR-011 |
| Portfolio Risk | Pending ADR-012 |
| PnL Attribution | Pending ADR-013 |
| Funding Arbitrage | Final application layer |

The next critical question is not Funding strategy logic. It is how a
portfolio decision safely enters a real market while preserving identity,
durability, exposure evidence and recovery.
