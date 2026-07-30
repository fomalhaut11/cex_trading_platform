# Platform Delivery Plan

Status: approved development sequence; implementation not started.

Effective date: 2026-07-30.

Planning baseline: `d1e24c0c89e8cf0a2addaf6e843b969c230da5e2`.

Production authorization: none.

Testnet grouped execution authorization: none.

## Mission Shift

The institution-oriented trading kernel is implemented through its bounded
offline gates. The next project objective is:

> enable a researcher to move one application through coherent research,
> deterministic execution rehearsal, Testnet protocol validation and
> reconciled PnL using the same economic policy and platform contracts.

Future effort allocation target:

```text
30%  kernel maintenance driven by real defects and measured bottlenecks
70%  application platform, replay, simulation and operating-loop delivery
```

This plan supersedes speculative kernel expansion as the default roadmap.

## Stable Architecture

```text
Applications
    |
ADR-014 Carry
    |
BasketTargetIntent
    |
ADR-012 Portfolio Risk
    |
ADR-011 OMS Order Group
    |
Execution
    |
Portfolio + ADR-013 Ledger
    |
Application assessment
```

The architecture is complete enough to begin runtime closure. It is not yet a
complete Testnet or production trading loop.

## Cross-Mode Principle

The same pure economic policy and intent contracts should run across:

```text
Historical Replay
Paper Execution
Testnet
Production
```

This does not mean all modes share identical clocks, data sources, execution
models or orchestration. Mode-specific adapters provide evidence and side
effects; applications must not inspect a mode flag to change economic logic.

The platform must never silently substitute:

- simulated fills for venue facts;
- expected Funding for authenticated settlement;
- OMS acknowledgement for Portfolio position truth;
- replay time for live operator/clock authority.

## Phase 0 - Kernel v1 Compatibility Freeze

Status: active.

Authoritative policy:

`architecture/kernel_v1_freeze.md`

Frozen areas:

- ADR-009 Snapshot;
- ADR-010 Basket;
- ADR-011 OMS execution control;
- ADR-012 Portfolio Risk;
- ADR-013 implemented Accounting contracts;
- ADR-014 Carry boundary.

Allowed changes are defect, security, recovery and evidence driven. Strategy
specialization inside the kernel and speculative ADR expansion are prohibited.

Exit condition:

- freeze rules are referenced by architecture and development documents;
- no active task depends on a speculative kernel redesign.

## Phase 1 - Execution Promotion

Status: next credential-free development phase.

### T045 - Composition Audit

T045 is an evidence-backed current-code audit before implementation. It must
answer:

1. how a `BasketTargetIntent` enters whole-Basket Risk admission;
2. who creates and durably binds `OrderGroupId`;
3. who chooses the next exact `ExecutionAction`;
4. who requests, validates and consumes its permit;
5. how child outcomes update OMS, Portfolio and Accounting independently;
6. how Carry observes those immutable views and changes application state;
7. where one runtime writer serializes the complete sequence;
8. which missing seam, if any, requires code rather than composition.

Deliverables:

- exact call/dependency map against current source;
- identity and causation map;
- state-writer ownership table;
- action/failure sequence diagrams;
- gap classification:
  - A. implementation defect;
  - B. missing composition;
  - C. external-promotion dependency;
  - D. non-blocking optimization;
- bounded T046 implementation plan.

T045 does not modify kernel interfaces or enable external I/O.

### T046 - Mode-Neutral Offline Execution Runtime

T046 implements only the composition proven necessary by T045.

The minimum runtime ports are conceptually:

```text
Application Intent Port
Portfolio Risk Port
Order Group Port
Execution Port
Portfolio/Accounting Evidence Ports
```

The first adapter is a deterministic fault-injection Execution port, not
Binance and not a full Paper Exchange.

Required scenarios:

- Spot `+10`, perpetual `-10` reaches Carry `ACTIVE/HEDGED`;
- Spot filled, perpetual rejected reaches
  `RECOVERY_REQUIRED/PARTIALLY_HEDGED`;
- perpetual filled, Spot partial reports the opposite signed residual;
- timeout-after-send creates UNKNOWN and no blind retry;
- permit expiry/invalidation prevents the action;
- position or margin change during opening triggers current Risk handling;
- operator halt blocks new exposure;
- restart at every non-terminal state reconstructs OMS, Portfolio, Carry and
  Ledger evidence;
- financial facts arriving before or after position reconciliation preserve
  physical/financial state separation;
- Funding reversal creates a new normal close Basket.

The runtime must be mode-neutral so A019 can replace only the Execution and
external evidence adapters. It must not contain a Funding branch.

### A018 - Offline Execution Acceptance

A018 passes only when:

- every scenario above is deterministic and restart-safe;
- UNKNOWN is reconciled before retry;
- the external route remains blocked;
- no kernel ownership changes;
- branch coverage and existing CI gates pass;
- a self-contained Testnet readiness handoff is produced.

Output:

```text
A018 Offline Execution Acceptance
Testnet go/no-go request
```

## Phase 2 - Minimal Binance Testnet Loop

Status: external and unauthorized.

Task:

`A019 Authenticated Grouped Binance Testnet Acceptance`

Initial bounded scope:

- Binance Spot;
- Binance linear perpetual;
- BTC only;
- one dedicated Testnet account;
- fixed quantity and explicit maximum notional;
- manual start;
- no capital optimizer;
- no multi-symbol or multi-venue automation.

Target loop:

```text
Funding Snapshot
  -> Carry policy
  -> Basket
  -> Portfolio Risk
  -> OMS Order Group
  -> Binance Testnet
  -> REST/private-stream reconciliation
  -> Portfolio
  -> Accounting Ledger
  -> Carry hedge/financial state
```

Required prerequisites:

- A018 accepted;
- ADR-013 final implementation acceptance;
- explicit project-owner Testnet authorization;
- Testnet credentials through `BinanceCredentialProvider`;
- approved account, instruments, quantity and limits;
- persistent healthy host/venue clock;
- kill switch and authenticated operator boundary;
- restart, UNKNOWN, cancel and reconciliation runbook;
- no production endpoint or credential.

A019 validates protocol, identity, recovery and Accounting integration. It
does not prove strategy profitability or production readiness.

Output:

```text
Funding Carry MVP v1 Testnet evidence
```

## Phase 3 - Application Runtime / SDK Lite

Status: planned after the first closed-loop evidence.

Task:

`T047 Application Runtime / SDK Lite`

The user-facing name is `Application Runtime`, because the platform hosts more
than traditional single-instrument strategies.

Shared capabilities may include:

- typed Snapshot consumption;
- pure intent generation;
- Objective registration;
- immutable Market, Feature, Portfolio and Risk context views;
- lifecycle-independent health/readiness;
- deterministic evidence and replay hooks;
- runtime start/stop controls.

Illustrative API:

```python
on_start()
on_snapshot(snapshot)
on_position_change(position_view)
on_risk_event(risk_view)
on_stop()
```

Safety rules:

- only a fresh coherent Snapshot may cause a new exposure-changing Intent;
- `on_position_change` and `on_risk_event` may update state or request a new
  Snapshot, but cannot bypass causation;
- `context.risk` is an immutable view, not a callable permit service;
- every output remains a generic `DecisionIntent`;
- applications cannot call OMS or Execution.

Do not create:

```text
UniversalApplicationState
Carry-derived BaseApplication
```

The same interfaces may host independent families:

```text
applications/cta
applications/carry
applications/arbitrage
applications/options
applications/market_making
```

The existing `cex_quant.runtime` remains the physical composition root. A
future `cex_quant.platform` may be a facade; this phase does not move existing
packages.

First new SDK validation application:

`CTA`, because it tests the research/runtime interface with lower domain
complexity than another multi-leg application.

## Phase 4 - Event Replay

Status: planned.

Task:

`T048 Historical Event Replay`

Architecture:

```text
Recorded canonical evidence
  -> deterministic Replay clock/source
  -> State and Feature reconstruction
  -> Snapshot stream
  -> Application Runtime
  -> intent/evidence output
  -> performance analysis
```

Replay is not a dataframe shortcut. It reuses canonical event, state,
Snapshot and policy contracts.

Initial applications:

- CTA validates the simple single-leg research workflow;
- Carry validates correlated Snapshot and Basket behavior.

Acceptance:

- repeated runs produce identical identities and decisions;
- replay cannot use live credentials or external gateways;
- clock semantics are explicit;
- missing/corrupt source evidence fails closed;
- research output cannot be mistaken for authenticated ledger truth.

## Phase 5 - Paper Exchange

Status: planned after Replay.

Task:

`T049 Paper Exchange and Fill Model`

Initial execution behavior:

- market orders;
- limit orders;
- configurable latency;
- slippage;
- partial fill;
- reject, cancel and timeout/UNKNOWN injection;
- simulated fees and Funding with explicit provenance.

Architecture:

```text
Application Runtime
  -> normal Risk/OMS contracts
  -> Paper Execution adapter
  -> simulated venue facts
  -> simulated Portfolio/Accounting namespace
```

Paper facts must be labelled simulated and must not enter an authenticated
production ledger.

High-frequency queue-position modeling, advanced market impact and exchange
microstructure emulation are out of the first Paper scope.

## Strategy Delivery Order

Do not develop multiple new strategies in parallel.

1. Funding Carry remains the first complete platform-loop application.
2. CTA is the first new Application Runtime and Replay example.
3. Cross-venue arbitrage follows only after a Multi-Venue layer is justified.
4. Option applications reuse existing Feature-owned Greeks and volatility
   surfaces after their execution/accounting evidence exists.
5. High-frequency Market Making is last because it requires measured latency,
   Quote Session semantics and order-book performance work.

## Planned Task Sequence

```text
Phase 0  Kernel v1 freeze
    |
T045  Execution Promotion Composition Audit
    |
T046  Mode-neutral offline execution runtime + fault harness
    |
A018  Offline Execution Acceptance
    |
A019  Binance grouped Testnet acceptance
    |
T047  Application Runtime / SDK Lite
    |
T048  Historical Event Replay
    |
T049  Paper Exchange
```

A019 is present in the sequence but cannot start from this plan alone.

## Program-Level Completion Criterion

The project moves from “architecture project” to “operating trading platform”
when one application has:

1. deterministic historical/replay decisions;
2. offline fault-injected grouped execution evidence;
3. separately authorized Testnet submit/query/cancel/recovery evidence;
4. reconciled Portfolio state;
5. authenticated-style financial facts and balanced Ledger attribution;
6. application hedge/lifecycle/financial state rebuilt after restart;
7. no application-specific contamination of the frozen kernel.

Production remains a later independent review.
