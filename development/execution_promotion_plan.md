# Grouped Execution Promotion Plan

Status: T045 complete; T046/A018 planned; credential-free work only.

Architecture basis: ADR-009 through ADR-014.

External execution: blocked until separate project-owner authorization.

Active program sequence: `development/funding_carry_fast_track_plan.md`.

The broader `development/platform_delivery_plan.md` is retained as Post-MVP
direction and is currently deferred.

Kernel change policy: `architecture/kernel_v1_freeze.md`.

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

## T045 - Execution Promotion Composition Audit

Status: complete. Evidence:
`development/t045_execution_promotion_composition_audit.md`.

T045 was an evidence-backed current-code audit and produced no external side
effect.

### Composition audit

- map `BasketTargetIntent` to whole-Basket Risk admission;
- bind approved Basket identity to one `OrderGroupId`;
- map the selected execution plan to exact actions and child attempts;
- reuse `PortfolioRiskExecutionGuard` and shared durable handoff;
- prove there is one runtime coordination point and no alternate external
  route;
- define read-only evidence returned to Carry.

T045 must identify the single runtime writer, map every identity/causation
edge and distinguish a real missing composition seam from a request to change
the frozen kernel.

Output:

```text
current-code call and dependency map
identity/causation map
state-writer ownership table
failure sequence matrix
bounded T046 implementation plan
```

## T046 - Mode-Neutral Offline Runtime and Fault Harness

T046 implements only gaps demonstrated by T045. It must use ports that allow
the deterministic execution adapter to be replaced by a separately authorized
Binance Testnet adapter without changing application policy or grouped
execution semantics.

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

### A018 promotion artifact

Produce one self-contained readiness report containing:

- exact code baseline;
- state/action sequence diagrams;
- failure matrix;
- test and coverage evidence;
- remaining external prerequisites;
- explicit go/no-go request for Testnet.

T045/T046/A018 cannot remove the external block.

## A019 - Explicit Testnet Promotion

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

## Deferred Post-MVP Reference

The sections below are retained design direction, not active Execution
Promotion work. After A019, the active Fast-Track continues through
T050/A020/A021 in `development/funding_carry_fast_track_plan.md`.

### T047 - Application Runtime / SDK Lite

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

### T048 - Historical Event Replay

Replay must use recorded canonical evidence and the same deterministic
Snapshot/Application contracts. It reconstructs State, Features and Snapshots
from canonical evidence and produces deterministic decisions without a live
gateway.

### T049 - Paper Exchange

Paper Trading emulates Execution outcomes through an explicit adapter and
must never be presented as venue truth. Its first Fill Model supports market
and limit orders, latency, slippage, partial fill, rejection and
timeout/UNKNOWN injection.

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
| T045 | Grouped execution current-code composition audit | Complete | None |
| T046 | Mode-neutral offline execution runtime and deterministic fault harness | Planned | None |
| A018 | Offline Execution Promotion acceptance | Planned | None |
| A019 | Authenticated grouped Binance Testnet acceptance | External, unauthorized | Testnet |
| T047 | Application Runtime / SDK Lite after closed-loop evidence | Deferred, Post-MVP | None |
| T048 | Historical event Replay foundation | Deferred, Post-MVP | None |
| T049 | Paper Exchange and Fill Model | Deferred, Post-MVP | None |
| T050 | Funding Carry Live Operations Lite and Shadow | Planned after A019 | None |
| A020 | Funding Carry MVP Live Readiness | Planned, no trading authority | None |
| A021 | Controlled BTC Funding Carry micro-live | External, unauthorized | Real money |

No item in this document changes the current external authorization state.
