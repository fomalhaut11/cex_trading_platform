# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5256 nodes · 17331 edges · 207 communities (153 shown, 54 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 3271 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e6dfc39d`
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
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 199
- Community 200
- Community 201
- Community 202
- Community 203
- Community 204
- Community 205
- Community 206

## God Nodes (most connected - your core abstractions)
1. `InstrumentId` - 105 edges
2. `OrderGroupRuntime` - 79 edges
3. `BinanceProduct` - 73 edges
4. `Quantity` - 69 edges
5. `OrderGroupView` - 69 edges
6. `ManualClock` - 68 edges
7. `PositionTargetIntent` - 65 edges
8. `ExecutionAction` - 63 edges
9. `PortfolioRiskCoordinator` - 62 edges
10. `ExecutionStage` - 61 edges

## Surprising Connections (you probably didn't know these)
- `AccountingAllocationTests` --uses--> `AllocationError`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/allocation.py
- `MemoryJournal` --uses--> `AllocationError`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/allocation.py
- `Adr013AcceptanceTests` --uses--> `AllocationBook`  [INFERRED]
  tests/acceptance/test_adr013_accounting.py → src/cex_quant/accounting/allocation.py
- `AccountingAllocationTests` --uses--> `AllocationBook`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/allocation.py
- `MemoryJournal` --uses--> `AllocationBook`  [INFERRED]
  tests/test_accounting_allocation.py → src/cex_quant/accounting/allocation.py

## Import Cycles
- None detected.

## Communities (207 total, 54 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (69): AuthenticatedBinanceExecutionAdapter, _error_code(), _error_message(), AccountId, Any, VenueOrderId, Authenticated Binance Spot and Futures execution boundary. The module owns…, Signed submit, cancel and query gateway for one Binance product. (+61 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (46): BinanceHttpRequest, BinanceHttpResponse, BinanceHttpTransport, BinanceProduct, Minimal HTTP port; implementations select the product base URL., BinanceProduct, StrEnum, ClockHealthMonitor (+38 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (68): _add_money(), AllocationBook, AllocationError, AllocationIdentityConflictError, AttributionAllocation, _normalize_money(), ValueError, Append-only ownership allocation over immutable ledger postings. (+60 more)

### Community 3 - "Community 3"
Cohesion: 0.20
Nodes (32): _action_from_dict(), _action_to_dict(), _admission_from_dict(), _admission_to_dict(), _boolean(), _decode(), decode_execution_action(), decode_execution_action_permit() (+24 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (82): execution_action_checksum(), execution_plan_parameters_checksum(), ExecutionAction, ExecutionActionPermit, ExecutionActionState, ExecutionActionView, ExecutionPlanRef, OrderGroupAdmission (+74 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (28): BasketIntentPolicyError, BasketTargetLeg, canonical_leg_key(), create_basket_target_intent(), deterministic_basket_intent_id(), deterministic_basket_leg_id(), ObjectiveTypeRef, ObjectiveTypeRegistrationError (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (44): FundingRateState, _is_stale(), Single-writer latest Funding market state for one perpetual instrument., Own the latest normalized Funding fact and publish an immutable view., Single-writer market-state engines and immutable reader views. Mutable state…, _is_stale(), L1State, Single-writer level-one market state. (+36 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (38): OrderEvent, OrderSide, OrderStatus, OrderSubmitEvent, OrderSubmitOutcome, OrderType, PositionSide, StrEnum (+30 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (19): _error_text(), PrivateStreamApplication, PrivateStreamApplicationSnapshot, PrivateStreamApplicationState, PrivateStreamApplicationStateError, BaseException, RuntimeError, StrEnum (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (32): ManualClock, operator_command(), Portfolio, MonotonicNanos, TestCase, UnixNanos, RuntimeOperationsAcceptanceTests, SystemCheck (+24 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (9): _finish_cancelled(), PrivateOrderStreamSupervisor, Event, Exception, Task, Recreate authorized transports with deterministic reconnect backoff., Return whether the current physical private stream is active., Wait until the supervised session confirms a physical connection. (+1 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (72): _canonical(), _decode_record(), _encode_record(), OperatorJournalError, OperatorJournalIntegrityError, OperatorJournalIoError, RuntimeError, Checksummed durable journal for operator command audit and recovery. (+64 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (48): Rate, Exact externally supplied rate, such as a venue funding rate., Binance JSON stream normalization without network or SDK dependencies., AggregateTrade, BestBidAsk, BookLevel, FundingRateUpdate, IndexPriceUpdate (+40 more)

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (24): Clock, AuthenticatedOperatorCommandService, _canonical_payload(), EnvironmentOperatorKeyProvider, HmacOperatorCommandAuthenticator, operator_command_signature(), OperatorKeyMaterial, OperatorKeyProvider (+16 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (25): ExecutionPermitId, PortfolioRiskExecutionGuard, Combine platform safety and one exact consumable Portfolio Risk permit., Adr011AcceptanceTests, A014 offline acceptance for the accepted ADR-011 boundary., _persist_boundary(), action_for(), admission() (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.20
Nodes (16): FundingCarryEconomicPolicy, Bounded immutable Funding Carry feature and economic policies., _add(), _close_intent(), decide_funding_carry(), _intent(), _open_intent(), _position() (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (5): ExecutionGateway, OrderReconciliationGateway, ExactExecutionRoute, Bind one exact account/instrument scope to a configured gateway., ValueError

### Community 18 - "Community 18"
Cohesion: 0.10
Nodes (40): FinancialSourceFact, AccountCashFlowFact, AccountCashFlowType, CashComponent, ExecutionFillFact, FillSide, FinancialFactObservation, StrEnum (+32 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (30): ObservationId, Parse a decimal string without binary floating-point conversion., InstrumentSensitivity, Registered model output consumed by Risk; Risk does not derive Greeks., RiskFactorLimit, WorkingOrderRiskView, Adr012AcceptanceTests, A015 offline acceptance for ADR-012 Portfolio Risk authorization. (+22 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (33): BinanceCredentialProvider, canonical_query(), Protocol, Encode parameters deterministically by key, independent of map order., Resolve credentials without making them part of adapter configuration., BinanceFuturesUserStreamControlAdapter, BinancePrivateStreamDisposition, BinancePrivateStreamMessage (+25 more)

### Community 21 - "Community 21"
Cohesion: 0.06
Nodes (44): BinanceCredentials, HMAC credentials whose representation never exposes either value., Return the lowercase HMAC-SHA256 digest for an encoded payload., BinanceFuturesUserStreamLease, Opaque Futures listenKey that never appears in representations., BinanceFuturesPrivateStreamTransport, BinancePrivateWebSocketConnection, BinancePrivateWebSocketConnector (+36 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (11): Runs one strategy serially in caller-provided input order. The caller is the…, StrategyRuntime, BadOutputStrategy, HookFailureStrategy, intent(), StrategyId, RaisingStrategy, RecordingStrategy (+3 more)

### Community 24 - "Community 24"
Cohesion: 0.09
Nodes (44): _average_from_quote_and_quantity(), BinanceOrderNormalizationError, _decimal_string(), _futures_user_update(), _identifier(), _integer(), _malformed(), _milliseconds_to_nanos() (+36 more)

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (44): Deterministic pre-trade risk contracts and evaluation., _confirmation_payload(), _PermitRecord, PortfolioRiskCoordinatorError, PortfolioRiskIdentityConflictError, PortfolioRiskPersistenceError, PortfolioRiskRecoveryError, PortfolioRiskWriterViolationError (+36 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (27): LedgerIngestResult, _DrainItem, _FactItem, FinancialFactExpiredError, FinancialFactHandoff, FinancialFactHandoffError, FinancialFactHandoffSnapshot, FinancialFactHandoffStateError (+19 more)

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (30): ExecutionConsistentPositionState, PortfolioPositionConflictError, PortfolioPositionCoverageError, PortfolioPositionStateError, PortfolioPositionWriterViolationError, AccountId, Decimal, RuntimeError (+22 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (36): observation_checksum(), observed_fact_checksum(), ObservedFinancialFact, AccountingJournal, AccountingJournalEntry, AccountingJournalError, Protocol, RuntimeError (+28 more)

### Community 29 - "Community 29"
Cohesion: 0.15
Nodes (45): IdentifierT, AggressorSide, StrEnum, _base(), _boolean(), _common(), _CommonFields, _decode_aggregate_trade() (+37 more)

### Community 30 - "Community 30"
Cohesion: 0.31
Nodes (4): ExampleEvent, FeatureValueValidationTests, metadata(), OnlineFeatureEngineTests

### Community 31 - "Community 31"
Cohesion: 0.08
Nodes (22): OperatorController, OperatorRiskGate, Apply halt/reduce-only authority after normal deterministic risk., Thread-safe, bounded and idempotent in-process trading authority., AllowRisk, Check, command(), context() (+14 more)

### Community 33 - "Community 33"
Cohesion: 0.07
Nodes (33): _d1_d2(), ImpliedVolatilityError, ImpliedVolatilityFailure, _intrinsic(), _normal_cdf(), _normal_pdf(), option_greeks(), option_price() (+25 more)

### Community 34 - "Community 34"
Cohesion: 0.10
Nodes (24): IntentId, OrderGroupView, GroupActionStateChangedEntry, UnixNanos, GroupedExecutionBlockedError, OrderGroupPersistenceError, OrderGroupRecoveryError, OrderGroupRuntime (+16 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (18): OrderView, OrderGroupStateMachine, BasketTargetLeg, ClientOrderId, Decimal, GroupActionId, OrderEvent, OrderGroupId (+10 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (41): AccountingCodecError, canonical_json(), _checksum(), _decode_component(), _decode_instrument_id(), decode_ledger_transaction(), _decode_metadata(), decode_observed_financial_fact() (+33 more)

### Community 37 - "Community 37"
Cohesion: 0.08
Nodes (36): funding_objective_registry(), SourceFreshnessRule, Adr014CarryAcceptanceTests, coordinator(), evaluate(), FundingCarryDecisionSnapshot, SnapshotSourceId, TestCase (+28 more)

### Community 38 - "Community 38"
Cohesion: 0.11
Nodes (28): AccountSnapshot, AccountUpdate, Position, PositionAccounting, StrEnum, Immutable account, balance, and position contracts., Atomic normalized venue update containing absolute entity values., Immutable, deterministically ordered account-state projection. (+20 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (28): FinancialReconciliationId, FinancialSourceKind, LedgerAccountType, StrEnum, AuthoritativeBalance, BalanceReconciliationProof, StrEnum, Source-coverage and account-balance reconciliation proofs. (+20 more)

### Community 41 - "Community 41"
Cohesion: 0.40
Nodes (5): microseconds_to_nanos(), milliseconds_to_nanos(), UnixNanos, Convert Unix milliseconds without pretending the source was precise., Convert Unix microseconds to the canonical unit.

### Community 42 - "Community 42"
Cohesion: 0.25
Nodes (3): JsonLinesOperatorCommandJournal, Path, Append-only JSONL journal with checksum, sequence and fsync.

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (9): Immutable assessment result; ALLOW carries no rejection reasons., Complete point-in-time input to an evaluation; contains no I/O., RiskContext, RiskDecision, Decimal, Protocol, _reduces_exposure(), _reject() (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (24): CarryApplicationFactId, CarryOwnershipId, deterministic_application_position_id(), deterministic_carry_fact_id(), deterministic_carry_ownership_id(), deterministic_carry_pair_id(), ApplicationPositionId, CarryPairId (+16 more)

### Community 46 - "Community 46"
Cohesion: 0.13
Nodes (15): AsyncioBinanceHttpTransport, BinanceHttpTimeouts, Send one HTTP/1.1 request over a fresh bounded TLS connection., AsyncioBinanceHttpTransportTests, BinanceHttpTimeoutTests, FakeOpener, FakeWriter, BinanceProduct (+7 more)

### Community 47 - "Community 47"
Cohesion: 0.14
Nodes (43): FixedPoint, Instrument, ScopeKey, _apply_other_reservations(), _apply_reservations(), _apply_working_envelope(), _assessment_checksum(), _calculate_exposure() (+35 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (34): Canonical time types and conversion constants. Unix nanoseconds are comparable…, Clock, ClockHealthThresholds, MonotonicClockRegressionError, MonotonicNanos, Protocol, RuntimeError, UnixNanos (+26 more)

### Community 49 - "Community 49"
Cohesion: 0.14
Nodes (39): InstrumentKind, OrderStatus, OrderSubmitEvent, _boolean(), _canonical_json(), _decode_blob(), _decode_entry(), _decode_event() (+31 more)

### Community 50 - "Community 50"
Cohesion: 0.13
Nodes (19): PortfolioRiskAuthorizationError, PortfolioRiskCoordinator, PortfolioApprovalId, UnixNanos, Own reservations and the liveness of exact execution permits., Persist reservation capacity before publishing ALLOW evidence., Persist issuance generation before publishing the permit., Durably issue one Stage permit and all exact Action authorities. (+11 more)

### Community 51 - "Community 51"
Cohesion: 0.16
Nodes (8): AccountingJournalIoError, JsonLinesAccountingJournal, Path, Bounded JSONL journal with sequence, checksum, flush and optional fsync., AccountingJournalTests, ledger(), MemoryAccountingJournal, observed()

### Community 52 - "Community 52"
Cohesion: 0.12
Nodes (11): Thread-safe, fail-fast handoff from a hot path to a blocking recorder.…, RecorderHandoff, BlockingRecorder, CollectingRecorder, event_at(), FailingRecorder, FlushFailingRecorder, GatedControlQueue (+3 more)

### Community 53 - "Community 53"
Cohesion: 0.16
Nodes (15): hmac_sha256_hex(), Pure signing helper useful for conformance tests., IsolatedAsyncioTestCase, SecurityAndOperatorRecoveryAcceptanceTests, AuthenticatedBinanceAdapterTest, BinanceSigningTest, CapturingTransport, instrument() (+7 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (34): AppendResult, EventReader, EventRecorder, MarketEvent, Path, Protocol, RuntimeError, StrEnum (+26 more)

### Community 55 - "Community 55"
Cohesion: 0.17
Nodes (26): ExecutionPlannerRegistry, ExecutionPlanResolver, Resolve immutable Basket metadata to one registered plan reference., Immutable exact registry keyed by the full execution-plan reference., GroupedAdmissionDisposition, GroupedAdmissionResult, GroupedBootstrapEvidence, GroupedBootstrapStep (+18 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (21): BinanceGoldenMappingAcceptanceTests, _book(), _Execution, _Features, _Health, _instrument(), _intent(), _Oms (+13 more)

### Community 57 - "Community 57"
Cohesion: 0.11
Nodes (22): OrderView, Immutable projection of canonical order state., AccountPolicy, CanonicalOmsApplicationService, _is_consistent(), OmsIdentityPolicy, OmsInvariantError, OmsPersistenceError (+14 more)

### Community 58 - "Community 58"
Cohesion: 0.08
Nodes (23): _DrainItem, _EventItem, OverflowPolicy, BaseException, MarketEvent, RuntimeError, StrEnum, Bounded worker handoff for synchronous event recorders. (+15 more)

### Community 59 - "Community 59"
Cohesion: 0.26
Nodes (18): basket_target_intent_checksum(), decode_basket_target_intent(), encode_basket_target_intent(), _integer(), _intent_from_dict(), _intent_to_dict(), _json_bytes(), _leg_from_dict() (+10 more)

### Community 60 - "Community 60"
Cohesion: 0.14
Nodes (7): _AcceptingAsyncGateway, _AdvanceClockGuard, _HaltSubmitGuard, CancelOrder, CancelResult, OrderRequest, SubmitResult

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (18): ArgumentParser, build_parser(), _check(), _explain(), main(), Path, _query(), Command-line interface for the CEX Quant project knowledge graph. (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (23): PerformanceHarnessTests, Small smoke tests; production-sized loads remain explicit opt-in runs., BenchmarkResult, environment_snapshot(), _instrument(), _metadata(), os_cpu_count(), Path (+15 more)

### Community 63 - "Community 63"
Cohesion: 0.16
Nodes (12): _canonical(), _decode(), _integer(), JsonLinesPortfolioRiskJournal, PortfolioRiskJournalError, PortfolioRiskJournalIntegrityError, PortfolioRiskJournalIoError, Path (+4 more)

### Community 64 - "Community 64"
Cohesion: 0.08
Nodes (35): EventHandler, Transport-neutral private-order stream session with bounded renewal., ConnectionPolicy, ConnectionState, StrEnum, Transport-neutral Binance WebSocket lifecycle and reconnect policy., Operational bounds independent of a concrete WebSocket client., Binance market-data adapter public API. The normalizer is pure and network-… (+27 more)

### Community 65 - "Community 65"
Cohesion: 0.08
Nodes (44): Carry economic recovery proposals, never execution instructions., BasketIntentPolicy, BasketTargetIntent, ObjectiveTypeRegistry, One immutable bounded portfolio target, not an execution plan., Deployment bounds below the immutable contract hard limits., Immutable deterministic registry of Objective Type metadata., Strategy runtime contracts that transform information into trade intents.… (+36 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (15): AcceptingState, basket(), basket_leg(), BasketDecisionPort, BasketIntentAcceptanceTests, FixedStrategy, Healthy, instrument() (+7 more)

### Community 67 - "Community 67"
Cohesion: 0.16
Nodes (16): encode_carry_application_fact(), CarryApplicationFact, _canonical_json(), CarryJournal, CarryJournalError, CarryJournalIntegrityError, CarryJournalIoError, _decode_record() (+8 more)

### Community 68 - "Community 68"
Cohesion: 0.25
Nodes (8): BasketStrategy, BasketStrategyRuntimeTests, publication(), DecisionIntent, DecisionSnapshotId, TestCase, UnixNanos, target()

### Community 69 - "Community 69"
Cohesion: 0.20
Nodes (12): coordinator(), evaluate(), EvidenceCollector, FailingAssembler, FailingEvidencePort, make_policy(), populate(), SnapshotSourceId (+4 more)

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (22): BinanceHttpTransportFailure, Exception, Transport failure with explicit knowledge of whether bytes were sent., _contains_control(), _contains_unsafe_target_character(), _encode_request(), _Endpoint, _open_tls_connection() (+14 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (17): EventId, EventSource, Origin of a canonical event., EventMetadataTest, TestCase, FundingRateStateTests, TestCase, update() (+9 more)

### Community 72 - "Community 72"
Cohesion: 0.17
Nodes (8): Balance, Absolute balance in one asset. ``total`` must equal ``available + locked``…, AccountStateTest, instrument(), money(), PortfolioContractsTest, price(), quantity()

### Community 73 - "Community 73"
Cohesion: 0.33
Nodes (28): CarryCodecError, _decode_payload(), _object_list(), CarryFactPayload, ValueError, Strict JSON-compatible codec for Carry application facts., CarryApplicationFactKind, CarryIntentLinked (+20 more)

### Community 74 - "Community 74"
Cohesion: 0.09
Nodes (14): BinanceProduct, InstrumentResolver, Protocol, StrEnum, Return a canonical instrument for an exact venue symbol., Explicit symbol table suitable for tests and immutable runtime snapshots., StaticInstrumentResolver, BinanceStreamSessionTest (+6 more)

### Community 75 - "Community 75"
Cohesion: 0.10
Nodes (18): BaseException, Exception, Never, OrderSubmitOutcome, GroupedExecutionRuntime, GroupedExecutionRuntimeStateError, _GroupedSubmitStateAdapter, BasketTargetIntent (+10 more)

### Community 76 - "Community 76"
Cohesion: 0.12
Nodes (23): CarryApplicationRuntime, CarryApplicationRuntimeError, CarryApplicationRuntimeStateError, CarryApplicationRuntimeStatus, CarryBasketEvidencePort, CarryRuntimeDisposition, CarryRuntimeResult, BaseException (+15 more)

### Community 77 - "Community 77"
Cohesion: 0.11
Nodes (17): BasketLegId, child_order_id_for_action(), deterministic_group_action_id(), deterministic_order_group_id(), ClientOrderId, GroupActionId, OrderGroupId, Derive the replay-stable group identity from intent and approval. (+9 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (50): MarketEvent, Composition root for the complete synchronous trading application., Own lifecycle and composition of the mandatory risk-gated pipeline., TradingApplication, OperatorControlDeploymentConfig, OperatorEndpointDeploymentConfig, MarketEvent, Concrete deployment assembly for secure operator control. (+42 more)

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (12): BookReplaySink, canonical_stream(), delta(), GatedRecorder, level(), metadata(), BaseException, MarketEvent (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.31
Nodes (6): decode_event(), encode_event(), _json_bytes(), Encode one event to deterministic UTF-8 JSON without a line terminator., Decode and validate one complete record without a line terminator., RecorderCodecTests

### Community 81 - "Community 81"
Cohesion: 0.16
Nodes (22): _annualized(), _basis(), _estimated_cost(), _event(), _expected_funding(), funding_carry_feature_definitions(), funding_feature_value(), FundingCarryFeatureInput (+14 more)

### Community 82 - "Community 82"
Cohesion: 0.29
Nodes (5): One system-computed IV observation; no interpolation is implied., Immutable, deterministically ordered raw surface points., VolatilitySurfacePoint, VolatilitySurfaceSnapshot, VolatilitySurfaceTests

### Community 83 - "Community 83"
Cohesion: 0.16
Nodes (11): BinanceExchangeInfoParser, InstrumentMappingError, InstrumentMappingErrorCode, Any, BinanceProduct, Exception, StrEnum, ValueError (+3 more)

### Community 84 - "Community 84"
Cohesion: 0.15
Nodes (8): OperatorControlRuntime, Own the journal, controller, authentication and health composition., AuthenticatedOperatorDeploymentAcceptanceTests, TestCase, OperatorControlDeploymentTests, Path, TestCase, signed()

### Community 85 - "Community 85"
Cohesion: 0.23
Nodes (12): CarryPositionView, CarryPositionBook, _project(), ApplicationPositionId, CarryFactPayload, CarryPairId, DecisionSnapshotId, IntentId (+4 more)

### Community 86 - "Community 86"
Cohesion: 0.05
Nodes (60): base_to_instrument_quantity(), create_funding_carry_pair(), _fixed(), _instrument(), AccountId, AssetId, quantity_to_base(), Funding Carry pair and exact linear quantity-conversion contracts. (+52 more)

### Community 87 - "Community 87"
Cohesion: 0.13
Nodes (28): Path, RuntimeError, build_project_graph(), collect_code_sources(), collect_project_sources(), _curated_evidence(), _ensure_edge_endpoints(), Evidence (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.09
Nodes (26): AccountPositionRiskView, ApplicationPositionId, BasketTargetLeg, CarryHedgeAssessment, CarryLifecycle, CarryPositionView, DecisionSnapshotId, FundingCarryPair (+18 more)

### Community 89 - "Community 89"
Cohesion: 0.13
Nodes (13): OperatorKeyBinding, Deployment metadata for one operator signing identity., OperatorRequestRateLimiter, Thread-safe fixed-window limiter with bounded LRU client state., OperatorEndpointRecoveryAcceptanceTests, TestCase, endpoint(), identity() (+5 more)

### Community 90 - "Community 90"
Cohesion: 0.20
Nodes (6): AggregateHealthTest, ClockHealthMonitorTest, ManualClock, MonotonicNanos, TestCase, UnixNanos

### Community 91 - "Community 91"
Cohesion: 0.09
Nodes (27): _money(), Decimal, UnixNanos, ValueError, _quantity(), Raised internally when a product cannot be valued unambiguously., Stateless policy: caller owns positions and rolling intent counters., Approve or reject an intent using only the supplied snapshot. (+19 more)

### Community 92 - "Community 92"
Cohesion: 0.10
Nodes (18): OrderRequest, Canonical request created by OMS from one approved instruction., DurableSubmitStatePort, ExternalSubmitGuardPort, ClientOrderId, Exception, Protocol, RuntimeError (+10 more)

### Community 93 - "Community 93"
Cohesion: 0.07
Nodes (12): ExactRiskValue, InstrumentRiskModelPolicy, LiquidationRequirement, T, Fixed-point Risk evidence with an explicit unit and provenance., _require_checksum(), _require_id(), _require_sorted_unique_ids() (+4 more)

### Community 94 - "Community 94"
Cohesion: 0.15
Nodes (18): LedgerAccountId, deterministic_ledger_account_id(), deterministic_ledger_posting_id(), deterministic_ledger_transaction_id(), _digest(), AccountId, AssetId, FinancialFactId (+10 more)

### Community 95 - "Community 95"
Cohesion: 0.23
Nodes (8): CoherenceGroup, assess(), observation(), policy(), SnapshotSourceId, rule(), SnapshotAssessmentTests, SnapshotContractTests

### Community 96 - "Community 96"
Cohesion: 0.11
Nodes (27): Single-writer bounded coordination of typed decision snapshots., Pure application adapter from ordered source views to a typed value., SnapshotAssembler, assess_snapshot(), MonotonicNanos, UnixNanos, Pure deterministic readiness assessment for decision snapshots., Assess latest observations without mutating source or runtime state. (+19 more)

### Community 97 - "Community 97"
Cohesion: 0.25
Nodes (8): delta(), L1StateTest, level(), metadata(), PartialBookStateTest, TestCase, ReconstructedOrderBookTest, snapshot()

### Community 98 - "Community 98"
Cohesion: 0.31
Nodes (5): CarryApplicationRuntimeTests, evaluate(), Evidence, TestCase, runtime()

### Community 99 - "Community 99"
Cohesion: 0.18
Nodes (12): SplitResult, BinanceEnvironment, BinanceProductEndpoints, _defaults(), _host(), Strongly typed Binance endpoint profiles without credential ownership., Deployment environment selected for every Binance product endpoint. ``TESTNET``…, REST and WebSocket origins for one product in one environment. (+4 more)

### Community 100 - "Community 100"
Cohesion: 0.09
Nodes (24): OrderReconciliationSnapshot, One authoritative venue observation normalized outside OMS., ReconciliationResult, _observation_order(), ClientOrderId, Protocol, RuntimeError, StrEnum (+16 more)

### Community 101 - "Community 101"
Cohesion: 0.22
Nodes (8): create_allocation(), AssetId, AttributionAllocationId, LedgerPostingId, LedgerTransactionId, AccountingAllocationTests, ledger_view(), MemoryJournal

### Community 102 - "Community 102"
Cohesion: 0.06
Nodes (28): ObservationIdentityConflictError, BaseException, DecisionSnapshotId, MonotonicNanos, Protocol, RuntimeError, T, UnixNanos (+20 more)

### Community 103 - "Community 103"
Cohesion: 0.12
Nodes (24): OrderParameters, PositionTargetIntent, RiskDecision, _Accounts, cancel_command(), decision(), _ExecutionOnlyGateway, _Gateway (+16 more)

### Community 104 - "Community 104"
Cohesion: 0.15
Nodes (10): HealthCheck, Protocol, Interface implemented by components that expose current health., Return the stable component name., Clock, UnixNanos, Evaluate registered checks in stable order and sanitize failures., RuntimeHealthService (+2 more)

### Community 105 - "Community 105"
Cohesion: 0.18
Nodes (5): FakeConnection, FakeContext, FakeTransport, BaseException, TracebackType

### Community 106 - "Community 106"
Cohesion: 0.26
Nodes (9): SecretScannerTests, Finding, main(), Path, Fail CI when tracked text contains high-confidence credential patterns., repository_files(), scan_repository(), scan_text() (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.12
Nodes (19): require_funding_carry_features(), Pure Funding Carry application contracts and policy., FundingCarryPair, FundingCarryControlInputs, FundingCarryEntrySnapshot, FundingCarryMarketInputs, FundingCarryPortfolioInputs, FundingCarryPositionSnapshot (+11 more)

### Community 109 - "Community 109"
Cohesion: 0.10
Nodes (23): AbstractEventLoop, Any, ExecutionQueryError, _ResultT, AsyncExecutionPortBridge, ExecutionBridgeError, ExecutionBridgeQueryError, ExecutionBridgeStateError (+15 more)

### Community 110 - "Community 110"
Cohesion: 0.12
Nodes (13): BinanceCredentialBinding, BinanceCredentialError, EnvironmentBinanceCredentialProvider, AccountId, RuntimeError, Sanitized credential lookup failure., Environment variable names for one explicitly selected account., Read fresh values per lookup so external rotation takes effect. (+5 more)

### Community 114 - "Community 114"
Cohesion: 0.15
Nodes (20): IsolatedAsyncioTestCase, ExactExecutionGatewayRouter, Dispatch child commands through an immutable exact-scope allowlist. The router…, cancel(), exact_route(), ExactExecutionGatewayRouterTests, ExactExecutionRouteConfigurationTests, _Gateway (+12 more)

### Community 115 - "Community 115"
Cohesion: 0.09
Nodes (20): ExecutionStateUnknownError, ExecutionTransportError, DeterministicOfflineExecutionPort, OfflineExecutionDirective, OfflineExecutionDirectiveKind, OfflineExecutionScriptExhaustedError, CancelOrder, CancelResult (+12 more)

### Community 116 - "Community 116"
Cohesion: 0.24
Nodes (10): assess_linear_funding_carry_hedge(), UnixNanos, Pure Carry hedge assessment from authoritative Portfolio position views., Classify residual Delta without using OMS fill quantities as truth., _unknown(), CarryHedgeAssessment, Immutable generic Carry position contracts., _require_bounded_unique() (+2 more)

### Community 117 - "Community 117"
Cohesion: 0.13
Nodes (15): JsonLinesOmsJournal, Path, Strict checksummed JSONL journal with an fsync boundary per append., _Accounts, decision(), _FailingJournal, _Identities, intent() (+7 more)

### Community 118 - "Community 118"
Cohesion: 0.19
Nodes (9): Stable Objective Type registrations for Funding Carry economics., ObjectiveTypeDefinition, Metadata-only registry entry; no callback or import path is allowed., basket(), BasketIntentTests, instrument(), leg(), AccountId (+1 more)

### Community 120 - "Community 120"
Cohesion: 0.17
Nodes (5): FakeConnection, FakeContext, FakeTransport, BaseException, TracebackType

### Community 121 - "Community 121"
Cohesion: 0.30
Nodes (5): BinanceNormalizerTest, normalizer(), BinanceProduct, TestCase, raw()

### Community 122 - "Community 122"
Cohesion: 0.31
Nodes (8): coordinator(), DecisionSnapshotAcceptanceTests, observation(), policy(), SnapshotSourceId, Offline acceptance scenarios for coherent decision snapshots., ThreeSourceAssembler, ThreeSourceDecisionInput

### Community 123 - "Community 123"
Cohesion: 0.14
Nodes (9): CollateralAssetSnapshot, MarginScopeSnapshot, PositionLiquidationReference, Venue-normalized margin facts; no venue payload leaks past adapters., Venue-provided liquidation reference for one derivative position., _require_id(), instrument(), InstrumentId (+1 more)

### Community 124 - "Community 124"
Cohesion: 0.07
Nodes (31): CarryPositionBook, DecisionSnapshotPublication, ExactRiskValue, JsonLinesOmsJournal, OrderEvent, PortfolioRiskCoordinator, PortfolioRiskEngine, PortfolioRiskPolicy (+23 more)

### Community 125 - "Community 125"
Cohesion: 0.29
Nodes (6): ExecutionPositionEffectBatch, A complete scan of one contiguous OMS journal sequence range., account_snapshot(), baseline(), effect(), ExecutionConsistentPositionStateTests

### Community 134 - "Community 134"
Cohesion: 0.09
Nodes (17): InvalidExecutionRequestError, ExecutionRoutingError, AccountId, CancelOrder, CancelResult, ExecutionGateway, InstrumentId, OrderReconciliationGateway (+9 more)

### Community 137 - "Community 137"
Cohesion: 0.09
Nodes (22): _bounded_values(), default_execution_planning(), ExecutionPlannerBinding, ExecutionPlanningConfigurationError, _is_pure_reduction(), ObjectiveExecutionPlanBinding, ObjectiveExecutionPlanResolver, OrderGroupPlanner (+14 more)

### Community 140 - "Community 140"
Cohesion: 0.18
Nodes (19): PortfolioReconciliationId, _approval_reservation_payload(), _decode_approval_reservation(), _decode_basket(), _decode_confirmation(), _decode_permit(), _decode_recovery(), _decode_resource_claims() (+11 more)

### Community 141 - "Community 141"
Cohesion: 0.31
Nodes (4): DeterministicOfflineExecutionPort, OfflineExecutionDirective, _AllowSubmitGuard, GroupedExecutionRuntimeTests

### Community 142 - "Community 142"
Cohesion: 0.33
Nodes (4): CarryRecoveryProposal, A fresh economic preference with no OMS or Risk authority., CarryProjectionValidationTests, _ledger()

### Community 143 - "Community 143"
Cohesion: 0.17
Nodes (14): Deterministic project knowledge-graph tooling., BuildResult, canonical_json(), _clean_table_value(), _code_label_candidates(), _document_kind(), _generated_artifacts(), _graph_identity_set() (+6 more)

### Community 145 - "Community 145"
Cohesion: 0.20
Nodes (25): _add_code_stub(), Edge, _ensure_reference_node(), _extract_adr(), _extract_architecture_constraints(), _extract_document_references(), _extract_state_ownership(), _extract_task_table() (+17 more)

### Community 146 - "Community 146"
Cohesion: 0.17
Nodes (6): BlockingConnection, BlockingTransport, ConnectionContext, PrivateStreamSupervisionAcceptanceTests, IsolatedAsyncioTestCase, TracebackType

### Community 147 - "Community 147"
Cohesion: 0.23
Nodes (19): ExecutionStageId, ExecutionStagePermitId, _blob(), _canonical(), _decode(), decode_execution_stage(), decode_execution_stage_permit(), _encode() (+11 more)

### Community 149 - "Community 149"
Cohesion: 0.08
Nodes (40): FeatureUpdate, FeatureUpdateDisposition, FeatureUpdateReport, InvalidFeatureEventError, OnlineFeatureEngine, StrEnum, Single-writer deterministic online feature engine., Raised when an event lacks canonical metadata. (+32 more)

### Community 150 - "Community 150"
Cohesion: 0.25
Nodes (7): Return a deterministic relationship identity., Hash ordered path/file-hash records using the Graphify convention., Return a lowercase SHA-256 digest., Return a lowercase SHA-256 digest for UTF-8 text., records_fingerprint(), sha256_bytes(), sha256_text()

### Community 151 - "Community 151"
Cohesion: 0.33
Nodes (3): Return a stable JSON representation., Return a stable JSON representation., Return the canonical federated project-graph descriptor.

### Community 152 - "Community 152"
Cohesion: 0.24
Nodes (3): BinanceEnvironmentConfig, Complete, immutable endpoint selection for the trading runtime. The Demo-backed…, BinanceEnvironmentConfigTests

### Community 153 - "Community 153"
Cohesion: 0.18
Nodes (8): ClientOrderId, OrderReconciliationSnapshot, QueryOrder, ReconciliationResult, ReconciliationSource, EmptyOms, NoQueryGateway, UnixNanos

### Community 154 - "Community 154"
Cohesion: 0.18
Nodes (10): ApprovedOrderIntent, ClientOrderId, UnixNanos, Risk-approved, venue-neutral order instruction accepted by OMS. This contract…, OrderStateMachine, ClientOrderId, Own one order's mutable state and expose only immutable snapshots., event() (+2 more)

### Community 155 - "Community 155"
Cohesion: 0.25
Nodes (13): _basket(), cross_venue_basket(), four_leg_basket(), leg(), max_leg_basket(), AccountId, BasketTargetIntent, BasketTargetLeg (+5 more)

### Community 156 - "Community 156"
Cohesion: 0.27
Nodes (4): CarryPositionBookTests, create(), MemoryCarryJournal, TestCase

### Community 157 - "Community 157"
Cohesion: 0.28
Nodes (8): ExecutionPositionEffectBatch, _effect_id(), OmsExecutionProjectionError, AccountId, Decimal, OrderRequest, RuntimeError, _remember_request()

### Community 158 - "Community 158"
Cohesion: 0.21
Nodes (6): MonotonicNanos, ManualClock, IsolatedAsyncioTestCase, UnixNanos, ServerTimeOpener, TransportAndClockAcceptanceTests

### Community 159 - "Community 159"
Cohesion: 0.26
Nodes (5): BinancePrivateOrderStreamProcessor, Classify one private-stream frame and normalize order updates., PrivateOrderStreamSessionTests, Event, IsolatedAsyncioTestCase

### Community 160 - "Community 160"
Cohesion: 0.38
Nodes (5): instrument_id(), level(), MarketDataValidationTest, metadata(), TestCase

### Community 161 - "Community 161"
Cohesion: 0.07
Nodes (12): ConnectionLifecycle, ConnectionTransitionError, DurationNanos, MonotonicNanos, RuntimeError, Capped exponential backoff with caller-supplied deterministic jitter., Return delay for a one-based attempt. Randomness is deliberately supplied by…, Single-writer state machine for one physical WebSocket connection. (+4 more)

### Community 162 - "Community 162"
Cohesion: 0.17
Nodes (10): EventMetadata, EventTimeSource, StrEnum, Metadata shared by immutable domain events., Precision supplied by an upstream source before nanosecond conversion., Origin of `event_time_ns`, independent of its storage unit., Transport-neutral metadata composed into strongly typed events., TimePrecision (+2 more)

### Community 163 - "Community 163"
Cohesion: 0.22
Nodes (9): create_carry_application_fact(), encode_carry_fact_payload(), _kind(), _ownership(), _payload_ownership(), ApplicationPositionId, CarryFactPayload, UnixNanos (+1 more)

### Community 165 - "Community 165"
Cohesion: 0.24
Nodes (6): _monotonic_now(), PrivateOrderStreamSession, MonotonicNanos, Consume one private connection and renew its authorization if required., Wait until the current physical connection is confirmed active., Run one connection; callers own reconnect-delay scheduling.

### Community 166 - "Community 166"
Cohesion: 0.60
Nodes (3): ExternalSubmitGuardPort, OrderGroupId, UnixNanos

### Community 167 - "Community 167"
Cohesion: 0.21
Nodes (6): stage_for(), stage_permit_for(), ExecutionStageContractTests, ExecutionStageOmsTests, MemoryOmsJournal, OmsJournalEntry

### Community 168 - "Community 168"
Cohesion: 0.40
Nodes (4): InvalidOrderTransitionError, UnixNanos, Apply one immediate submit fact without inventing venue lifecycle., Raised when an event requests an illegal lifecycle transition.

### Community 172 - "Community 172"
Cohesion: 0.22
Nodes (3): SSLContext, StreamReader, Writer

### Community 173 - "Community 173"
Cohesion: 0.29
Nodes (5): PrivateStreamConnection, PrivateStreamTransport, AbstractAsyncContextManager, Protocol, Open one already-authorized account stream connection.

### Community 174 - "Community 174"
Cohesion: 0.29
Nodes (5): Keepalive, MonotonicNow, SnapshotHandler, Sleep, TransportFactory

### Community 195 - "Community 195"
Cohesion: 0.71
Nodes (7): decode_carry_application_fact(), _decode_ownership(), _integer(), _object(), JsonObject, _quantity(), _string()

### Community 196 - "Community 196"
Cohesion: 0.33
Nodes (3): OrderParameters, OrderPolicy, Translate an approved target into an explicit executable instruction.

### Community 197 - "Community 197"
Cohesion: 0.40
Nodes (3): ExternalSubmitGuardPort, UnixNanos, SynchronousExecutionSubmitPort

### Community 198 - "Community 198"
Cohesion: 0.67
Nodes (4): _fixed(), _fixed_or_none(), Price, Quantity

### Community 201 - "Community 201"
Cohesion: 0.67
Nodes (3): MarginMode, StrEnum, Normalized collateral scope semantics.

## Knowledge Gaps
- **2 isolated node(s):** `cex-quant`, `SecretPattern`
  These have ≤1 connection - possible missing edges or undocumented components.
- **54 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BinanceCredentials` connect `Community 21` to `Community 0`, `Community 1`, `Community 110`, `Community 20`, `Community 53`, `Community 159`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `BinanceEnvironmentConfig` connect `Community 152` to `Community 202`, `Community 99`, `Community 158`, `Community 199`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `JsonLinesOperatorCommandJournal` connect `Community 42` to `Community 12`, `Community 78`, `Community 14`, `Community 84`, `Community 53`, `Community 31`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `InstrumentId` (e.g. with `perpetual()` and `spot()`) actually correct?**
  _`InstrumentId` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `OrderGroupRuntime` (e.g. with `GroupedAdmissionDisposition` and `GroupedAdmissionResult`) actually correct?**
  _`OrderGroupRuntime` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `BinanceProduct` (e.g. with `AuthenticatedBinanceExecutionAdapter` and `BinanceCredentialProvider`) actually correct?**
  _`BinanceProduct` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Quantity` (e.g. with `.test_same_instrument_across_accounts_and_zero_target_are_valid()` and `.test_exact_rescale_preserves_nominal_type()`) actually correct?**
  _`Quantity` has 11 INFERRED edges - model-reasoned connections that need verification._