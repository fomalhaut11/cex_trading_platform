# Codex Handoff: ADR-011 Remediation Acceptance

Date: 2026-07-28

Status: Architecture remains accepted; implementation findings remediated;
local and remote acceptance passed

## Committee Decision Applied

ADR-011 was not redesigned. Its frozen separation remains:

```text
Economic Intent
  -> Execution Control
  -> exact permitted Execution Action
  -> durable Child Order Attempt
```

The remediation closes implementation and acceptance gaps found after the
original `80_codex_adr011_implementation_acceptance.md` handoff.

Implementation commit:

`c2c306dbe7675076ae200021d2c98f127736f09e`

## Closed Implementation Findings

### Immediate pre-I/O safety recheck

`DurableExecutionHandoff` now requires an `ExternalSubmitGuardPort`.

The sequence is:

```text
persist SUBMITTING
  -> immediate runtime/operator health recheck
  -> external submit only when still authorized
```

If the guard blocks after durability but before Execution, OMS records
`DEFINITELY_NOT_SENT` and the Execution adapter receives no call.

### Before-dispatch bridge classification

`ExecutionBridgeStateError` is now a typed `ExecutionTransportError`.
Bridge-not-running and invalid-thread failures occur before dispatch and are
therefore recorded as definitely not sent, not unknown.

### Capacity suspension

`OrderGroupLimits` now includes a configured active-group bound per
strategy/account. Child-attempt, group-child and unresolved-action capacity
failures durably move an existing group to `SUSPENDED`.

A suspended group cannot start a prepared transmission. Resumption must occur
through the explicit group-control transition.

### Identity ownership

`GroupActionId` is required to be a lowercase SHA-256 digest. Before journal
mutation, the runtime checks the global `ClientOrderId -> OrderGroupId`
mapping. Recovery performs the same check and rejects histories assigning one
child identity to multiple groups.

### Single writer

`OrderGroupRuntime` now captures its owner thread and rejects every mutation
from another thread. This protects the group registry, Basket ownership,
capacity checks, child mappings and journal ordering in addition to the
existing per-group state-machine guard.

## Added Acceptance Evidence

New deterministic tests cover:

- HALT/health change after durable preparation and before Execution;
- guard rejection as definitely not sent with zero exchange calls;
- bridge state failure as definitely not sent;
- journal failure after gateway response and recovery as `SUBMITTING`;
- failure before group append;
- restart after group append but before in-memory registration;
- durable replay of capacity-triggered `SUSPENDED`;
- active-group capacity per strategy/account;
- suspended-group transmission rejection;
- cross-group child-ID collision rejection;
- invalid non-deterministic action identity;
- runtime mutation from a non-owner thread.

Local verification:

```text
430 tests passed
133 subtests passed
37 acceptance tests passed
49 acceptance subtests passed
93 source files passed strict MyPy
86.25% branch coverage
Ruff passed
compileall passed
secret scan passed
git diff --check passed
```

Remote documentation head
`df2fd83ab7bae89e35da819e7671f79eeb20dbc0` passed GitHub Actions run
`30351998834`:

```text
Quality and coverage       success
Regression / Python 3.11   success
Regression / Python 3.14   success
```

Run URL:

`https://github.com/fomalhaut11/cex_trading_platform/actions/runs/30351998834`

## Boundary Confirmation

The remediation adds no:

- Delta, basis, margin, liquidation or Greeks calculation to OMS;
- Funding or Carry branch;
- Portfolio Risk approval or permit issuer;
- grouped Execution router;
- Testnet or production group submission.

`OrderGroupRuntime.submit_prepared_child` remains hard-blocked pending
ADR-012.

## Next Gate

ADR-012 proposal work may proceed. Real grouped external execution remains
forbidden until ADR-012 is accepted, implemented and independently accepted.
