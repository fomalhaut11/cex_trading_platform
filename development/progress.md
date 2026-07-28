# Project Progress

Last updated: 2026-07-28

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
- T023 canonical HMAC-SHA256 operator envelopes with bounded freshness,
  deployment-derived actor identity, explicit per-action authorization and
  fresh environment-backed key rotation.
- Durable replay safety that treats exact redelivery as an idempotent retry,
  rejects changed content and cannot roll authority back across restart.
- Concrete operator and trading deployment roots that own the audit journal
  and make operator health and risk gating mandatory in the application.
- A010 offline acceptance covering invalid, expired, unauthorized and replayed
  commands, restart restoration, independent safety authority and secret
  exclusion.
- T024 bounded operator endpoint with mandatory mTLS identity, strict JSON
  schema, bounded request/client state, rate limiting and non-blocking
  concurrency admission.
- Secret-free external-audit contracts with certificate fingerprint evidence,
  received/terminal ordering, health latching and durable system halt on
  audit, executor, durability or monotonic-clock failure.
- A011 offline endpoint and restart acceptance proving dual mTLS/HMAC
  authentication, replay idempotency, bounded rejection paths and restored
  authority.
- Initial deployment, rollback/recovery and incident-response runbooks.
- ADR-009 Portfolio Decision Snapshot accepted after Web GPT review and
  project-owner approval.
- T025 generic immutable source-observation, freshness, coherence, readiness,
  metadata and publication contracts.
- T026 single-writer bounded Snapshot Coordinator with deterministic identity,
  source-sequence handling, failure latching and non-blocking evidence port.
- A012 offline decision-snapshot acceptance covering three-source coherence,
  fail-closed readiness, deterministic replay and restart from empty state.
- ADR-010 Basket Intent Architecture accepted after current-code compatibility
  review. It reuses `IntentId`, versions Objective Type references, keeps
  lifecycle out of the intent and canonically orders legs by account and
  instrument.
- T027 generic two-to-16-leg Basket contracts, versioned metadata-only
  Objective Type registry, bounded policy, deterministic identities and
  checksummed canonical evidence codec.
- T028 additive decision-snapshot Strategy input, Basket causation validation
  and explicit single-leg Pipeline rejection before Portfolio/Risk/OMS.
- A013 offline compatibility and replay acceptance covering unchanged
  `PositionTargetIntent`, BTC Spot `+10`/Perpetual `-10`, a three-leg option
  spread with Delta hedge, Snapshot mismatch and zero child execution.
- T029 immutable `OrderGroupId`, plan/action/permit contracts, exact
  checksums, bounded codecs and single-action permit binding.
- T030 generic two-to-16-leg Order Group state with one unresolved action,
  exact signed child-fill vectors, 8-attempt/64-child hard limits, lower
  deployment limits, mixed V1/V2 OMS journal replay and
  `RECOVERY_REQUIRED`.
- T031 shared durable submit handoff for the existing single-leg Pipeline:
  `SUBMITTING` is persisted before external I/O and immediate accepted,
  rejected, definitely-not-sent or unknown outcomes return to OMS.
- The grouped runtime prepares and replays synthetic child attempts offline
  but raises `GroupedExecutionBlockedError` before any Execution adapter;
  real permit issuance and external grouped submission remain ADR-012 gates.
- A014 offline acceptance covers two-leg Spot/Perpetual and three-leg
  option-spread/Delta-hedge groups, exact permits, same-ID technical retry,
  unknown recovery, hard/configured bounds, closure evidence, durability,
  mixed replay and unchanged single-leg behavior.
- ADR-011 post-review remediation adds a mandatory immediate safety recheck
  after durable preparation and before external I/O, correct before-dispatch
  failure classification, strategy/account active-group bounds, durable
  capacity suspension, global child-ID collision protection and runtime-level
  single-writer enforcement. Fault injection covers the newly identified
  halt, append, recovery and ownership boundaries without adding ADR-012 Risk
  logic or enabling grouped external execution.

## In Progress

- ADR-012 Portfolio Risk Extension architecture review. No portfolio Delta,
  basis, margin, liquidation calculation or real action-permit issuance has
  been implemented.
- Repository branch-protection planning.
- Authenticated Testnet private-stream and restart evidence preparation.
- Concrete TLS termination, protected identity forwarding and remote audit
  service configuration around the completed bounded endpoint.
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

1. Draft and review ADR-012 Portfolio Risk Extension against the implemented
   immutable group views and permit-validation boundary.
2. Keep grouped external submission blocked until ADR-012 is accepted and
   its implementation/acceptance tasks are explicitly authorized.
3. Configure protected-branch checks after agreeing the direct-push policy.
4. Configure concrete TLS/mTLS termination, protected identity forwarding,
   remote audit retention and deployment secret injection around T024.
5. Configure a persistent approved host time source and collect clock
   distributions for threshold calibration.
6. Run A002C authenticated Binance Testnet acceptance.
7. Run A002B target-host soak and latency-distribution acceptance.
8. Exercise and approve the initial runbooks on the target host; add Binance
   Options mapping when it enters scope.

## Verification

- `python -m compileall -q src`: passed.
- `python -m unittest discover -s tests -q`: 430 passed.
- `python -m unittest discover -s tests/acceptance -q`: 37 passed.
- `ruff check src tests tools`: passed with Ruff 0.16.0.
- `python -m mypy`: passed with MyPy 2.3.0 for 93 source files.
- Pytest branch coverage: 86.25%; the 85% CI gate passes locally with 430
  tests and 133 subtests.
- GitHub Actions run `30345476372` passed quality/coverage and regression on
  Python 3.11 and 3.14 for the original ADR-011 head `9ccf0c5`; remote
  remediation head `df2fd83` passed all three jobs in run `30351998834`.
- Release archive extraction and isolated regression: 218 passed.
- `websockets==16.1.1` import and transport construction: passed on Python 3.14.
- Binance public WebSocket handshake and receive: passed.
- Live trade raw-to-canonical normalization: passed; canonical validation
  correctly rejected the event because host clock skew exceeded policy.
