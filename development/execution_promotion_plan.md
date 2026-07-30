# Grouped Execution Promotion Plan

Status: planned; credential-free preparation only.

Architecture basis: ADR-009 through ADR-014.

External execution: blocked until separate project-owner authorization.

## Objective

Close the first application runtime loop without changing domain ownership:

```text
Funding Carry Snapshot
  -> BasketTargetIntent
  -> Portfolio Risk approval/reservation
  -> OMS Order Group
  -> exact ExecutionActionPermit
  -> durable child handoff
  -> existing Binance Testnet adapter
  -> Portfolio reconciliation
  -> ADR-013 financial facts and ledger
  -> Carry hedge and financial assessment
```

Execution Promotion is integration and operational evidence work. It is not a
new Funding-specific execution architecture and does not require reopening
ADR-011, ADR-012 or ADR-014.

## Frozen Invariants

1. Carry still emits only generic absolute Basket targets.
2. Portfolio Risk approves the complete Basket and authorizes each exact
   exposure-changing action.
3. OMS owns group, child and unknown/recovery execution state.
4. `PERMIT_CONSUMED` and durable child submission state precede external I/O.
5. Existing venue adapters remain child-order oriented.
6. Portfolio positions, not acknowledgements or fills alone, determine current
   effective exposure.
7. Actual Funding, fee and trade cash flows reach ADR-013 only from
   authenticated account/execution evidence.
8. UNKNOWN never causes blind economic retry.
9. Carry, Risk, OMS and Accounting remain unaware of Binance-specific
   payloads.
10. Testnet promotion grants no production permission.

## Sprint 2A - Offline Promotion Readiness

This is the next credential-free development scope.

### Composition audit

- map `BasketTargetIntent` to whole-Basket Risk admission;
- bind approved Basket identity to one `OrderGroupId`;
- map the selected execution plan to exact actions and child attempts;
- reuse `PortfolioRiskExecutionGuard` and shared durable handoff;
- prove there is one runtime coordination point and no alternate external
  route;
- define read-only evidence returned to Carry.

### Closed-loop deterministic harness

Use an in-memory/fault-injectable execution gateway, never a network adapter,
to test:

- both legs accepted and reconciled;
- first leg fills, second leg rejects;
- partial fills on either leg;
- timeout-after-send and UNKNOWN;
- permit expiry/invalidation between actions;
- margin or position change during opening;
- operator halt;
- journal restart at every non-terminal boundary;
- financial facts arriving before/after Portfolio reconciliation;
- normal close and funding-reversal close.

### Promotion artifact

Produce one self-contained readiness report containing:

- exact code baseline;
- state/action sequence diagrams;
- failure matrix;
- test and coverage evidence;
- remaining external prerequisites;
- explicit go/no-go request for Testnet.

Sprint 2A cannot remove the external block.

## Sprint 2B - Explicit Testnet Promotion

This phase starts only after all of the following are recorded:

- project-owner authorization for grouped Binance Testnet execution;
- ADR-013 final implementation acceptance;
- user-provided Testnet credentials through `BinanceCredentialProvider`;
- healthy persistent host/venue clock evidence;
- approved Testnet account, instruments, size and maximum loss/notional;
- working kill switch and authenticated operator controls;
- successful offline fault/restart matrix;
- approved rollback and incident procedure.

The first Testnet scenario must use bounded quantities and a dedicated account.
It must exercise submit, query, cancel, private-stream reconciliation,
UNKNOWN recovery, ledger ingestion and restart. Production endpoints remain
forbidden.

## Sprint 3 - Strategy/Application SDK

Build only after the first closed-loop integration identifies repeated
interfaces.

Allowed shared abstractions:

- typed Snapshot consumption;
- pure intent generation;
- objective registration;
- application health/readiness;
- evidence/replay hooks;
- lifecycle-independent runtime controls.

Forbidden abstraction:

```text
UniversalApplicationState
```

Carry, CTA and Market Making may share protocols but retain independent state:

```text
CarryPosition
CTAState
QuoteSession / InventoryState
```

No `BaseApplication` should require Carry-specific position, hedge, financial
or recovery lifecycle fields.

## Sprint 4 - Replay and Paper Trading

Replay must use recorded canonical evidence and the same deterministic
Snapshot/Strategy contracts. Paper Trading must emulate Execution outcomes
through an explicit adapter and must never be presented as venue truth.

Required separation:

```text
historical replay        deterministic recorded inputs
paper execution          simulated order/fill model
Testnet execution        real venue protocol, non-production account
production execution     separate future authorization
```

Paper fills, Funding and fees must be labelled simulated and kept out of an
authenticated production ledger.

## Planned Work Items

| ID | Work item | Status | External effect |
|---|---|---|---|
| T045 | Grouped execution composition audit and offline promotion runtime | Planned | None |
| T046 | Deterministic grouped closed-loop/fault harness | Planned | None |
| A018 | Offline Execution Promotion acceptance | Planned | None |
| A019 | Authenticated grouped Binance Testnet acceptance | External, unauthorized | Testnet |
| T047 | Minimal Strategy/Application SDK after integration feedback | Planned | None |
| T048 | Replay and Paper Trading foundation | Planned | None |

No item in this document changes the current external authorization state.

