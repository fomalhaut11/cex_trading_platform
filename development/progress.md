# Project Progress

Last updated: 2026-07-24

## Current Phase

Phase 4 - Production readiness and external acceptance.

The deterministic offline trading foundation is complete. This phase does not
authorize production trading; it closes deployment, recovery, supervision,
target-host performance and authenticated Testnet gates.

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
- Git repository initialized on `main` and synchronized to
  `https://github.com/fomalhaut11/cex_trading_platform`.
- Baseline commit `889572c3b62b2833143084b4eea79bf5a4bf7468` verified
  identical locally and on `origin/main`.
- Project files synchronized to `D:\cex_quant_codex_docs_v2`.
- Current-phase, roadmap, external-gate and architecture documents reconciled
  with the implemented scope; CI requirements documented.
- GitHub Actions CI implemented for Python 3.11 and 3.14 with compilation,
  regression, Ruff, strict MyPy, branch coverage and high-confidence secret
  scanning.
- Strict MyPy passes for all 64 source files.
- Initial branch coverage measured at 87.07%; CI minimum set to 85%.
- First complete remote GitHub Actions run passed quality/coverage and
  regression jobs on Python 3.11 and 3.14; coverage artifact retained.
- T016 checksummed append-only OMS journal, deterministic restart replay,
  fail-closed durability latch and venue-neutral REST/user-stream
  reconciliation kernel.
- A003 offline restart acceptance covering uncertain `SUBMITTING` recovery,
  REST convergence, user-stream fill completion and a second deterministic
  restart.
- T017 signed Binance Spot, USD-M and COIN-M order queries plus deterministic
  REST/private-stream normalization into the OMS reconciliation boundary.
- A004 offline Binance recovery-protocol acceptance covering raw REST
  convergence, Futures stream fill completion and restart persistence.
- T018 current Spot signature subscription, Futures listen-key lifecycle,
  bounded renewal/reconnect supervision and fail-closed startup reconciliation
  orchestration.
- A005 offline startup-race acceptance covering stream-first buffering, REST
  convergence, durable fill replay and a final restart.
- T019 immutable Binance Testnet/production endpoint profiles, explicit
  production acknowledgement and product/environment host validation.
- Interruptible private-stream supervision with real monotonic connection
  timestamps, consecutive exponential backoff and complete task cleanup.
- Private-stream application lifecycle with stream-first reconciliation,
  immutable readiness snapshots, fail-closed degradation and bounded shutdown.
- A006 offline environment and supervision acceptance covering Testnet
  defaults, production guarding, readiness opening and connection cleanup.
- T020 bounded asyncio Binance REST transport with strict request validation,
  bounded HTTP framing and explicit before/after-send failure semantics.
- Three-product public server-time adapters and an interruptible, bounded
  clock-probe service feeding the existing midpoint health monitor.
- Owned Spot signature-subscription and Futures listen-key WebSocket
  transports with complete renewal, cancellation and lease cleanup.
- A007 offline transport/clock acceptance from the default Testnet profile
  through concrete HTTP framing to healthy clock samples.
- T021 protocol-neutral aggregate health queries with stable ordered child
  reports, worst-status aggregation and sanitized fail-closed check failures.
- Fail-closed operator controller that starts halted, requires explicit
  activation, supports bounded idempotent commands and exposes immutable
  operational snapshots.
- Strict operator risk gate that rejects every intent while halted and permits
  reduce-only intents only when both strategy and global exposure shrink
  without crossing through zero.
- A008 scenario acceptance proving activation, permitted reduction, rejected
  expansion and emergency halt all stop or reach OMS/execution at the intended
  boundary.
- T022 explicit per-account environment credential bindings that read fresh
  values on every request, support external rotation and sanitize all lookup
  failures and representations.
- Checksummed, sequenced and bounded operator-command JSONL audit with an
  fsync-before-mutation boundary, exact restart restoration and durable
  idempotency beyond the in-memory command cache.
- Journal corruption, external modification, append failure or record-limit
  failure latches operator authority `HALTED` and reports `JOURNAL_FAILED`.
- A009 acceptance proving credential rotation changes the next signed request,
  no credential enters the operator journal and reduce-only authority is
  restored exactly after restart.

## In Progress

- Repository branch-protection planning.
- Authenticated Testnet private-stream and restart evidence preparation.
- Deployment secret injection and authenticated operator-command transport
  planning.
- External acceptance preparation.

## Open External Gates

- The Singapore VPN route now reaches all three Binance Testnet public time
  endpoints. A route change requires the credential-free smoke to be repeated.
- Windows Time is running automatically, but VPN Fake-IP routing currently
  blocks NTP over UDP/123. One-time HTTPS venue-time correction produced
  healthy offsets of -23.967 ms, +32.652 ms and +44.133 ms for Spot, USD-M
  and COIN-M respectively. A persistent approved time source is still needed.
- Authenticated Binance Testnet acceptance requires user-provided Testnet
  credentials through the credential-provider boundary.

## Next

1. Configure protected-branch checks after agreeing the direct-push policy.
2. Configure deployment secret injection and authenticated operator command
   transport around the completed T022 adapters.
3. Configure a persistent approved host time source and collect clock
   distributions for threshold calibration.
4. Run A002C authenticated Binance Testnet acceptance.
5. Run A002B target-host soak and latency-distribution acceptance.
6. Add production recovery runbooks and Binance Options mapping when each
   enters scope.

## Verification

- `python -m compileall -q src`: passed.
- `python -m unittest discover -s tests -v`: 336 passed.
- `python -m unittest discover -s tests/acceptance -v`: 27 passed.
- `ruff check src tests tools`: passed with Ruff 0.16.0.
- `python -m mypy`: passed with MyPy 2.3.0 for 78 source files.
- Pytest branch coverage: 86.43%; 85% CI gate passed.
- Release archive extraction and isolated regression: 218 passed.
- `websockets==16.1.1` import and transport construction: passed on Python 3.14.
- Binance public WebSocket handshake and receive: passed.
- Live trade raw-to-canonical normalization: passed; canonical validation
  correctly rejected the event because host clock skew exceeded policy.
