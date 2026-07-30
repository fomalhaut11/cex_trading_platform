# CEX Quant — Current Project State and LLM Handoff

Status date: 2026-07-30.

Audience: the next LLM/Codex session, project owner and external architecture
reviewer.

This is the fastest self-contained entry point. Read it before proposing,
editing or executing work. If repository `HEAD` is newer than the baseline
below, inspect the intervening commits and update this file before relying on
its status claims.

## 1. Exact Baseline

```text
Repository:   fomalhaut11/cex_trading_platform
Remote:       https://github.com/fomalhaut11/cex_trading_platform.git
Branch:       main
State base:   0123b6322de80f9fb488b92942ef19b31cdd6512
origin/main:  matched the state base when verified
Worktree:     clean before this documentation-only handoff
```

Latest code implementation baseline:

```text
40d10125318ebafc6c9979dc6ee3447c10739657
feat(carry): implement ADR-014 offline application
```

Later commits through current `HEAD` are documentation, acceptance, Kernel
freeze and delivery planning.

Remote CI:

```text
GitHub Actions run: 30519391352
Result:             success
Head:               0123b6322de80f9fb488b92942ef19b31cdd6512
```

## 2. Current Mission

The institution-oriented kernel is implemented through bounded offline
acceptance. The project owner has now changed the sole active product mission
to:

> close the first Binance single-account BTC Funding Carry loop with bounded
> real capital as quickly as safety and evidence allow.

Active effort allocation:

```text
70%  Execution Promotion and closed-loop reliability
20%  minimal operations, monitoring, Shadow and runbooks
10%  documentation and evidence synchronization
```

Keep existing platform capabilities, but defer general SDK, Replay, Paper and
additional-strategy work until after the Fast-Track MVP. Do not resume
speculative kernel expansion.

## 3. Current User Direction

The project owner confirmed the Fast-Track objective and instructed the
project to retain existing capabilities while shelving non-MVP plans.

Current state:

- `development/funding_carry_fast_track_plan.md` is the active plan;
- no T045 implementation work has started;
- T045 is the only current next engineering task;
- Testnet/grouped external execution is not authorized.
- real-money micro-live execution is not authorized.

## 4. Kernel v1 Freeze

The public kernel is compatibility-frozen under:

`architecture/kernel_v1_freeze.md`

Frozen architecture:

```text
ADR-009  Decision Snapshot
ADR-010  Basket Intent
ADR-011  Parent Order Group and multi-leg execution control
ADR-012  Portfolio Risk and exact action authorization
ADR-013  Financial Ledger and PnL Attribution contracts
ADR-014  Carry Application boundary
```

Allowed kernel changes:

- correctness, security, durability or recovery fixes;
- measured performance fixes with unchanged semantics;
- compatibility-preserving adapters and evidence;
- real integration defects with tests and explicit approval.

Forbidden by default:

- Funding-specific fields/branches in OMS;
- CTA-specific fields/branches in Risk;
- Market Making quote state in Portfolio;
- Carry lifecycle as a universal application lifecycle;
- one universal application journal/state machine;
- new speculative ADRs or physical package moves without demonstrated need.

## 5. ADR Status

| ADR | Status | Implementation |
|---|---|---|
| ADR-009 Snapshot | Accepted | T025-T026/A012 complete |
| ADR-010 Basket Intent | Accepted | T027-T028/A013 complete |
| ADR-011 Order Group | Accepted | T029-T031/A014 complete; remediation closed |
| ADR-012 Portfolio Risk | Accepted | T032-T035/A015 complete; A-01–A-07 closed |
| ADR-013 Financial Ledger | Approved in principle | T036-T039/A016 complete under project-owner offline authority; final Web GPT acceptance pending |
| ADR-014 Carry Application | Design and offline implementation Accepted | T040-T044/A017 closed |

Do not describe ADR-013 as finally accepted until its final review is recorded.

## 6. Implemented Platform Capabilities

### Foundation

- immutable identifiers, fixed-point values and nanosecond time;
- Spot, perpetual, dated-future and option instruments;
- venue-neutral event and state contracts;
- deterministic single-writer state and checksummed replay.

### Market and Information

- Binance Spot, USD-M and COIN-M normalization;
- trades, klines, mark/index/Funding and depth;
- L1, partial and reconstructed order-book state;
- authoritative latest `FundingView`;
- registered online Features;
- Black-Scholes/Black-76, IV, Greeks and volatility-surface contracts.

### Decision and Snapshot

- generic coherent ADR-009 Snapshot infrastructure;
- existing single-leg `PositionTargetIntent`;
- generic bounded 2–16-leg `BasketTargetIntent`;
- exact Snapshot causation and versioned Objective Type registry.

### OMS and Execution Control

- single-order OMS and durable journal/reconciliation;
- Parent Order Group identity, plan/action/child facts and replay;
- UNKNOWN/recovery semantics;
- shared durable-before-external-I/O handoff;
- authenticated Binance execution/query/cancel/private-stream adapters.

Important:

`OrderGroupRuntime.submit_prepared_child()` remains deliberately blocked for
grouped external execution.

### Portfolio Risk

- execution-consistent effective positions;
- normalized margin/liquidation inputs;
- generic N-leg projection and whole-Basket approval;
- reservations/resource claims;
- exact per-action permits and generation invalidation;
- immediate pre-I/O guard and recovery evidence.

### Accounting

- immutable authenticated-style financial facts;
- balanced per-asset ledger;
- deterministic mapping, replay and exact reversal;
- source and balance reconciliation;
- generic owner allocation;
- explicit valuation evidence and PnL views;
- bounded fail-closed financial-fact handoff.

Accounting never treats market Funding rate as realized settlement.

### Applications

`cex_quant.applications.carry` is implemented offline:

- Funding Carry pair and exact quantity conversion;
- typed entry/position Snapshots;
- expected Funding, basis, cost, net carry and APR Features;
- pure open/close Basket policy;
- durable Carry position facts, journal and replay;
- independent lifecycle, hedge and financial-finality states;
- recovery proposals without Risk or execution authority.

`CarryApplicationRuntime` currently stops after recording generic Basket
evidence. It does not yet compose the full Risk/OMS/Portfolio/Accounting loop.

## 7. What Is Not Implemented or Authorized

Not yet implemented:

- T045 current-code grouped composition audit;
- T046 mode-neutral offline execution runtime and fault harness;
- A018 full offline grouped execution-loop acceptance;
- T050 Funding Carry Live Operations Lite and Shadow mode;
- A020 live-readiness acceptance;
- A021 controlled micro-live acceptance;
- CTA application;
- real grouped Carry integration.

Retained but deferred until after the MVP:

- T047 researcher-facing Application Runtime / SDK Lite;
- T048 historical event Replay platform;
- T049 Paper Exchange and Fill Model;
- additional strategy families and general platform UI.

Not authorized:

- A019 authenticated grouped Binance Testnet;
- external Funding Carry execution;
- production trading;
- production endpoints or credentials;
- automatic multi-symbol/multi-venue capital allocation.

External prerequisites also remain for persistent host time, target-host soak,
concrete TLS termination, remote audit retention and runbook exercises.

## 8. Active Fast-Track Sequence

Authoritative plan:

`development/funding_carry_fast_track_plan.md`

Detailed execution-promotion plan:

`development/execution_promotion_plan.md`

Sequence:

```text
Phase 0  Kernel v1 compatibility freeze        ACTIVE
T045     Execution Promotion composition audit NEXT, NOT STARTED
T046     Mode-neutral offline runtime/harness  PLANNED
A018     Offline Execution acceptance          PLANNED
A019     Binance grouped Testnet acceptance    EXTERNAL, UNAUTHORIZED
T050     Live Operations Lite + Shadow         PLANNED
A020     MVP Live Readiness                    PLANNED, NO TRADING AUTHORITY
A021     Controlled Micro-Live                 EXTERNAL, UNAUTHORIZED
```

The broader `development/platform_delivery_plan.md`, T047, T048 and T049 are
retained Post-MVP plans and are not in the active queue.

## 9. Exact T045 Scope

T045 is a current-code audit before implementation. It must answer:

1. how `BasketTargetIntent` enters whole-Basket Risk admission;
2. who creates and binds `OrderGroupId`;
3. who chooses the next exact `ExecutionAction`;
4. who requests, validates and consumes the action permit;
5. how child outcomes update OMS, Portfolio and Accounting independently;
6. how Carry observes those views and changes application state;
7. where one runtime writer serializes the full sequence;
8. which gap is a defect, missing composition, external dependency or
   non-blocking optimization.

T045 deliverables:

- current-code call/dependency map;
- identity and causation map;
- state-writer ownership table;
- happy-path and failure sequence diagrams;
- bounded T046 plan.

T045 does not enable network I/O and should not modify frozen public
interfaces without first showing a reproducible gap.

## 10. Deferred Application Runtime Decisions

These decisions are retained for Post-MVP T047. They are not active
implementation scope. The future user-facing name is `Application Runtime`,
not only Strategy SDK.

The same pure policy/intent code should be reusable across Replay, Paper,
Testnet and future production through different adapters.

Callbacks may include:

```python
on_start()
on_snapshot(snapshot)
on_position_change(position_view)
on_risk_event(risk_view)
on_stop()
```

Safety rule:

> only a fresh coherent Snapshot may cause a new exposure-changing Intent.

Position/Risk callbacks may update application state or request a new
Snapshot. They cannot call OMS/Execution or bypass Snapshot causation.

`context.risk` is an immutable view, never a permit-issuing service.

Do not create a Carry-derived `BaseApplication` or universal application
state.

## 11. Deferred Replay and Paper Separation

T048/T049 are retained Post-MVP work.

T048 Replay:

- replays recorded canonical evidence;
- reconstructs State, Features and Snapshots;
- must be deterministic;
- performs no external I/O.

T049 Paper:

- simulates market/limit orders;
- supports latency, slippage, partial fills and failures;
- labels fees/Funding/fills as simulated;
- cannot write simulated facts into an authenticated production ledger.

Replay is not Paper, and neither is Testnet.

## 12. Deferred Strategy Order

1. Funding Carry is the first complete platform-loop application.
2. CTA is the first new Application Runtime/Replay example.
3. Cross-venue arbitrage follows only after Multi-Venue need is proven.
4. Option applications reuse Feature-owned Greeks/volatility surfaces.
5. High-frequency Market Making is last.

Do not develop multiple new strategies in parallel.

## 13. Verification Baseline

Last full local validation after ADR-014 implementation:

```text
pytest:             544 passed
unittest subtests:  188 passed
branch coverage:    85.13% (minimum 85%)
Ruff:               passed
strict MyPy:        passed over 136 source files
compileall:         passed
secret scan:        passed
```

The verified state base passed GitHub Actions run `30519391352`.

A local Windows pytest run may emit a `.pytest_cache` creation warning. It did
not affect test results, and clean remote CI passed.

## 14. Recommended Read Order

Read only what is needed, in this order:

1. `START_HERE.md` — current status and next action;
2. `development/funding_carry_fast_track_plan.md` — active MVP path;
3. `architecture/kernel_v1_freeze.md` — allowed/prohibited changes;
4. `development/execution_promotion_plan.md` — T045/A018 detail;
5. `architecture/module_topology.md` — dependencies;
6. `architecture/state_ownership.md` — single writers;
7. `development/tasks.md` and `development/progress.md` — task/evidence status;
8. `development/platform_delivery_plan.md` only for deferred Post-MVP scope;
9. specific accepted ADR/interface files only when changing that boundary.

For ADR-014:

- `adr/ADR-014-carry-application-boundary.md`;
- `interfaces/carry_application_schema.md`;
- `ai_collaboration/topics/carry_application/70_web_gpt_adr014_final_acceptance.md`.

For ADR-013 pending review:

- `ai_collaboration/topics/financial_ledger/40_codex_clarification_response.md`;
- `ai_collaboration/topics/financial_ledger/50_codex_adr013_offline_implementation_handoff.md`.

Historical AI discussions are evidence, not architecture authority.

## 15. Development and Git Notes

Environment:

- Windows PowerShell;
- Python 3.11+ supported;
- local development interpreter normally `.venv\Scripts\python.exe`;
- `src` package layout.

Useful validation:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src
.\.venv\Scripts\python.exe -m ruff check src tests tools
.\.venv\Scripts\python.exe -m mypy --strict src
.\.venv\Scripts\python.exe -m pytest --cov=cex_quant --cov-branch `
  --cov-report=term-missing --cov-report=xml --cov-fail-under=85
```

Git:

- `origin/main` is the authoritative baseline;
- direct pushes are currently used; branch protection remains planned;
- if Windows `schannel` fails during push, the previously successful
  non-persistent fallback is:

```powershell
git -c http.version=HTTP/1.1 push origin main
```

Never place API credentials in source, fixtures, logs, documentation or Git.

## 16. Handoff Maintenance Rule

Update this file whenever any of the following changes:

- Git implementation baseline;
- ADR acceptance status;
- completed/current task;
- external authorization;
- test/coverage baseline;
- first Testnet or production evidence;
- next recommended action.

At each update:

1. record exact full commit SHA;
2. verify `HEAD == origin/main`;
3. record the CI run for that exact head;
4. keep “implemented”, “accepted” and “authorized” as separate statuses;
5. remove stale next-step instructions instead of appending contradictions.
