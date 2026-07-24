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
4. Add concrete transport ownership, secrets management, health endpoints and
   operator controls.
5. Synchronize the deployment-host clock and calibrate health thresholds.
6. Run authenticated Binance Testnet acceptance.
7. Run target-host soak, burst, durability and latency-distribution acceptance.
8. Publish deployment, rollback, recovery and incident runbooks.

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
