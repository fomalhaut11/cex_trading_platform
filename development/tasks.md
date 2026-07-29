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
| T032 | Execution-consistent Portfolio baseline/overlay and normalized margin/liquidation inputs | Complete | ADR-012, T016, T025 |
| T033 | Immutable Portfolio Risk contracts, pure N-leg projection and whole-Basket/action decisions | Complete | T032, T027, T029 |
| T034 | Durable Portfolio Risk reservations, permit generations, directives and recovery evidence | Complete | T033, T030 |
| T035 | Immediate pre-I/O Portfolio Risk guard with grouped external route still blocked | Complete | T031, T034 |
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
| A015 | Offline Portfolio position coverage, N-leg Risk, reservation, permit, recovery and blocked-route acceptance | Complete | T032-T035 |

A post-implementation review kept ADR-011 accepted and temporarily reopened
its implementation evidence. Commit
`c2c306dbe7675076ae200021d2c98f127736f09e` closed the identified T031/A014
gaps: immediate pre-I/O authority recheck, capacity suspension and
strategy/account active-group limits, child identity collision protection,
runtime single-writer enforcement and the missing fault/race cases. A014 is
therefore `Complete` after remediation. ADR-012 offline implementation is now
also complete, but grouped external submission remains blocked pending a
separate explicit Testnet promotion.

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

ADR-012 Portfolio Risk and Grouped Execution Authorization was accepted on
2026-07-29 for bounded offline implementation after the current branch
confirmed that the referenced ADR-011 remediation blockers were already
closed. T032-T035 and A015 are complete at implementation commit
`69297d52e764822a1bdd60a23a9b7fca8446a520`.

The implementation provides execution-consistent effective positions,
normalized margin/liquidation inputs, generic N-leg exposure projection,
whole-Basket reservations, exact action permits, generation invalidation,
directives, recovery/confirmation evidence and the immediate pre-I/O Risk
guard. `OrderGroupRuntime.submit_prepared_child()` remains hard-blocked.

Web GPT retained ADR-012 design acceptance and initially conditionally
accepted the implementation. A-01 through A-07 were remediated/confirmed at
`b082af0618e180f98441af5dc6d49c906994a012`: explicit snapshot freshness,
typed invalidation triggers, resource-key reservation capacity, versioned
target tolerance, unchanged Feature-owned Greeks and consume-before-I/O, and
typed failure statuses. The focused review accepted and closed every finding;
final result:
`ai_collaboration/topics/funding_arbitrage/96_web_gpt_adr012_formal_closure.md`.

ADR-013 Financial Ledger and PnL Attribution and ADR-014 Carry Application
Boundary remain Proposed. Funding Arbitrage, Accounting implementation,
Testnet and production multi-leg execution remain unauthorized. Current
ADR-013 review entry:
`ai_collaboration/topics/financial_ledger/20_codex_architecture_response.md`.
ADR-014 formal review follows ADR-013 scope alignment.
