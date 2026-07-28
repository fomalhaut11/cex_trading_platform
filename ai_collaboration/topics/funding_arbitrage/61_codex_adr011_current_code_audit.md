# Codex ADR-011 Current-Code Compatibility Audit

Date: 2026-07-28

Baseline commit inspected:
`157ee6b4ba7446396ed36d07a55c5727dec6cd5a`

Status: Design evidence only; no ADR-011 implementation is authorized

## Conclusion

The current platform contains a strong reusable single-order kernel, but it
does not yet contain a safe Parent Order Group runtime.

ADR-011 must not create an unrelated second OMS. It should compose and extend
the existing:

- `OrderRequest`;
- `OrderStateMachine`;
- checksummed OMS journal;
- REST/user-stream reconciliation;
- typed execution unknown-state errors;
- stream-first startup recovery;
- operator halt and reduce-only authority.

The audit also found one existing live-composition gap that ADR-011 must close
for both single-leg and grouped execution:

```text
current TradingApplication:
  OMS.create_order
  -> Execution.submit

missing mandatory handoff:
  OMS.persist submit intent / mark SUBMITTING
  -> only then call Execution
  -> record immediate outcome back into OMS
```

Without that handoff, a crash after an exchange request was sent but before a
private-stream update can leave only `CREATED` in the journal.
`reconciliation_candidates()` currently excludes `CREATED`, so restart may
not query the possibly-live venue order. Existing isolated recovery tests call
`mark_submitting` explicitly, but the concrete `TradingApplication`
composition does not.

This is not a reason to modify code before ADR acceptance. It is a required
compatibility decision for ADR-011.

## 1. Existing Reusable Capabilities

### 1.1 Single-order contract

`cex_quant.oms.model` already provides:

- `ApprovedOrderIntent`;
- immutable `OrderRequest`;
- stable `ClientOrderId`;
- `IntentId` and approval causation;
- account and canonical Instrument scope;
- exact fixed-point quantity and price;
- Spot, Perpetual, Future and Option-compatible canonical fields;
- order type, TIF, post-only, reduce-only and position-side validation.

Execution adapters consume one `OrderRequest`. That remains the correct child
order boundary for a Parent Order Group.

### 1.2 Child order state

`OrderStateMachine` already owns one order with:

```text
CREATED
SUBMITTING
OPEN
PARTIALLY_FILLED
CANCEL_PENDING
FILLED / CANCELED / EXPIRED / REJECTED / FAILED
```

It validates:

- one writer;
- legal transitions;
- stable client identity;
- idempotent venue updates;
- monotonic cumulative fill;
- full quantity for `FILLED`;
- cancellation/fill races.

ADR-011 should reuse this state machine for every child. It should not copy
these states into a second child-order implementation.

### 1.3 Durable journal

`JsonLinesOmsJournal` already supplies:

- contiguous global sequence;
- canonical JSON;
- SHA-256 checksum;
- record size limit;
- flush and optional `fsync`;
- strict truncation, version and sequence validation;
- deterministic restart replay.

Current entry types are:

```text
OrderCreatedEntry
OrderSubmittingEntry
CancelRequestedEntry
VenueEventEntry
```

The journal has no group identity, group revision, Basket leg mapping,
action permit, submit outcome or group control event. ADR-011 needs an
additive, backward-readable journal evolution rather than a separate
non-atomic group journal.

### 1.4 Unknown-state and reconciliation

The Binance adapter already distinguishes:

- definitely not sent: `ExecutionTransportError`;
- possibly sent: `ExecutionStateUnknownError`;
- read-only query failure: `ExecutionQueryError`.

`OrderReconciliationSnapshot` normalizes both REST and private-stream order
facts. Startup recovery:

1. starts the private stream and buffers observations;
2. queries reconciliation candidates;
3. merges REST and buffered stream evidence deterministically;
4. treats `not found` as unresolved, not terminal;
5. never blindly resubmits an uncertain order.

This is the correct child recovery kernel. ADR-011 must aggregate its results
into the group view.

### 1.5 Operator authority

The operator controller starts `HALTED`, restores durable authority, and
supports `ACTIVE`, `REDUCE_ONLY` and `HALTED`.

The current gate is evaluated once for a single Position intent. A long-lived
Order Group needs authority checked again before every new child submit. HALT
must still permit read-only query, reconciliation and safe cancel actions.

## 2. Missing Group Capabilities

| Requirement | Current state |
|---|---|
| `OrderGroupId` | Missing |
| Basket leg to child mapping | Missing |
| Multiple child attempts per leg | Missing |
| Group revision/stale-action protection | Missing |
| Whole-Basket admission identity | Pending ADR-012 |
| Per-child execution permit | Missing; must be distinct from Basket approval |
| Group lifecycle/control state | Missing |
| Signed filled vector by Basket leg | Missing |
| Dynamic next-action protocol | Missing |
| Group-level recovery aggregation | Missing |
| Group bounds and retention | Missing |
| Multi-account/product execution routing | Missing |
| Immediate submit outcome written back to OMS | Missing |

## 3. Approval Is Not Permission

ADR-011 should define two separate boundaries:

### Basket admission

```text
Basket Risk ALLOW
  -> permits creation of one durable Order Group
  -> permits no exchange action
```

### Child action permit

```text
exact child proposal
  + current group revision
  + fresh portfolio/risk evidence
  + finite action expiry
  -> one single-use child submit permit
```

OMS must reject a permit if any identity, proposal checksum, revision,
portfolio evidence or validity field differs.

Cancel and query are not new exposure-increasing submits. They need OMS and
operator authorization, but should not require a new ordinary trade approval.

## 4. Group State Must Not Mix Three Different Meanings

The Web GPT input proposed names including `PARTIALLY_FILLED`, `HEDGED`,
`UNKNOWN` and `FAILED`. The current-code audit recommends separating them.

### Durable OMS control lifecycle

Recommended dimension:

```text
CREATED
ACTIVE
SUSPENDED
RECOVERY_REQUIRED
CLOSING
CLOSED
```

### Child/execution facts

Existing child states remain authoritative. The group derives facts such as:

- no children;
- working children;
- partial fills;
- quiescent children;
- unresolved/unknown external actions.

### Portfolio exposure assessment

`HEDGED`, net Delta, basis, margin and liquidation risk require Instrument,
Portfolio and current feature state. They belong to ADR-012 Risk assessment,
not the OMS lifecycle.

`FAILED` should be a terminal group outcome only after all live or unknown
children are resolved. An unknown child cannot be hidden inside terminal
failure.

## 5. Leg Tracking Boundary

OMS can authoritatively expose:

- immutable Basket target per `BasketLegId`;
- every child `ClientOrderId` and action ID;
- child side and requested quantity;
- cumulative venue-reported fill;
- signed filled quantity delta per leg;
- working and unresolved child sets.

OMS cannot authoritatively call that value the actual account position.
Portfolio state owns actual positions, and ADR-012 combines them with contract
multipliers, marks and Greeks.

For a simple Spot/Perpetual pair, Risk may derive `+3 BTC` residual exposure.
For an option spread, adding contract quantities is meaningless; Delta must
come from current features. The generic OMS therefore publishes a leg fill
vector, not one universal `unhedged_exposure` scalar.

## 6. Child Topology

One Basket leg cannot map to exactly one child by assumption.

Required relation:

```text
OrderGroup
  -> Basket legs
      -> zero or more child order attempts
          -> one existing OrderStateMachine each
```

Partial fill, cancel/replace, venue rejection and dynamically sized hedge can
all create multiple child attempts for one leg. Child limits must be bounded.

`OrderRequest` should remain unchanged for Execution compatibility. Group,
leg and action identities can be stored in an OMS-owned mapping and group
journal entry. The Execution adapter still receives the existing one-order
contract.

## 7. Runtime Impact

The existing event-to-single-order `TradingPipeline` is not a suitable
long-lived group state machine. A proposed `OrderGroupRuntime` should be:

- single-writer and caller-driven;
- deterministic;
- bounded;
- supplied with explicit clocks and views;
- free of a hidden universal Event Bus;
- responsible for orchestration only, not canonical OMS or Portfolio state.

A shared durable execution handoff should serve both:

- the current single-leg Pipeline; and
- every Order Group child.

That handoff must:

1. validate a current single-use action permit where required;
2. persist child creation and submit intent;
3. only then call the gateway;
4. report accepted, rejected, definitely-not-sent or unknown outcome to OMS;
5. force query/reconciliation for every unknown outcome.

The current async bridge timeout cannot be treated as definitely not sent.
Cancellation of a local future does not prove that the venue request was not
sent; group runtime must classify it as unknown.

## 8. Restart Reconstruction

Recommended recovery sequence:

```text
operator authority starts/restores HALTED
  -> replay mixed legacy order and new group journal entries
  -> rebuild group-child mapping and child state machines
  -> buffer private stream
  -> query every child with a persisted external-action intent
  -> merge REST and stream evidence
  -> derive group state from reconciled children
  -> refresh authoritative Portfolio state
  -> ADR-012 re-assesses exposure
  -> explicit operator/risk decision before any new child submit
```

A database may provide a journal backend or read model, but it cannot override
the ordered action journal or venue evidence as canonical OMS history.

## 9. Journal Compatibility Requirement

Existing V1 single-order journals must replay unchanged.

Recommended evolution:

- retain one global append sequence;
- add version-aware decoding that accepts legacy records;
- write group and child-mapping records in the new version;
- permit a mixed historical stream during migration;
- preserve exact `OrderRequest` decoding;
- never rewrite an old journal in place;
- require operator-approved migration/archival tooling.

A separate group journal is rejected because a crash between group mapping and
child-order persistence would create cross-journal atomicity ambiguity.

## 10. Proposed Review Decisions

The ADR should propose:

- `OrderGroupId`, `GroupActionId` and typed approval/permit identities;
- immutable group admission and action contracts;
- one-to-many leg/child mapping;
- group revision on every accepted mutation;
- orthogonal control, child-progress and Risk-exposure dimensions;
- dynamic, versioned execution policy outside Strategy;
- one exact finite permit per exposure-changing child submit;
- durable-before-external-action sequencing;
- group recovery built on the existing child reconciliation kernel;
- unchanged venue `OrderRequest` and Execution adapters;
- shared correction of the current single-leg submit handoff.

## 11. Questions for Web GPT and Project Owner

1. Should V1 default to one in-flight child per group while allowing a lower
   configured bound and a future reviewed parallel stage model?
2. Should every retry reuse the same `ClientOrderId` only when the transport
   proves “not sent,” while unknown results always require reconciliation?
3. Is a group permitted to resume from `RECOVERY_REQUIRED` automatically after
   complete reconciliation, or must Risk and operator explicitly resume it?
4. Should group closure require a fresh Portfolio/Risk confirmation that the
   target is reached, rather than only terminal child orders?
5. Should implementation of group state/journal proceed after ADR-011
   acceptance while external child submission remains blocked until ADR-012
   action-permit semantics are accepted?
