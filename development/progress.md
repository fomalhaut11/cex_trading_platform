# Project Progress

Last updated: 2026-07-23

## Current Phase

Phase 2 - Integration.

## Completed

- Architecture decisions for deployment, contracts and option analytics.
- Module topology, state ownership, coding and testing baselines.
- T001 project skeleton and public package boundaries.
- T002 core identifiers, nanosecond time, event metadata and fixed-point values.
- Canonical spot, perpetual, future and option instrument definitions.
- Initial canonical market facts and order-book sequence contracts.
- T004 raw-message normalization boundary, structured errors and canonical
  market-data validation.
- Canonical `KlineUpdate` and strongly typed event-source venue identity.
- Binance product-aware adapter and static instrument resolver.
- Binance trade, aggregate trade, book ticker, diff-depth and partial-depth
  normalization with official-format offline fixtures.
- Explicit receive-clock fallback for payloads without venue event time.
- T003 Binance mark/index/funding and kline normalization.
- Binance Spot, USD-M and COIN-M `exchangeInfo` instrument mapping.
- Explicit contract multiplier asset for linear and inverse products.
- Bounded combined-stream session, connection lifecycle and deterministic
  reconnect policy.
- Production `websockets` 16.1.x transport boundary.
- T005 single-writer L1 and exchange-supplied partial-depth state engines.
- Sequence-aware reconstructed order book with bounded pre-snapshot buffering,
  exact-decimal level identity and atomic delta application.
- Explicit duplicate, gap, `previous_sequence`, crossed-book and resync
  behavior with immutable reader views.
- T006 deterministic append-only JSONL recording, strict bounded reading,
  checksummed records and ordered replay for all canonical market events.
- T007A immutable feature values, validated dependency registry, deterministic
  online execution and explicit venue-option-analytics lineage.
- Injectable wall/monotonic nanosecond clocks, venue offset and RTT sampling,
  wall-jump detection and composable health reports.
- T007B Black-Scholes and Black-76 option valuation, deterministic implied
  volatility solving, Greeks and immutable volatility-surface contracts.
- Explicit no-arbitrage option bounds and finite-difference regression checks
  for both valuation models.
- Bounded single-worker recorder handoff with explicit overflow, drain, stop
  and failure-latching semantics.
- T008 synchronous strategy lifecycle, scope isolation, immutable position
  target intents and strict Risk/OMS boundary.
- T009 fail-closed Risk Engine with strategy/global limits, exact-decimal
  notionals, freshness and health gates.
- T010 single-writer OMS with risk-approved requests, legal transition checks,
  idempotent venue updates and immutable order views.
- T011 venue-neutral execution gateway plus pure Binance Spot, USD-M and
  COIN-M submit/cancel parameter mapping.
- T012 immutable balance/position/account snapshots and single-writer account
  state with idempotency and ordering guarantees.
- T013 deterministic fail-closed runtime pipeline with mandatory
  Strategy-to-Risk-to-OMS-to-Execution ordering.
- T014 authenticated Binance adapter with deterministic HMAC signing,
  credential redaction and explicit unknown-execution-state failures.
- A001 offline scenario acceptance covering replay/recovery, the trading
  pipeline, option mathematics, clock safety, OMS races and Binance mappings.
- T015 concrete feature, market-state, OMS and asynchronous-execution runtime
  adapters plus the complete application composition root.
- A002A 100,000-event order-book and recorder/replay baselines with stable
  digests, bounded retained memory and no leaked worker threads.

## In Progress

- External acceptance preparation and deployment handoff.

## Blocked

- MyPy cannot be installed in the current sandbox: package-index requests
  stall and direct PyPI wheel downloads are rejected by the sandbox network
  identity. Ruff and runtime tests remain green.
- Synchronization to `D:\cex_quant_codex_docs_v2` is blocked by the external
  path sandbox despite the target ACL granting the sandbox account modify
  access. The verified integration copy remains in the Codex workspace.
- Live smoke testing measured the local host clock roughly 13 seconds behind
  Binance. Production use requires clock synchronization and offset monitoring.

## Next

- A002B rerun the performance harness on target hardware and establish
  measured throughput/latency gates.
- A002C run authenticated Binance Testnet acceptance after test credentials
  and host clock synchronization are supplied.
- Production calibration of clock-health and recorder supervision thresholds.
- Binance Options instrument and stream mapping when option work enters scope.

## Verification

- `python -m compileall -q src`: passed.
- `python -m unittest discover -s tests -v`: 218 passed.
- `python -m unittest discover -s tests/acceptance -v`: 19 passed.
- `ruff check src tests tools`: passed with Ruff 0.15.22.
- Release archive extraction and isolated regression: 218 passed.
- `websockets==16.1.1` import and transport construction: passed on Python 3.14.
- Binance public WebSocket handshake and receive: passed.
- Live trade raw-to-canonical normalization: passed; canonical validation
  correctly rejected the event because host clock skew exceeded policy.
