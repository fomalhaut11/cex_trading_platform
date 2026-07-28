# Initial Tasks

| ID | Task | Status | Depends on |
|---|---|---|---|
| T001 | Project skeleton | Complete | - |
| T002 | Core and instrument schema definitions | Complete | T001 |
| T003 | Binance connector and venue normalizers | Complete | T002, T004 |
| T004 | Market event normalization and validation contracts | Complete | T002 |
| T005 | Market state engine | Complete | T004 |
| T006 | Recorder | Complete | T002 |
| T007A | Online feature engine contracts and deterministic runtime | Complete | T005 |
| T007B | Core option feature calculators and surface contracts | Complete | T007A |
| T008 | Strategy runtime | Complete | T007B |
| T009 | Risk engine | Complete | T008 |
| T010 | OMS | Complete | T009 |
| T011 | Execution gateway | Complete | T010 |
| T012 | Portfolio and account state | Complete | T010 |
| T013 | Runtime pipeline composition | Complete | T005-T012 |
| T014 | Authenticated Binance execution adapter | Complete | T011, T013 |
| T015 | Concrete runtime port adapters and application assembly | Complete | T013-T014 |
| T016 | Durable OMS journal, restart replay and reconciliation kernel | Complete | T010, T015 |
| T017 | Binance order query and private order-event normalization | Complete | T014, T016 |
| T018 | Private order-stream lifecycle and startup reconciliation | Complete | T017 |
| T019 | Binance environment configuration and private-stream application supervision | Complete | T018 |
| T020 | Concrete Binance HTTP/private WebSocket transport and clock probing | Complete | T019 |
| T021 | Aggregate runtime health reporting and operator controls | Complete | T020 |
| T022 | Secure credential delivery and durable operator recovery | Complete | T021 |
| T023 | Authenticated operator boundary and secure deployment assembly | Complete | T022 |
| T024 | Bounded mTLS operator endpoint, audit boundary and runbooks | Complete | T023 |
| T025 | Generic decision-snapshot contracts, policy and readiness assessment | Complete | ADR-009 |
| T026 | Deterministic bounded snapshot coordinator and replay integration | Complete | T025 |
| T027 | Basket IDs, Objective Type registry, immutable contracts and policy | Complete | ADR-010 |
| T028 | Strategy Snapshot/Basket compatibility and explicit single-leg rejection | Complete | T027 |
| T029 | Order Group, Execution Plan/Action/Permit identifiers and immutable contracts | Complete | ADR-011 |
| T030 | Bounded Order Group state, mixed-version OMS journal, replay and recovery model | Complete | T029, T016 |
| T031 | Shared durable submit handoff and fail-closed group runtime boundary | Complete | T030, T015-T016 |
| A001 | Offline foundation scenario acceptance | Complete | T001-T014 |
| A002A | Offline performance and bounded-memory baseline | Complete | T015 |
| A002B | Target-host soak and latency acceptance | External | A002A |
| A002C | Binance Testnet authenticated acceptance | External | T017 |
| A003 | Offline OMS restart and reconciliation acceptance | Complete | T016 |
| A004 | Offline Binance recovery-protocol acceptance | Complete | T017 |
| A005 | Offline private-stream startup race acceptance | Complete | T018 |
| A006 | Offline environment and private-stream supervision acceptance | Complete | T019 |
| A007 | Offline transport ownership and server-time acceptance | Complete | T020 |
| A008 | Offline runtime health and operator-control acceptance | Complete | T021 |
| A009 | Offline credential rotation and operator restart acceptance | Complete | T022 |
| A010 | Offline authenticated operator deployment acceptance | Complete | T023 |
| A011 | Offline operator endpoint, audit and recovery acceptance | Complete | T024 |
| A012 | Offline decision-snapshot contract, coherence, replay and restart acceptance | Complete | T025-T026 |
| A013 | Offline Basket contract, replay, compatibility and two-/three-leg acceptance | Complete | T027-T028 |
| A014 | Offline Order Group identity, state, journal, retry, recovery and compatibility acceptance | Complete | T029-T031 |

A post-implementation review kept ADR-011 accepted and temporarily reopened
its implementation evidence. Commit
`c2c306dbe7675076ae200021d2c98f127736f09e` closed the identified T031/A014
gaps: immediate pre-I/O authority recheck, capacity suspension and
strategy/account active-group limits, child identity collision protection,
runtime single-writer enforcement and the missing fault/race cases. A014 is
therefore `Complete` after remediation; grouped external submission remains
blocked by ADR-012.

## Current Acceptance Baseline

- Public contracts are immutable and exported explicitly.
- No venue-native payload crosses an adapter boundary.
- Unit tests run offline and deterministic state tests support replay.
- Contract, ownership or schema changes update documentation in the same change.

## Authorized Next Work

ADR-009 was accepted by the project owner on 2026-07-28. T025, T026 and A012
are complete. They cover generic Snapshot Infrastructure only and do not
authorize Funding Arbitrage, Basket execution or Testnet.

ADR-010 was accepted on 2026-07-28 after current-code compatibility review.
T027, T028 and A013 are complete. They add only generic Basket decision
contracts, deterministic evidence serialization, Strategy compatibility and
explicit single-leg rejection. They create no OMS Order Groups, child orders
or exchange requests.

ADR-011 Parent Order Group and Multi-leg Execution Model was accepted on
2026-07-28 after Codex incorporated all eight second-review decisions and the
Execution Intent/Plan/Action/Child distinction. T029, T030, T031 and A014 are
complete.

The implemented scope is offline and bounded. T031 fails closed before any
exposure-changing Order Group child reaches an Execution adapter. Real
Portfolio action-permit issuance and external group submission remain blocked
until ADR-012 is accepted. Funding Arbitrage, Testnet and production
multi-leg execution remain unauthorized.

ADR-012 Portfolio Risk and Grouped Execution Authorization, ADR-013 Financial
Ledger and PnL Attribution, and ADR-014 Carry Application Boundary are now
Proposed for the 2026-07-29 batch review. No T032-or-later implementation task
and no A015-or-later acceptance item is assigned before Web GPT review and
explicit project-owner acceptance.

The proposals do not change the completed status of T029-T031/A014, implement
Portfolio Risk/Accounting/Carry, or remove the grouped external execution
block. Review entry:
`ai_collaboration/topics/funding_arbitrage/88_codex_20260729_batch_review_handoff.md`.
