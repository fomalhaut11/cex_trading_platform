# Order Group Execution-Control Schema

Status: Implemented offline under accepted ADR-011 on 2026-07-28.

## Boundary

The Order Group schema converts an admitted immutable Basket target into
durable execution-control facts. It is generic N-leg infrastructure, not a
Funding Arbitrage strategy and not a Portfolio Risk model.

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> OrderGroupId + ExecutionPlanRef
  -> ExecutionAction
  -> ExecutionActionPermit
  -> Child Order Attempt
  -> existing OrderRequest
```

`OrderGroupAdmission` permits group creation only.
`ExecutionActionPermit` is finite evidence for one exact action at one group
revision; it is not general order permission. Real permit issuance belongs to
ADR-012 and is not implemented.

## Public Contracts

`cex_quant.oms` exports:

- `OrderGroupAdmission`, `ExecutionPlanRef`, `ExecutionAction` and
  `ExecutionActionPermit`;
- `OrderGroupView`, `OrderGroupLegView` and `ExecutionActionView`;
- `OrderGroupStatus`, `ExecutionActionState` and
  `OrderGroupCloseOutcome`;
- `OrderGroupLimits`, deterministic identity/checksum helpers and bounded
  canonical codecs;
- `OrderGroupStateMachine` and typed state/identity/authorization/capacity
  failures;
- mixed-version group journal facts.

`cex_quant.runtime` exports:

- `OrderGroupRuntime` for caller-driven durable orchestration;
- `DurableExecutionHandoff` for shared single-order submission safety;
- `GroupedExecutionBlockedError`, which is the mandatory pre-ADR-012
  external-execution boundary.

## Identities and Binding

```text
DecisionSnapshotId
  -> Basket IntentId
  -> PortfolioApprovalId
  -> OrderGroupId
  -> BasketLegId
  -> GroupActionId
  -> ExecutionPermitId
  -> ClientOrderId
  -> VenueOrderId
```

Rules:

- one Basket `IntentId` owns at most one Order Group;
- one `ExecutionPermitId` can bind only one exact action;
- action checksum, group ID, revision, leg, plan and expiry must match before
  child creation;
- one action owns one deterministic venue-safe child `ClientOrderId`;
- changed price, quantity, maker/taker choice or other content requires a new
  action and child identity;
- a definitely-not-sent technical retransmission reuses the same action,
  child and `ClientOrderId`, and V1 permits at most one.

## Group Control

```text
CREATED -> ACTIVE <-> SUSPENDED
              |
              v
       RECOVERY_REQUIRED

ACTIVE/SUSPENDED/RECOVERY_REQUIRED -> CLOSING -> CLOSED
```

Child order lifecycle remains in the existing `OrderStateMachine`.
`UNKNOWN` forces `RECOVERY_REQUIRED` and cannot be blindly retransmitted.
`TARGET_CONFIRMED` closure requires explicit external Portfolio/Risk evidence
and no unresolved child.

OMS does not expose `HEDGED` or `PARTIALLY_HEDGED`. It exposes exact signed
cumulative fills, signed working quantity and unresolved action IDs per
Basket leg. ADR-012 will interpret those facts economically.

## Bounds and Persistence

Hard limits:

- 16 Basket legs, inherited from ADR-010;
- 8 child attempts per leg;
- 64 children per group;
- 1 technical retransmission per action;
- 1 unresolved exposure-changing action per group;
- 4096 retained groups in the default bounded runtime.

Deployment limits may be lower but never higher.

The OMS JSONL journal accepts immutable legacy V1 single-order records and V2
submit-outcome/group records in one contiguous checksummed sequence.
Historical records are never rewritten. Group admission, plan, action,
permit, child mapping and control changes replay deterministically.

## External-Execution Gate

Offline tests may construct synthetic permits and durably prepare child
attempts. `OrderGroupRuntime.submit_prepared_child` always raises before any
Execution adapter can be called. ADR-012 acceptance is required before this
boundary may be replaced with real Portfolio Risk authorization and routing.
