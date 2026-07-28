# Codex Handoff: ADR-011 Proposed

Date: 2026-07-28

Status: Proposed for Web GPT and project-owner review

Implementation authorization: None

## Review Package

This package is self-contained for reviewers who cannot inspect the local
repository:

1. `60_web_gpt_adr011_review.md` records the review request and constraints.
2. `61_codex_adr011_current_code_audit.md` describes the reusable code,
   concrete gaps and compatibility requirements found by Codex.
3. `../../../adr/ADR-011-parent-order-group-multi-leg-execution.md` is the
   proposed architecture decision.

The repository baseline reviewed by Codex is commit
`157ee6b4ba7446396ed36d07a55c5727dec6cd5a`.

## Short Conclusion

The existing code already has a strong single-order kernel:

- immutable `OrderRequest`;
- canonical child-order state machine;
- durable JSONL journal and replay;
- normalized private-stream and REST reconciliation;
- typed distinction between definitely-not-sent transport failures and
  possibly-sent unknown outcomes;
- operator halt and reduce-only controls.

ADR-011 therefore proposes an additive Parent Order Group control plane. It
does not replace `OrderRequest`, child state machines, Execution adapters or
venue reconciliation.

The most important current-code finding is that the concrete single-leg
`TradingApplication` does not yet persist `SUBMITTING` before the external
submit or immediately return the synchronous submit result to OMS. Isolated
OMS APIs support this, but the production composition does not use them.
ADR-011 requires one shared durable handoff for both single-leg and grouped
orders so that the new Basket path is not safer than the legacy path.

## Proposed Ownership Boundary

```text
Strategy
  owns the immutable Basket economic target

Portfolio Risk
  owns group admission and one finite permit per exposure-changing action

Execution policy
  proposes order sequence, type, price and quantity; it grants no authority

OMS Parent Order Group
  owns durable group control, child mapping, child execution facts and recovery

Execution adapter
  submits, cancels and queries one canonical child order

Portfolio
  owns actual balances and positions

Risk / Carry application
  interprets Delta, basis, margin and economic hedging
```

Consequently:

```text
Basket ALLOW
  != permission to submit all legs

Child proposal
  != execution permission

Fresh exact action permit
  + matching group revision
  + durable submit intent
  = eligibility for one external child submit
```

## Proposed Identity Chain

```text
DecisionSnapshotId
  -> IntentId
  -> PortfolioApprovalId
  -> OrderGroupId
  -> BasketLegId
  -> GroupActionId
  -> ExecutionPermitId
  -> ClientOrderId
  -> VenueOrderId
```

One Basket leg may produce zero, one or multiple child-order attempts.
Unknown outcomes prohibit blind replacement until venue reconciliation
resolves the original identity.

## Proposed Group Control State

```text
CREATED -> ACTIVE <-> SUSPENDED
              |
              v
       RECOVERY_REQUIRED

ACTIVE/SUSPENDED -> CLOSING -> CLOSED
```

`PARTIALLY_FILLED` remains a child-order fact. `HEDGED` remains a Portfolio
Risk or Carry economic assessment. `UNKNOWN` is an action/child condition that
forces the group into `RECOVERY_REQUIRED`; it must not be hidden as terminal
failure.

## Proposed Restart Rule

Restart remains fail-closed:

```text
HALTED
  -> replay one ordered journal
  -> rebuild group/child/action identities
  -> buffer private-stream facts
  -> query every persisted external-action intent and unknown child
  -> merge normalized venue facts
  -> refresh actual Portfolio state
  -> obtain fresh Risk assessment
  -> require explicit operator resume
```

No stale Basket admission or action permit survives restart as permission to
create new exposure.

## Decisions Requested from Reviewers

1. Accept V1's maximum of one new in-flight submit per group, or define a
   bounded parallel action-batch permit now?
2. Require a new explicit action after every definitely-not-sent failure, or
   allow a bounded automatic retry using the same `ClientOrderId`?
3. Require both fresh Risk assessment and explicit operator resume after
   `RECOVERY_REQUIRED`?
4. Require fresh Portfolio/Risk target confirmation before closing a group as
   `TARGET_CONFIRMED`?
5. After ADR-011 acceptance, may the group model, journal and durable handoff
   be implemented while all exposure-changing group submission remains
   blocked until ADR-012 accepts action-permit semantics?
6. Accept the names `PortfolioApprovalId` and `ExecutionPermitId`?
7. Accept hard bounds of 16 legs, 8 attempts per leg and 64 children per
   group?
8. Accept mixed legacy and new-version records in one ordered journal instead
   of a one-time journal rewrite?

## Explicit Non-Goals

This proposal does not:

- implement Parent/Child OMS code;
- define portfolio Delta, basis, Greeks, margin or liquidation formulas;
- define Carry position economics;
- authorize Funding Arbitrage application code;
- authorize Testnet or production order submission.
