# T045 Execution Promotion Composition Audit

Status: complete.

Completed: 2026-08-01.

Authority: credential-free current-code audit under ADR-009 through ADR-014
and the Kernel v1 compatibility freeze.

External effect: none. This audit does not authorize Testnet or production
execution.

## 1. Decision

The frozen domain contracts are sufficient for the first Funding Carry closed
loop. No Kernel v1 public-interface change is justified by current evidence.

The codebase contains the required domain capabilities, but no production
composition owns the complete sequence from a Carry `BasketTargetIntent` to
whole-Basket Risk, Order Group execution, Portfolio reconciliation,
Accounting truth and Carry read-side state. T046 must add that composition and
only the adapters demonstrated as missing below.

The principal evidence is:

- `CarryApplicationRuntime.evaluate()` emits generic Basket targets and
  deliberately stops before Risk/OMS;
- `TradingPipeline.process()` explicitly rejects Basket intents because it is
  the frozen single-leg path;
- the full Basket/Risk/Order Group/permit path is exercised only by tests;
- `OrderGroupRuntime.submit_prepared_child()` remains a deliberate hard block;
- no production module constructs `OrderGroupAdmission` or `ExecutionAction`;
- no production composition instantiates `OrderGroupRuntime`,
  `PortfolioRiskCoordinator`, `PortfolioRiskExecutionGuard`,
  `ExecutionConsistentPositionState`, `AccountingLedger` and
  `CarryPositionBook` as one ordered runtime;
- execution-position effects and authenticated financial facts currently have
  contracts and consumers, but no grouped production projection/source path.

These are missing-composition findings, not missing domain authority.

## 2. Current-Code Call and Dependency Map

```text
FundingCarryDecisionSnapshot
  -> StrategyRuntime
  -> BasketTargetIntent
  -> [MISSING: grouped composition entry]
  -> PortfolioRiskEngine.assess_basket
  -> PortfolioRiskCoordinator.reserve_approval
  -> OrderGroupAdmission
  -> OrderGroupRuntime.create_group
  -> PortfolioRiskCoordinator.attach_reservation
  -> OrderGroupRuntime.activate_group
  -> [MISSING: execution-plan/next-action selector]
  -> ExecutionAction
  -> PortfolioRiskEngine.authorize_action
  -> PortfolioRiskCoordinator.issue_permit
  -> OrderGroupRuntime.prepare_child_submit
  -> PortfolioRiskExecutionGuard
  -> DurableExecutionHandoff
  -> [T046 only: deterministic fault-injectable Execution port]
  -> [MISSING: grouped submit outcome adapter]
  -> OrderGroupRuntime child/action state
  -> [MISSING: OMS-journal-to-position-effect projection]
  -> ExecutionConsistentPositionState
  -> PortfolioRiskCoordinator.confirm_portfolio_target
  -> [MISSING: authenticated financial-fact source composition]
  -> FinancialFactHandoff
  -> AccountingLedger
  -> [MISSING: Carry read-side lifecycle projector]
  -> CarryPositionBook
```

### Existing reusable boundaries

| Boundary | Existing code | Audit result |
|---|---|---|
| Snapshot to economic decision | `runtime/carry_application.py`, `strategy/runtime.py` | Reuse unchanged; it correctly emits only generic Basket targets. |
| Whole-Basket Risk | `risk/portfolio_engine.py::assess_basket` | Reuse unchanged. It projects all legs and returns approval evidence only when the complete Basket passes. |
| Durable reservation | `risk/portfolio_coordinator.py::reserve_approval` | Reuse unchanged; append precedes publication. |
| Stable group identity | `oms/group_model.py::deterministic_order_group_id` | Reuse unchanged; identity binds Basket intent and Portfolio approval. |
| Durable Order Group | `runtime/order_group_runtime.py` | Reuse as OMS-side group writer and journal replay owner. |
| Exact action Risk | `risk/portfolio_engine.py::authorize_action` | Reuse unchanged; authorization is bound to group revision and exact action content. |
| Permit liveness | `risk/portfolio_coordinator.py` | Reuse issue, validate, consume and restart-generation invalidation unchanged. |
| Immediate pre-I/O safety | `runtime/portfolio_risk_guard.py` | Reuse unchanged; platform safety runs before durable permit consumption. |
| Durable submit boundary | `runtime/execution_handoff.py` | Reuse through a grouped OMS adapter; it already records definitely-not-sent and UNKNOWN distinctly. |
| Venue reconciliation facts | `oms/reconciliation.py`, Binance reconciliation adapters | Reuse normalized order observations; no Binance payload may cross into OMS. |
| Effective position truth | `portfolio/exposure_state.py` | Reuse unchanged; authoritative baseline plus uncovered durable fill effects determines exposure. |
| Financial truth | `accounting/*`, `runtime/financial_fact_handoff.py` | Reuse unchanged; only authenticated observed facts enter the ledger. |
| Carry truth | `applications/carry/state.py`, `hedge.py`, `financial.py` | Reuse unchanged; Carry observes Portfolio and Accounting instead of owning their state. |

## 3. Identity and Causation Map

| Identity/evidence | Created by | Binds to / derivation | Durable owner |
|---|---|---|---|
| `DecisionSnapshotId` | Snapshot Coordinator | coherent source observations and publication metadata | snapshot evidence boundary |
| `IntentId` | Basket strategy contracts | strategy, decision snapshot and canonical Basket content | Strategy evidence / Carry journal link |
| `PortfolioApprovalId` | `PortfolioRiskEngine` | Basket checksum, Risk snapshot, policy and resource claims | Portfolio Risk journal |
| `PortfolioReservationId` | `PortfolioRiskCoordinator` | deterministic from approval ID | Portfolio Risk journal |
| `OrderGroupId` | `deterministic_order_group_id` | Basket intent ID plus Portfolio approval ID | OMS journal |
| `ExecutionPlanId` and checksum | execution-plan policy | bounded plan version and canonical parameters | OMS `GroupCreatedEntry` |
| `GroupActionId` | `deterministic_group_action_id` | group, revision, Basket leg, plan and attempt sequence | OMS journal |
| `ExecutionPermitId` | `PortfolioRiskEngine.authorize_action` | exact action checksum, group revision, Risk snapshot and expiry | Portfolio Risk journal |
| `ClientOrderId` | `child_order_id_for_action` | exact `GroupActionId` | OMS journal |
| venue update identity | venue-neutral reconciliation adapter | source, source update and client order | OMS journal |
| execution-position effect identity | Portfolio projection adapter, missing | durable OMS sequence and cumulative child fill delta | Portfolio position state |
| `FinancialFactId` | authenticated fact source, composition missing | authenticated execution/account observation | Accounting journal |
| `ApplicationPositionId` | Carry state | strategy, pair and opening snapshot | Carry journal |

No runtime may invent a replacement identity after restart. Exact redelivery is
idempotent; changed content under the same identity must fail closed.

## 4. State-Writer Ownership

| State | Existing single writer | T046 composition duty |
|---|---|---|
| Snapshot coherence/publication | `SnapshotCoordinator` | read publications only |
| Basket economic decision | `StrategyRuntime` / Carry policy | accept immutable intents only |
| Risk reservations and permits | `PortfolioRiskCoordinator` owner thread | call in ordered runtime sequence |
| Order Group, actions and children | `OrderGroupRuntime` owner thread | make it the sole grouped OMS mutation route |
| Single-leg OMS | existing `OmsAdapter` | keep isolated; do not route Basket work through `TradingPipeline` |
| Effective account positions | one `ExecutionConsistentPositionState` writer per account | project contiguous durable OMS effects before Risk/Carry reads |
| Account snapshot state | one `AccountState` writer per account | accept authenticated account baselines |
| Financial ledger | `AccountingLedger`; optionally owned by the bounded `FinancialFactHandoff` worker | submit authenticated facts and drain before financial finality reads |
| Carry application positions | `CarryPositionBook` owner thread | link intent/group and project read-only hedge/financial assessments |
| Full orchestration order | missing | one `GroupedExecutionRuntime` owner thread in T046 |

The phrase “one runtime writer” means one coordinator serializes cross-domain
commands. It does not collapse the independent journals or transfer domain
truth into Runtime.

## 5. Happy-Path Sequence

1. Carry publishes one immutable `BasketTargetIntent` from a coherent decision
   snapshot.
2. The grouped runtime obtains a current Portfolio Risk snapshot and calls
   `assess_basket`.
3. An ALLOW decision is durably reserved before the approval is exposed.
4. The runtime creates one `OrderGroupAdmission`; the OMS runtime derives and
   durably records the one `OrderGroupId`.
5. The Risk reservation is attached to that exact group, then the group is
   activated.
6. The execution-plan policy selects one exact residual-reducing child action.
7. Risk authorizes that action and durably issues one finite permit.
8. OMS durably prepares the child before any execution call.
9. The immediate platform guard runs; Risk validates and durably consumes the
   permit.
10. The deterministic T046 Execution port returns an immediate outcome; the
    grouped OMS adapter persists it.
11. Venue-neutral child events advance cumulative fill state. A contiguous OMS
    journal projection advances effective Portfolio positions.
12. The loop reassesses residual exposure and selects the next action until no
    unresolved child action remains.
13. Portfolio confirms that effective positions match the Basket target; the
    group closes with confirmation evidence and the reservation is released.
14. Authenticated fill, fee and Funding facts pass through the bounded
    Accounting handoff and ledger.
15. Carry reads Portfolio hedge assessment and Accounting financial state,
    then durably advances its own lifecycle.

Steps 1, 2-5, 7-9, and the individual consumers in 10-15 exist as tested
capabilities. The ordered coordinator and adapters joining them are the T046
scope.

## 6. Failure and Restart Matrix

| Scenario | Existing fail-closed capability | Missing T046 composition/evidence |
|---|---|---|
| Basket Risk reject | whole-Basket reject reasons | terminate without group creation and record disposition |
| Reservation append failure | Risk coordinator latches unhealthy | propagate runtime failure and create no group |
| Group append failure | Order Group runtime latches unhealthy | mark reservation recovery-required or preserve it for restart reconciliation |
| Action Risk reject | exact-action reasons, no permit | suspend/replan without execution |
| Permit expires or generation changes | immediate validation rejects | route to definitely-not-sent; select a new action only from fresh group/Risk state |
| Platform halt after child preparation | guard blocks and durable handoff records definitely-not-sent | map result back to action and preserve retry bounds |
| Transport fails before send | definitely-not-sent | bounded technical retry with the same economic action identity rules |
| Timeout/failure after possible send | UNKNOWN | require reconciliation; never make a blind economic retry |
| First leg fills, second rejects | group residual quantities and Portfolio effective positions | choose recovery/reduce-risk action and update Carry to degraded/recovery state |
| Partial fill | cumulative child fill and signed residual contracts | deterministic next-action selection from effective exposure |
| Cancel failure | OMS unresolved/UNKNOWN semantics | fault-injected cancel policy and recovery evidence |
| Position or margin changes while opening | Risk generation/material-change invalidation | resnapshot, invalidate permit, supervise group and choose fail-closed action |
| Private stream gap | startup reconciliation and readiness gates | grouped child routing and group recovery state |
| Accounting fact missing/incomplete | ledger and reconciliation completeness contracts | Carry financial state remains provisional; no false finality |
| Restart with issued permit | Risk constructor invalidates pre-restart permits | bootstrap ordering and group/action reconciliation before any new action |
| Restart with PREPARED/TRANSMITTING/UNKNOWN child | OMS journal replay and recovery candidates | deterministic reconciliation and resumed loop ownership |
| Journal identity conflict | each domain latches or raises recovery error | aggregate readiness must remain closed |

## 7. Restart Order

T046 must make the following order explicit and testable:

1. open and replay Accounting, Carry, Portfolio Risk and OMS journals without
   permitting external action;
2. instantiate Portfolio effective-position state as UNRECONCILED;
3. start private-stream buffering;
4. query authoritative account/position and order baselines;
5. reconcile all OMS recovery candidates, including UNKNOWN children;
6. project contiguous durable OMS fill effects into Portfolio;
7. ingest and drain authenticated financial facts into Accounting;
8. recompute Carry hedge and financial read-side assessments;
9. expose grouped runtime readiness only when every mandatory child health
   report is healthy;
10. issue only fresh post-restart Risk permits.

Any gap or conflict keeps the grouped runtime halted or recovery-required.

## 8. Finding Classification

### A. Existing capability — reuse unchanged

- coherent decision snapshots and generic Basket intents;
- whole-Basket Risk decisions and durable reservations;
- deterministic Order Group/action/child identities;
- exact finite permits with durable consumption;
- shared durable-before-I/O handoff and immediate platform safety gate;
- Order Group journal, replay, residual quantities and UNKNOWN state;
- venue-neutral REST/private-stream reconciliation;
- execution-consistent Portfolio positions;
- Accounting facts, balanced journal/ledger and reconciliation proofs;
- Carry journal, hedge assessment and financial-state projection.

### B. Missing composition — implement in T046

1. one mode-neutral `GroupedExecutionRuntime` and readiness/lifecycle state;
2. Basket admission composition that calls Risk, reserves, creates the group,
   attaches the reservation and links Carry evidence;
3. a bounded execution-plan/next-action policy using exact current residuals;
4. a grouped durable-submit adapter that connects prepared group actions to
   `DurableExecutionHandoff` and routes every immediate result back to the
   correct group/action;
5. venue-neutral child-event routing into the Order Group runtime;
6. a contiguous OMS-journal-to-Portfolio execution-effect projector;
7. authenticated financial-fact source ports and Accounting handoff
   composition, without deriving facts from market rates;
8. a Carry read-side projector for intent/group links, hedge assessment,
   financial state and recovery transitions;
9. explicit bootstrap/restart ordering and aggregate fail-closed readiness.

### C. External-promotion dependencies — remain blocked

- Binance Testnet credentials and exact account/instrument bounds;
- project-owner authorization for A019;
- persistent approved host time source;
- deployed TLS/mTLS termination, protected identity forwarding and remote
  audit retention;
- target-host soak and authenticated restart evidence.

### D. Non-blocking optimization

- throughput tuning beyond the existing bounds;
- generalized SDK, historical Replay and Paper Exchange;
- additional strategy families or products;
- production dashboards beyond Funding Carry Operations Lite;
- renaming the stale ADR-012 wording in the defensive grouped-submit block.

## 9. Bounded T046 Implementation Plan

T046 may add Runtime-owned composition and internal adapters, but must not
change frozen public semantics.

1. Add a synchronous, owner-thread `GroupedExecutionRuntime` with explicit
   NEW/RUNNING/HALTED/RECOVERY_REQUIRED/STOPPED/FAILED readiness.
2. Add narrow ports for current Risk snapshot, Portfolio views, authenticated
   financial facts and deterministic Execution; do not add Binance types.
3. Add the admission composer and a fixed, versioned two-leg execution-plan
   policy for the configured BTC Spot/USD-M Carry MVP.
4. Add the grouped durable-submit state adapter and exact outcome router around
   `DurableExecutionHandoff` and `PortfolioRiskExecutionGuard`.
5. Add durable OMS fill-effect projection into Portfolio and Carry read-side
   projection from Portfolio/Accounting views.
6. Add deterministic bootstrap and restart recovery with external I/O disabled.
7. Add a fault-injectable in-memory Execution adapter and A018 scenarios for
   fill, reject, partial fill, UNKNOWN, cancel failure, permit invalidation,
   material position change, accounting incompleteness and restart.
8. Keep authenticated grouped submission behind the separate A019 authority.

## 10. Exit Assessment

T045 is complete because it identifies the current call graph, all identity
and causation edges, domain writers, happy/failure/restart sequences and the
smallest evidenced T046 composition scope.

Kernel v1 remains frozen. T046 is now the next credential-free engineering
task. A018 remains planned; A019 Testnet and all production execution remain
unauthorized.
