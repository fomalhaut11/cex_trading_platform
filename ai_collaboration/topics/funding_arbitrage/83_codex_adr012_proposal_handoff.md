---
id: AI-20260728-013
title: ADR-012 Proposed Handoff
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-28
code_baseline: a752d3bff06a1b73b1103f543c64a2b6b64d2016
supersedes: none
related:
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
  - 82_codex_adr012_current_code_audit.md
external_share: allowed
sensitivity: public-project
---

# Codex Handoff: ADR-012 Proposed

## Review Request

Please review ADR-012 as the Portfolio Risk and grouped-execution
authorization layer.

Do not redesign ADR-011. Review whether ADR-012 correctly consumes its frozen
contracts:

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> OrderGroup
  -> ExecutionAction
  -> ExecutionActionPermit
  -> canonical Child Order
```

Implementation authorization is currently none. Grouped external submission
remains hard-blocked.

## Architecture Conclusion

ADR-012 proposes:

```text
Portfolio facts
  -> Portfolio Risk snapshot
  -> pure exposure projection
  -> durable Risk authority
  -> OMS evidence validation
  -> Runtime immediate safety guard
```

The design separates two decisions:

```text
Whole-Basket approval
  may create one durable group

Per-action permit
  may authorize one exact exposure-changing action now
```

An old Basket approval never authorizes all future children.

## Critical Current-Code Finding

The current system has:

- authoritative absolute `AccountSnapshot` positions;
- OMS cumulative signed fill vectors.

It is unsafe to add them directly because the account snapshot may already
include the same fills.

ADR-012 therefore defines:

```text
reconciled account baseline
  + OMS fill increments strictly after a proven coverage cursor
  = effective position
```

Portfolio owns this view. Risk consumes it. OMS remains the owner of fill
facts.

If coverage cannot be proven, ordinary action authorization fails closed.

## Proposed Risk Inputs

One current typed Portfolio Risk snapshot contains:

- execution-consistent effective positions;
- all relevant working orders and Order Groups;
- active approval reservations;
- instrument definitions and contract multipliers;
- marks and currency conversions;
- normalized margin/collateral/liquidation facts;
- required Feature values, including option Greeks;
- configured spread/basis inputs;
- health, freshness, coherence and policy evidence.

The Basket's Strategy snapshot and the action's current Risk snapshot are
different causation points and may have different IDs.

## Proposed Exposure Model

Risk calculates three views:

```text
current realized exposure
projected target or full-fill action exposure
conservative adverse working-order exposure
```

At minimum it covers:

- signed positions;
- net/gross Delta;
- notional and concentration;
- residual/legging exposure;
- configured basis/spread risk;
- margin utilization and liquidation buffer;
- option Gamma/Vega when policy requires them.

Risk factors are generic and versioned. There is no Funding-specific branch.

System-computed IV, Greeks and volatility surfaces remain Features. Risk
consumes their value, unit, quality and lineage.

## Proposed Stateful Boundary

The calculation engine remains pure.

A separate single-writer Risk coordinator durably owns:

- admission reservations;
- approvals and permits;
- active policy version;
- authorization generation;
- continuous directives;
- recovery and target-confirmation evidence.

Reservations prevent two concurrently approved Baskets from spending the same
margin or exposure capacity.

Every material Portfolio, OMS, market, Feature, margin, policy, health or
operator change invalidates affected unconsumed permits. The immediate
pre-external-I/O guard verifies that the permit's Risk generation is still
current.

TTL alone is not considered sufficient.

## Proposed Continuous Supervision

Risk may publish:

```text
CLEAR
BLOCK_NEW_ACTIONS
RECONCILIATION_REQUIRED
RECOVERY_ACTION_REQUIRED
OPERATOR_REVIEW_REQUIRED
```

A directive is evidence and constraint only.

It cannot:

- mutate OMS directly;
- create or size an order;
- call Execution;
- declare Carry `HEDGED` or `ACTIVE`;
- decide Funding profitability.

Any hedge/flatten action still requires an execution-plan proposal, exact
permit, durable OMS preparation and immediate runtime guard.

## Proposed Recovery Boundary

Restart remains:

```text
HALTED
  -> replay Risk and OMS evidence
  -> reconcile unknown/unresolved children
  -> establish account/OMS execution coverage
  -> rebuild reservations
  -> assemble fresh Risk snapshot
  -> reassess active groups
  -> explicit operator resume
```

Old permits do not survive restart as live authority.

ADR-012 also defines typed semantics for:

- group recovery authorization;
- Portfolio target confirmation.

A definitely-not-sent same-ID technical retransmission keeps the original
latched permit as immutable causation, but requires fresh exact recovery
authorization and current Risk/operator validation. It does not replace the
action, child ID or permit.

Target confirmation means effective positions match the admitted Basket and
children are resolved. It does not mean the application is profitable or
economically `HEDGED`.

## Expansion Check

### Funding Arbitrage

Uses generic underlying Delta, a configured Spot/Perpetual basis set and
derivative margin inputs. Funding rate and APR remain application inputs.

### Market Making

Can reuse working-order exposure and exact per-action authorization. Quote
lifecycle and inventory-skew policy remain outside ADR-012.

### Option Spread plus Delta Hedge

Uses system-computed Feature Greeks and instrument multipliers. Raw option
contract quantities are never summed with Spot/Perpetual quantities as Delta.

### Multi-venue

Requires explicit account, venue, asset and conversion-rate scope. No implicit
global USD conversion is allowed.

## Explicit Non-Goals

ADR-012 does not:

- implement Funding Arbitrage;
- define Funding APR or entry/exit rules;
- calculate IV, Greeks or a volatility surface;
- define the Financial Ledger or PnL attribution;
- redesign OMS group lifecycle;
- replace existing single-leg Risk;
- authorize grouped external submission;
- authorize Testnet or production trading.

## Questions for Web GPT

Please classify findings as:

```text
A. ADR-012 design error
B. ADR-013/ADR-014 or later concern
C. Long-term optimization
```

Review these decisions:

1. Is the reconciled baseline plus post-watermark execution overlay correct?
2. Should missing execution coverage fail closed?
3. Is the pure engine plus durable single-writer Risk coordinator separation
   correct?
4. Do durable reservations correctly prevent approval overcommit?
5. Is the generic risk-factor/spread model free of Funding leakage?
6. Are current/full-fill/conservative-working exposure views sufficient for
   V1?
7. Should material updates invalidate unconsumed permits through an
   authorization generation checked immediately before I/O?
8. Are Risk directives correctly prohibited from creating orders?
9. Are recovery authorization, operator resume and Carry economic state
   sufficiently separate?
10. Does the proposal safely support Funding, Market Making and option spreads
    without changing ADR-011?
11. Which hard caps must be fixed before implementation?
12. May implementation begin after acceptance while external grouped
    submission remains blocked through offline acceptance?

The complete proposed decision is:

`adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md`
