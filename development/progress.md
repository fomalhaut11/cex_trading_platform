# Project Progress

Last updated: 2026-08-01

Current self-contained handoff:

`START_HERE.md`

## Current Phase

Primary delivery track: Kernel v1 compatibility freeze is active; T045
Execution Promotion composition audit and T046 mode-neutral offline
runtime/fault-harness implementation are complete. A018 offline promotion
acceptance is next. The sole active product target is the Binance
single-account BTC Funding Carry Fast-Track MVP.

Parallel external track: Phase 4 production readiness and external acceptance
continues. Neither track authorizes grouped Testnet or production trading.

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
- ADR-012 Portfolio Risk and Grouped Execution Authorization accepted for
  bounded offline implementation after the current branch confirmed that the
  repeated ADR-011 blockers were already remediated.
- T032 execution-consistent Portfolio position truth with explicit OMS
  coverage, cumulative-fill increments, exact replay, no-double-count
  rebaselining and normalized margin/liquidation inputs.
- T033 immutable unit-labelled Risk contracts and a pure generic N-leg engine
  for current/projected/conservative exposure, whole-Basket decisions,
  options Greeks, spreads, margin and exact action permits.
- T034 checksummed durable Risk journal and single-writer coordinator for
  reservations, authorization generations, permit liveness, directives,
  restart invalidation, recovery authorization and target confirmation.
- T035 `PortfolioRiskExecutionGuard` composes platform/operator checks with
  durable exact permit consumption at the shared pre-I/O boundary.
- A015 offline acceptance covers two-leg Spot/Perpetual, three-leg option
  spread plus Delta hedge, position coverage, reservation races, journal
  failures, action residuals and restart. Grouped external submission remains
  hard-blocked pending separate Testnet authorization.
- Web GPT accepted and closed ADR-012 findings A-01 through A-07. Commit
  `b082af0618e180f98441af5dc6d49c906994a012` provides explicit freshness,
  typed invalidation, resource claims, target tolerance and failure statuses;
  Feature-owned Greeks and durable permit-consume-before-I/O remain unchanged.
  ADR-012 implementation is now Accepted and its acceptance process is
  formally closed without reopening the ADR.
- T036 immutable authenticated financial facts, strong Accounting identities,
  generic economic-owner references and separate economic/observation/posting
  time contracts.
- T037 deterministic balanced per-asset mapping, checksummed append-only
  Accounting journal, durable-before-publish ledger state, source convergence,
  restart replay and exact append-only reversals.
- T038 independent source-completeness and balance proofs, append-only
  allocation with explicit unallocated remainder, versioned conversion paths
  and evidence, and generic realized/marked PnL read views.
- T039 bounded single-writer financial-fact handoff with explicit overflow,
  age, persistence-failure and aggregate-health semantics.
- A016 offline acceptance covers Spot, Perpetual, Funding, fees, private/history
  convergence, restart, reconciliation, allocation and valuation. The full
  regression passes 502 tests and 188 subtests with 85.18% branch coverage;
  Ruff, strict MyPy over 115 source files and the secret scan pass.
- T045 current-code Execution Promotion composition audit completed the call
  and dependency map, identity/causation map, state-writer table,
  happy/failure/restart matrix and bounded T046 plan. It found missing Runtime
  composition seams but no reason to change frozen Kernel v1 interfaces.
- T046 mode-neutral offline runtime now composes whole-Basket Risk admission,
  Order Group actions, exact permits, durable submit/cancel routing,
  OMS-to-Portfolio effects, Carry read-side state and ordered restart gates.
  Its deterministic adapter performs no network I/O. Evidence:
  `development/t046_offline_execution_runtime.md`.

## In Progress

- ADR-013 Financial Ledger and PnL Attribution remains approved in principle,
  awaiting final Web GPT acceptance. Project-owner-authorized offline
  implementation T036-T039/A016 is complete and recorded in
  `ai_collaboration/topics/financial_ledger/50_codex_adr013_offline_implementation_handoff.md`.
  This does not authorize authenticated source activation or external trading.
- ADR-014 Carry Application Boundary is Accepted. T040-T044/A017 are complete
  offline: authoritative Funding state, immutable Carry contracts, typed
  decision Snapshots, registered economic Features, pure open/close policy,
  durable Carry lifecycle/replay, Portfolio-derived hedge assessment,
  Accounting-derived financial finality and recovery proposals.
  `CarryApplicationRuntime` records generic Basket evidence and stops before
  Portfolio Risk, OMS and Execution. Implementation commit:
  `40d10125318ebafc6c9979dc6ee3447c10739657`.
- Web GPT accepted and closed the ADR-014 offline implementation after
  reviewing the handoff, public interface and ADR. No A-class correction or
  redesign was requested. Long-term guidance keeps Carry, CTA and Market
  Making state family-specific.
- Execution Promotion T045-T046 is complete. A018 fault/restart acceptance is
  the next credential-free scope. Authenticated grouped Testnet A019 remains
  unauthorized.
- Kernel v1 compatibility freeze is recorded in
  `architecture/kernel_v1_freeze.md`. The former Phase 0-5 platform sequence
  remains in `development/platform_delivery_plan.md` as deferred direction.
- The project owner retained but deferred T047 Application Runtime / SDK Lite,
  T048 historical Replay, T049 Paper Exchange and all non-MVP strategy work.
  The active plan is `development/funding_carry_fast_track_plan.md`:
  T046/A018, separately authorized A019 Testnet, T050 Operations/Shadow,
  A020 live readiness and separately authorized A021 controlled micro-live.
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

1. Complete A018's deterministic restart/fault matrix, frozen-boundary audit
   and self-contained Testnet readiness handoff without enabling external I/O.
2. Complete ADR-013 final review using the clarification response and offline
   implementation handoff; do not enable authenticated sources or trading.
3. Produce an explicit Testnet go/no-go artifact only after A018 passes;
   grouped external submission remains blocked until project-owner
   authorization.
4. After separately authorized A019, build only T050 Operations Lite and
   Shadow evidence required by A020; do not resume general SDK/Replay/Paper.
5. Require a separate real-money go/no-go before A021.
6. Configure protected-branch checks after agreeing the direct-push policy.
7. Configure concrete TLS/mTLS termination, protected identity forwarding,
   remote audit retention and deployment secret injection around T024.
8. Configure a persistent approved host time source and collect clock
   distributions for threshold calibration.
9. Run A002C authenticated Binance Testnet acceptance.
10. Run A002B target-host soak and latency-distribution acceptance.
11. Exercise and approve the initial runbooks on the target host; add Binance
   Options mapping when it enters scope.

## Verification

- `python -m compileall -q src`: passed.
- `python -m unittest discover -s tests -p "test*.py"`: 565 passed.
- ADR-014 A017: 5 acceptance scenarios passed.
- `ruff check src tests tools`: passed with Ruff 0.16.0.
- `python -m mypy --strict src`: passed with MyPy 2.3.0 for 140 source files.
- T045 composition audit: complete; Kernel v1 public interfaces unchanged.
- T046 offline runtime/fault harness: complete; external I/O disabled.
- Pytest branch coverage: 85.03%; the 85% CI gate passes locally with 565
  tests and 216 subtests.
- ADR-014 remote GitHub Actions run `30510254523` passed for handoff commit
  `ba32dce7ce468b14307088ef13e649c52f6fb74e`.
- Final ADR-014 evidence-only head `2835ee2523642f8650d3ecd2388fc6db694c52b0`
  passed GitHub Actions run `30510324704`.
- GitHub Actions run `30345476372` passed quality/coverage and regression on
  Python 3.11 and 3.14 for the original ADR-011 head `9ccf0c5`; remote
  remediation head `df2fd83` passed all three jobs in run `30351998834`;
  ADR-012 proposal baseline `fa0df9e` passed all three jobs in run
  `30354281030`; ADR-012 implementation/documentation head `1a86b84` passed
  all three jobs in run `30431970845`; ADR-012 conditional-remediation head
  `345791e` passed all three jobs in run `30439995029`.
- Release archive extraction and isolated regression: 218 passed.
- `websockets==16.1.1` import and transport construction: passed on Python 3.14.
- Binance public WebSocket handshake and receive: passed.
- Live trade raw-to-canonical normalization: passed; canonical validation
  correctly rejected the event because host clock skew exceeded policy.
