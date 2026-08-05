# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5105 nodes · 17121 edges · 152 communities (139 shown, 13 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 3310 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `436f84a0`
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
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151

## God Nodes (most connected - your core abstractions)
1. `InstrumentId` - 112 edges
2. `OrderRequest` - 88 edges
3. `Quantity` - 80 edges
4. `BinanceProduct` - 74 edges
5. `PositionTargetIntent` - 65 edges
6. `ManualClock` - 62 edges
7. `OrderEvent` - 60 edges
8. `OrderGroupStateMachine` - 59 edges
9. `BinanceCredentials` - 57 edges
10. `OrderGroupView` - 57 edges

## Surprising Connections (you probably didn't know these)
- `Adr013AcceptanceTests` --uses--> `AllocationBook`  [INFERRED]
  tests/acceptance/test_adr013_accounting.py → src/cex_quant/accounting/allocation.py
- `AccountingAttributionTests` --uses--> `AllocationBook`  [INFERRED]
  tests/test_accounting_attribution.py → src/cex_quant/accounting/allocation.py
- `MemoryJournal` --uses--> `AllocationBook`  [INFERRED]
  tests/test_accounting_attribution.py → src/cex_quant/accounting/allocation.py
- `ledger_view()` --calls--> `FinancialFactMetadata`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/facts.py
- `accounting_state()` --calls--> `FinancialFactMetadata`  [INFERRED]
  tests/test_accounting_attribution.py → src/cex_quant/accounting/facts.py

## Import Cycles
- None detected.

## Communities (152 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (68): AuthenticatedBinanceExecutionAdapter, _error_code(), _error_message(), AccountId, Any, VenueOrderId, Authenticated Binance Spot and Futures execution boundary. The module owns…, Signed submit, cancel and query gateway for one Binance product. (+60 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (47): BinanceHttpRequest, BinanceHttpResponse, BinanceHttpTransportFailure, BinanceProduct, Exception, Transport failure with explicit knowledge of whether bytes were sent., BinanceProduct, StrEnum (+39 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (53): _add_money(), AttributionCompleteness, build_pnl_attribution(), PnlAttributionView, PnlComponent, PnlComponentType, DecisionSnapshotId, StrEnum (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.20
Nodes (32): _action_from_dict(), _action_to_dict(), _admission_from_dict(), _admission_to_dict(), _boolean(), _decode(), decode_execution_action(), decode_execution_action_permit() (+24 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (56): execution_plan_parameters_checksum(), ExecutionAction, ExecutionActionPermit, ExecutionActionState, ExecutionPlanRef, OrderGroupAdmission, OrderGroupCloseOutcome, OrderGroupStatus (+48 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (28): Stable Objective Type registrations for Funding Carry economics., BasketIntentPolicyError, BasketTargetLeg, canonical_leg_key(), create_basket_target_intent(), deterministic_basket_intent_id(), deterministic_basket_leg_id(), ObjectiveTypeRef (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (47): InstrumentId, Structured canonical identity; `symbol` is venue-native and opaque., FundingRateState, _is_stale(), Single-writer latest Funding market state for one perpetual instrument., Own the latest normalized Funding fact and publish an immutable view., Single-writer market-state engines and immutable reader views. Mutable state…, _is_stale() (+39 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (30): ExecutionActionView, OrderGroupLegView, OrderGroupLimits, OrderGroupView, Deployment limits constrained by immutable ADR-011 hard caps., _require_bounded_positive_int(), _ActionRecord, OrderGroupAuthorizationError (+22 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (30): OrderEvent, OrderView, One normalized venue update; `venue_update_id` is its idempotency key., Immutable projection of canonical order state., DuplicateUpdateConflictError, InvalidFillProgressError, InvalidOrderTransitionError, OrderIdentityError (+22 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (19): _error_text(), PrivateStreamApplication, PrivateStreamApplicationSnapshot, PrivateStreamApplicationState, PrivateStreamApplicationStateError, BaseException, RuntimeError, StrEnum (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (32): ManualClock, operator_command(), Portfolio, MonotonicNanos, TestCase, UnixNanos, RuntimeOperationsAcceptanceTests, SystemCheck (+24 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (37): Keepalive, MonotonicNow, SnapshotHandler, _finish_cancelled(), _monotonic_now(), PrivateOrderStreamSession, PrivateOrderStreamSupervisor, PrivateStreamConnection (+29 more)

### Community 12 - "Community 12"
Cohesion: 0.10
Nodes (50): OperatorAction, OperatorCommandConflictError, OperatorControlDurabilityError, OperatorControlSnapshot, RuntimeError, Raised when one idempotency key is reused for a different command., Raised after a journal failure has latched trading halted., OperatorAuthenticationError (+42 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (49): Binance JSON stream normalization without network or SDK dependencies., AggregateTrade, BestBidAsk, BookLevel, FundingRateUpdate, IndexPriceUpdate, KlineUpdate, MarketTrade (+41 more)

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (24): Clock, AuthenticatedOperatorCommandService, _canonical_payload(), EnvironmentOperatorKeyProvider, HmacOperatorCommandAuthenticator, operator_command_signature(), OperatorKeyMaterial, OperatorKeyProvider (+16 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (31): ExecutionActionPermit, JsonLinesOmsJournal, Adr011AcceptanceTests, A014 offline acceptance for the accepted ADR-011 boundary., _AllowSubmitGuard, OfflineExecutionRestartMatrixTests, _persist_boundary(), OrderGroupRuntime (+23 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (21): funding_feature_value(), base_to_instrument_quantity(), Convert base units exactly, rejecting non-terminating decimal ratios., FundingCarryEconomicPolicy, Bounded immutable Funding Carry feature and economic policies., _add(), _close_intent(), decide_funding_carry() (+13 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (57): ExternalSubmitGuardPort, ExactExecutionRoute, Bind one exact account/instrument scope to a configured gateway., _bounded_values(), default_execution_planning(), ExecutionPlannerBinding, ExecutionPlannerRegistry, ExecutionPlanningConfigurationError (+49 more)

### Community 18 - "Community 18"
Cohesion: 0.10
Nodes (38): FinancialSourceFact, AccountCashFlowFact, AccountCashFlowType, CashComponent, ExecutionFillFact, FillSide, StrEnum, Immutable canonical financial source facts for ADR-013. Facts represent… (+30 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (32): ObservationId, Parse a decimal string without binary floating-point conversion., Instrument, Tradable product definition independent of venue payload formats., PortfolioRiskEngine, Stateless whole-Basket and exact-action Risk engine., InstrumentSensitivity, Registered model output consumed by Risk; Risk does not derive Greeks. (+24 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (40): BinanceCredentialProvider, BinanceHttpTransport, canonical_query(), hmac_sha256_hex(), Protocol, Minimal HTTP port; implementations select the product base URL., Encode parameters deterministically by key, independent of map order., Pure signing helper useful for conformance tests. (+32 more)

### Community 21 - "Community 21"
Cohesion: 0.10
Nodes (26): BinanceCredentials, HMAC credentials whose representation never exposes either value., Return the lowercase HMAC-SHA256 digest for an encoded payload., BinanceFuturesUserStreamLease, Opaque Futures listenKey that never appears in representations., BinanceFuturesPrivateStreamTransport, BinanceSpotPrivateStreamTransport, Own a Futures listenKey, WebSocket and renewal task as one resource. (+18 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (13): StrategyId, Runs one strategy serially in caller-provided input order. The caller is the…, Stable identity owned by the strategy instance., StrategyRuntime, BadOutputStrategy, HookFailureStrategy, intent(), StrategyId (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.09
Nodes (19): SplitResult, BinanceEnvironment, BinanceEnvironmentConfig, BinanceProductEndpoints, _defaults(), _host(), BinanceProduct, StrEnum (+11 more)

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (42): _average_from_quote_and_quantity(), _decimal_string(), _futures_user_update(), _identifier(), _integer(), _malformed(), _milliseconds_to_nanos(), normalize_binance_order_query() (+34 more)

### Community 25 - "Community 25"
Cohesion: 0.13
Nodes (53): Deterministic pre-trade risk contracts and evaluation., _approval_reservation_payload(), _confirmation_payload(), _decode_resource_claims(), _encode_resource_claims(), _PermitRecord, PortfolioRiskAuthorizationError, PortfolioRiskCoordinatorError (+45 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (27): LedgerIngestResult, _DrainItem, _FactItem, FinancialFactExpiredError, FinancialFactHandoff, FinancialFactHandoffError, FinancialFactHandoffSnapshot, FinancialFactHandoffStateError (+19 more)

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (28): PortfolioPositionConflictError, PortfolioPositionCoverageError, PortfolioPositionStateError, PortfolioPositionWriterViolationError, Decimal, RuntimeError, _quantity(), Single-writer state for execution-consistent effective positions. (+20 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (36): ObservedFinancialFact, AccountingJournal, AccountingJournalEntry, AccountingJournalError, AccountingJournalIoError, JsonLinesAccountingJournal, Path, Protocol (+28 more)

### Community 29 - "Community 29"
Cohesion: 0.09
Nodes (58): IdentifierT, EventTimeSource, StrEnum, Precision supplied by an upstream source before nanosecond conversion., Origin of `event_time_ns`, independent of its storage unit., TimePrecision, Rate, Exact externally supplied rate, such as a venue funding rate. (+50 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (37): FeatureUpdate, FeatureUpdateDisposition, FeatureUpdateReport, InvalidFeatureEventError, OnlineFeatureEngine, StrEnum, Single-writer deterministic online feature engine., Raised when an event lacks canonical metadata. (+29 more)

### Community 31 - "Community 31"
Cohesion: 0.08
Nodes (23): AuthenticatedOperatorDeploymentAcceptanceTests, TestCase, OperatorControlDeploymentTests, Path, TestCase, signed(), AllowRisk, Check (+15 more)

### Community 32 - "Community 32"
Cohesion: 0.13
Nodes (15): deterministic_group_action_id(), deterministic_order_group_id(), execution_action_checksum(), _fixed(), _fixed_or_none(), BasketLegId, OrderGroupId, Checksum every field that can alter one child order attempt. (+7 more)

### Community 33 - "Community 33"
Cohesion: 0.11
Nodes (28): _d1_d2(), ImpliedVolatilityError, ImpliedVolatilityFailure, _intrinsic(), _normal_cdf(), _normal_pdf(), option_greeks(), option_price() (+20 more)

### Community 34 - "Community 34"
Cohesion: 0.11
Nodes (17): GroupedExecutionBlockedError, OrderGroupPersistenceError, OrderGroupRecoveryError, OrderGroupRuntime, OrderGroupRuntimeError, ClientOrderId, GroupActionId, OmsJournalEntry (+9 more)

### Community 35 - "Community 35"
Cohesion: 0.17
Nodes (32): ScopeKey, _apply_other_reservations(), _apply_reservations(), _apply_working_envelope(), _assessment_checksum(), _calculate_exposure(), _decision_status(), _deduplicate_reasons() (+24 more)

### Community 36 - "Community 36"
Cohesion: 0.14
Nodes (44): AccountingCodecError, canonical_json(), _checksum(), _decode_component(), _decode_instrument_id(), decode_ledger_transaction(), _decode_metadata(), decode_observed_financial_fact() (+36 more)

### Community 37 - "Community 37"
Cohesion: 0.12
Nodes (20): active_control(), feature_snapshot(), instruments(), markets(), metadata(), pair(), portfolio(), CarryFinancialAndRecoveryTests (+12 more)

### Community 38 - "Community 38"
Cohesion: 0.11
Nodes (28): AccountSnapshot, AccountUpdate, Position, PositionAccounting, StrEnum, Immutable account, balance, and position contracts., Atomic normalized venue update containing absolute entity values., Immutable, deterministically ordered account-state projection. (+20 more)

### Community 39 - "Community 39"
Cohesion: 0.09
Nodes (22): DecisionSnapshotPublication, Exception, ExecutionActionRiskDecision, Never, OrderGroupId, OrderSubmitOutcome, PortfolioRiskExecutionGuard, PortfolioRiskPolicy (+14 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (25): FinancialReconciliationId, FinancialSourceKind, _add_money(), AuthoritativeBalance, Source-coverage and account-balance reconciliation proofs., Prove opening plus accepted movements against a closing snapshot., reconcile_balance(), _require_identifier() (+17 more)

### Community 41 - "Community 41"
Cohesion: 0.24
Nodes (10): BinanceMarketDataNormalizer, Any, MarketEvent, UnixNanos, Normalize selected Binance raw or combined WebSocket stream payloads., MarketEvent, ValueError, Raw message captured once at the connector boundary. (+2 more)

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (24): _canonical(), _decode_record(), _encode_record(), JsonLinesOperatorCommandJournal, OperatorJournalError, OperatorJournalIntegrityError, OperatorJournalIoError, Path (+16 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (12): Immutable contracts for deterministic pre-trade risk assessment., Immutable assessment result; ALLOW carries no rejection reasons., Complete point-in-time input to an evaluation; contains no I/O., RiskContext, RiskDecision, OmsIdentityPolicy, OrderParameters, _reject() (+4 more)

### Community 45 - "Community 45"
Cohesion: 0.11
Nodes (21): CarryApplicationFactId, CarryOwnershipId, deterministic_application_position_id(), deterministic_carry_fact_id(), deterministic_carry_ownership_id(), ApplicationPositionId, DecisionSnapshotId, StrategyId (+13 more)

### Community 46 - "Community 46"
Cohesion: 0.13
Nodes (15): AsyncioBinanceHttpTransport, BinanceHttpTimeouts, Send one HTTP/1.1 request over a fresh bounded TLS connection., AsyncioBinanceHttpTransportTests, BinanceHttpTimeoutTests, FakeOpener, FakeWriter, BinanceProduct (+7 more)

### Community 47 - "Community 47"
Cohesion: 0.11
Nodes (16): BinancePrivateWebSocketConnection, BinancePrivateWebSocketConnector, _bounded(), _connected(), _lease_operation(), AbstractAsyncContextManager, Protocol, Task (+8 more)

### Community 48 - "Community 48"
Cohesion: 0.06
Nodes (44): Clock, ClockHealthThresholds, MonotonicClockRegressionError, MonotonicNanos, Protocol, RuntimeError, UnixNanos, Clock injection, venue offset sampling and clock-health evaluation. (+36 more)

### Community 49 - "Community 49"
Cohesion: 0.18
Nodes (31): _boolean(), _canonical_json(), _decode_blob(), _decode_entry(), _decode_event(), _decode_instrument(), decode_journal_record(), _decode_request() (+23 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (29): ExecutionPermitId, PortfolioReconciliationId, _decode_approval_reservation(), _decode_basket(), _decode_confirmation(), _decode_permit(), _decode_recovery(), _integer() (+21 more)

### Community 51 - "Community 51"
Cohesion: 0.07
Nodes (13): ExactRiskValue, InstrumentRiskModelPolicy, LiquidationRequirement, T, Fixed-point Risk evidence with an explicit unit and provenance., _require_checksum(), _require_id(), _require_sorted_unique_ids() (+5 more)

### Community 52 - "Community 52"
Cohesion: 0.14
Nodes (10): Thread-safe, fail-fast handoff from a hot path to a blocking recorder.…, RecorderHandoff, BlockingRecorder, CollectingRecorder, event_at(), FailingRecorder, FlushFailingRecorder, GatedControlQueue (+2 more)

### Community 53 - "Community 53"
Cohesion: 0.23
Nodes (11): IsolatedAsyncioTestCase, SecurityAndOperatorRecoveryAcceptanceTests, AuthenticatedBinanceAdapterTest, CapturingTransport, instrument(), order(), AccountId, Any (+3 more)

### Community 54 - "Community 54"
Cohesion: 0.18
Nodes (13): EventReader, EventRecorder, Protocol, Stable contracts and failures for append-only event recording., Flush userspace buffers; durability policy belongs to the adapter., ReplaySink, Append-only canonical-event recording and deterministic replay. The package…, Deterministic synchronous replay orchestration. (+5 more)

### Community 55 - "Community 55"
Cohesion: 0.15
Nodes (18): LedgerAccountId, deterministic_ledger_account_id(), deterministic_ledger_posting_id(), deterministic_ledger_transaction_id(), _digest(), AccountId, AssetId, FinancialFactId (+10 more)

### Community 56 - "Community 56"
Cohesion: 0.11
Nodes (14): _book(), _Execution, _Features, _Health, _instrument(), _intent(), _pipeline(), _Portfolio (+6 more)

### Community 57 - "Community 57"
Cohesion: 0.09
Nodes (23): ApprovedOrderIntent, ClientOrderId, UnixNanos, Risk-approved, venue-neutral order instruction accepted by OMS. This contract…, AccountPolicy, CanonicalOmsApplicationService, OmsInvariantError, OmsPersistenceError (+15 more)

### Community 58 - "Community 58"
Cohesion: 0.07
Nodes (23): _DrainItem, _EventItem, OverflowPolicy, BaseException, MarketEvent, RuntimeError, StrEnum, Bounded worker handoff for synchronous event recorders. (+15 more)

### Community 59 - "Community 59"
Cohesion: 0.32
Nodes (16): decode_basket_target_intent(), encode_basket_target_intent(), _integer(), _intent_from_dict(), _intent_to_dict(), _json_bytes(), _leg_from_dict(), _list() (+8 more)

### Community 60 - "Community 60"
Cohesion: 0.19
Nodes (11): CarryApplicationFactKind, create_carry_application_fact(), encode_carry_fact_payload(), _kind(), _ownership(), _payload_ownership(), ApplicationPositionId, CarryFactPayload (+3 more)

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (18): ArgumentParser, build_parser(), _check(), _explain(), main(), Path, _query(), Command-line interface for the CEX Quant project knowledge graph. (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (24): PerformanceHarnessTests, Small smoke tests; production-sized loads remain explicit opt-in runs., BenchmarkResult, environment_snapshot(), _instrument(), _level(), _metadata(), os_cpu_count() (+16 more)

### Community 63 - "Community 63"
Cohesion: 0.17
Nodes (12): _canonical(), _decode(), _integer(), JsonLinesPortfolioRiskJournal, PortfolioRiskJournalError, PortfolioRiskJournalIntegrityError, PortfolioRiskJournalIoError, Path (+4 more)

### Community 64 - "Community 64"
Cohesion: 0.04
Nodes (47): EventHandler, ConnectionLifecycle, ConnectionPolicy, ConnectionState, ConnectionTransitionError, DurationNanos, MonotonicNanos, RuntimeError (+39 more)

### Community 65 - "Community 65"
Cohesion: 0.09
Nodes (42): BasketIntentPolicy, BasketTargetIntent, ObjectiveTypeRegistrationError, ObjectiveTypeRegistry, One immutable bounded portfolio target, not an execution plan., Deployment bounds below the immutable contract hard limits., An Objective Type registry is malformed or lacks a reference., Immutable deterministic registry of Objective Type metadata. (+34 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (14): AcceptingState, basket(), basket_leg(), BasketDecisionPort, BasketIntentAcceptanceTests, FixedStrategy, Healthy, instrument() (+6 more)

### Community 67 - "Community 67"
Cohesion: 0.15
Nodes (16): encode_carry_application_fact(), CarryApplicationFact, _canonical_json(), CarryJournal, CarryJournalError, CarryJournalIntegrityError, CarryJournalIoError, _decode_record() (+8 more)

### Community 68 - "Community 68"
Cohesion: 0.23
Nodes (7): BasketStrategy, BasketStrategyRuntimeTests, publication(), DecisionIntent, DecisionSnapshotId, TestCase, UnixNanos

### Community 69 - "Community 69"
Cohesion: 0.21
Nodes (11): coordinator(), evaluate(), EvidenceCollector, FailingAssembler, FailingEvidencePort, populate(), SnapshotSourceId, SnapshotCoordinatorTests (+3 more)

### Community 70 - "Community 70"
Cohesion: 0.07
Nodes (23): child_order_id_for_action(), ClientOrderId, GroupActionId, Use the stable action hash as the venue idempotency key., OrderRequest, Canonical request created by OMS from one approved instruction., DurableSubmitStatePort, ExternalSubmitGuardPort (+15 more)

### Community 71 - "Community 71"
Cohesion: 0.07
Nodes (28): EventId, EventMetadata, EventSource, Metadata shared by immutable domain events., Origin of a canonical event., Transport-neutral metadata composed into strongly typed events., Strong identifiers shared by domain contracts., Stable primitives shared by all CEX Quant domains. This package owns… (+20 more)

### Community 72 - "Community 72"
Cohesion: 0.17
Nodes (8): Balance, Absolute balance in one asset. ``total`` must equal ``available + locked``…, AccountStateTest, instrument(), money(), PortfolioContractsTest, price(), quantity()

### Community 73 - "Community 73"
Cohesion: 0.45
Nodes (20): CarryIntentLinked, CarryOrderGroupLinked, CarryOwnershipRegistered, CarryPositionCreated, CarryRecoveryRequired, CarryStateChanged, Immutable append-only facts for the Carry economic aggregate., Carry application contracts. This package owns economic lifecycle and policy… (+12 more)

### Community 74 - "Community 74"
Cohesion: 0.25
Nodes (10): Stateless policy: caller owns positions and rolling intent counters., RiskEngine, Exposure, rate, and freshness limits for one evaluation policy. Notional caps…, RiskLimits, context(), intent(), perpetual(), TestCase (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.10
Nodes (32): MarketEvent, Composition root for the complete synchronous trading application., Own lifecycle and composition of the mandatory risk-gated pipeline., TradingApplication, OperatorControlDeploymentConfig, OperatorControlRuntime, OperatorEndpointDeploymentConfig, MarketEvent (+24 more)

### Community 76 - "Community 76"
Cohesion: 0.11
Nodes (21): CarryApplicationRuntime, CarryApplicationRuntimeError, CarryApplicationRuntimeStateError, CarryApplicationRuntimeStatus, CarryBasketEvidencePort, CarryRuntimeDisposition, CarryRuntimeResult, BaseException (+13 more)

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (9): CarryPositionBook, Publish application state only after durable fact append., Adr014CarryAcceptanceTests, TestCase, CarryPositionBookTests, create(), MemoryCarryJournal, ownership() (+1 more)

### Community 78 - "Community 78"
Cohesion: 0.10
Nodes (26): DurableExecutionHandoff, ExternalSubmitBlockedError, A durable submit intent was stopped before reaching Execution., Persist SUBMITTING before I/O and persist every immediate outcome., ExecutionPort, PipelineFailure, PipelineInvariantError, PipelineOutcome (+18 more)

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (12): BookReplaySink, canonical_stream(), delta(), GatedRecorder, level(), metadata(), BaseException, MarketEvent (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (15): Path, RuntimeError, StrEnum, Typed storage-boundary failure; corrupt data is never skipped silently., RecorderError, RecorderErrorCode, JsonLinesReader, JsonLinesRecorder (+7 more)

### Community 81 - "Community 81"
Cohesion: 0.21
Nodes (18): _annualized(), _basis(), _estimated_cost(), _event(), _expected_funding(), funding_carry_feature_definitions(), FundingCarryFeatureInput, _net_carry() (+10 more)

### Community 82 - "Community 82"
Cohesion: 0.12
Nodes (13): OptionGreeks, pricing_model_for(), UnixNanos, ValueError, First- and second-order sensitivities in decimal model units. Under Black-76,…, One system-computed IV observation; no interpolation is implied., Immutable, deterministically ordered raw surface points., Choose the closed-form model from the canonical underlying product. (+5 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (9): BinanceExchangeInfoParser, InstrumentMappingError, Any, BinanceProduct, Exception, ValueError, Map one product family's public exchange information response., BinanceExchangeInfoTest (+1 more)

### Community 84 - "Community 84"
Cohesion: 0.11
Nodes (10): Price, Quantity, Exact decimal fixed-point values for trading contracts., Exact price in an instrument's quote convention., Exact order or position quantity., _require_positive_trade(), FixedPointTest, TestCase (+2 more)

### Community 85 - "Community 85"
Cohesion: 0.27
Nodes (10): CarryPositionView, _project(), ApplicationPositionId, CarryFactPayload, CarryPairId, DecisionSnapshotId, IntentId, OrderGroupId (+2 more)

### Community 86 - "Community 86"
Cohesion: 0.31
Nodes (12): Canonical instrument definitions. Public API covers spot, perpetual, dated…, ContractValueType, ExerciseStyle, FutureSpecification, InstrumentKind, InstrumentStatus, PerpetualSpecification, StrEnum (+4 more)

### Community 87 - "Community 87"
Cohesion: 0.13
Nodes (28): Path, RuntimeError, build_project_graph(), collect_code_sources(), collect_project_sources(), _curated_evidence(), _ensure_edge_endpoints(), Evidence (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.08
Nodes (27): AccountPositionRiskView, ApplicationPositionId, CarryHedgeAssessment, CarryLifecycle, CarryPositionBook, CarryPositionView, DecisionSnapshotId, FundingCarryPair (+19 more)

### Community 89 - "Community 89"
Cohesion: 0.16
Nodes (11): OperatorRequestRateLimiter, Thread-safe fixed-window limiter with bounded LRU client state., OperatorEndpointRecoveryAcceptanceTests, TestCase, endpoint(), identity(), MemoryAuditSink, OperatorEndpointTests (+3 more)

### Community 90 - "Community 90"
Cohesion: 0.21
Nodes (6): AggregateHealthTest, ClockHealthMonitorTest, ManualClock, MonotonicNanos, TestCase, UnixNanos

### Community 91 - "Community 91"
Cohesion: 0.16
Nodes (15): _money(), _notional(), Decimal, UnixNanos, ValueError, _quantity(), Pure, deterministic pre-trade evaluation of position target intents., Raised internally when a product cannot be valued unambiguously. (+7 more)

### Community 92 - "Community 92"
Cohesion: 0.22
Nodes (7): DurableExecutionHandoffTests, _Execution, _Guard, _Oms, ClientOrderId, Exception, request()

### Community 93 - "Community 93"
Cohesion: 0.16
Nodes (19): _contains_control(), _contains_unsafe_target_character(), _encode_request(), _Endpoint, _open_tls_connection(), _parse_base_url(), _parse_content_length(), _parse_response_headers() (+11 more)

### Community 94 - "Community 94"
Cohesion: 0.40
Nodes (3): FeatureEngineAdapter, MarketEvent, Update the engine, then expose its immutable point-in-time snapshot.

### Community 95 - "Community 95"
Cohesion: 0.36
Nodes (4): assess(), observation(), SnapshotSourceId, SnapshotAssessmentTests

### Community 96 - "Community 96"
Cohesion: 0.18
Nodes (21): Single-writer bounded coordination of typed decision snapshots., Pure application adapter from ordered source views to a typed value., SnapshotAssembler, assess_snapshot(), MonotonicNanos, UnixNanos, Pure deterministic readiness assessment for decision snapshots., Assess latest observations without mutating source or runtime state. (+13 more)

### Community 97 - "Community 97"
Cohesion: 0.15
Nodes (12): Discard invalid state so new deltas and a fresh snapshot can align., Return a frozen, sorted view; ``None`` until a snapshot is loaded., Build a local book from a REST snapshot and ordered depth deltas. The engine is…, ReconstructedOrderBook, delta(), L1StateTest, level(), metadata() (+4 more)

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (20): funding_objective_registry(), coordinator(), evaluate(), FundingCarryDecisionSnapshot, SnapshotSourceId, snapshot_policy(), strategy_runtime(), entry_observations() (+12 more)

### Community 99 - "Community 99"
Cohesion: 0.21
Nodes (7): ClockFailClosedAcceptanceTest, ManualClock, MonotonicNanos, TestCase, UnixNanos, Scenario acceptance tests for option analytics and clock fail-closed safety., spot()

### Community 100 - "Community 100"
Cohesion: 0.06
Nodes (34): OrderReconciliationSnapshot, StrEnum, Venue-neutral REST and user-stream order reconciliation contracts., One authoritative venue observation normalized outside OMS., ReconciliationDisposition, ReconciliationResult, ReconciliationSource, _observation_order() (+26 more)

### Community 101 - "Community 101"
Cohesion: 0.07
Nodes (33): _add_money(), AllocationBook, AllocationError, AllocationIdentityConflictError, AttributionAllocation, create_allocation(), _normalize_money(), AssetId (+25 more)

### Community 102 - "Community 102"
Cohesion: 0.07
Nodes (30): ObservationIdentityConflictError, BaseException, DecisionSnapshotId, MonotonicNanos, Protocol, RuntimeError, T, UnixNanos (+22 more)

### Community 103 - "Community 103"
Cohesion: 0.14
Nodes (21): _Accounts, cancel_command(), decision(), _ExecutionOnlyGateway, _Gateway, _Identities, intent(), _Orders (+13 more)

### Community 104 - "Community 104"
Cohesion: 0.19
Nodes (7): AppendResult, MarketEvent, Location and size of one successfully appended record., Append one event or fail explicitly without reporting success., Read records in append order, failing on the first invalid record., Consume one event synchronously in recorded order., MarketEvent

### Community 105 - "Community 105"
Cohesion: 0.18
Nodes (5): FakeConnection, FakeContext, FakeTransport, BaseException, TracebackType

### Community 106 - "Community 106"
Cohesion: 0.26
Nodes (9): SecretScannerTests, Finding, main(), Path, Fail CI when tracked text contains high-confidence credential patterns., repository_files(), scan_repository(), scan_text() (+1 more)

### Community 107 - "Community 107"
Cohesion: 0.11
Nodes (9): ManualClock, IsolatedAsyncioTestCase, MonotonicNanos, SSLContext, StreamReader, UnixNanos, ServerTimeOpener, TransportAndClockAcceptanceTests (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (17): require_funding_carry_features(), Pure Funding Carry application contracts and policy., FundingCarryPair, FundingCarryControlInputs, FundingCarryEntrySnapshot, FundingCarryMarketInputs, FundingCarryPortfolioInputs, FundingCarryPositionSnapshot (+9 more)

### Community 109 - "Community 109"
Cohesion: 0.09
Nodes (25): AbstractEventLoop, Any, ExecutionQueryError, _ResultT, AsyncExecutionPortBridge, ExecutionBridgeError, ExecutionBridgeQueryError, ExecutionBridgeStateError (+17 more)

### Community 110 - "Community 110"
Cohesion: 0.12
Nodes (14): BinanceCredentialBinding, BinanceCredentialError, EnvironmentBinanceCredentialProvider, AccountId, RuntimeError, Explicit environment-backed Binance credential delivery adapter., Sanitized credential lookup failure., Environment variable names for one explicitly selected account. (+6 more)

### Community 112 - "Community 112"
Cohesion: 0.20
Nodes (7): Self, FixedPoint, Decimal, An exact decimal value represented by an integer and decimal scale., Return an exact Decimal representation., Return the same value at another scale, rejecting precision loss., _fixed_payload()

### Community 113 - "Community 113"
Cohesion: 0.13
Nodes (14): OrderEvent, PortfolioRiskEngine, OfflineExecutionDirective, _AcceptingAsyncGateway, _AdvanceClockGuard, _AllowSubmitGuard, GroupedExecutionRuntimeTests, _HaltSubmitGuard (+6 more)

### Community 114 - "Community 114"
Cohesion: 0.15
Nodes (20): IsolatedAsyncioTestCase, ExactExecutionGatewayRouter, Dispatch child commands through an immutable exact-scope allowlist. The router…, cancel(), exact_route(), ExactExecutionGatewayRouterTests, ExactExecutionRouteConfigurationTests, _Gateway (+12 more)

### Community 115 - "Community 115"
Cohesion: 0.09
Nodes (19): ExecutionStateUnknownError, ExecutionTransportError, DeterministicOfflineExecutionPort, OfflineExecutionDirectiveKind, OfflineExecutionScriptExhaustedError, CancelOrder, CancelResult, ClientOrderId (+11 more)

### Community 116 - "Community 116"
Cohesion: 0.23
Nodes (11): quantity_to_base(), assess_linear_funding_carry_hedge(), UnixNanos, Pure Carry hedge assessment from authoritative Portfolio position views., Classify residual Delta without using OMS fill quantities as truth., _unknown(), CarryHedgeAssessment, Immutable generic Carry position contracts. (+3 more)

### Community 117 - "Community 117"
Cohesion: 0.16
Nodes (13): _Accounts, decision(), _FailingJournal, _Identities, intent(), _NthFailJournal, OmsJournalTests, _Orders (+5 more)

### Community 118 - "Community 118"
Cohesion: 0.22
Nodes (8): ObjectiveTypeDefinition, Metadata-only registry entry; no callback or import path is allowed., basket(), BasketIntentTests, instrument(), leg(), AccountId, TestCase

### Community 119 - "Community 119"
Cohesion: 0.18
Nodes (5): BlockingConnection, BlockingTransport, ConnectionContext, BaseException, TracebackType

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (14): _require_text(), CoherenceGroup, DurationNanos, SnapshotSourceId, Bounded freshness and coherence policies for decision snapshots., _require_duration(), SnapshotPolicy, SourceFreshnessRule (+6 more)

### Community 121 - "Community 121"
Cohesion: 0.13
Nodes (12): BinanceProduct, InstrumentResolver, Protocol, StrEnum, Return a canonical instrument for an exact venue symbol., Explicit symbol table suitable for tests and immutable runtime snapshots., StaticInstrumentResolver, BinanceNormalizerTest (+4 more)

### Community 122 - "Community 122"
Cohesion: 0.33
Nodes (7): coordinator(), DecisionSnapshotAcceptanceTests, observation(), SnapshotSourceId, Offline acceptance scenarios for coherent decision snapshots., ThreeSourceAssembler, ThreeSourceDecisionInput

### Community 123 - "Community 123"
Cohesion: 0.11
Nodes (13): CollateralAssetSnapshot, MarginMode, MarginScopeSnapshot, PositionLiquidationReference, StrEnum, Execution-consistent position and normalized margin inputs for Portfolio Risk.…, Normalized collateral scope semantics., Venue-normalized margin facts; no venue payload leaks past adapters. (+5 more)

### Community 124 - "Community 124"
Cohesion: 0.13
Nodes (16): ExactRiskValue, PortfolioRiskCoordinator, PortfolioRiskReservationView, ReconciledAccountBaseline, _AllowSubmitGuard, basket_targets(), empty_position_state(), exact() (+8 more)

### Community 125 - "Community 125"
Cohesion: 0.22
Nodes (9): ExecutionConsistentPositionState, AccountId, One account's baseline plus only the not-yet-covered fill effects., ExecutionPositionEffectBatch, A complete scan of one contiguous OMS journal sequence range., account_snapshot(), baseline(), effect() (+1 more)

### Community 134 - "Community 134"
Cohesion: 0.09
Nodes (17): InvalidExecutionRequestError, ExecutionRoutingError, AccountId, CancelOrder, CancelResult, ExecutionGateway, InstrumentId, OrderReconciliationGateway (+9 more)

### Community 135 - "Community 135"
Cohesion: 0.14
Nodes (14): ExecutionPositionEffectBatch, OmsJournal, _effect_id(), OmsExecutionEffectProjector, OmsExecutionProjectionError, AccountId, Decimal, OrderRequest (+6 more)

### Community 136 - "Community 136"
Cohesion: 0.21
Nodes (16): BasketTargetLeg, InstrumentKind, _basket(), cross_venue_basket(), four_leg_basket(), leg(), max_leg_basket(), AccountId (+8 more)

### Community 137 - "Community 137"
Cohesion: 0.43
Nodes (13): CarryCodecError, decode_carry_application_fact(), _decode_ownership(), _decode_payload(), _integer(), _object(), _object_list(), CarryFactPayload (+5 more)

### Community 140 - "Community 140"
Cohesion: 0.33
Nodes (6): BinanceGoldenMappingAcceptanceTests, OmsAcceptanceTests, _order_request(), ClientOrderId, TestCase, _venue_event()

### Community 141 - "Community 141"
Cohesion: 0.14
Nodes (17): create_funding_carry_pair(), _fixed(), _instrument(), AccountId, AssetId, Funding Carry pair and exact linear quantity-conversion contracts., Validate instrument metadata before persisting only stable references., _require_id() (+9 more)

### Community 142 - "Community 142"
Cohesion: 0.29
Nodes (5): CarryRecoveryKind, CarryRecoveryProposal, StrEnum, Carry economic recovery proposals, never execution instructions., A fresh economic preference with no OMS or Risk authority.

### Community 143 - "Community 143"
Cohesion: 0.17
Nodes (14): Deterministic project knowledge-graph tooling., BuildResult, canonical_json(), _clean_table_value(), _code_label_candidates(), _document_kind(), _generated_artifacts(), _graph_identity_set() (+6 more)

### Community 145 - "Community 145"
Cohesion: 0.20
Nodes (25): _add_code_stub(), Edge, _ensure_reference_node(), _extract_adr(), _extract_architecture_constraints(), _extract_document_references(), _extract_state_ownership(), _extract_task_table() (+17 more)

### Community 146 - "Community 146"
Cohesion: 0.20
Nodes (6): OperatorCommandJournal, OperatorController, Clock, Protocol, Thread-safe, bounded and idempotent in-process trading authority., _validate_text()

### Community 147 - "Community 147"
Cohesion: 0.47
Nodes (3): OrderParameters, PositionTargetIntent, RiskDecision

### Community 149 - "Community 149"
Cohesion: 0.67
Nodes (3): FeatureQuality, StrEnum, Consumer-facing quality of a computed value.

### Community 150 - "Community 150"
Cohesion: 0.25
Nodes (7): Return a deterministic relationship identity., Hash ordered path/file-hash records using the Graphify convention., Return a lowercase SHA-256 digest., Return a lowercase SHA-256 digest for UTF-8 text., records_fingerprint(), sha256_bytes(), sha256_text()

### Community 151 - "Community 151"
Cohesion: 0.33
Nodes (3): Return a stable JSON representation., Return a stable JSON representation., Return the canonical federated project-graph descriptor.

## Knowledge Gaps
- **2 isolated node(s):** `cex-quant`, `SecretPattern`
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InstrumentId` connect `Community 6` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 137`, `Community 10`, `Community 140`, `Community 141`, `Community 13`, `Community 16`, `Community 18`, `Community 19`, `Community 25`, `Community 27`, `Community 29`, `Community 30`, `Community 33`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 40`, `Community 41`, `Community 45`, `Community 49`, `Community 53`, `Community 56`, `Community 59`, `Community 62`, `Community 64`, `Community 66`, `Community 71`, `Community 72`, `Community 74`, `Community 82`, `Community 83`, `Community 84`, `Community 86`, `Community 92`, `Community 97`, `Community 99`, `Community 100`, `Community 118`, `Community 121`, `Community 123`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `BinanceEnvironmentConfig` connect `Community 23` to `Community 107`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `ManualClock` connect `Community 15` to `Community 135`, `Community 136`, `Community 17`, `Community 113`, `Community 19`, `Community 117`, `Community 124`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `InstrumentId` (e.g. with `perpetual()` and `spot()`) actually correct?**
  _`InstrumentId` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `OrderRequest` (e.g. with `_ActionRecord` and `OrderGroupAuthorizationError`) actually correct?**
  _`OrderRequest` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Quantity` (e.g. with `.test_same_instrument_across_accounts_and_zero_target_are_valid()` and `.test_exact_rescale_preserves_nominal_type()`) actually correct?**
  _`Quantity` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `BinanceProduct` (e.g. with `AuthenticatedBinanceExecutionAdapter` and `BinanceCredentialProvider`) actually correct?**
  _`BinanceProduct` has 59 INFERRED edges - model-reasoned connections that need verification._