# BTC Funding Carry Fast-Track MVP Plan

Status: active delivery plan.

Effective date: 2026-07-30.

Planning baseline: `0123b6322de80f9fb488b92942ef19b31cdd6512`.

Demo authorization: not yet granted.

Real-money authorization: not granted.

## Objective

The sole active product objective is:

> close the first Binance single-account BTC Funding Carry loop with bounded
> real capital as quickly as safety and evidence allow.

Target loop:

```text
real-time market/account evidence
  -> Funding Carry Application
  -> BasketTargetIntent
  -> Portfolio Risk
  -> OMS Order Group
  -> Binance Spot + linear perpetual
  -> execution/account reconciliation
  -> Portfolio
  -> Accounting Ledger
  -> Funding / fee / trading PnL
  -> Carry lifecycle, hedge and financial state
```

This is a scope reduction, not a kernel downgrade.

## Delivery Policy

Keep all implemented capabilities and historical plans. Do not delete or
weaken them merely to simplify the MVP.

Active effort allocation:

```text
70%  Execution Promotion and closed-loop reliability
20%  minimal operations, monitoring, shadow and runbooks
10%  documentation, evidence and status synchronization
```

Do not open a new ADR unless a reproducible closed-loop defect cannot be fixed
behind the Kernel v1 interfaces.

## MVP Scope

Enabled product scope:

- Binance only;
- Spot and USD-M linear perpetual only;
- BTC only;
- one dedicated account;
- fixed configured quantity;
- explicit maximum gross notional and loss envelope;
- manual application start;
- operator-controlled stop of new exposure;
- no automatic capital allocation;
- no multi-symbol, multi-account or multi-venue behavior.

Existing generic modules remain in the repository but are disabled by
configuration when outside this envelope.

## Configure, Do Not Delete

### Accounting

Retain the generic ADR-013 ledger, allocation, valuation and reconciliation
contracts.

MVP configuration uses:

- dedicated account ownership;
- trade settlement;
- commission/fee;
- actual Funding settlement;
- realized/marked net PnL.

Dedicated ownership makes allocation simple; it does not justify deleting the
generic allocation model.

### Portfolio Risk

Retain the generic ADR-012 engine and safety contracts.

MVP policy emphasizes:

- account and instrument position limits;
- maximum gross notional;
- margin and liquidation inputs;
- net BTC Delta/residual;
- maximum unhedged quantity and duration;
- price/position/margin freshness;
- clock, health, permit and reservation validity;
- operator halt.

Do not add VaR or speculative new models. Do not disable existing fail-closed
health and authorization checks.

### Execution

Retain venue-neutral child-order contracts and existing adapters.

The active deployment enables only Binance Spot and USD-M linear perpetual.
No Funding-specific branch may enter OMS or the Execution adapter.

## Active Sequence

```text
Kernel v1 freeze
    |
T045  Execution Promotion Composition Audit
    |
T046  Mode-neutral offline execution runtime + fault harness
    |
A018  Offline Execution Acceptance
    |
A019  Binance grouped Demo acceptance
    |
T050  Funding Carry Live Operations Lite + Shadow
    |
A020  Funding Carry MVP Live Readiness
    |
A021  Controlled Micro-Live Acceptance
```

T045, T046 and A018 are complete. A019 is the next promotion gate, but remains
external and unauthorized.

## T045 - Composition Audit

Status: complete. Evidence:
`development/t045_execution_promotion_composition_audit.md`.

T045 completed the current-code audit before implementation:

- exact Basket-to-Risk admission path;
- Basket approval to `OrderGroupId` identity binding;
- execution-plan and next-action ownership;
- exact permit request, validation and durable consumption;
- child outcome routing to OMS;
- Portfolio/account reconciliation;
- authenticated financial-fact routing to Accounting;
- Carry read-side lifecycle/hedge/financial transitions;
- one runtime writer and restart order;
- smallest set of missing composition seams.

Output:

- call/dependency map;
- identity/causation map;
- state-writer table;
- happy/failure/restart sequence matrix;
- bounded T046 implementation tasks;
- confirmation that Kernel v1 remains unchanged or evidence for a narrowly
  scoped defect correction.

## T046 and A018 - Offline Closed Loop

T046 uses a deterministic, fault-injectable in-memory Execution port.

T046 implementation is complete and recorded in
`development/t046_offline_execution_runtime.md`. A018 is accepted at tested
code baseline `b7c99af127ae04b51fa9459df8d2d30297d53635`; its complete
restart/fault matrix and promotion handoff are recorded in
`development/a018_offline_execution_acceptance.md`.

Required scenarios:

- both legs fill and Carry becomes `ACTIVE/HEDGED`;
- either leg rejects after the other fills;
- partial fill on either side and signed residual exposure;
- timeout-after-send creates UNKNOWN with no blind retry;
- cancel failure;
- permit expiry/invalidation;
- position or margin change while opening;
- operator halt;
- restart at every non-terminal boundary;
- Portfolio and Accounting evidence arriving in different orders;
- Funding reversal creates a normal close Basket;
- physical close remains distinct from financial reconciliation.

A018 passed complete regression, branch coverage and the frozen-boundary
audit. External I/O remains blocked.

## A019 - Binance Grouped Demo

Status: external and unauthorized until separately approved.

Scope:

- dedicated Binance Demo account;
- BTC Spot and BTC USD-M linear perpetual;
- fixed bounded quantity;
- manual start;
- submit/query/cancel;
- REST/private-stream reconciliation;
- duplicate and timeout/UNKNOWN recovery;
- no production endpoint or credential.

A019 proves protocol, identity, durable recovery and Accounting integration.
It does not prove production economics or authorize real money.

Prerequisites:

- A018 accepted;
- ADR-013 final implementation acceptance;
- explicit project-owner Demo authorization;
- user-provided Demo credentials through `BinanceCredentialProvider`;
- healthy persistent clock evidence;
- approved Demo account, symbols, quantity and maximum notional;
- working operator halt and recovery procedure.

## T050 - Live Operations Lite and Shadow

T050 reuses the existing T021-T024 health, operator and authenticated-control
foundation. It does not build a general dashboard platform.

Minimum operational view:

```text
Position
  Spot quantity
  perpetual quantity
  residual BTC Delta
  Carry lifecycle / hedge state

Risk
  gross notional
  margin and liquidation references
  active reservations/permits
  unhedged quantity and age

Execution
  active Order Group
  child states
  UNKNOWN / recovery status

Accounting
  trade PnL
  actual Funding
  fees
  net PnL
  reconciliation state

Health
  market/account freshness
  clock
  private stream / REST
  storage/journals
  operator authority
```

Minimum operator action:

```text
STOP ALL NEW EXPOSURE
```

The first surface may be a local CLI/TUI or localhost-only page. Do not add a
public web dashboard, user-management platform or broad analytics system.

Shadow mode:

```text
live market/account read evidence
  -> normal Snapshot / Carry / Basket / Risk / OMS decision path
  -X-> external submit
```

Shadow evidence must show that production data produces coherent decisions,
bounded Risk behavior and no unexpected application transitions before
real-money authorization.

## A020 - Funding Carry MVP Live Readiness

Status: planned; does not authorize a trade.

A020 requires a written and machine-enforced trading envelope:

- exact dedicated account;
- exact Spot/perpetual instruments;
- fixed base quantity;
- maximum gross notional;
- maximum loss;
- minimum margin headroom;
- maximum BTC residual and unhedged duration;
- allowed order types;
- price/slippage bounds;
- maximum retries and explicit UNKNOWN behavior;
- start/stop authority;
- halt/reset authority;
- storage and journal locations;
- rollback and incident contacts/procedure.

Required evidence:

- A019 accepted;
- stable shadow run;
- healthy clock, market, account and private-stream state;
- kill switch exercise;
- restart/recovery exercise;
- Ledger backup and reconciliation check;
- no production credential in source, logs or recorder;
- explicit go/no-go checklist signed by the project owner.

## A021 - Controlled Micro-Live Acceptance

Status: external and unauthorized.

A021 starts only after the project owner explicitly approves:

- real-money endpoint;
- account;
- instruments;
- exact quantity/notional;
- maximum loss;
- operating window;
- named operator;
- abort criteria.

First acceptance objective:

1. manually authorize one bounded open;
2. reconcile both legs and Portfolio hedge state;
3. observe actual fees and, when available within the approved operating
   window, authenticated Funding settlement;
4. reconcile Ledger and PnL;
5. close to proven baselines;
6. verify no unexplained balance or position difference;
7. halt new exposure and archive evidence.

If Funding settlement is not observed during the first bounded window, the
system may validate execution/fee/PnL mechanics, but must not claim Funding
income acceptance.

Production automation and scaling remain blocked after A021 until a separate
review.

## Deferred Post-MVP Work

Retained but removed from the active queue:

- T047 Application Runtime / SDK Lite;
- T048 Historical Event Replay platform;
- T049 Paper Exchange and general Fill Model;
- CTA;
- cross-venue arbitrage;
- multi-account operation;
- option execution applications;
- high-frequency Market Making;
- general dashboard/platform UI;
- automatic capital optimization.

Minimal fault injection and Shadow required by A018/A020 are not the deferred
general Paper/Replay platform.

## Operating Timeline

Planning targets, not delivery guarantees:

```text
Weeks 1-4  T045/T046/A018 and Demo readiness
Next gate  A019 after external authorization and credentials
Weeks 5-6  T050/A020 live operations and Shadow readiness
Next gate  A021 only after explicit real-money go/no-go
```

Network, credentials, venue behavior, host clock and unresolved recovery
evidence may extend the schedule. No date pressure waives a safety gate.

## Fast-Track Completion

The MVP proves platform value when one bounded BTC Funding Carry cycle has:

- real exchange fills;
- reconciled Spot/perpetual positions;
- accepted hedge state;
- actual fee and Funding evidence where observed;
- balanced Ledger and explainable PnL;
- successful close/recovery;
- archived operator, Risk, OMS, Portfolio and Accounting evidence.

This milestone is the first road test, not general production completion.
