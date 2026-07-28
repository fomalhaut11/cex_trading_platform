# Development Roadmap

Status legend: Complete, In progress, External, Planned.

## Phase 1 - Domain Foundation

Status: Complete.

- Repository structure, coding conventions and public package boundaries.
- Canonical identifiers, nanosecond time, fixed-point values and event metadata.
- Spot, perpetual, dated-future and option instrument contracts.
- Immutable public contracts and explicit package exports.

Exit evidence: T001-T002 complete with deterministic unit tests.

## Phase 2 - Market Data and State

Status: Complete.

- Binance Spot, USD-M and COIN-M instrument discovery and normalization.
- Trade, kline, mark/index/funding and depth event normalization.
- Validation, L1, partial depth and reconstructed order books.
- Deterministic recording, checksummed replay and bounded recorder handoff.

Exit evidence: T003-T006 complete; duplicate, gap, corruption and resync
scenarios accepted.

## Phase 3 - Trading Runtime

Status: Complete for the deterministic offline foundation.

- Registered online features and explicit provenance.
- Black-Scholes and Black-76 pricing, implied volatility and Greeks.
- Strategy runtime, fail-closed Risk, OMS and account/portfolio state.
- Venue-neutral execution plus authenticated Binance request mapping.
- Mandatory application flow from health and validation through execution.

Exit evidence: T007A-T015 complete; A001 passes 19 acceptance scenarios and
the complete regression passes 218 tests.

## Phase 4 - Production Readiness

Status: In progress.

1. Correct and maintain the documentation baseline.
2. Require the successful CI checks on protected branches after the
   direct-push policy is agreed.
3. Complete the Binance environment and private-stream application
   supervision boundary. **Complete (T019/A006).**
4. Add concrete HTTP/private WebSocket transport ownership and public
   server-time probing. **Complete (T020/A007).**
5. Add secrets management, aggregate health endpoints and operator controls.
   **Health aggregation and operator controls complete (T021/A008);
   credential delivery and durable operator recovery complete (T022/A009);
   authenticated operator boundary and mandatory deployment composition
   complete (T023/A010); bounded mTLS identity adapter, external-audit port
   and failure latching complete (T024/A011); concrete TLS termination and
   remote audit service configuration remain.**
6. Synchronize the deployment-host clock and calibrate health thresholds.
   **Public Testnet probes healthy; persistent approved time source remains.**
7. Run authenticated Binance Testnet acceptance.
8. Run target-host soak, burst, durability and latency-distribution acceptance.
9. Publish deployment, rollback, recovery and incident runbooks.
   **Initial operational runbooks complete (T024); target-host validation
   remains.**

Exit criterion: every gate in `remaining_external_gates.md` is passed with
recorded evidence. Completion authorizes a production-release review, not an
automatic real-money deployment.

## Phase 5 - Venue and Product Expansion

Status: Planned and scope-driven.

- Binance Options contract discovery and canonical market-stream mapping.
- Venue-provided IV and Greeks retained only as labelled venue analytics.
- Internal registered features remain authoritative for IV, Greeks and
  volatility surfaces.
- Additional venues are introduced through adapters without changing domain
  ownership or allowing venue payloads into the core.
- Rust migration is considered only after profiling identifies a justified
  boundary.

## Phase 6 - Portfolio Applications and Multi-Leg Trading

Status: In progress at the ADR-gated architecture-foundation layer.

- Typed, deterministic application-snapshot infrastructure is complete under
  ADR-009 (T025/T026/A012).
- Bounded generic N-leg Basket intents and single-leg compatibility are
  complete under ADR-010 (T027/T028/A013).
- ADR-011 Parent Order Group and Multi-leg Execution Model is accepted after
  the second Web GPT review. T029-T031/A014 bounded offline foundation work
  and the post-implementation safety remediation are complete; external
  exposure-changing group submission remains blocked by ADR-012.
- ADR-012 Portfolio Risk and Grouped Execution Authorization is Proposed for
  review. It covers execution-consistent positions, normalized margin facts,
  whole-Basket reservations, exact per-action permits, continuous supervision
  and recovery evidence. **No implementation task is authorized yet.**
- ADR-013 Financial Ledger and PnL Attribution is Proposed for the same review
  batch. It covers canonical fill/account financial facts, a balanced
  per-asset ledger, source/balance reconciliation, ownership allocation and
  derived PnL. **No implementation task is authorized yet.**
- ADR-014 Carry Application Boundary is Proposed for the same review batch. It
  places economic lifecycle, hedge assessment and ownership evidence in
  `applications.carry` while preserving generic platform authority.
  **No application implementation is authorized yet.**
- Extend OMS with durable Parent Order Groups and canonical child orders;
  existing Execution adapters remain child-order oriented. **Bounded offline
  foundation complete as T029-T031/A014; external group submission blocked by
  ADR-012.**
- Add normalized margin/collateral state and an idempotent Financial Ledger.
  **Proposed under ADR-012/013; implementation requires acceptance.**
- Add `applications/` as the concrete portfolio-strategy layer; Funding
  Arbitrage is the first validating application. **Proposed under ADR-014;
  implementation requires accepted/implemented dependencies.**
- The ADR-010 decision layer is validated with a Funding-shaped two-leg
  target and a synthetic option-spread-plus-Delta-hedge three-leg target.
  This is contract acceptance, not application or execution acceptance.

Detailed topology, interface drafts, compatibility rules and acceptance gates
are maintained in `multi_leg_portfolio_trading_plan.md`.

Entry gate: ADR-009 through ADR-014 are reviewed in dependency order. Planning
does not authorize implementation, Testnet or production trading.
