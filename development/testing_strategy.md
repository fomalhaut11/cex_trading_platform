# Testing Strategy

## Layers

- Unit tests verify value objects and deterministic state transitions.
- Contract tests verify adapter-to-canonical mappings and schema compatibility.
- Integration tests verify bounded module pipelines and recovery behavior.
- Replay tests feed recorded events and compare deterministic state outputs.
- Security-boundary tests mutate signed fields, identities, validity windows
  and authorization scopes, and prove rejection occurs before state mutation.

## Baseline

Every public domain type requires construction, invariant and serialization
tests. Every state engine requires ordering, duplicate, gap and recovery tests.
No live exchange or network access is required by the default test suite.

## A012 Decision Snapshot Acceptance

The accepted ADR-009 implementation must add offline tests for:

- immutable typed IDs, observations, policies, assessments and metadata;
- duplicate/missing source rules and deterministic issue ordering;
- event-age, arrival-age, future-skew and coherence boundaries;
- unhealthy clock and monotonic regression fail-closed behavior;
- source scope, schema, sequence and observation-identity conflicts;
- single-writer coordinator behavior and bounded latest-only retention;
- exactly-once publication per ordered observation fingerprint;
- assembler exceptions and readiness loss after a prior ready snapshot;
- deterministic recording/replay and restart beginning not ready;
- a synthetic typed application with at least three sources, proving the
  infrastructure is neither Carry-specific nor limited to two sources.

All existing single-instrument regression and acceptance tests remain
mandatory. A012 requires no network or exchange credential.

## A013 Basket Intent Acceptance

Status: Complete on 2026-07-28.

The accepted ADR-010 implementation must add offline tests for:

- common `IntentId`, unique `BasketLegId` and versioned Objective Type
  references;
- Objective Type format, registration, versioning and historical decoding;
- two-to-16-leg hard bounds and lower deployment limits;
- mandatory expiry and maximum validity;
- canonical account/instrument order and duplicate-scope rejection;
- same Instrument in different explicitly allowed accounts;
- exact fixed-point target preservation, including zero close targets;
- deterministic identity, serialization, redelivery and conflict behavior;
- additive `DecisionIntent` and `StrategyInput` compatibility;
- Basket-to-DecisionSnapshot causation validation;
- unchanged single-leg Strategy and Pipeline results;
- explicit Basket rejection by the single-leg pipeline before Risk/OMS;
- the same public contract for synthetic two-leg and three-leg scenarios.

A013 must prove that no OMS child order or Execution request can be produced
by the ADR-010 implementation.

Evidence: `tests/acceptance/test_basket_intents.py`, the Basket unit and
Strategy compatibility suites, and the unchanged single-leg regression.

## A014 Parent Order Group Acceptance

Status: Complete on 2026-07-28 for the T029-T031 offline boundary, including
post-implementation safety remediation.

T029-T031 must add deterministic offline tests for:

- strong `OrderGroupId`, `ExecutionPlanId`, `GroupActionId`,
  `PortfolioApprovalId` and `ExecutionPermitId` identities;
- immutable admission, plan, action, permit and group-view contracts;
- exact action/permit checksum, revision, expiry and single-action binding;
- two-to-16-leg groups with zero children at creation;
- zero-to-eight sequential actions and child attempts per Basket leg;
- the 64-child group hard bound and lower configured limits;
- exactly one exposure-changing in-flight submit per group;
- unchanged maker/taker, price, quantity and identity rules;
- at most one definitely-not-sent technical retransmission with the same
  action, child and `ClientOrderId`;
- possibly-sent and unknown outcomes entering `RECOVERY_REQUIRED` with no
  retransmission;
- child `PARTIALLY_FILLED` facts without an OMS `HEDGED` state;
- `TARGET_CONFIRMED` requiring fresh synthetic Portfolio/Risk evidence;
- mixed legacy and group journal replay without rewriting old facts;
- restart beginning halted, complete reconciliation, fresh Risk and explicit
  operator resume;
- durable-before-external-I/O fault injection at every handoff boundary;
- unchanged existing `OrderRequest`, child state machine, Execution adapters
  and single-leg Pipeline behavior;
- the concrete single-leg runtime persisting `SUBMITTING` before gateway and
  returning immediate outcomes to OMS.
- an immediate health/operator recheck after durable preparation and before
  gateway invocation;
- capacity-triggered durable `SUSPENDED`, configured active groups per
  strategy/account and no transmission while suspended;
- global child-identity collision rejection during live preparation and
  recovery;
- runtime-level non-owner mutation rejection;
- restart after group append but before registration, and after gateway
  response but before outcome append.

A014 must also prove a negative boundary: no exposure-changing Order Group
child reaches an Execution adapter. Synthetic permits may test durable
preparation, state and recovery only. Real action-permit issuance and group
submission remain blocked until ADR-012.

Evidence:

- `tests/acceptance/test_adr011_order_group.py`;
- `tests/test_oms_order_group.py`;
- `tests/test_execution_handoff.py`;
- mixed legacy/group and immediate-outcome cases in
  `tests/test_oms_journal.py`;
- unchanged single-leg Pipeline and runtime acceptance suites.

The tests exercise the immutable 8-attempt/64-child hard bounds and lower
deployment limits, one unresolved action, one same-identity technical
retransmission, `RECOVERY_REQUIRED`, exact fill vectors and
`TARGET_CONFIRMED` evidence. External grouped execution remains deliberately
unreachable, so this completion is not ADR-012 Risk acceptance.
