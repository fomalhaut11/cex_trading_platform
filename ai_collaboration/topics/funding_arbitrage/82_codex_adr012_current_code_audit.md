---
id: AI-20260728-012
title: ADR-012 Current-Code Audit
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-28
code_baseline: a752d3bff06a1b73b1103f543c64a2b6b64d2016
supersedes: none
related:
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
  - 81_codex_adr011_remediation_acceptance.md
external_share: allowed
sensitivity: public-project
---

# ADR-012 Current-Code Audit

## Audit Result

The current repository can support ADR-012 additively, but real grouped
execution is not safe yet.

The reusable foundation is stronger than the original planning document
assumed:

- ADR-009 provides coherent typed snapshot metadata and readiness;
- ADR-010 provides complete immutable 2-to-16-leg targets;
- ADR-011 provides durable group/action/child facts and exact permit
  validation;
- the shared execution handoff persists `SUBMITTING` before external I/O and
  performs an immediate safety recheck;
- option IV, Greeks and volatility surfaces already belong to Features;
- the single-leg Risk engine already demonstrates deterministic fail-closed
  policy evaluation with exact fixed-point inputs.

ADR-012 must fill four concrete gaps:

1. execution-consistent position truth;
2. portfolio exposure and margin projection;
3. durable admission reservations and action-permit issuance;
4. continuous supervision and recovery authority.

## Current Module Findings

### `cex_quant.risk`

Current behavior:

```text
PositionTargetIntent
  + one Instrument
  + current strategy/global quantity
  + one reference price
  -> ALLOW / REJECT
```

`RiskEngine` is pure and stateless. It supports Spot, linear/inverse
perpetual/future and option notional. It does not aggregate portfolio Delta,
basis, margin, liquidation, working orders or reservations.

Decision:

- keep the existing single-leg API unchanged;
- add a separate Portfolio Risk engine;
- keep projection pure;
- place approval/reservation/supervision state in a separate single-writer
  coordinator.

### `cex_quant.portfolio`

Current behavior:

- `AccountState` owns one `(venue, account)` pair;
- `AccountUpdate` contains absolute positions and balances;
- `AccountSnapshot` is immutable and deterministic;
- the package explicitly performs no Greeks, margin or valuation.

The absolute-update rule correctly prevents duplicate application inside the
account state. It does not prove whether an account snapshot already reflects
an OMS fill.

Critical finding:

```text
AccountSnapshot position
  + OrderGroup cumulative fills
```

can double-count exposure.

ADR-012 therefore needs a Portfolio-owned reconciliation baseline with an OMS
journal coverage cursor. Only fill increments after that cursor form the
execution overlay. Risk consumes the resulting effective position and must not
build a second position store.

### `cex_quant.snapshots`

The generic snapshot package already supports:

- source identity and scope;
- event and arrival time;
- schema version and sequence;
- freshness, coherence and clock health;
- immutable typed publication;
- deterministic replay identity.

ADR-012 can use a new typed `PortfolioRiskSnapshot` without changing the
generic snapshot model.

The Basket's `decision_snapshot_id` and an action permit's
`risk_snapshot_id` have different roles:

```text
Basket snapshot ID
  Strategy decision causation

Risk snapshot ID
  current action authorization causation
```

They must not be forced equal.

### `cex_quant.features`

System-computed option Greeks and volatility surfaces already exist in
Features. Venue-published analytics are explicitly labelled reference data.

ADR-012 must consume Feature values, units, quality, validity and lineage.
It must not move Greeks or volatility surfaces into Market Data or Risk.

Portfolio Risk needs a documented conversion from finite Feature floats to
canonical fixed-point Risk evidence before exact comparisons.

### `cex_quant.oms`

ADR-011 already implements:

- `OrderGroupAdmission`;
- exact `ExecutionAction`;
- finite `ExecutionActionPermit`;
- per-leg cumulative signed fill and working quantity;
- group revision;
- one unresolved action per group;
- durable group/action/child replay;
- unknown-outcome recovery.

OMS deliberately does not call its signed fill vector an actual position. That
boundary is correct.

The current `recovery_authorization_id` and
`portfolio_confirmation_id` are string evidence boundaries. ADR-012 should
define their typed issuance semantics without making OMS calculate Risk.

### `cex_quant.runtime`

The grouped runtime still raises:

```text
GroupedExecutionBlockedError
```

before reaching an Execution adapter.

This is correct and must remain until ADR-012 is:

1. accepted;
2. implemented;
3. accepted offline;
4. explicitly authorized for Testnet.

The immediate `ExternalSubmitGuardPort` can host the final Risk-generation,
group-revision, operator and health validation. The grouped runtime still
needs an adapter binding each prepared child to its exact action and permit.

## Required Ownership Boundary

```text
Portfolio
  account baseline, execution coverage, fill overlay, effective positions,
  normalized margin/collateral facts

Portfolio Risk
  projections, limits, admission reservations, approvals, permits,
  continuous directives and recovery evidence

OMS
  group/action/child identity, state, journal and execution facts

Runtime
  serialized calls and the immediate pre-I/O guard

Execution
  one canonical child request

Application
  objective, profitability and economic success
```

## Required Risk Views

ADR-012 needs three projections, not one:

```text
current realized exposure
projected target/action exposure
conservative working-order exposure
```

The working-order view is necessary for:

- partial multi-leg execution;
- multiple active groups;
- market-making quotes;
- approval races;
- recovery actions.

## Required Durable State

A stateless pure engine alone is insufficient.

If two complete Baskets are evaluated against the same free margin before
either creates a group, both can be incorrectly allowed. A single-writer Risk
coordinator must therefore durably reserve approved capacity before returning
approval evidence.

The Risk journal and OMS journal remain separate ownership logs. Restart must
cross-check them and rebuild reservations before issuing new authority.

## Fail-Closed Cases

No approval or permit may be issued when any of these is true:

- account baseline or OMS execution coverage is missing;
- account and OMS exposure diverge;
- required mark, Feature, margin or liquidation input is stale/missing;
- instrument, multiplier, unit or margin model is unsupported;
- group revision or action checksum differs;
- active working orders/reservations exceed a limit;
- Risk journal, OMS journal, clock, health, route or operator authority is
  unhealthy;
- a prior action has an unresolved unknown outcome.

## Compatibility Conclusion

ADR-012 requires additive modules and typed evidence. It does not require:

- changing `PositionTargetIntent`;
- replacing the existing single-leg `RiskEngine`;
- moving Greeks out of Features;
- changing Execution adapters to understand Baskets;
- adding Funding-specific branches to Risk or OMS;
- reopening ADR-011 execution-control design.

The proposed ADR is compatible with the repository baseline.
