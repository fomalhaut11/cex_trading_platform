---
id: AI-20260727-003
title: Codex Architecture Capacity Review for Funding Arbitrage
origin: codex
status: REVIEWED
created: 2026-07-27
code_baseline: 97d10e33f8d69c2535a542bee9f095aec1c312b9
supersedes: none
related:
  - 10_web_gpt_input.md
  - references/related_architecture.md
external_share: allowed
sensitivity: public-project
---

# Funding Arbitrage Architecture Capacity Review

## 1. Verdict

**Current architecture has a sound single-instrument foundation, but it does not yet safely support
live two-leg funding arbitrage.**

The project can already represent Spot and Perpetual instruments, normalize funding events, deliver
multiple declared scopes to one strategy, enforce an independent fail-closed Risk boundary, create
and recover individual orders, and execute Spot/USD-M/COIN-M requests.

However, the following capabilities are absent:

- a coherent cross-instrument and account-state decision snapshot；
- strategy/application-level carry position ownership；
- portfolio-wide basket intent and basket risk decision；
- durable parent-child OMS state；
- preflight approval of every leg before the first submission；
- legging, compensation and hedge-timeout recovery；
- live Binance balance/position/margin event integration；
- funding cash-flow, fees and strategy PnL attribution；
- liquidation and margin-risk models。

Therefore:

- offline signal prototyping on recorded data: **possible after a small read-model extension**；
- unattended Testnet execution: **not yet acceptable**；
- production or real-money execution: **not authorized**。

## 2. Capability Matrix

| Capability | Status | Evidence-based finding |
|---|---|---|
| Canonical Spot and Perpetual instruments | YES | `InstrumentKind`, `Instrument`, `PerpetualSpecification` exist with exact product metadata |
| Funding market event | YES | `FundingRateUpdate` is canonical, validated, recorded/replayed and delivered to strategies |
| Spot/perpetual market prices | PARTIAL | L1/order-book and mark/index events exist, but no unified multi-market read model exists |
| Multi-scope strategy input | PARTIAL | `StrategyRuntime.accepted_scopes` allows declared scopes, but inputs arrive one at a time |
| General Event Bus | NO, by design | Core runtime uses synchronous direct calls; typed events do not imply a generic bus |
| Correlated market/account snapshot | NO | No immutable carry vector with per-input timestamps, quality and coherence rules |
| Account/position canonical state | PARTIAL | `AccountState` exists per `(venue, account)`, but live Binance private streams currently process order updates only |
| Strategy-level carry position | NO | No aggregate linking spot/perp legs, expected carry, hedge state or lifecycle |
| Multiple intents from one strategy decision | YES | A strategy callback may return a tuple of `PositionTargetIntent` values |
| Atomic basket risk evaluation | NO | Risk evaluates each instrument intent independently |
| Composite/parent-child OMS | NO | One approved intent produces one `OrderRequest`; no parent or child identity exists |
| Safe two-leg submission | NO | Current pipeline approves, creates and submits each intent sequentially |
| Individual-order idempotency/recovery | YES | OMS journal, restart replay, query and user-stream reconciliation exist |
| Basket recovery/compensation | NO | No durable group state or hedge-repair policy exists |
| Independent Risk boundary | YES | Strategy cannot call OMS/Execution through the standard assembly; Risk is mandatory |
| Portfolio/basket risk model | NO | Current limits and context are instrument-level |
| Margin/liquidation model | NO | Portfolio design explicitly excludes margin and liquidation calculation |
| Funding/fee/PnL attribution | NO | Only venue-supplied realized PnL and cost basis are stored; no cash-flow ledger exists |
| Execution adapters for individual legs | YES | Spot, USD-M and COIN-M request mapping and authenticated execution exist |
| Production-ready funding arbitrage | NO | Required state, basket safety, accounting and external acceptance are missing |

## 3. Important Correction: Typed Events Are Not an Event Bus

The codebase is event-oriented at its domain boundaries, but it does not contain a general internal
event bus. The deterministic core currently calls:

```text
health
  -> validation
  -> market state
  -> features
  -> strategy
  -> portfolio read
  -> risk
  -> OMS
  -> execution
```

for one `MarketEvent` at a time.

This is not a defect by itself. Funding arbitrage does not require introducing a generic pub/sub bus
into the hot path. A general bus could weaken ordering and ownership guarantees.

The required abstraction is instead an application-owned, deterministic **correlated read model**:

```text
Spot L1/mark state ---------+
Perpetual mark/index state -+
Funding state --------------+--> CarrySnapshotAssembler
Account/position snapshots -+          |
Health/clock state ---------+          v
                                  CarrySnapshot
```

Each source remains single-writer. The assembler consumes immutable views and publishes one
immutable snapshot with explicit source timestamps, quality and freshness.

`MarketStateUpdatedEvent` and `PortfolioStateChangedEvent` should only be introduced if a concrete
consumer and ordering contract require them. They should not be invented as generic notification
objects while the true need is a coherent snapshot.

## 4. Current Multi-Market Support

`StrategyRuntime` supports an explicit `accepted_scopes` set. This means one strategy instance can
legitimately receive both Spot and Perpetual inputs in a deterministic caller-provided order.

That is necessary but insufficient:

- each callback receives one market event or one feature snapshot；
- `OnlineFeatureEngine` owns one explicit scope, normally one instrument；
- `FeatureSnapshot` is scalar-feature state for one scope；
- the concrete pipeline has one `MarketStatePort` and one `FeaturePort`；
- no router assembles multiple market-state engines into a coherent portfolio view；
- no maximum cross-leg timestamp skew is defined；
- no rule states which Spot and Perpetual observations may be combined。

Funding rate normalization is already present, but there is no authoritative funding-state view that
joins the latest rate and next funding time with Spot/Perpetual price state.

The concrete market-state engines currently accept L1, partial-depth or reconstructed-depth inputs.
There is no concrete router/state owner that can pass `FundingRateUpdate`, mark and index updates
through the complete `TradingApplication` as one multi-product state graph. The canonical event
contract is ready; the production composition is not.

### Required read-model contract

The first design should define a venue-neutral snapshot similar to:

```text
CarrySnapshot
  pair_id
  spot_instrument_id
  perpetual_instrument_id
  spot_price + as_of_ns + quality
  perpetual_mark_or_executable_price + as_of_ns + quality
  funding_rate + next_funding_time_ns + as_of_ns + quality
  account_snapshot_refs
  spot_position
  perpetual_position
  available_collateral
  margin_health
  clock_health
  assembled_at_ns
  maximum_source_skew_ns
  overall_quality
```

The snapshot must fail closed when a required component is absent, stale, from the wrong account,
or outside the allowed cross-source skew.

Basis, annualized expected funding, transaction-cost estimate and expected net carry are registered
Features. Positions, balances and margin are State. `CarrySnapshot` is an application read model
combining references to both; it is not raw market data and should not be disguised as one scalar
Feature.

## 5. Where the Carry Engine Should Live

Do not put the implementation in `cex_quant.strategy.funding`.

The existing `cex_quant.strategy` package is generic runtime infrastructure and public intent
contracts. A concrete funding strategy would mix application policy with infrastructure.

Recommended placement:

```text
src/cex_quant/applications/carry/
  __init__.py
  model.py          # CarryPair, CarryPosition, lifecycle and identifiers
  snapshot.py       # correlated immutable read model
  features.py       # registered basis/carry feature definitions
  strategy.py       # pure strategy policy
  risk.py           # carry-specific risk policy plugged into central boundary
  orchestration.py  # parent intent lifecycle; no venue payloads
```

Dependency direction:

```text
applications.carry
  -> core / instruments / market_data public facts
  -> features public contracts
  -> strategy public contracts
  -> portfolio immutable snapshots
  -> risk public decision contracts
  -> OMS basket contracts

runtime
  -> assembles applications.carry with concrete state and adapters
```

`applications.carry` must never import a Binance adapter. Instrument pairing is explicit metadata,
not inferred from symbol text. This also allows later reuse for cross-venue carry and dated-future
basis strategies.

## 6. Strategy-Level Carry Position Ownership

The current `AccountState` is canonical venue/account truth. Its `Position` represents one
instrument and intentionally does not calculate mark-to-market, margin or liquidation.

It must remain authoritative for actual venue holdings.

A new `CarryPosition` should be an **application aggregate**, not a replacement for canonical
portfolio positions:

```text
CarryPosition
  carry_position_id
  strategy_id
  pair_id
  parent_intent_id
  spot_target / actual / child_order_ids
  perpetual_target / actual / child_order_ids
  lifecycle
  opened_at_ns
  expected_carry_snapshot_ref
  recovery_reason
```

Suggested lifecycle:

```text
PROPOSED
  -> APPROVED
  -> OPENING
  -> HEDGED
  -> REBALANCING
  -> CLOSING
  -> CLOSED

OPENING / REBALANCING / CLOSING
  -> IMBALANCED
  -> RECOVERY_REQUIRED
  -> HALTED
```

The aggregate records strategy intent and reconciliation status. Actual quantities must always be
derived or reconciled from OMS fills and canonical account positions. It must not become a second
independent mutable source of venue position truth.

This state needs durable recovery because a process restart during the interval between leg fills is
one of the highest-risk scenarios.

## 7. OMS Finding: Multiple Intents Are Not a Composite Order

The strategy runtime can return multiple `PositionTargetIntent` objects, but the current pipeline
loops over them as follows:

```text
for each intent:
  build risk context
  evaluate risk
  create one OMS order
  immediately submit that order
```

Consequences:

1. Leg A may be submitted before Leg B has passed Risk.
2. Leg A may fill before Leg B order construction fails.
3. A rejection on Leg B returns a rejected pipeline result after Leg A has already reached the venue.
4. Individual order journals can recover Leg A and Leg B, but no durable parent object knows whether
   the carry position is hedged.
5. There is no basket idempotency key, parent lifecycle, hedge timeout or compensation command.

Therefore current OMS does **not** support composite orders.

### Required contracts

The design should introduce venue-neutral contracts along these lines:

```text
PortfolioTargetIntent
  parent_intent_id
  strategy_id
  tuple[PositionTargetLeg, ...]
  decision_time_ns
  valid_until_ns
  hedge_policy_ref

PortfolioRiskDecision
  parent_intent_id
  ALLOW / REJECT
  approved_legs
  projected_portfolio_exposure
  risk_constraints

OrderGroup
  order_group_id
  parent_intent_id
  child_order_ids
  lifecycle
  durable execution/recovery facts
```

All legs must pass identity, freshness, balance, margin and portfolio-risk preflight before any child
is submitted. Cross-market execution cannot be truly atomic, so “composite” means a durable logical
transaction with explicit legging policy, not an atomic exchange primitive.

The execution coordinator must define:

- simultaneous versus maker-first/taker-hedge policy；
- maximum unhedged delta；
- hedge timeout；
- partial-fill sizing；
- whether to complete, resize, cancel or unwind；
- behavior when one child is in unknown execution state；
- restart reconciliation before any new child order；
- operator halt and manual recovery boundary。

Execution adapters remain single-order venue adapters. Parent-child coordination belongs above them
and below the strategy, under OMS/runtime ownership.

## 8. Risk Finding

Risk is structurally independent today:

- the standard runtime requires a `RiskPort`；
- strategy output is venue-neutral；
- risk rejection stops OMS and execution；
- the strategy package does not own adapters。

This is a strong foundation.

But current `RiskContext` is one-instrument context containing one current strategy position, one
global position, one reference price, feature freshness, clock health and intent-rate counts.
Notional aggregation is explicitly not cross-asset. The engine cannot evaluate a Spot/Perpetual
basket as one proposed portfolio transition.

Required extensions:

- projected net delta after all legs；
- gross and net notional in a common valuation asset；
- basis and basis-stress loss；
- expected funding and funding-reversal threshold；
- available collateral, initial/maintenance margin and liquidation distance；
- maximum legging exposure and duration；
- fee and slippage reserve；
- concentration across carry positions；
- stale/missing account-state rejection；
- post-trade continuous limits。

Funding arbitrage needs two risk layers:

1. **Pre-trade portfolio risk** approves or rejects the whole proposed basket before submission.
2. **Continuous carry risk supervision** monitors the open aggregate and may request rebalance,
   reduce-only close or operator halt.

The continuous supervisor still cannot submit orders directly. It emits a risk action that returns
through the same OMS boundary.

## 9. Account, Margin and Accounting Finding

The canonical `AccountState` is useful but insufficient:

- it stores exact balances and per-instrument positions；
- it stores venue-supplied cost basis and realized PnL；
- it does not calculate margin, mark-to-market, liquidation or collateral conversion；
- the current Binance private stream processor accepts order events and ignores other event types；
- no live adapter was found that converts Binance balance/position account events into
  `AccountUpdate`；
- no funding-payment or fee ledger exists；
- no strategy attribution model exists。

Before Funding Arbitrage can be validated, add:

- Binance Spot balance update normalization；
- Binance Futures `ACCOUNT_UPDATE` balance/position normalization；
- REST account snapshot bootstrap and reconciliation；
- margin/collateral snapshot contracts；
- cash-flow ledger entries for trade cash flow, commissions, funding, transfer and adjustment；
- mark-to-market valuation；
- attribution by strategy, carry position, instrument and cash-flow type；
- realized/unrealized/basis/funding/fee decomposition。

Funding APR without fee, slippage, borrow cost, margin usage and actual funding cash flow is an
estimate, not verified strategy PnL.

## 10. Recommended Architecture Decisions Before Coding

Create and approve ADRs before implementation:

1. **Application Strategy Boundary**
   - establish `applications/` and dependency rules；
   - distinguish application aggregates from canonical Portfolio truth。
2. **Correlated Multi-Scope Snapshot**
   - define source ownership, timestamps, maximum skew, quality and deterministic assembly；
   - explicitly reject a generic unbounded event bus。
3. **Portfolio/Basket Intent and Risk**
   - define whole-basket approval before submission；
   - preserve mandatory central Risk。
4. **OMS Parent-Child Order Groups**
   - define durable lifecycle, idempotency, partial fill, unknown state and restart recovery。
5. **Account, Margin and Cash-Flow Ledger**
   - define authoritative inputs, valuation asset, funding/fee records and PnL attribution。
6. **Carry Pair Metadata**
   - explicitly map Spot and Perpetual instruments, contract multipliers and hedge ratios；
   - prohibit symbol-string inference。

The name “Carry Arbitrage Engine” is acceptable as an application domain, but it should not become a
new bypass around Feature, Risk, OMS or Execution.

## 11. Phased Implementation Plan

### Phase C0 — Design and offline data readiness

- approve the six decisions above；
- define CarryPair and exact hedge-ratio semantics；
- add account/funding/fee fixtures and replay datasets；
- define safety invariants and acceptance criteria。

### Phase C1 — Read-only carry observation

- add multi-scope state routing and `CarrySnapshotAssembler`；
- register basis, annualized funding and expected net carry features；
- implement a read-only carry strategy that emits no orders；
- prove deterministic replay and stale/skew rejection。

### Phase C2 — Portfolio and accounting truth

- connect Binance account balance/position streams and REST bootstrap；
- add margin/collateral snapshot；
- add cash-flow ledger and PnL attribution；
- reconcile all state across restart。

### Phase C3 — Basket intent and risk

- add `PortfolioTargetIntent` and portfolio projection；
- evaluate all legs as one decision；
- add delta, basis, funding reversal, margin, liquidation and legging limits；
- keep submission disabled。

### Phase C4 — Durable parent-child OMS

- add order-group journal and recovery；
- preflight every leg before first submission；
- implement partial-fill and unknown-state recovery；
- add deterministic failure injection tests。

### Phase C5 — Offline end-to-end acceptance

- replay normal entry/exit；
- test every asymmetric leg outcome；
- test disconnect, timeout, duplicate, restart and stale state；
- require zero unintended new orders after an unknown state。

### Phase C6 — Testnet

- use dedicated Testnet credentials injected outside Git；
- execute small, bounded scenarios；
- verify account, order, funding and PnL reconciliation；
- run supervised soak and operator recovery。

Passing C6 may authorize a production-readiness review. It does not itself authorize real-money
trading.

## 12. Minimum Acceptance Scenarios

At least the following scenarios are required:

1. deterministic Spot/Perpetual/Funding replay produces the same carry snapshots and decisions；
2. stale Spot, stale Perpetual, stale funding, stale account or unhealthy clock each fail closed；
3. source timestamp skew above the configured bound prevents entry；
4. all legs are risk-approved before any `submit` call；
5. second-leg risk rejection causes zero submitted children；
6. first leg partial fill sizes the hedge from actual fill, not requested quantity；
7. second-leg submission failure triggers the specified recovery policy；
8. unknown state blocks retry until venue reconciliation；
9. restart between child submissions reconstructs the parent and does not duplicate either child；
10. private-stream gap closes trading and forces REST reconciliation；
11. funding-rate sign reversal triggers the configured exit/reduction policy；
12. basis shock and margin deterioration trigger continuous risk action；
13. operator HALT prevents every new child while allowing explicitly approved reduce-only recovery；
14. fees and funding payments reconcile to the cash-flow ledger；
15. strategy PnL attribution equals the sum of trade, mark, fee and funding components；
16. different event arrival orders within the declared ordering contract remain deterministic；
17. bounded queues and retained state remain bounded during burst and soak；
18. no credential appears in logs, reports, journals or Git history。

## 13. Direct Answers to the Web GPT Questions

1. **Does current architecture support the abstraction?**

   Partially. The boundaries are appropriate, but essential portfolio and basket capabilities are
   missing.

2. **Where should Carry Engine live?**

   In `cex_quant.applications.carry`, depending only on public domain contracts and assembled by
   `runtime`.

3. **Is existing State sufficient?**

   No. Venue/account truth exists, but correlated carry snapshots, strategy aggregates, live account
   ingestion, margin and ledger state are missing.

4. **Does OMS support multi-leg orders?**

   No. Multiple intents are processed sequentially as unrelated individual orders.

5. **What modules need modification?**

   `strategy` contracts, `risk` contracts/engine, `oms` model/journal/service, `runtime` routing and
   orchestration, `portfolio` account integration and accounting, `features` multi-scope support,
   Binance private account adapters, plus a new `applications.carry` package.

## 14. Questions Returned for Architecture Review

Web GPT should review:

1. Is `applications.carry` the right ownership boundary, or should the application aggregate have a
   more generic `portfolio_construction` parent package?
2. Should the first basket contract be generic from day one, or introduced as carry-specific and
   generalized after one proven use case?
3. Which legging policy is the first supported policy: simultaneous taker, maker-first with taker
   hedge, or strictly one limited Testnet mode?
4. What is the authoritative hedge metric for linear USDT-margined carry: base quantity, contract
   delta or quote notional?
5. Which margin and liquidation model is required for the first Testnet milestone?
6. Should funding cash flow be sourced from income-history REST, private events, or both with
   reconciliation?
7. Which states require durable journals versus rebuild from canonical OMS/account evidence?

## 15. Review Boundary

This review inspected the repository at commit
`97d10e33f8d69c2535a542bee9f095aec1c312b9`. It proposes no source-code change and grants no
production authorization. The next valid step is architecture review and resolution, not direct
strategy implementation.
