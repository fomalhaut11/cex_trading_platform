# Codex Response: ADR-011 Second Review

Date: 2026-07-28

Status: Accepted after incorporation of the conditional review

Implementation authorization: T029/T030/T031/A014 offline scope only

Reviewed repository baseline:
`c6a998102f744dfe51e430ee46cf9889e0aa21df`

## Conclusion

Codex accepts all eight Web GPT decisions and the requested distinction
between execution intent, plan, action and child attempt.

The project owner supplied this conditional review to Codex with an
instruction to read and act. Because the review explicitly directs promotion
after the requested revision, ADR-011 moved to `Accepted` only after all
eight decisions and the execution-layer distinction were incorporated. No
Parent/Child OMS, Portfolio Risk or exchange-submission code was written
before acceptance.

## Point-by-Point Disposition

| Review item | Codex disposition | Incorporated rule |
|---|---|---|
| One in-flight action | Accept | V1 hard maximum is one exposure-changing in-flight submit per group |
| Retry identity | Accept with precise transport boundary | No automatic new economic action; at most one definitely-not-sent technical retransmission uses the same action, child and `ClientOrderId` |
| Recovery resume | Accept | Reconciliation, fresh Portfolio Risk and explicit operator resume are all mandatory |
| Group closure | Accept | `TARGET_CONFIRMED` requires fresh authoritative Portfolio/Risk confirmation |
| Implementation sequencing | Accept | After ADR acceptance, offline group/state/journal/recovery may proceed; exposure-changing group submit waits for ADR-012 |
| Identity names | Accept | `PortfolioApprovalId` and `ExecutionPermitId` are fixed in the proposal |
| Bounds | Accept | Hard 16 legs, 8 child attempts per leg, 64 children per group; configured limits may be lower |
| Journal versions | Accept | One ordered mixed-version journal; no in-place rewrite of historical evidence |

## Execution-Layer Clarification

The revised ADR now defines:

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> Order Group execution intent
  -> ExecutionPlanRef
  -> ExecutionAction
  -> ExecutionActionPermit
  -> Child Order Attempt
  -> existing ExecutionGateway
```

### Execution intent

The Order Group's durable intention to move toward the admitted Basket target
under one immutable plan. It is not an order and grants no exchange authority.

### Execution plan

A registered versioned policy reference plus bounded immutable parameters.
The group journal stores data and checksums, never callbacks or import paths.

### Execution action

One exact proposed attempt for one Basket leg at one group revision. It has a
stable `GroupActionId`, but it cannot reach Execution without a matching
finite permit.

### Child order attempt

One canonical `OrderRequest` and existing `OrderStateMachine`, created only
after the action and permit have been validated and durably recorded.

The cardinality is:

```text
one Basket leg
  -> zero to eight ExecutionActions
      -> exactly one Child Order Attempt per action
```

A maker action followed by a taker action therefore creates two action and
child identities under the same Basket leg.

## Retry Clarification

The distinction between an economic retry and a transport retransmission is
now explicit:

```text
price / quantity / maker-taker / other content changes
  -> new ExecutionAction
  -> new Child Order Attempt
  -> new ClientOrderId

transport proves request was not sent
  -> same prepared ExecutionAction
  -> same Child Order Attempt
  -> same ClientOrderId
  -> at most one V1 technical retransmission

request possibly sent or outcome unknown
  -> no retransmission
  -> RECOVERY_REQUIRED
  -> query and reconcile
```

The permit is consumed by and latched to one action. It can never authorize
another action. Its persisted causation may cover the one bounded
same-identity technical retransmission only while the permit and group
deadlines remain fresh and no intervening fact invalidates retry eligibility.

## Group and Portfolio Boundary

The revised ADR keeps three state dimensions separate:

| Dimension | Owner | Examples |
|---|---|---|
| Group execution control | OMS | `ACTIVE`, `SUSPENDED`, `RECOVERY_REQUIRED`, `CLOSING`, `CLOSED` |
| Child/action facts | OMS child kernel | `PARTIALLY_FILLED`, acknowledged, retry-eligible, unknown |
| Portfolio/economic assessment | Portfolio Risk / Carry | residual Delta, basis, margin, `PARTIALLY_HEDGED`, `HEDGED` |

`CLOSED(TARGET_CONFIRMED)` is legal only after every external action is
resolved, no working venue child remains, and fresh Portfolio/Risk evidence
confirms the target state.

## Implementation Gate

If the project owner explicitly accepts the revised ADR, the next planning
step may assign task and acceptance IDs for:

- identifiers and immutable group/action contracts;
- group state machine and bounded views;
- mixed-version OMS journal facts and replay;
- shared durable-before-external-I/O handoff for single and grouped orders;
- restart/reconciliation framework;
- deterministic offline tests using synthetic permits.

The following remain prohibited until ADR-012 is accepted:

- issuance of real Portfolio Risk action permits;
- exposure-changing group submission to any Execution adapter;
- Funding Arbitrage application execution;
- Testnet or production multi-leg trading.

## Acceptance Outcome

ADR-011 is accepted with the following authorized offline work:

```text
T029  immutable group/plan/action/permit contracts and identifiers
T030  bounded group state, mixed-version journal, replay and recovery
T031  shared durable handoff and fail-closed group runtime boundary
A014  deterministic offline ADR-011 acceptance
```

T031 must explicitly prevent exposure-changing Order Group requests from
reaching an Execution adapter until ADR-012 is accepted. Funding Arbitrage,
Testnet and production multi-leg execution remain unauthorized.
