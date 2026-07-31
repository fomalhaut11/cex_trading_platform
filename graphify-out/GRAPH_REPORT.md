# Graph Report - .  (2026-07-31)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 4559 nodes · 15955 edges · 122 communities (111 shown, 11 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 3169 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `59733c6f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 104
- Community 105
- Community 106
- Community 112
- Community 113
- Community 115
- Community 117
- Community 118
- Community 119
- Community 121
- Community 124
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133

## God Nodes (most connected - your core abstractions)
1. `InstrumentId` - 113 edges
2. `OrderRequest` - 90 edges
3. `Quantity` - 80 edges
4. `BinanceProduct` - 74 edges
5. `PositionTargetIntent` - 70 edges
6. `OrderEvent` - 60 edges
7. `BasketTargetIntent` - 60 edges
8. `OrderGroupStateMachine` - 59 edges
9. `OrderGroupView` - 58 edges
10. `BinanceCredentials` - 57 edges

## Surprising Connections (you probably didn't know these)
- `Adr013AcceptanceTests` --uses--> `AllocationBook`  [INFERRED]
  tests/acceptance/test_adr013_accounting.py → src/cex_quant/accounting/allocation.py
- `AccountingAllocationTests` --uses--> `AllocationBook`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/allocation.py
- `MemoryJournal` --uses--> `AllocationBook`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/allocation.py
- `ledger_view()` --calls--> `FinancialFactMetadata`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/facts.py
- `accounting_state()` --calls--> `FinancialFactMetadata`  [INFERRED]
  tests/test_accounting_attribution.py → src/cex_quant/accounting/facts.py

## Import Cycles
- None detected.

## Communities (122 total, 11 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (67): AuthenticatedBinanceExecutionAdapter, _error_code(), _error_message(), AccountId, Any, VenueOrderId, Authenticated Binance Spot and Futures execution boundary. The module owns…, Signed submit, cancel and query gateway for one Binance product. (+59 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (45): BinanceHttpRequest, BinanceHttpResponse, BinanceProduct, BinanceProduct, StrEnum, ClockHealthMonitor, Clock injection, venue offset sampling and clock-health evaluation., One venue clock observation using the request midpoint estimate. (+37 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (51): AllocationBook, Validate allocations without changing Accounting financial totals., _add_money(), AttributionCompleteness, build_pnl_attribution(), PnlAttributionView, PnlComponent, PnlComponentType (+43 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (25): Single-writer bounded coordination of typed decision snapshots., Pure application adapter from ordered source views to a typed value., SnapshotAssembler, assess_snapshot(), MonotonicNanos, UnixNanos, Pure deterministic readiness assessment for decision snapshots., Assess latest observations without mutating source or runtime state. (+17 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (64): deterministic_order_group_id(), execution_plan_parameters_checksum(), ExecutionAction, ExecutionActionPermit, ExecutionActionState, ExecutionActionView, ExecutionPlanRef, OrderGroupAdmission (+56 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (31): Stable Objective Type registrations for Funding Carry economics., BasketIntentPolicyError, BasketTargetLeg, canonical_leg_key(), create_basket_target_intent(), deterministic_basket_intent_id(), deterministic_basket_leg_id(), ObjectiveTypeDefinition (+23 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (37): SnapshotSourceId, InstrumentId, Structured canonical identity; `symbol` is venue-native and opaque., FundingRateState, _is_stale(), Single-writer latest Funding market state for one perpetual instrument., Own the latest normalized Funding fact and publish an immutable view., Single-writer market-state engines and immutable reader views. Mutable state… (+29 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (13): _ActionRecord, OrderGroupStateMachine, ClientOrderId, Decimal, GroupActionId, IntentId, OrderGroupId, UnixNanos (+5 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (52): OrderEvent, OrderRequest, OrderSubmitEvent, OrderSubmitOutcome, OrderView, Immutable order contracts at the risk-to-OMS and venue-to-OMS boundaries., Canonical request created by OMS from one approved instruction., One normalized venue update; `venue_update_id` is its idempotency key. (+44 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (26): _error_text(), PrivateStreamApplication, PrivateStreamApplicationSnapshot, PrivateStreamApplicationState, PrivateStreamApplicationStateError, BaseException, RuntimeError, StrEnum (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (32): ManualClock, operator_command(), Portfolio, MonotonicNanos, TestCase, UnixNanos, RuntimeOperationsAcceptanceTests, SystemCheck (+24 more)

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (34): Keepalive, MonotonicNow, SnapshotHandler, BinancePrivateOrderStreamProcessor, Classify one private-stream frame and normalize order updates., _finish_cancelled(), _monotonic_now(), PrivateOrderStreamSession (+26 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (52): OperatorAction, OperatorCommandConflictError, OperatorControlDurabilityError, OperatorControlSnapshot, RuntimeError, Raised when one idempotency key is reused for a different command., Raised after a journal failure has latched trading halted., OperatorAuthenticationError (+44 more)

### Community 13 - "Community 13"
Cohesion: 0.11
Nodes (44): Binance JSON stream normalization without network or SDK dependencies., AggregateTrade, BestBidAsk, FundingRateUpdate, IndexPriceUpdate, KlineUpdate, MarketTrade, MarkPriceUpdate (+36 more)

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (64): MarketEvent, Composition root for the complete synchronous trading application., Own lifecycle and composition of the mandatory risk-gated pipeline., TradingApplication, OperatorControlDeploymentConfig, OperatorControlRuntime, OperatorEndpointDeploymentConfig, MarketEvent (+56 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (29): Adr011AcceptanceTests, A014 offline acceptance for the accepted ADR-011 boundary., action_for(), admission(), _basket(), execution_plan(), leg(), ManualClock (+21 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (48): Pure Funding Carry application contracts and policy., base_to_instrument_quantity(), create_funding_carry_pair(), _fixed(), FundingCarryPair, _instrument(), AccountId, AssetId (+40 more)

### Community 17 - "Community 17"
Cohesion: 0.28
Nodes (3): ClientOrderId, Exception, RuntimeError

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (36): FinancialSourceFact, AccountCashFlowFact, AccountCashFlowType, CashComponent, ExecutionFillFact, FillSide, StrEnum, Immutable canonical financial source facts for ADR-013. Facts represent… (+28 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (36): ObservationId, Parse a decimal string without binary floating-point conversion., Instrument, Tradable product definition independent of venue payload formats., PortfolioRiskEngine, Stateless whole-Basket and exact-action Risk engine., InstrumentSensitivity, Registered model output consumed by Risk; Risk does not derive Greeks. (+28 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (50): BinanceCredentialProvider, BinanceHttpTransport, canonical_query(), hmac_sha256_hex(), Protocol, Minimal HTTP port; implementations select the product base URL., Encode parameters deterministically by key, independent of map order., Pure signing helper useful for conformance tests. (+42 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (27): BinanceCredentials, HMAC credentials whose representation never exposes either value., Return the lowercase HMAC-SHA256 digest for an encoded payload., BinanceFuturesUserStreamLease, BinanceProduct, Opaque Futures listenKey that never appears in representations., BinanceFuturesPrivateStreamTransport, BinanceSpotPrivateStreamTransport (+19 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (11): Runs one strategy serially in caller-provided input order. The caller is the…, StrategyRuntime, BadOutputStrategy, HookFailureStrategy, intent(), StrategyId, RaisingStrategy, RecordingStrategy (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.09
Nodes (19): SplitResult, BinanceEnvironment, BinanceEnvironmentConfig, BinanceProductEndpoints, _defaults(), _host(), BinanceProduct, StrEnum (+11 more)

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (42): _average_from_quote_and_quantity(), _decimal_string(), _futures_user_update(), _identifier(), _integer(), _malformed(), _milliseconds_to_nanos(), normalize_binance_order_query() (+34 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (58): Deterministic pre-trade risk contracts and evaluation., _approval_reservation_payload(), _confirmation_payload(), _decode_resource_claims(), _encode_resource_claims(), _PermitRecord, PortfolioRiskAuthorizationError, PortfolioRiskCoordinatorError (+50 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (27): LedgerIngestResult, _DrainItem, _FactItem, FinancialFactExpiredError, FinancialFactHandoff, FinancialFactHandoffError, FinancialFactHandoffSnapshot, FinancialFactHandoffStateError (+19 more)

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (34): ExecutionConsistentPositionState, PortfolioPositionConflictError, PortfolioPositionCoverageError, PortfolioPositionStateError, PortfolioPositionWriterViolationError, AccountId, Decimal, RuntimeError (+26 more)

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (48): ObservedFinancialFact, AccountingJournal, AccountingJournalEntry, AccountingJournalError, AccountingJournalIntegrityError, AccountingJournalIoError, _decode_record(), _json_object() (+40 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (52): IdentifierT, EventTimeSource, StrEnum, Metadata shared by immutable domain events., Precision supplied by an upstream source before nanosecond conversion., Origin of `event_time_ns`, independent of its storage unit., TimePrecision, Strong identifiers shared by domain contracts. (+44 more)

### Community 30 - "Community 30"
Cohesion: 0.10
Nodes (34): FeatureUpdate, FeatureUpdateDisposition, FeatureUpdateReport, InvalidFeatureEventError, OnlineFeatureEngine, StrEnum, Single-writer deterministic online feature engine., Raised when an event lacks canonical metadata. (+26 more)

### Community 31 - "Community 31"
Cohesion: 0.10
Nodes (20): OperatorController, Thread-safe, bounded and idempotent in-process trading authority., AuthenticatedOperatorDeploymentAcceptanceTests, TestCase, AllowRisk, Check, command(), context() (+12 more)

### Community 32 - "Community 32"
Cohesion: 0.08
Nodes (23): child_order_id_for_action(), deterministic_group_action_id(), execution_action_checksum(), _fixed(), _fixed_or_none(), BasketLegId, ClientOrderId, GroupActionId (+15 more)

### Community 33 - "Community 33"
Cohesion: 0.09
Nodes (31): _d1_d2(), ImpliedVolatilityError, ImpliedVolatilityFailure, _intrinsic(), _normal_cdf(), _normal_pdf(), option_greeks(), option_price() (+23 more)

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (18): OrderGroupView, GroupedExecutionBlockedError, OrderGroupPersistenceError, OrderGroupRecoveryError, OrderGroupRuntime, OrderGroupRuntimeError, ClientOrderId, GroupActionId (+10 more)

### Community 35 - "Community 35"
Cohesion: 0.13
Nodes (37): ScopeKey, _apply_other_reservations(), _apply_reservations(), _apply_working_envelope(), _assessment_checksum(), _calculate_exposure(), _decision_status(), _deduplicate_reasons() (+29 more)

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (37): AccountingCodecError, canonical_json(), _checksum(), _decode_component(), _decode_instrument_id(), decode_ledger_transaction(), _decode_metadata(), decode_observed_financial_fact() (+29 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (43): FundingCarryFeatureInput, Coherent application input consumed by the generic Feature engine., CarryRecoveryProposal, A fresh economic preference with no OMS or Risk authority., Adr014CarryAcceptanceTests, coordinator(), evaluate(), FundingCarryDecisionSnapshot (+35 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (45): AccountSnapshot, AccountUpdate, Balance, Position, PositionAccounting, StrEnum, Immutable account, balance, and position contracts., Atomic normalized venue update containing absolute entity values. (+37 more)

### Community 39 - "Community 39"
Cohesion: 0.09
Nodes (16): EventMetadata, EventSource, Origin of a canonical event., Transport-neutral metadata composed into strongly typed events., BinanceNormalizerTest, normalizer(), BinanceProduct, TestCase (+8 more)

### Community 40 - "Community 40"
Cohesion: 0.10
Nodes (33): FinancialReconciliationId, FinancialSourceKind, LedgerAccountType, StrEnum, _add_money(), AuthoritativeBalance, BalanceReconciliationProof, StrEnum (+25 more)

### Community 41 - "Community 41"
Cohesion: 0.19
Nodes (15): microseconds_to_nanos(), milliseconds_to_nanos(), UnixNanos, Convert Unix milliseconds without pretending the source was precise., Convert Unix microseconds to the canonical unit., BinanceMarketDataNormalizer, Any, MarketEvent (+7 more)

### Community 42 - "Community 42"
Cohesion: 0.11
Nodes (23): _canonical(), _decode_record(), _encode_record(), JsonLinesOperatorCommandJournal, OperatorJournalError, OperatorJournalIntegrityError, OperatorJournalIoError, Path (+15 more)

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (15): Immutable assessment result; ALLOW carries no rejection reasons., Complete point-in-time input to an evaluation; contains no I/O., RiskContext, RiskDecision, AccountPolicy, OmsIdentityPolicy, OrderParameters, OrderPolicy (+7 more)

### Community 44 - "Community 44"
Cohesion: 0.14
Nodes (13): OperatorEndpointRecoveryAcceptanceTests, TestCase, endpoint(), identity(), MemoryAuditSink, OperatorEndpointTests, ManualClock, TestCase (+5 more)

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (24): CarryApplicationFactId, deterministic_application_position_id(), deterministic_carry_fact_id(), deterministic_carry_pair_id(), ApplicationPositionId, CarryPairId, DecisionSnapshotId, StrategyId (+16 more)

### Community 46 - "Community 46"
Cohesion: 0.07
Nodes (37): BinanceHttpTransportFailure, Exception, Transport failure with explicit knowledge of whether bytes were sent., AsyncioBinanceHttpTransport, BinanceHttpTimeouts, _contains_control(), _contains_unsafe_target_character(), _encode_request() (+29 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (28): Clock, OperatorCommand, One authenticated command after a transport adapter validates identity., AuthenticatedOperatorCommandService, _canonical_payload(), EnvironmentOperatorKeyProvider, HmacOperatorCommandAuthenticator, operator_command_signature() (+20 more)

### Community 48 - "Community 48"
Cohesion: 0.05
Nodes (38): Canonical time types and conversion constants. Unix nanoseconds are comparable…, Clock, ClockHealthThresholds, MonotonicClockRegressionError, MonotonicNanos, Protocol, RuntimeError, UnixNanos (+30 more)

### Community 49 - "Community 49"
Cohesion: 0.18
Nodes (34): Price, Exact price in an instrument's quote convention., _action_from_dict(), _action_to_dict(), _admission_from_dict(), _admission_to_dict(), _boolean(), _decode() (+26 more)

### Community 50 - "Community 50"
Cohesion: 0.12
Nodes (25): ExecutionPermitId, PortfolioReconciliationId, _decode_approval_reservation(), _decode_basket(), _decode_confirmation(), _decode_permit(), _decode_recovery(), _integer() (+17 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (5): ExactRiskValue, Fixed-point Risk evidence with an explicit unit and provenance., _require_checksum(), _require_id(), _require_text()

### Community 52 - "Community 52"
Cohesion: 0.16
Nodes (8): BlockingRecorder, CollectingRecorder, event_at(), FailingRecorder, FlushFailingRecorder, GatedControlQueue, Expose the lifecycle state after it changes but before control enqueue., RecorderHandoffTests

### Community 53 - "Community 53"
Cohesion: 0.23
Nodes (11): IsolatedAsyncioTestCase, SecurityAndOperatorRecoveryAcceptanceTests, AuthenticatedBinanceAdapterTest, CapturingTransport, instrument(), order(), AccountId, Any (+3 more)

### Community 54 - "Community 54"
Cohesion: 0.14
Nodes (18): EventReader, EventRecorder, Protocol, StrEnum, Stable contracts and failures for append-only event recording., Flush userspace buffers; durability policy belongs to the adapter., RecorderErrorCode, ReplaySink (+10 more)

### Community 55 - "Community 55"
Cohesion: 0.15
Nodes (17): LedgerAccountId, deterministic_ledger_account_id(), deterministic_ledger_posting_id(), deterministic_ledger_transaction_id(), _digest(), AccountId, AssetId, FinancialFactId (+9 more)

### Community 56 - "Community 56"
Cohesion: 0.09
Nodes (16): BinanceGoldenMappingAcceptanceTests, _book(), _Execution, _Features, _Health, _instrument(), _intent(), _pipeline() (+8 more)

### Community 57 - "Community 57"
Cohesion: 0.15
Nodes (14): CanonicalOmsApplicationService, OmsInvariantError, OmsPersistenceError, OmsRecoveryError, ClientOrderId, RuntimeError, UnixNanos, Own canonical order state with optional durable journal recovery. (+6 more)

### Community 58 - "Community 58"
Cohesion: 0.08
Nodes (25): _DrainItem, _EventItem, OverflowPolicy, BaseException, MarketEvent, RuntimeError, StrEnum, Bounded worker handoff for synchronous event recorders. (+17 more)

### Community 59 - "Community 59"
Cohesion: 0.32
Nodes (16): decode_basket_target_intent(), encode_basket_target_intent(), _integer(), _intent_from_dict(), _intent_to_dict(), _json_bytes(), _leg_from_dict(), _list() (+8 more)

### Community 60 - "Community 60"
Cohesion: 0.11
Nodes (16): BinancePrivateWebSocketConnection, BinancePrivateWebSocketConnector, _bounded(), _connected(), _lease_operation(), AbstractAsyncContextManager, Protocol, Task (+8 more)

### Community 61 - "Community 61"
Cohesion: 0.19
Nodes (10): OrderStateMachine, ClientOrderId, Own one order's mutable state and expose only immutable snapshots., OmsAcceptanceTests, _order_request(), ClientOrderId, _venue_event(), event() (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (24): PerformanceHarnessTests, Small smoke tests; production-sized loads remain explicit opt-in runs., BenchmarkResult, environment_snapshot(), _instrument(), _level(), _metadata(), os_cpu_count() (+16 more)

### Community 63 - "Community 63"
Cohesion: 0.13
Nodes (15): _canonical(), _decode(), _integer(), JsonLinesPortfolioRiskJournal, PortfolioRiskJournalEntry, PortfolioRiskJournalError, PortfolioRiskJournalIntegrityError, PortfolioRiskJournalIoError (+7 more)

### Community 64 - "Community 64"
Cohesion: 0.04
Nodes (40): EventHandler, ConnectionLifecycle, ConnectionPolicy, ConnectionState, ConnectionTransitionError, DurationNanos, MonotonicNanos, RuntimeError (+32 more)

### Community 65 - "Community 65"
Cohesion: 0.09
Nodes (17): HealthCheck, Protocol, Interface implemented by components that expose current health., Return the stable component name., Evaluate and return current health., OperatorCommandJournal, Clock, Decimal (+9 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (15): AcceptingState, basket(), basket_leg(), BasketDecisionPort, BasketIntentAcceptanceTests, FixedStrategy, Healthy, instrument() (+7 more)

### Community 67 - "Community 67"
Cohesion: 0.13
Nodes (21): encode_carry_application_fact(), CarryApplicationFact, create_carry_application_fact(), encode_carry_fact_payload(), _kind(), _payload_ownership(), ApplicationPositionId, CarryFactPayload (+13 more)

### Community 68 - "Community 68"
Cohesion: 0.25
Nodes (8): BasketStrategy, BasketStrategyRuntimeTests, publication(), DecisionIntent, DecisionSnapshotId, TestCase, UnixNanos, target()

### Community 69 - "Community 69"
Cohesion: 0.20
Nodes (12): coordinator(), evaluate(), EvidenceCollector, FailingAssembler, FailingEvidencePort, make_policy(), populate(), SnapshotSourceId (+4 more)

### Community 70 - "Community 70"
Cohesion: 0.15
Nodes (33): BasketIntentPolicy, BasketTargetIntent, ObjectiveTypeRegistry, One immutable bounded portfolio target, not an execution plan., Deployment bounds below the immutable contract hard limits., Immutable deterministic registry of Objective Type metadata., Strategy runtime contracts that transform information into trade intents.…, One deterministically numbered input delivered to a strategy. (+25 more)

### Community 71 - "Community 71"
Cohesion: 0.18
Nodes (31): _boolean(), _canonical_json(), _decode_blob(), _decode_entry(), _decode_event(), _decode_instrument(), decode_journal_record(), _decode_request() (+23 more)

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (14): CoherenceGroup, DurationNanos, _require_duration(), SourceFreshnessRule, SnapshotSourceId, snapshot_policy(), snapshot_policy(), assess() (+6 more)

### Community 73 - "Community 73"
Cohesion: 0.14
Nodes (51): CarryOwnershipId, CarryCodecError, decode_carry_application_fact(), _decode_ownership(), _decode_payload(), _integer(), _object(), _object_list() (+43 more)

### Community 74 - "Community 74"
Cohesion: 0.05
Nodes (52): Canonical instrument definitions. Public API covers spot, perpetual, dated…, ContractValueType, ExerciseStyle, FutureSpecification, InstrumentKind, InstrumentStatus, OptionSide, OptionSpecification (+44 more)

### Community 75 - "Community 75"
Cohesion: 0.11
Nodes (9): ManualClock, IsolatedAsyncioTestCase, MonotonicNanos, SSLContext, StreamReader, UnixNanos, ServerTimeOpener, TransportAndClockAcceptanceTests (+1 more)

### Community 76 - "Community 76"
Cohesion: 0.11
Nodes (21): CarryApplicationRuntime, CarryApplicationRuntimeError, CarryApplicationRuntimeStateError, CarryApplicationRuntimeStatus, CarryBasketEvidencePort, CarryRuntimeDisposition, CarryRuntimeResult, BaseException (+13 more)

### Community 77 - "Community 77"
Cohesion: 0.17
Nodes (9): BinanceFuturesUserStreamControlAdapter, AccountId, Create, renew and close the 60-minute Futures listenKey lease., _response_object(), BinanceFuturesStreamControlTests, CapturingHttpTransport, AccountId, IsolatedAsyncioTestCase (+1 more)

### Community 78 - "Community 78"
Cohesion: 0.15
Nodes (7): DecisionIntent, Exception, Never, StrategyInput, Transform one input into zero or more decision intents., Release deterministic in-memory state without performing I/O., Initialize deterministic in-memory state.

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (12): BookReplaySink, canonical_stream(), delta(), GatedRecorder, level(), metadata(), BaseException, MarketEvent (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (9): Path, RuntimeError, Typed storage-boundary failure; corrupt data is never skipped silently., RecorderError, JsonLinesRecorder, Exception, MarketEvent, Path (+1 more)

### Community 81 - "Community 81"
Cohesion: 0.27
Nodes (15): _annualized(), _basis(), _estimated_cost(), _event(), _expected_funding(), funding_carry_feature_definitions(), _net_carry(), _output() (+7 more)

### Community 82 - "Community 82"
Cohesion: 0.25
Nodes (5): One system-computed IV observation; no interpolation is implied., Immutable, deterministically ordered raw surface points., VolatilitySurfacePoint, VolatilitySurfaceSnapshot, VolatilitySurfaceTests

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (7): ApprovedOrderIntent, ClientOrderId, UnixNanos, Risk-approved, venue-neutral order instruction accepted by OMS. This contract…, _validate_order_fields(), approved(), OmsModelTests

### Community 84 - "Community 84"
Cohesion: 0.19
Nodes (10): decision(), _FailingJournal, _Identities, intent(), _NthFailJournal, OmsJournalTests, ClientOrderId, OmsJournalEntry (+2 more)

### Community 85 - "Community 85"
Cohesion: 0.12
Nodes (18): CarryJournal, Protocol, CarryPositionView, CarryPositionBook, _project(), ApplicationPositionId, CarryFactPayload, CarryPairId (+10 more)

### Community 86 - "Community 86"
Cohesion: 0.30
Nodes (6): basket(), BasketIntentTests, instrument(), leg(), AccountId, TestCase

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (24): BookLevel, Price level; zero quantity represents deletion in a delta., RuntimeError, StateBufferOverflowError, _apply_levels(), _is_crossed(), _levels_by_price(), Decimal (+16 more)

### Community 88 - "Community 88"
Cohesion: 0.25
Nodes (10): _Accounts, decision(), _Gateway, _Identities, intent(), _Orders, AccountId, TestCase (+2 more)

### Community 89 - "Community 89"
Cohesion: 0.18
Nodes (5): BlockingConnection, BlockingTransport, ConnectionContext, BaseException, TracebackType

### Community 90 - "Community 90"
Cohesion: 0.20
Nodes (6): ExampleGateway, ExecutionContractsTest, ExecutionGatewayProtocolTest, instrument(), IsolatedAsyncioTestCase, TestCase

### Community 91 - "Community 91"
Cohesion: 0.15
Nodes (4): Immediate submit result, not canonical order lifecycle state., SubmitResult, Submit once using `command.client_order_id` as idempotency key., Exception

### Community 92 - "Community 92"
Cohesion: 0.31
Nodes (6): DurableExecutionHandoffTests, _Execution, _Guard, _Oms, ClientOrderId, request()

### Community 93 - "Community 93"
Cohesion: 0.31
Nodes (8): coordinator(), DecisionSnapshotAcceptanceTests, observation(), policy(), SnapshotSourceId, Offline acceptance scenarios for coherent decision snapshots., ThreeSourceAssembler, ThreeSourceDecisionInput

### Community 94 - "Community 94"
Cohesion: 0.15
Nodes (9): funding_feature_value(), require_funding_carry_features(), FeatureSnapshot, Deterministically ordered point-in-time engine state., FeatureEngineAdapter, MarketEvent, Feature-engine adapter for the synchronous pipeline port., Update the engine, then expose its immutable point-in-time snapshot. (+1 more)

### Community 95 - "Community 95"
Cohesion: 0.38
Nodes (5): instrument_id(), level(), MarketDataValidationTest, metadata(), TestCase

### Community 96 - "Community 96"
Cohesion: 0.07
Nodes (30): ObservationIdentityConflictError, BaseException, DecisionSnapshotId, MonotonicNanos, Protocol, RuntimeError, T, UnixNanos (+22 more)

### Community 97 - "Community 97"
Cohesion: 0.43
Nodes (5): funding_objective_registry(), strategy_runtime(), economic_policy(), FundingCarryStrategyTests, TestCase

### Community 99 - "Community 99"
Cohesion: 0.16
Nodes (10): ClockFailClosedAcceptanceTest, ManualClock, model_inputs(), OptionAnalyticsAcceptanceTest, MonotonicNanos, TestCase, UnixNanos, Scenario acceptance tests for option analytics and clock fail-closed safety. (+2 more)

### Community 100 - "Community 100"
Cohesion: 0.22
Nodes (8): DelayedGateway, FakeOms, ClientOrderId, IsolatedAsyncioTestCase, UnixNanos, request(), snapshot(), StartupReconciliationTests

### Community 101 - "Community 101"
Cohesion: 0.07
Nodes (28): _add_money(), AllocationError, AllocationIdentityConflictError, AttributionAllocation, create_allocation(), _normalize_money(), AssetId, AttributionAllocationId (+20 more)

### Community 104 - "Community 104"
Cohesion: 0.19
Nodes (7): AppendResult, MarketEvent, Location and size of one successfully appended record., Append one event or fail explicitly without reporting success., Read records in append order, failing on the first invalid record., Consume one event synchronously in recorded order., MarketEvent

### Community 105 - "Community 105"
Cohesion: 0.11
Nodes (10): BinanceStreamSessionTest, FakeConnection, FakeContext, FakeTransport, FixedClock, BaseException, IsolatedAsyncioTestCase, MonotonicNanos (+2 more)

### Community 106 - "Community 106"
Cohesion: 0.26
Nodes (9): SecretScannerTests, Finding, main(), Path, Fail CI when tracked text contains high-confidence credential patterns., repository_files(), scan_repository(), scan_text() (+1 more)

### Community 112 - "Community 112"
Cohesion: 0.22
Nodes (6): Self, FixedPoint, Decimal, An exact decimal value represented by an integer and decimal scale., Return an exact Decimal representation., Return the same value at another scale, rejecting precision loss.

### Community 113 - "Community 113"
Cohesion: 0.30
Nodes (5): EventId, ExampleEvent, FeatureValueValidationTests, metadata(), OnlineFeatureEngineTests

### Community 115 - "Community 115"
Cohesion: 0.22
Nodes (8): decode_event(), encode_event(), _json_bytes(), Encode one event to deterministic UTF-8 JSON without a line terminator., Decode and validate one complete record without a line terminator., Bounded append-only JSON Lines storage adapter., metadata(), RecorderCodecTests

### Community 118 - "Community 118"
Cohesion: 0.44
Nodes (4): instrument_id(), MarketDataEventsTest, metadata(), TestCase

### Community 119 - "Community 119"
Cohesion: 0.50
Nodes (3): _require_bounded_unique(), _require_id(), _require_reason()

### Community 124 - "Community 124"
Cohesion: 0.18
Nodes (9): InstrumentMappingErrorCode, StrEnum, BinanceProduct, InstrumentResolver, Protocol, StrEnum, Return a canonical instrument for an exact venue symbol., Explicit symbol table suitable for tests and immutable runtime snapshots. (+1 more)

## Knowledge Gaps
- **2 isolated node(s):** `cex-quant`, `SecretPattern`
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InstrumentId` connect `Community 6` to `Community 0`, `Community 4`, `Community 5`, `Community 8`, `Community 10`, `Community 13`, `Community 16`, `Community 18`, `Community 19`, `Community 25`, `Community 27`, `Community 29`, `Community 33`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 39`, `Community 40`, `Community 41`, `Community 45`, `Community 49`, `Community 53`, `Community 56`, `Community 59`, `Community 61`, `Community 62`, `Community 66`, `Community 68`, `Community 71`, `Community 73`, `Community 74`, `Community 83`, `Community 86`, `Community 87`, `Community 90`, `Community 92`, `Community 95`, `Community 99`, `Community 100`, `Community 105`, `Community 113`, `Community 118`, `Community 124`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `OrderRequest` connect `Community 8` to `Community 0`, `Community 4`, `Community 7`, `Community 10`, `Community 14`, `Community 15`, `Community 17`, `Community 32`, `Community 34`, `Community 43`, `Community 53`, `Community 56`, `Community 57`, `Community 61`, `Community 71`, `Community 83`, `Community 90`, `Community 91`, `Community 92`, `Community 100`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `Quantity` connect `Community 16` to `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 13`, `Community 18`, `Community 22`, `Community 24`, `Community 25`, `Community 27`, `Community 29`, `Community 32`, `Community 36`, `Community 38`, `Community 41`, `Community 45`, `Community 49`, `Community 59`, `Community 61`, `Community 62`, `Community 71`, `Community 73`, `Community 74`, `Community 83`, `Community 86`, `Community 112`, `Community 121`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `InstrumentId` (e.g. with `perpetual()` and `spot()`) actually correct?**
  _`InstrumentId` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `OrderRequest` (e.g. with `_ActionRecord` and `OrderGroupAuthorizationError`) actually correct?**
  _`OrderRequest` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Quantity` (e.g. with `.test_same_instrument_across_accounts_and_zero_target_are_valid()` and `.test_exact_rescale_preserves_nominal_type()`) actually correct?**
  _`Quantity` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `BinanceProduct` (e.g. with `AuthenticatedBinanceExecutionAdapter` and `BinanceCredentialProvider`) actually correct?**
  _`BinanceProduct` has 59 INFERRED edges - model-reasoned connections that need verification._