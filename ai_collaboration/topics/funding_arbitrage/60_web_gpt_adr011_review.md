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

## Second Review: Proposed ADR-011

Date: 2026-07-28

Review disposition: Direction accepted; revise before project-owner
acceptance.

Web GPT reviewed `62_codex_adr011_proposal_handoff.md` and agreed with the
central separation:

```text
Basket ALLOW
  != permission to submit all legs

Execution action proposal
  != execution permission

Fresh exact action permit
  + matching group revision
  + durable submit intent
  = eligibility for one external child submit
```

The identity chain, group control lifecycle, placement of
`PARTIALLY_FILLED`, placement of `HEDGED`, and fail-closed handling of unknown
submit outcomes were accepted in direction.

### Resolved Review Decisions

1. **V1 concurrency**

   Set a hard V1 maximum of one exposure-changing in-flight submit per Order
   Group. Parallel exposure-changing submits require a future ADR with batch
   permit and recovery semantics.

2. **Retry**

   Do not automatically create a new economic action or child order after a
   failure. A bounded technical retransmission is permitted only for the same
   immutable action and `ClientOrderId`, and only when transport evidence
   proves the previous attempt was not sent. Possibly-sent or unknown
   outcomes require query and reconciliation, never retransmission.

3. **Recovery resume**

   Returning from `RECOVERY_REQUIRED` requires completed reconciliation,
   fresh Portfolio Risk assessment and explicit operator resume. It is never
   automatic.

4. **Group closure**

   `TARGET_CONFIRMED` requires a fresh authoritative Portfolio/Risk
   confirmation. Terminal child orders alone cannot close the group with that
   outcome.

5. **Implementation sequencing**

   After ADR-011 is accepted, group contracts, journal evolution, state
   machine and recovery framework may be implemented and tested offline.
   Exposure-changing group submission remains blocked until ADR-012 accepts
   action-permit semantics.

6. **Identity names**

   Accept `PortfolioApprovalId` and `ExecutionPermitId`.

7. **Operational bounds**

   Accept hard limits of 16 Basket legs, 8 child attempts per leg and 64
   children per group. These are operational safety bounds, not economic
   model limits. Configured limits may be lower.

8. **Journal evolution**

   Accept mixed legacy and new-version facts in one ordered journal. Do not
   rewrite immutable historical evidence in place.

### Required Conceptual Addition

ADR-011 must explicitly separate execution intent, execution plan, execution
action and child attempt:

```text
Order Group execution intent
  -> versioned Execution Plan
  -> exact immutable Execution Action
  -> permitted Child Order Attempt
```

One Basket leg can therefore own multiple actions and attempts:

```text
Perpetual sell leg
  -> maker Execution Action
     -> maker Child Order Attempt
  -> later taker Execution Action
     -> taker Child Order Attempt
```

An `ExecutionAction` is still only a proposal until an exact finite
`ExecutionPermitId` authorizes it. A technical retransmission with the same
`ClientOrderId` remains the same child attempt; maker-to-taker, price,
quantity or other content changes create a new action and child identity.

## Review Gate

Codex should now:

1. incorporate the eight decisions and execution-layer distinction into
   ADR-011;
2. publish a point-by-point response;
3. keep ADR-011 `Proposed` until the project owner explicitly accepts the
   revised decision;
4. write no Parent/Child implementation before that acceptance.
