---
id: AI-20260730-001
title: Codex ADR-014 Offline Implementation Handoff
origin: codex
status: READY_FOR_IMPLEMENTATION_REVIEW
created: 2026-07-30
code_baseline: 40d10125318ebafc6c9979dc6ee3447c10739657
supersedes: none
related:
  - 30_web_gpt_review.md
  - 40_codex_adr014_scope_alignment.md
  - 50_codex_adr014_review_handoff.md
  - 90_resolution.md
  - ../../../adr/ADR-014-carry-application-boundary.md
  - ../../../interfaces/carry_application_schema.md
external_share: allowed
sensitivity: public-project
---

# Codex ADR-014 Offline Implementation Handoff

## Decision Status

Web GPT accepted ADR-014, approved its boundary and authorized credential-free
offline T040-T044/A017 implementation.

Implementation commit:

`40d10125318ebafc6c9979dc6ee3447c10739657`

This handoff requests implementation review. It does not infer external
execution, Testnet or production authorization.

## Result

T040-T044 and A017 are complete offline:

```text
authoritative Funding state
  + Spot/Perpetual/Portfolio/Feature views
  -> coherent typed Funding Carry Snapshot
  -> pure economic policy
  -> generic BasketTargetIntent
  -> offline Basket evidence
  -X-> Portfolio Risk / OMS / Execution

immutable Carry application facts
  -> durable checksummed journal
  -> single-writer aggregate and restart replay
  -> lifecycle / hedge / financial / recovery views
```

The final `-X->` is deliberate. No grouped order is submitted.

## T040 - Funding Market-State View

Added `FundingRateState` and immutable `FundingView` under
`cex_quant.market_data.state`.

Properties:

- one authoritative latest view per perpetual instrument;
- exact event ID, event time, receive time, sequence and next settlement time;
- sequence-first stale rejection with event-time fallback;
- wrong instrument and impossible next-Funding time rejection;
- only `LIVE` views can leave the state owner.

Funding rate remains a market fact. It is not converted into an ADR-013
financial settlement.

## T041 - Carry Contracts

Added `cex_quant.applications.carry` with:

- deterministic `CarryPairId`, `ApplicationPositionId`,
  `CarryOwnershipId` and application fact identity;
- exact Spot/perpetual same-underlying pair validation;
- explicit base-units-per-contract conversion;
- immutable application ownership mapped generically to ADR-013
  `EconomicOwnerRef`;
- bounded immutable `CarryPositionView`;
- separate lifecycle, hedge and financial-finality states.

Lifecycle is application-owned:

```text
PROPOSED
  -> OPENING
  -> ACTIVE
  -> CLOSING
  -> CLOSED

RECOVERY_REQUIRED and HALTED are explicit non-happy-path states.
```

The other dimensions are orthogonal:

```text
hedge:      UNKNOWN | UNHEDGED | PARTIALLY_HEDGED | HEDGED
financial:  NOT_READY | PROVISIONAL | RECONCILED
```

`ACTIVE` and physical `CLOSED` require a hedged physical state, but physical
close does not force financial reconciliation.

## T042 - Typed Snapshot and Pure Economic Policy

Added Funding Carry:

- exact entry and position Snapshot types;
- semantic assembler over ADR-009 ordered observations;
- registered Feature calculations for basis, expected Funding, estimated
  cost, expected net carry and APR;
- versioned Feature/economic policies;
- registered open, close, rebalance and recovery Objective Types;
- pure `FundingCarryStrategy`.

The assembler validates:

- exact source set, source type and source identity;
- Spot/perpetual instrument relationship;
- source wrapper time versus immutable source time;
- live market status;
- READY Portfolio positions and required perpetual margin scope;
- Feature scope, quality, completeness and validity;
- bounded Carry/Order Group/Risk directive associations for position views.

The application may consume immutable `OrderGroupView` and
`PortfolioRiskDirective` evidence. It does not mutate OMS/Risk or use those
views as permission.

The current positive-Funding policy produces:

```text
Spot target:       baseline + target base quantity
Perpetual target:  baseline - converted target base quantity
```

A normal economic exit produces a new Basket restoring immutable owned-leg
baselines. Both are ordinary generic `BasketTargetIntent`; neither contains
an execution plan, child order, retry rule, permit or venue request.

## T043 - Aggregate, Replay and Recovery

Added immutable Carry facts, strict canonical JSON codec, checksummed JSONL
journal and `CarryPositionBook`.

Safety properties:

- single-writer mutation;
- durable append before state publication;
- deterministic IDs and exact revision continuity;
- idempotent intent/group links;
- bounded retained positions, legs and references;
- corruption/conflict/revision gaps fail recovery closed;
- restart replay reconstructs the same application view.

Hedge assessment reads authoritative effective Portfolio quantities and exact
contract conversion. OMS fills are not treated as current position truth.

Financial-finality assessment consumes only ADR-013 ledger, attribution,
allocation and reconciliation views. Carry cannot create or modify them.

`CarryRecoveryProposal` is not an OMS recovery command or Risk permit:

- wait and operator-halt proposals contain no Basket;
- restore/reduce/flatten proposals require one fresh generic Basket;
- the Basket must reference the exact fresh decision Snapshot;
- every exposure-changing proposal still requires ADR-012 and ADR-011.

## T044 - Offline Runtime Composition

Added `CarryApplicationRuntime`.

Constructor dependencies are deliberately limited to:

- `SnapshotCoordinator`;
- `StrategyRuntime`;
- optional offline evidence recorder.

There is no Risk engine, Risk permit issuer, OMS, Execution gateway or venue
adapter dependency.

When policy produces a Basket, the result is:

```text
disposition = BASKET_RECORDED_EXTERNAL_BLOCKED
external_execution_blocked = true
```

The Runtime latches Snapshot, Strategy and evidence failures as failed. It
cannot be configured to enable external execution.

## A017 Acceptance Evidence

A017 contains five end-to-end offline scenarios:

1. positive Funding generates Spot `+10` and perpetual `-10`, then stops at
   the blocked Basket boundary;
2. Funding sign reversal on an active position generates a fresh close Basket
   to the proven baselines;
3. UNKNOWN child outcome persists as application recovery, survives restart
   and creates no order or permit;
4. physical `CLOSED` remains financially `PROVISIONAL` until ADR-013 evidence
   completes;
5. the unchanged generic platform still accepts a three-leg option spread
   plus Delta hedge.

Additional unit/negative-path coverage validates Funding staleness, pair and
conversion errors, Feature quality/expiry, Snapshot scope/time/source errors,
ownership/lifecycle constraints, durable replay/corruption, hedge assessment,
financial finality and recovery semantics.

Full validation:

```text
pytest:             544 passed
unittest subtests:  188 passed
branch coverage:    85.13% (minimum 85%)
Ruff:               passed
strict MyPy:        passed, 136 source files
compileall:         passed
secret scan:        passed within full regression
```

Remote GitHub Actions CI run `30510254523` passed for handoff commit
`ba32dce7ce468b14307088ef13e649c52f6fb74e`.

## Frozen Boundary Audit

- Carry owns economic lifecycle and policy only.
- Market State owns `FundingView`.
- Portfolio owns effective positions and margin source truth.
- Features own expected Funding/basis/cost/APR calculations.
- ADR-012 remains Risk approval and permit authority.
- ADR-011 remains Order Group and child execution-control authority.
- ADR-013 remains financial fact, ledger and PnL truth.
- Runtime is the only future composition point across authority boundaries.
- OMS, Risk and Accounting contain no Carry import or strategy-name branch.
- Carry contains no Execution gateway call or permit issuance.
- no external group route was enabled.

## Requested Review Classification

Please classify any finding as:

A. ADR-014 implementation error;
B. dependency or future external-promotion requirement;
C. non-blocking long-term optimization.

The accepted ADR-014 design should not be reopened unless the implementation
violates its frozen boundary.
