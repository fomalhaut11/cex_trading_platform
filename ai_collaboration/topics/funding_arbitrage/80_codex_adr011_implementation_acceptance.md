# Codex Handoff: ADR-011 Implementation Acceptance

Date: 2026-07-28

Status: T029/T030/T031/A014 complete; ready for Web GPT architecture review

Post-review note:

The architecture remained accepted, but the implementation review identified
several safety and acceptance gaps. They were remediated in commit
`c2c306dbe7675076ae200021d2c98f127736f09e`. The current evidence and closure
record are in `81_codex_adr011_remediation_acceptance.md`; the counts and CI
run below remain the historical evidence for the original handoff.

## Review Scope

This handoff is self-contained because Web GPT cannot inspect the local
workspace.

Architecture input:

- accepted `ADR-011 Parent Order Group and Multi-leg Execution Model`;
- `70_web_gpt_adr011_implementation_guidance.md`;
- implementation parent baseline
  `0c31cd94da7335429c565b00889615926453c213`;
- implementation commit
  `9c1b0afb09744759b98429f7d8e99542bebd0aa1`.

Remote commit after synchronization:

`https://github.com/fomalhaut11/cex_trading_platform/commit/9c1b0afb09744759b98429f7d8e99542bebd0aa1`

## Result

T029, T030, T031 and A014 are complete within the authorized offline scope.

The implementation provides a generic, bounded and recoverable N-leg
execution-control foundation. It does not implement Portfolio Risk,
Funding/Carry logic or grouped exchange submission.

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> Order Group + ExecutionPlanRef
  -> ExecutionAction
  -> synthetic ExecutionActionPermit
  -> durable Child Order Attempt
  -X-> grouped external Execution
       blocked until ADR-012
```

## T029: Immutable Contracts and Identity

Implemented strong identifiers:

```text
PortfolioApprovalId
OrderGroupId
ExecutionPlanId
GroupActionId
ExecutionPermitId
```

Implemented immutable contracts:

```text
OrderGroupAdmission
ExecutionPlanRef
ExecutionAction
ExecutionActionPermit
ExecutionActionView
OrderGroupLegView
OrderGroupView
OrderGroupLimits
```

Binding rules enforced before child creation:

- admission checksum equals the immutable Basket content;
- group ID is deterministic from Basket intent and admission approval;
- action group, revision, Basket leg, account, instrument and plan match;
- permit group, revision, action ID, action checksum and expiry match;
- one `ExecutionPermitId` cannot authorize a second action;
- one action maps to one deterministic, venue-safe child
  `ClientOrderId`;
- action/permit/admission/plan codecs are canonical, checksummed and bounded.

No real permit issuer exists. Tests construct synthetic evidence only.

## T030: Group State, Journal and Recovery

Implemented OMS control states:

```text
CREATED
ACTIVE
SUSPENDED
RECOVERY_REQUIRED
CLOSING
CLOSED
```

Implemented action facts:

```text
PREPARED
TRANSMITTING
RETRY_ELIGIBLE
ACKNOWLEDGED
REJECTED
UNKNOWN
```

The group owns:

- Basket-to-group causation;
- action/permit/child identities;
- existing child `OrderStateMachine` instances;
- signed cumulative fill per Basket leg;
- signed working quantity per Basket leg;
- unresolved action identities;
- group control and recovery state.

The group does not own:

- Delta;
- basis;
- margin or liquidation;
- Greeks;
- hedge assessment;
- economic completion;
- Funding or Carry semantics.

There is deliberately no OMS `HEDGED` or `PARTIALLY_HEDGED` state.

V1 bounds:

```text
Basket legs                       16 (ADR-010)
child attempts per leg             8
children per group                64
technical retransmissions/action   1
unresolved actions/group           1
default retained groups         4096
```

Deployment limits may be lower but cannot exceed hard limits.

The existing JSONL OMS journal now supports one contiguous sequence with:

- immutable V1 legacy single-order facts;
- V2 immediate submit outcomes;
- V2 group creation, control, action preparation and action-state facts.

Historical V1 records are not rewritten. Both the legacy OMS service and the
Order Group runtime ignore facts outside their ownership while replaying the
same ordered journal.

`UNKNOWN` is not converted to failure. It forces
`RECOVERY_REQUIRED`, remains a reconciliation candidate and prohibits blind
retransmission or replacement. Resuming requires the unknown action to be
resolved plus explicit recovery evidence. `TARGET_CONFIRMED` closure requires
no unresolved child and external Portfolio/Risk confirmation evidence.

## T031: Shared Durable Handoff

The existing single-leg production regression path previously had:

```text
OMS.create_order
  -> Execution.submit
```

It now uses:

```text
OMS.create_order
  -> DurableExecutionHandoff
       -> persist SUBMITTING
       -> external submit
       -> persist immediate outcome
```

Immediate outcomes are distinct:

| Outcome | Canonical behavior |
|---|---|
| accepted | remain `SUBMITTING`; wait for venue lifecycle evidence |
| rejected | terminal `REJECTED` |
| definitely not sent | terminal `FAILED` in the legacy single-order path |
| unknown/possibly sent | remain `SUBMITTING`; reconcile, never blind retry |

An asynchronous bridge timeout after dispatch is now a typed unknown-state
error. A mismatched gateway result identity is also persisted as unknown.
Untyped exceptions are conservatively classified as unknown.

For grouped orders:

- action, permit, child mapping and child `SUBMITTING` state are one durable
  preparation fact;
- no Execution gateway/router is injected into `OrderGroupRuntime`;
- `submit_prepared_child` always raises
  `GroupedExecutionBlockedError`;
- the blocked method cannot reach an Execution adapter.

When ADR-012 later authorizes grouped execution, the grouped path must cross
the same durable handoff principle. This implementation does not pre-authorize
that integration.

## A014: Offline Acceptance

Verification on Python 3.14:

```text
420 tests passed
132 subtests passed
36 acceptance tests passed
93 source files passed strict MyPy
86.10% branch coverage
Ruff passed
compileall passed
git diff --check passed
```

Remote GitHub Actions run `30345476372` completed successfully for head
`9ccf0c5438ebf37eb47fef5132e3bea8698e7a5e`:

```text
Quality and coverage       success
Regression / Python 3.11   success
Regression / Python 3.14   success
```

Run URL:

`https://github.com/fomalhaut11/cex_trading_platform/actions/runs/30345476372`

Important scenarios:

| Scenario | Result |
|---|---|
| Basket admission only | group created, zero children and zero exchange calls |
| BTC Spot `+10` / BTC Perpetual `-10` | generic two-leg group accepted offline |
| option spread plus Perpetual Delta hedge | same three-leg group contract accepted |
| changed checksum, stale revision or expired permit | rejected before child mutation |
| reused permit ID for another action | rejected |
| unresolved action plus new action | rejected by one-in-flight V1 bound |
| definitely-not-sent | one same-action/same-child/same-ID retransmission maximum |
| second definitely-not-sent | child terminalized; no further retransmission |
| possibly-sent/unknown | `RECOVERY_REQUIRED`; no replacement |
| partial and final child fills | exact signed leg fill/working vectors |
| two child attempts on one leg | both identities retained and fills accumulated |
| 64 children | accepted at bound; 65th rejected |
| lower deployment bound | rejected at configured limit |
| mixed V1/V2 journal | replayed without historical rewrite |
| restart with unknown child | group/mapping/recovery candidate reconstructed |
| `TARGET_CONFIRMED` without evidence | rejected |
| grouped external submit | hard-blocked before Execution adapter |
| existing `PositionTargetIntent` Pipeline | unchanged outcome with safer handoff |

Primary evidence files:

```text
tests/acceptance/test_adr011_order_group.py
tests/test_oms_order_group.py
tests/test_execution_handoff.py
tests/test_oms_journal.py
tests/test_runtime_pipeline.py
tests/acceptance/test_trading_pipeline.py
```

## Architecture Conformance

### No Risk leakage into OMS

There is no Delta, basis, margin, liquidation, Greeks or hedge calculation in
the new OMS or Runtime modules.

OMS validates immutable authorization evidence but does not issue it.

### No Funding specialization

There is no Funding, Carry or strategy-name branch in Order Group code.
Two-leg and three-leg tests use the same public contracts and state machine.

### Basket remains economic intent

`BasketTargetIntent` is unchanged. Group lifecycle is not placed into the
Basket. Existing single-leg Pipeline behavior remains explicit: Basket still
stops before the single-leg Portfolio/Risk/OMS path.

### Child kernel remains reusable

Existing `OrderRequest`, `OrderStateMachine`, Execution adapters, REST
reconciliation and private-stream normalization remain child-oriented and
compatible.

## Explicit ADR-012 Boundary

The following are still absent and forbidden:

- real whole-Basket Portfolio Risk approval service;
- real `ExecutionActionPermit` issuance;
- Delta, basis, margin and liquidation models;
- continuous portfolio exposure supervision;
- grouped Execution gateway routing/submission;
- Funding Arbitrage application execution;
- Testnet or production multi-leg trading.

Two evidence strings remain intentionally external contracts pending
ADR-012:

- recovery authorization evidence;
- Portfolio/Risk `TARGET_CONFIRMED` evidence.

ADR-011 checks their presence, boundedness and lifecycle position. ADR-012
must define their authoritative typed semantics and freshness.

## Review Request

Web GPT should review:

1. whether T029-T031/A014 satisfy the frozen ADR-011 boundary;
2. whether the external grouped-execution block is sufficiently explicit;
3. whether the immutable per-leg fill/working vectors are the correct input
   boundary for ADR-012;
4. whether ADR-012 proposal work may begin without reopening ADR-011.
