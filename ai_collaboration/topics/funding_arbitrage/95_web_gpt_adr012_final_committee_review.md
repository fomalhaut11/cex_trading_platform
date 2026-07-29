---
id: AI-20260729-010
title: Web GPT ADR-012 Final Committee Review
origin: web-gpt
status: PROMOTED
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 93_codex_adr012_remediation_response.md
  - 94_web_gpt_adr012_final_acceptance.md
  - 96_web_gpt_adr012_formal_closure.md
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
  - ../carry_application/10_web_gpt_input.md
external_share: allowed
sensitivity: public-project
---

# Web GPT ADR-012 Final Committee Review

## Final Decision

```text
ADR-012 Design:                 ACCEPTED
ADR-012 Implementation:         ACCEPTED
ADR-012 Remediation:            CLOSED
Grouped External Execution:     BLOCKED
Testnet / Production:           NOT AUTHORIZED
```

A-01 through A-07 are accepted and closed. ADR-012 does not need to be
reopened.

## Remediation Assessment

### Risk Snapshot Freshness

`RiskSnapshotMetadata` now provides the exact snapshot identity, generation
time, source as-of bounds, effective validity deadline and policy version.
Approval and permit validity cannot exceed the oldest relevant market,
position, margin or liquidation-reference evidence.

Committee result: accepted.

### Risk Invalidation

`RiskInvalidationTrigger` replaces an untyped changed flag with auditable
causes covering price, volatility, margin, position, collateral, policy,
market status, working order, reservation, execution, reconciliation, health
and restart changes.

Committee result: accepted.

### Risk Resource Claims

Whole-Basket approval now carries typed resource claims for position targets,
margin, gross notional and risk-factor capacity such as Delta, Gamma and Vega.
This establishes portfolio-level authorization rather than independent
single-order approval.

Committee result: accepted.

### Target Confirmation

`TargetMatchPolicy` compares effective position quantity with the economic
target under a versioned tolerance. It does not absorb price, Delta or Greeks
assessment from Risk.

Committee result: accepted.

### Options Boundary

Portfolio Risk consumes Delta, Gamma and Vega evidence but does not calculate
IV, Greeks or volatility surfaces. Feature ownership remains unchanged.

Committee result: accepted.

### Permit Consumption

The required order remains:

```text
validate platform/operator authority
  -> validate exact Risk generation, action and group
  -> durably append PERMIT_CONSUMED
  -> external I/O
```

Committee result: accepted.

### Failure Classification

Risk decisions distinguish:

```text
ALLOW
REJECT
STALE
INSUFFICIENT_DATA
RECOVERY_REQUIRED
```

Temporal invalidity is not misclassified as an economic rejection.

Committee result: accepted.

## Verification Recognized by the Committee

- 467 regression tests;
- 141 subtests;
- 39 acceptance tests;
- 85.11% branch coverage;
- Ruff passed;
- strict MyPy passed for 100 source files;
- remote CI passed.

## Transition Decision

Proceed to the ADR-013/ADR-014 application-enablement design phase.

The later formal closure record `96_web_gpt_adr012_formal_closure.md`
clarifies the gate order: align ADR-013 Accounting scope first, then perform
ADR-014 formal review.

Do not implement Funding Arbitrage execution until both:

- ADR-013 Financial Ledger and PnL Attribution; and
- ADR-014 Carry Application Boundary

are reviewed and accepted.

Grouped external execution, Testnet and production remain unauthorized.

## ADR-014 Review Focus

The next design must make explicit:

1. the Carry position model and its application-owned economic lifecycle;
2. Funding payments, trading fees, borrow cost and PnL attribution as ADR-013
   Accounting facts;
3. the relationship among search, open, hedge, carry/collect and unwind
   workflow stages;
4. generation of generic `BasketTargetIntent`, followed by ADR-012 Risk
   authorization and ADR-011 Order Group execution control.
