# Module Topology

## Core Flow

```text
Exchange -> market_data -> market_state -> features -> strategy
                                                     -> risk -> oms -> execution -> Exchange
```

For applications that require correlated state, the accepted additive path is:

```text
authoritative immutable source views
  -> snapshots policy/assessment
  -> runtime SnapshotCoordinator
  -> application-specific typed decision snapshot
  -> strategy
```

`snapshots` owns generic observation, readiness and coherence contracts.
`runtime` owns serialized coordination. An application owns its typed
assembler and payload. Snapshot coordination does not replace source state or
the mandatory Strategy -> Risk -> OMS -> Execution boundary.

`runtime` assembles the flow. `recorder`, `monitoring`, `operations_api` and
`storage` consume bounded side channels and cannot block the trading path.

Public kernel semantics are compatibility-frozen under
`architecture/kernel_v1_freeze.md`. New application/runtime work must prefer
composition and adapters; application-specific fields cannot be added to
generic Strategy, Risk, OMS, Portfolio or Accounting contracts without
reproducible evidence and explicit change approval.

ADR-010 adds the decision boundary below:

```text
DecisionSnapshotPublication
  -> StrategyRuntime
  -> PositionTargetIntent | BasketTargetIntent
```

`strategy.basket` owns immutable, bounded portfolio targets, Objective Type
metadata and deterministic identity. `strategy.basket_codec` owns canonical
checksummed evidence serialization. Neither module owns Risk decisions,
Parent/Child orders, execution sequencing or application lifecycle.

The existing `runtime.TradingPipeline` remains single-leg. It rejects a
`BasketTargetIntent` at the Strategy boundary before Portfolio, Risk, OMS and
Execution.

Accepted ADR-011 defines the future execution-control topology:

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> OMS Order Group + ExecutionPlanRef
  -> ExecutionAction
  -> ExecutionActionPermit        # issued durably by Portfolio Risk
  -> durable Child Order Attempt
  -> existing OrderRequest
  -> existing Execution adapter
```

T029-T031/A014 implement the bounded offline group foundation:

```text
core.identifiers
  -> oms.group_model / oms.group_codec
  -> oms.group_state
  -> oms.journal
  -> runtime.order_group_runtime
```

`runtime.execution_handoff` is shared by the existing single-leg Pipeline:
it persists `SUBMITTING`, requires an immediate runtime/operator guard before
external I/O and returns every immediate result or typed unknown/not-sent
failure to OMS. The Order Group runtime enforces single-writer mutation,
bounded strategy/account activation, durable capacity suspension and global
child identity ownership. It can durably prepare synthetic child attempts,
but its external submission method always fails closed. The current
single-leg Pipeline remains the production regression path.

Accepted ADR-012 adds:

```text
portfolio.risk_inputs
  -> portfolio.exposure_state
  -> risk.portfolio_model
  -> risk.portfolio_engine
  -> risk.portfolio_coordinator / risk.portfolio_journal
  -> runtime.portfolio_risk_guard
  -> shared durable handoff
  -X-> grouped external Execution
```

T032-T035/A015 are complete offline. The final arrow remains hard-blocked
pending a separate explicit Testnet promotion.

The project-owner-authorized ADR-013 offline foundation adds:

```text
authenticated normalized financial evidence
  -> runtime.financial_fact_handoff
  -> accounting facts / deterministic mapping
  -> durable balanced ledger / replay / reversal
  -> reconciliation + allocation
  -> valuation + PnL read views
```

Accounting is an independent domain. It does not import Carry, issue execution
permits, mutate OMS/Portfolio, infer Funding from market rates or treat marks
as ledger facts. The bounded runtime handoff creates the ledger on its owning
worker and reports overflow, excessive queue age or persistence failure as
unhealthy. T036-T039/A016 are complete offline; authenticated source activation
and every external execution route remain blocked.

The ADR-012 conditional-review remediation adds typed freshness,
`RiskInvalidationTrigger`, `RiskResourceClaim`, `TargetMatchPolicy` and
non-economic failure statuses inside the same ownership boundaries. It does
not add an OMS, Execution or application dependency to Risk.

Accepted ADR-014 adds the offline application path:

```text
market_data.state.FundingRateState
  + immutable Spot/Perpetual/Portfolio/Feature views
  -> applications.carry.funding_arbitrage typed Snapshot assembler
  -> pure Funding Carry Strategy
  -> generic BasketTargetIntent
  -> runtime.CarryApplicationRuntime
  -X-> Portfolio Risk / OMS / Execution

applications.carry immutable facts
  -> checksummed Carry journal
  -> single-writer CarryPositionBook / replay
  -> pure hedge, financial-finality and recovery assessments
```

The Runtime records only offline Basket evidence and exposes a permanent
`external_execution_blocked` result. It has no Risk, OMS, permit or Execution
dependency. T040-T044/A017 are complete; this is not execution authorization.

`runtime.operator_endpoint` is the protocol-neutral `operations_api` adapter.
It accepts identity only after external mTLS validation and owns no public
listener. Concrete TLS termination remains a deployment boundary.

## Dependency Rules

1. `core` depends on no business domain.
2. `instruments` depends only on `core`.
3. `market_data` depends on `core` and `instruments`.
4. `features` consumes canonical market facts and state views, never connectors.
5. `strategy` produces trade intents and cannot create venue orders.
6. `risk` approves, modifies or rejects intents.
7. `oms` exclusively owns order lifecycle state.
8. `execution` adapts commands and reports; it does not own canonical orders.
9. `portfolio` exclusively owns account and position state.
10. Domain modules cannot depend on `runtime`.
11. Venue-specific objects cannot escape their adapter package.
12. `snapshots` depends only on foundational types and minimal health status;
    it cannot depend on source domains, applications or runtime.
13. Application-specific snapshot assemblers may read public immutable domain
    views but cannot depend on runtime or venue adapters.
14. `strategy.basket` may depend on `core`, `instruments` and snapshot
    identity contracts, but cannot depend on Risk, OMS, Execution,
    applications, runtime or venue adapters.
15. `oms` may consume accepted Basket contracts and generic permit evidence,
    but cannot depend on a concrete Risk engine, execution planner, Carry
    application, runtime or venue adapter.
16. An Execution Plan proposes immutable actions but owns no Risk or operator
    authority; only Runtime may coordinate the accepted boundaries.
17. OMS group state owns group control, child mappings and execution facts;
    it cannot compute Delta, basis, margin, `HEDGED` or application meaning.
18. `ExecutionActionPermit` is immutable evidence issued by Portfolio Risk;
    OMS validates exact binding but never issues it.
19. Accepted ADR-012 keeps execution-consistent positions and normalized
    margin facts in Portfolio, exposure/approval/permit authority in Risk,
    group/action/child facts in OMS and ordered coordination in Runtime.
    Risk directives never mutate OMS or call Execution.
20. ADR-013 offline implementation adds an independent Accounting domain for immutable
    financial facts, balanced per-asset postings, reconciliation, allocation
    and derived PnL. Accounting cannot mutate OMS/Portfolio or import an
    application implementation. Final Web GPT acceptance is pending.
21. Accepted ADR-014 places Carry economic state in
    `applications.carry`; applications consume immutable public views and emit
    Basket targets, but cannot issue permits, create child orders, write the
    ledger or call Execution. Its scope is aligned with ADR-013
    `EconomicOwnerRef`, `PnlAttributionView` and reconciliation/valuation
    views. T040-T044/A017 implement this boundary offline while external
    execution remains blocked.

## Process Boundaries

The initial `trading-core` process contains the core flow. A module becomes a
service only for measured scaling, language-runtime or fault-domain reasons.
