---
id: AI-20260729-004
title: Codex ADR-012 Conditional Acceptance Remediation
status: READY_FOR_REVIEW
date: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
references:
  - 92_web_gpt_adr012_implementation_review.md
  - ../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md
---

# Codex Response: ADR-012 Conditional Acceptance

## Result

The conditional items are closed locally at:

`b082af0618e180f98441af5dc6d49c906994a012`

This remediation changes no ADR-011 execution ownership, implements no Carry
or Funding semantics, and does not enable grouped external execution.

## Finding Resolution

### A-01 Risk Snapshot Freshness — CLOSED

`RiskSnapshotMetadata` now records:

- exact Risk snapshot identity;
- generation time;
- oldest market-data as-of time;
- oldest Portfolio-state as-of time;
- effective validity deadline;
- Risk policy version.

The deadline is the minimum of:

- Decision Snapshot age;
- mark and spread age/expiry;
- sensitivity age/expiry;
- reconciled position age;
- margin age;
- liquidation-reference age.

Approval and permit expiry cannot outlive that deadline. A stale snapshot
returns `STALE`, not an economic rejection.

ADR-009 `DecisionSnapshotMetadata` remains the authoritative generic snapshot
metadata. `RiskSnapshotMetadata` is the ADR-012 derived freshness evidence; it
does not create a second snapshot owner.

### A-02 Material Change Taxonomy — CLOSED

`RiskInvalidationTrigger` is required for every external material change and
is persisted with the authorization-generation journal entry.

The taxonomy includes price, volatility, margin, position, collateral,
policy, market status, working order, reservation, execution,
reconciliation, health, restart and Risk-directive changes.

An untyped trigger fails before journal mutation.

### A-03 Reservation Resource Semantics — CLOSED

Whole-Basket approval now carries canonical `RiskResourceClaim` evidence.

Current resource kinds cover:

- exclusive account/instrument position targets;
- shared available margin;
- gross notional;
- initial margin;
- factor absolute net Delta;
- factor gross Delta;
- factor Gamma;
- factor Vega.

The coordinator serializes claims by `RiskResourceKey`. Disjoint BTC and ETH
targets may reserve concurrently while shared capacity is available.
Concurrent stale approvals that would exceed a shared limit are rejected even
when their instrument targets do not overlap.

Claims and freshness evidence replay durably. Legacy journal records without
the new fields replay conservatively with exact position-target claims.

### A-04 Target Confirmation Tolerance — CLOSED

`TargetMatchPolicy` is explicit and versioned. It defines:

- default absolute quantity tolerance;
- optional per-instrument quantity tolerance.

`PortfolioTargetConfirmation` persists the policy version and checksum.
Confirmation compares effective position quantity with the Basket target
inside this tolerance.

Price, Delta and Greeks are deliberately not included. They are Risk
assessment inputs, not the economic position-target equality owned by this
confirmation boundary.

### A-05 Options Risk Boundary — CONFIRMED

No code change was needed.

`PortfolioRiskEngine` consumes exact, unit-labelled Delta/Gamma/Vega
evidence. It does not calculate IV, Greeks or volatility surfaces. Feature
and future Risk Analytics layers remain the producers.

### A-06 Permit Consume Ordering — CONFIRMED

No ordering change was needed.

The shared guard remains:

```text
validate current platform/operator authority
  -> validate exact Risk generation/action/group
  -> durably append PERMIT_CONSUMED
  -> future external I/O
```

Grouped external I/O is still unreachable.

### A-07 Failure Classification — CLOSED

Portfolio decisions now expose:

- `ALLOW`;
- `REJECT`;
- `STALE`;
- `INSUFFICIENT_DATA`;
- `RECOVERY_REQUIRED`.

Economic limits remain `REJECT`. Temporal invalidity is `STALE`; missing or
unready evidence is `INSUFFICIENT_DATA`; unresolved recovery state is
`RECOVERY_REQUIRED`.

## Verification

- 467 full regression tests passed;
- 141 subtests passed;
- 39 isolated acceptance tests passed;
- branch coverage is 85.11%, above the 85% gate;
- Ruff passed;
- strict MyPy passed for 100 source files;
- compileall and high-confidence secret scanning passed.
- documentation head `345791e9af181a255676f0b0b9751bcabb4b3acf`
  passed every remote job in GitHub Actions run `30439995029`.

## Committee Request

Please review only whether A-01 through A-07 are closed.

Classify any new finding as:

- A. ADR-012 remediation error;
- B. ADR-013/ADR-014 concern;
- C. long-term optimization.

Do not interpret this handoff as Testnet, production, Carry or Funding
authorization.
