# Carry Application Interface

Status: ADR-014 Accepted; T040-T044/A017 complete offline.

External execution status: blocked.

## Boundary

`cex_quant.applications.carry` owns economic application identity, lifecycle,
hedge interpretation, recovery proposals and policy. It reads immutable public
views from Market State, Features, Portfolio, Risk, OMS and Accounting.

It does not own or mutate those domains. In particular, Carry cannot:

- issue an `ExecutionActionPermit`;
- create a child `OrderRequest`;
- mutate an OMS `OrderGroup`;
- post, allocate or reconcile a financial fact;
- call an Execution gateway or venue adapter.

## Public Packages

`cex_quant.applications.carry` exports stable generic Carry contracts:

- `ApplicationPositionId`, `CarryPairId`, `CarryOwnershipId`;
- `CarryLifecycle`, `CarryHedgeState`, `CarryFinancialState`;
- `CarryPositionView`, `CarryLegOwnership`, `CarryHedgeAssessment`;
- immutable application facts and recovery proposals;
- pure Portfolio-derived hedge and Accounting-derived finality assessment.

Mutable journal and aggregate implementations remain explicit internal
imports from `carry.journal` and `carry.state`; they are not re-exported as
cross-domain contracts.

`cex_quant.applications.carry.funding_arbitrage` exports the first application:

- `FundingCarryPair` and exact base/instrument quantity conversion;
- entry and position Snapshot contracts plus semantic assembler;
- versioned Feature and economic policies;
- registered open, close, rebalance and recover Objective Types;
- `FundingCarryStrategy`, which emits generic `BasketTargetIntent` only.

## State Dimensions

Carry deliberately maintains three orthogonal dimensions:

```text
economic lifecycle:
  PROPOSED -> OPENING -> ACTIVE -> CLOSING -> CLOSED
                \          \          \
                 -> RECOVERY_REQUIRED -> HALTED

hedge assessment:
  UNKNOWN | UNHEDGED | PARTIALLY_HEDGED | HEDGED

financial finality:
  NOT_READY | PROVISIONAL | RECONCILED
```

OMS execution state does not determine `HEDGED`; authoritative Portfolio
effective positions do. Physical `CLOSED` does not imply financial
`RECONCILED`; that requires complete ADR-013 evidence.

## Snapshot Contract

`FundingCarrySnapshotAssembler` consumes one exact ADR-009 observation set:

- Spot and perpetual executable L1 views;
- perpetual mark, index and authoritative `FundingView`;
- READY Portfolio positions and perpetual margin scope;
- registered Funding Carry Feature snapshot;
- for position decisions only, the Carry position plus bounded Risk directive
  and Order Group read views.

It rejects missing, duplicate, stale, wrong-type, wrong-instrument,
wrong-account, wrong-scope or wrapper/source-time-inconsistent evidence.

## Decision Contract

The pure policy may produce a new absolute economic target:

```text
DecisionSnapshotPublication[FundingCarryDecisionSnapshot]
  -> FundingCarryStrategy
  -> BasketTargetIntent
```

An entry target is positive Spot base exposure plus offsetting negative
perpetual base exposure. A normal exit restores the immutable leg baselines.
The output carries no plan, child-order, retry, permit or venue field.

Recovery that changes exposure is also a fresh `BasketTargetIntent` caused by
a fresh Snapshot. A `CarryRecoveryProposal` is an economic preference only;
ADR-012 must still authorize it and ADR-011 must still control execution.

## Runtime Gate

`CarryApplicationRuntime` composes `SnapshotCoordinator` and
`StrategyRuntime`. It may record offline Basket evidence, then returns:

```text
BASKET_RECORDED_EXTERNAL_BLOCKED
external_execution_blocked = true
```

Its constructor exposes no Risk, OMS, permit, Execution or venue port. No
ADR-014 offline success authorizes Funding execution, grouped submission,
Testnet or production.
