# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 5247 nodes · 17352 edges · 195 communities (148 shown, 47 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 3279 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f222b39a`
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

## God Nodes (most connected - your core abstractions)
1. `InstrumentId` - 105 edges
2. `OrderGroupRuntime` - 79 edges
3. `BinanceProduct` - 74 edges
4. `Quantity` - 69 edges
5. `OrderGroupView` - 69 edges
6. `ManualClock` - 68 edges
7. `PositionTargetIntent` - 65 edges
8. `ExecutionAction` - 63 edges
9. `PortfolioRiskCoordinator` - 62 edges
10. `ExecutionStage` - 61 edges

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

## Communities (195 total, 47 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (72): AuthenticatedBinanceExecutionAdapter, _error_code(), _error_message(), AccountId, Any, VenueOrderId, Authenticated Binance Spot and Futures execution boundary. The module owns…, Signed submit, cancel and query gateway for one Binance product. (+64 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (46): BinanceHttpRequest, BinanceHttpResponse, BinanceHttpTransport, BinanceProduct, Minimal HTTP port; implementations select the product base URL., BinanceProduct, StrEnum, ClockHealthMonitor (+38 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (54): AllocationBook, Validate allocations without changing Accounting financial totals., _add_money(), AttributionCompleteness, build_pnl_attribution(), PnlAttributionView, PnlComponent, PnlComponentType (+46 more)

### Community 3 - "Community 3"
Cohesion: 0.18
Nodes (34): Price, Exact price in an instrument's quote convention., _action_from_dict(), _action_to_dict(), _admission_from_dict(), _admission_to_dict(), _boolean(), _decode() (+26 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (71): deterministic_order_group_id(), execution_action_checksum(), execution_plan_parameters_checksum(), ExecutionAction, ExecutionActionPermit, ExecutionActionState, ExecutionActionView, ExecutionPlanRef (+63 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (26): BasketIntentPolicyError, BasketTargetLeg, canonical_leg_key(), create_basket_target_intent(), deterministic_basket_intent_id(), deterministic_basket_leg_id(), ObjectiveTypeRef, AccountId (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (38): InstrumentId, Structured canonical identity; `symbol` is venue-native and opaque., FundingRateState, _is_stale(), Single-writer latest Funding market state for one perpetual instrument., Own the latest normalized Funding fact and publish an immutable view., Single-writer market-state engines and immutable reader views. Mutable state…, _is_stale() (+30 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (29): OrderEvent, OrderStatus, OrderSubmitEvent, OrderSubmitOutcome, One normalized venue update; `venue_update_id` is its idempotency key., Immediate submit evidence persisted before private-stream lifecycle., Immediate transport result, distinct from venue order lifecycle., DuplicateUpdateConflictError (+21 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (23): _error_text(), PrivateStreamApplication, PrivateStreamApplicationSnapshot, PrivateStreamApplicationState, PrivateStreamApplicationStateError, BaseException, RuntimeError, StrEnum (+15 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (22): ManualClock, operator_command(), Portfolio, TestCase, RuntimeOperationsAcceptanceTests, SystemCheck, application(), _Gateway (+14 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (44): Keepalive, MonotonicNow, SnapshotHandler, BinancePrivateOrderStreamProcessor, Classify one private-stream frame and normalize order updates., _finish_cancelled(), _monotonic_now(), PrivateOrderStreamSession (+36 more)

### Community 12 - "Community 12"
Cohesion: 0.08
Nodes (53): OperatorAction, OperatorCommandConflictError, OperatorControlDurabilityError, OperatorControlSnapshot, RuntimeError, Raised when one idempotency key is reused for a different command., Raised after a journal failure has latched trading halted., OperatorAuthenticationError (+45 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (53): EventSource, Origin of a canonical event., InstrumentResolver, Protocol, Binance JSON stream normalization without network or SDK dependencies., Bounded Binance stream session independent of a WebSocket library., AggregateTrade, BestBidAsk (+45 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (29): OperatorControlRuntime, Clock, Own the journal, controller, authentication and health composition., OperatorCommand, OperatorCommandJournal, OperatorController, Clock, Protocol (+21 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (21): Adr011AcceptanceTests, A014 offline acceptance for the accepted ADR-011 boundary., _persist_boundary(), action_for(), admission(), execution_plan(), permit_for(), UnixNanos (+13 more)

### Community 16 - "Community 16"
Cohesion: 0.23
Nodes (15): FundingCarryEconomicPolicy, _add(), _close_intent(), decide_funding_carry(), _intent(), _open_intent(), _position(), AccountId (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (5): ExecutionGateway, OrderReconciliationGateway, ExactExecutionRoute, Bind one exact account/instrument scope to a configured gateway., ValueError

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (21): FinancialSourceFact, AccountCashFlowFact, CashComponent, ExecutionFillFact, Immutable canonical financial source facts for ADR-013. Facts represent…, _require_identifier(), _require_text(), _validate_components() (+13 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (30): ObservationId, Parse a decimal string without binary floating-point conversion., InstrumentSensitivity, Registered model output consumed by Risk; Risk does not derive Greeks., RiskFactorLimit, WorkingOrderRiskView, Adr012AcceptanceTests, A015 offline acceptance for ADR-012 Portfolio Risk authorization. (+22 more)

### Community 20 - "Community 20"
Cohesion: 0.06
Nodes (43): BinanceCredentialProvider, canonical_query(), Protocol, Encode parameters deterministically by key, independent of map order., Resolve credentials without making them part of adapter configuration., BinanceFuturesUserStreamControlAdapter, BinancePrivateStreamDisposition, BinancePrivateStreamMessage (+35 more)

### Community 21 - "Community 21"
Cohesion: 0.10
Nodes (26): BinanceCredentials, HMAC credentials whose representation never exposes either value., Return the lowercase HMAC-SHA256 digest for an encoded payload., BinanceFuturesUserStreamLease, Opaque Futures listenKey that never appears in representations., BinanceFuturesPrivateStreamTransport, BinanceSpotPrivateStreamTransport, Own a Futures listenKey, WebSocket and renewal task as one resource. (+18 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (12): Runs one strategy serially in caller-provided input order. The caller is the…, StrategyRuntime, strategy_runtime(), BadOutputStrategy, HookFailureStrategy, intent(), StrategyId, RaisingStrategy (+4 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (12): SplitResult, BinanceEnvironment, BinanceProductEndpoints, _defaults(), _host(), StrEnum, Strongly typed Binance endpoint profiles without credential ownership., Deployment environment selected for every Binance product endpoint. (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (32): _average_from_quote_and_quantity(), BinanceOrderNormalizationError, _decimal_string(), _futures_user_update(), _identifier(), _integer(), _malformed(), _milliseconds_to_nanos() (+24 more)

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (46): Deterministic pre-trade risk contracts and evaluation., _confirmation_payload(), _PermitRecord, PortfolioRiskAuthorizationError, PortfolioRiskCoordinatorError, PortfolioRiskIdentityConflictError, PortfolioRiskPersistenceError, PortfolioRiskRecoveryError (+38 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (26): _DrainItem, _FactItem, FinancialFactExpiredError, FinancialFactHandoff, FinancialFactHandoffError, FinancialFactHandoffSnapshot, FinancialFactHandoffStateError, FinancialFactHandoffStatus (+18 more)

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (28): PortfolioPositionConflictError, PortfolioPositionCoverageError, PortfolioPositionStateError, PortfolioPositionWriterViolationError, Decimal, RuntimeError, _quantity(), Single-writer state for execution-consistent effective positions. (+20 more)

### Community 28 - "Community 28"
Cohesion: 0.07
Nodes (71): LedgerAccountId, observed_fact_checksum(), AccountCashFlowType, FillSide, ObservedFinancialFact, StrEnum, deterministic_ledger_account_id(), deterministic_ledger_posting_id() (+63 more)

### Community 29 - "Community 29"
Cohesion: 0.14
Nodes (47): IdentifierT, Rate, Exact externally supplied rate, such as a venue funding rate., AggressorSide, StrEnum, _base(), _boolean(), _common() (+39 more)

### Community 30 - "Community 30"
Cohesion: 0.12
Nodes (15): OnlineFeatureEngine, Updates registered features synchronously in dependency order. One instance…, FeatureRef, Stable identity of one versioned feature definition., FeatureDefinition, FeatureRegistrationError, FeatureRegistry, ValueError (+7 more)

### Community 31 - "Community 31"
Cohesion: 0.10
Nodes (20): OperatorRiskGate, Apply halt/reduce-only authority after normal deterministic risk., OperatorControlDeploymentTests, Path, TestCase, signed(), AllowRisk, Check (+12 more)

### Community 33 - "Community 33"
Cohesion: 0.09
Nodes (32): _d1_d2(), ImpliedVolatilityError, ImpliedVolatilityFailure, _intrinsic(), _normal_cdf(), _normal_pdf(), option_greeks(), option_price() (+24 more)

### Community 34 - "Community 34"
Cohesion: 0.11
Nodes (23): IntentId, OrderGroupView, GroupActionStateChangedEntry, GroupedExecutionBlockedError, OrderGroupPersistenceError, OrderGroupRecoveryError, OrderGroupRuntime, OrderGroupRuntimeError (+15 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (19): OrderView, _ActionRecord, OrderGroupStateMachine, BasketTargetLeg, ClientOrderId, Decimal, GroupActionId, OrderEvent (+11 more)

### Community 36 - "Community 36"
Cohesion: 0.18
Nodes (36): AccountingCodecError, canonical_json(), _checksum(), _decode_component(), _decode_instrument_id(), decode_ledger_transaction(), _decode_metadata(), decode_observed_financial_fact() (+28 more)

### Community 37 - "Community 37"
Cohesion: 0.09
Nodes (30): Adr014CarryAcceptanceTests, coordinator(), evaluate(), FundingCarryDecisionSnapshot, SnapshotSourceId, TestCase, snapshot_policy(), active_control() (+22 more)

### Community 38 - "Community 38"
Cohesion: 0.11
Nodes (28): AccountSnapshot, AccountUpdate, Position, PositionAccounting, StrEnum, Immutable account, balance, and position contracts., Atomic normalized venue update containing absolute entity values., Immutable, deterministically ordered account-state projection. (+20 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (27): FinancialReconciliationId, FinancialSourceKind, _add_money(), AuthoritativeBalance, StrEnum, Source-coverage and account-balance reconciliation proofs., Prove opening plus accepted movements against a closing snapshot., reconcile_balance() (+19 more)

### Community 41 - "Community 41"
Cohesion: 0.19
Nodes (15): microseconds_to_nanos(), milliseconds_to_nanos(), UnixNanos, Convert Unix milliseconds without pretending the source was precise., Convert Unix microseconds to the canonical unit., BinanceMarketDataNormalizer, Any, MarketEvent (+7 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (25): _canonical(), _decode_record(), _encode_record(), JsonLinesOperatorCommandJournal, OperatorJournalError, OperatorJournalIntegrityError, OperatorJournalIoError, Path (+17 more)

### Community 43 - "Community 43"
Cohesion: 0.25
Nodes (3): Immutable assessment result; ALLOW carries no rejection reasons., RiskDecision, _reject()

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (26): CarryApplicationFactId, CarryOwnershipId, deterministic_application_position_id(), deterministic_carry_fact_id(), deterministic_carry_ownership_id(), deterministic_carry_pair_id(), ApplicationPositionId, CarryPairId (+18 more)

### Community 46 - "Community 46"
Cohesion: 0.07
Nodes (37): BinanceHttpTransportFailure, Exception, Transport failure with explicit knowledge of whether bytes were sent., AsyncioBinanceHttpTransport, BinanceHttpTimeouts, _contains_control(), _contains_unsafe_target_character(), _encode_request() (+29 more)

### Community 47 - "Community 47"
Cohesion: 0.14
Nodes (42): Instrument, ScopeKey, _encode_resource_claims(), _apply_other_reservations(), _apply_reservations(), _apply_working_envelope(), _assessment_checksum(), _calculate_exposure() (+34 more)

### Community 48 - "Community 48"
Cohesion: 0.05
Nodes (45): Canonical time types and conversion constants. Unix nanoseconds are comparable…, Clock, ClockHealthThresholds, MonotonicClockRegressionError, MonotonicNanos, Protocol, RuntimeError, UnixNanos (+37 more)

### Community 49 - "Community 49"
Cohesion: 0.14
Nodes (40): InstrumentKind, OrderStatus, OrderSubmitEvent, OrderSubmitOutcome, _boolean(), _canonical_json(), _decode_blob(), _decode_entry() (+32 more)

### Community 50 - "Community 50"
Cohesion: 0.13
Nodes (16): _approval_reservation_payload(), PortfolioRiskCoordinator, PortfolioApprovalId, UnixNanos, Own reservations and the liveness of exact execution permits., Persist reservation capacity before publishing ALLOW evidence., Persist issuance generation before publishing the permit., Durably issue one Stage permit and all exact Action authorities. (+8 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (18): AccountingJournalEntry, AccountingJournalIntegrityError, AccountingJournalIoError, _decode_record(), _json_object(), JsonLinesAccountingJournal, _positive_integer(), JsonObject (+10 more)

### Community 52 - "Community 52"
Cohesion: 0.13
Nodes (10): Thread-safe, fail-fast handoff from a hot path to a blocking recorder.…, RecorderHandoff, BlockingRecorder, CollectingRecorder, event_at(), FailingRecorder, FlushFailingRecorder, GatedControlQueue (+2 more)

### Community 53 - "Community 53"
Cohesion: 0.16
Nodes (15): hmac_sha256_hex(), Pure signing helper useful for conformance tests., IsolatedAsyncioTestCase, SecurityAndOperatorRecoveryAcceptanceTests, AuthenticatedBinanceAdapterTest, BinanceSigningTest, CapturingTransport, instrument() (+7 more)

### Community 54 - "Community 54"
Cohesion: 0.13
Nodes (19): EventReader, EventRecorder, Protocol, StrEnum, Stable contracts and failures for append-only event recording., Flush userspace buffers; durability policy belongs to the adapter., RecorderErrorCode, ReplaySink (+11 more)

### Community 55 - "Community 55"
Cohesion: 0.15
Nodes (30): default_execution_planning(), ExecutionPlannerRegistry, ExecutionPlanResolver, Build the backwards-compatible one-plan Runtime composition., Resolve immutable Basket metadata to one registered plan reference., Immutable exact registry keyed by the full execution-plan reference., GroupedAdmissionDisposition, GroupedAdmissionResult (+22 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (21): BinanceGoldenMappingAcceptanceTests, _book(), _Execution, _Features, _Health, _instrument(), _intent(), _Oms (+13 more)

### Community 57 - "Community 57"
Cohesion: 0.12
Nodes (19): AccountPolicy, CanonicalOmsApplicationService, OmsIdentityPolicy, OmsInvariantError, OmsPersistenceError, OmsRecoveryError, OrderPolicy, AccountId (+11 more)

### Community 58 - "Community 58"
Cohesion: 0.08
Nodes (23): _DrainItem, _EventItem, OverflowPolicy, BaseException, MarketEvent, RuntimeError, StrEnum, Bounded worker handoff for synchronous event recorders. (+15 more)

### Community 59 - "Community 59"
Cohesion: 0.27
Nodes (18): basket_target_intent_checksum(), decode_basket_target_intent(), encode_basket_target_intent(), _integer(), _intent_from_dict(), _intent_to_dict(), _json_bytes(), _leg_from_dict() (+10 more)

### Community 60 - "Community 60"
Cohesion: 0.09
Nodes (16): OrderReconciliationSnapshot, QueryOrder, PortfolioRiskExecutionGuard, Combine platform safety and one exact consumable Portfolio Risk permit., ManualClock, _AcceptingAsyncGateway, _AdvanceClockGuard, _HaltSubmitGuard (+8 more)

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (18): ArgumentParser, build_parser(), _check(), _explain(), main(), Path, _query(), Command-line interface for the CEX Quant project knowledge graph. (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (24): PerformanceHarnessTests, Small smoke tests; production-sized loads remain explicit opt-in runs., BenchmarkResult, environment_snapshot(), _instrument(), _level(), _metadata(), os_cpu_count() (+16 more)

### Community 63 - "Community 63"
Cohesion: 0.16
Nodes (12): _canonical(), _decode(), _integer(), JsonLinesPortfolioRiskJournal, PortfolioRiskJournalError, PortfolioRiskJournalIntegrityError, PortfolioRiskJournalIoError, Path (+4 more)

### Community 64 - "Community 64"
Cohesion: 0.04
Nodes (34): EventHandler, ConnectionLifecycle, ConnectionState, ConnectionTransitionError, MonotonicNanos, RuntimeError, StrEnum, Single-writer state machine for one physical WebSocket connection. (+26 more)

### Community 65 - "Community 65"
Cohesion: 0.08
Nodes (42): OrderParameters, BasketIntentPolicy, BasketTargetIntent, One immutable bounded portfolio target, not an execution plan., Deployment bounds below the immutable contract hard limits., Strategy runtime contracts that transform information into trade intents.…, PositionTargetIntent, One deterministically numbered input delivered to a strategy. (+34 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (15): AcceptingState, basket(), basket_leg(), BasketDecisionPort, BasketIntentAcceptanceTests, FixedStrategy, Healthy, instrument() (+7 more)

### Community 67 - "Community 67"
Cohesion: 0.11
Nodes (21): encode_carry_application_fact(), CarryApplicationFact, create_carry_application_fact(), encode_carry_fact_payload(), _kind(), _ownership(), _payload_ownership(), ApplicationPositionId (+13 more)

### Community 68 - "Community 68"
Cohesion: 0.25
Nodes (8): BasketStrategy, BasketStrategyRuntimeTests, publication(), DecisionIntent, DecisionSnapshotId, TestCase, UnixNanos, target()

### Community 69 - "Community 69"
Cohesion: 0.21
Nodes (11): coordinator(), evaluate(), EvidenceCollector, FailingAssembler, FailingEvidencePort, populate(), SnapshotSourceId, SnapshotCoordinatorTests (+3 more)

### Community 70 - "Community 70"
Cohesion: 0.17
Nodes (9): DurableSubmitStatePort, ExternalSubmitGuardPort, ClientOrderId, Exception, Protocol, RuntimeError, OMS-side state needed by the shared submit handoff., Recheck runtime/operator authority immediately before external I/O. (+1 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (17): EventId, EventMetadata, Transport-neutral metadata composed into strongly typed events., encode_event(), _json_bytes(), Encode one event to deterministic UTF-8 JSON without a line terminator., EventMetadataTest, TestCase (+9 more)

### Community 72 - "Community 72"
Cohesion: 0.17
Nodes (8): Balance, Absolute balance in one asset. ``total`` must equal ``available + locked``…, AccountStateTest, instrument(), money(), PortfolioContractsTest, price(), quantity()

### Community 73 - "Community 73"
Cohesion: 0.21
Nodes (40): CarryCodecError, decode_carry_application_fact(), _decode_ownership(), _decode_payload(), _integer(), _object(), _object_list(), CarryFactPayload (+32 more)

### Community 74 - "Community 74"
Cohesion: 0.30
Nodes (8): Exposure, rate, and freshness limits for one evaluation policy. Notional caps…, RiskLimits, context(), intent(), perpetual(), TestCase, RiskEngineTests, spot()

### Community 75 - "Community 75"
Cohesion: 0.14
Nodes (14): BaseException, Exception, Never, GroupedExecutionRuntime, GroupedExecutionRuntimeStateError, BasketTargetIntent, CancelOrder, CancelResult (+6 more)

### Community 76 - "Community 76"
Cohesion: 0.11
Nodes (21): CarryApplicationRuntime, CarryApplicationRuntimeError, CarryApplicationRuntimeStateError, CarryApplicationRuntimeStatus, CarryBasketEvidencePort, CarryRuntimeDisposition, CarryRuntimeResult, BaseException (+13 more)

### Community 77 - "Community 77"
Cohesion: 0.09
Nodes (18): BasketLegId, child_order_id_for_action(), deterministic_group_action_id(), ClientOrderId, GroupActionId, OrderGroupId, Derive one stable action identity before constructing its content., Use the stable action hash as the venue idempotency key. (+10 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (50): MarketEvent, Composition root for the complete synchronous trading application., Own lifecycle and composition of the mandatory risk-gated pipeline., TradingApplication, OperatorControlDeploymentConfig, OperatorEndpointDeploymentConfig, MarketEvent, Concrete deployment assembly for secure operator control. (+42 more)

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (12): BookReplaySink, canonical_stream(), delta(), GatedRecorder, level(), metadata(), BaseException, MarketEvent (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.11
Nodes (11): decode_event(), Decode and validate one complete record without a line terminator., Path, RuntimeError, Typed storage-boundary failure; corrupt data is never skipped silently., RecorderError, JsonLinesRecorder, Exception (+3 more)

### Community 81 - "Community 81"
Cohesion: 0.18
Nodes (20): _annualized(), _basis(), _estimated_cost(), _event(), _expected_funding(), funding_carry_feature_definitions(), funding_feature_value(), FundingCarryFeatureInput (+12 more)

### Community 82 - "Community 82"
Cohesion: 0.29
Nodes (5): One system-computed IV observation; no interpolation is implied., Immutable, deterministically ordered raw surface points., VolatilitySurfacePoint, VolatilitySurfaceSnapshot, VolatilitySurfaceTests

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (9): BinanceExchangeInfoParser, InstrumentMappingError, Any, BinanceProduct, Exception, ValueError, Map one product family's public exchange information response., BinanceExchangeInfoTest (+1 more)

### Community 84 - "Community 84"
Cohesion: 0.20
Nodes (6): ApprovedOrderIntent, ClientOrderId, UnixNanos, Risk-approved, venue-neutral order instruction accepted by OMS. This contract…, approved(), OmsModelTests

### Community 85 - "Community 85"
Cohesion: 0.16
Nodes (15): CarryPositionView, CarryPositionBook, ApplicationPositionId, CarryFactPayload, CarryPairId, DecisionSnapshotId, IntentId, OrderGroupId (+7 more)

### Community 86 - "Community 86"
Cohesion: 0.11
Nodes (22): Exact decimal fixed-point values for trading contracts., Stable primitives shared by all CEX Quant domains. This package owns…, Canonical instrument definitions. Public API covers spot, perpetual, dated…, ContractValueType, ExerciseStyle, FutureSpecification, InstrumentKind, InstrumentStatus (+14 more)

### Community 87 - "Community 87"
Cohesion: 0.14
Nodes (29): Path, RuntimeError, _add_code_stub(), build_project_graph(), collect_code_sources(), collect_project_sources(), _curated_evidence(), _ensure_edge_endpoints() (+21 more)

### Community 88 - "Community 88"
Cohesion: 0.09
Nodes (26): ApplicationPositionId, BasketTargetLeg, CarryHedgeAssessment, CarryLifecycle, CarryPositionView, DecisionSnapshotId, FundingCarryPair, OrderGroupAdmission (+18 more)

### Community 89 - "Community 89"
Cohesion: 0.19
Nodes (10): OperatorKeyBinding, Deployment metadata for one operator signing identity., OperatorEndpointRecoveryAcceptanceTests, TestCase, endpoint(), MemoryAuditSink, OperatorEndpointTests, ManualClock (+2 more)

### Community 90 - "Community 90"
Cohesion: 0.21
Nodes (6): AggregateHealthTest, ClockHealthMonitorTest, ManualClock, MonotonicNanos, TestCase, UnixNanos

### Community 91 - "Community 91"
Cohesion: 0.11
Nodes (20): _money(), _notional(), Decimal, UnixNanos, ValueError, _quantity(), Raised internally when a product cannot be valued unambiguously., Stateless policy: caller owns positions and rolling intent counters. (+12 more)

### Community 92 - "Community 92"
Cohesion: 0.26
Nodes (7): DurableExecutionHandoffTests, _Execution, _Guard, _Oms, ClientOrderId, Exception, request()

### Community 93 - "Community 93"
Cohesion: 0.08
Nodes (11): ExactRiskValue, InstrumentRiskModelPolicy, LiquidationRequirement, T, Fixed-point Risk evidence with an explicit unit and provenance., _require_checksum(), _require_id(), _require_sorted_unique_ids() (+3 more)

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
Cohesion: 0.10
Nodes (19): _apply_levels(), _is_crossed(), _levels_by_price(), Decimal, Discard invalid state so new deltas and a fresh snapshot can align., Return a frozen, sorted view; ``None`` until a snapshot is loaded., Build a local book from a REST snapshot and ordered depth deltas. The engine is…, Buffer before initialization or atomically apply to a live book. (+11 more)

### Community 98 - "Community 98"
Cohesion: 0.14
Nodes (14): FundingCarryStrategy, Stateless replay-deterministic economic decision policy., entry_observations(), CarryApplicationRuntimeTests, evaluate(), Evidence, TestCase, runtime() (+6 more)

### Community 99 - "Community 99"
Cohesion: 0.17
Nodes (8): ClockFailClosedAcceptanceTest, ManualClock, model_inputs(), OptionAnalyticsAcceptanceTest, MonotonicNanos, TestCase, UnixNanos, Scenario acceptance tests for option analytics and clock fail-closed safety.

### Community 100 - "Community 100"
Cohesion: 0.07
Nodes (35): OrderSide, OrderType, OrderView, PositionSide, StrEnum, Immutable order contracts at the risk-to-OMS and venue-to-OMS boundaries., Immutable projection of canonical order state., Position leg used by derivatives venues with hedge mode. (+27 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (20): _add_money(), AllocationError, AllocationIdentityConflictError, AttributionAllocation, create_allocation(), _normalize_money(), AssetId, AttributionAllocationId (+12 more)

### Community 102 - "Community 102"
Cohesion: 0.07
Nodes (30): ObservationIdentityConflictError, BaseException, DecisionSnapshotId, MonotonicNanos, Protocol, RuntimeError, T, UnixNanos (+22 more)

### Community 103 - "Community 103"
Cohesion: 0.12
Nodes (24): OrderParameters, PositionTargetIntent, RiskDecision, _Accounts, cancel_command(), decision(), _ExecutionOnlyGateway, _Gateway (+16 more)

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
Cohesion: 0.21
Nodes (6): ManualClock, IsolatedAsyncioTestCase, MonotonicNanos, UnixNanos, ServerTimeOpener, TransportAndClockAcceptanceTests

### Community 108 - "Community 108"
Cohesion: 0.09
Nodes (28): require_funding_carry_features(), Pure Funding Carry application contracts and policy., base_to_instrument_quantity(), create_funding_carry_pair(), _fixed(), FundingCarryPair, _instrument(), AccountId (+20 more)

### Community 109 - "Community 109"
Cohesion: 0.10
Nodes (23): AbstractEventLoop, Any, ExecutionQueryError, _ResultT, AsyncExecutionPortBridge, ExecutionBridgeError, ExecutionBridgeQueryError, ExecutionBridgeStateError (+15 more)

### Community 110 - "Community 110"
Cohesion: 0.12
Nodes (13): BinanceCredentialBinding, BinanceCredentialError, EnvironmentBinanceCredentialProvider, AccountId, RuntimeError, Sanitized credential lookup failure., Environment variable names for one explicitly selected account., Read fresh values per lookup so external rotation takes effect. (+5 more)

### Community 112 - "Community 112"
Cohesion: 0.22
Nodes (6): Self, FixedPoint, Decimal, An exact decimal value represented by an integer and decimal scale., Return an exact Decimal representation., Return the same value at another scale, rejecting precision loss.

### Community 114 - "Community 114"
Cohesion: 0.15
Nodes (20): IsolatedAsyncioTestCase, ExactExecutionGatewayRouter, Dispatch child commands through an immutable exact-scope allowlist. The router…, cancel(), exact_route(), ExactExecutionGatewayRouterTests, ExactExecutionRouteConfigurationTests, _Gateway (+12 more)

### Community 115 - "Community 115"
Cohesion: 0.09
Nodes (20): ExecutionStateUnknownError, ExecutionTransportError, DeterministicOfflineExecutionPort, OfflineExecutionDirective, OfflineExecutionDirectiveKind, OfflineExecutionScriptExhaustedError, CancelOrder, CancelResult (+12 more)

### Community 116 - "Community 116"
Cohesion: 0.11
Nodes (18): quantity_to_base(), assess_linear_funding_carry_hedge(), UnixNanos, Pure Carry hedge assessment from authoritative Portfolio position views., Classify residual Delta without using OMS fill quantities as truth., _unknown(), CarryHedgeAssessment, Immutable generic Carry position contracts. (+10 more)

### Community 117 - "Community 117"
Cohesion: 0.13
Nodes (15): JsonLinesOmsJournal, Path, Strict checksummed JSONL journal with an fsync boundary per append., _Accounts, decision(), _FailingJournal, _Identities, intent() (+7 more)

### Community 118 - "Community 118"
Cohesion: 0.13
Nodes (14): funding_objective_registry(), Stable Objective Type registrations for Funding Carry economics., ObjectiveTypeDefinition, ObjectiveTypeRegistrationError, ObjectiveTypeRegistry, Metadata-only registry entry; no callback or import path is allowed., An Objective Type registry is malformed or lacks a reference., Immutable deterministic registry of Objective Type metadata. (+6 more)

### Community 119 - "Community 119"
Cohesion: 0.11
Nodes (10): BinanceEnvironmentAcceptanceTests, BlockingConnection, BlockingTransport, ConnectionContext, NoQueryGateway, PrivateStreamSupervisionAcceptanceTests, BaseException, IsolatedAsyncioTestCase (+2 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (14): _require_text(), CoherenceGroup, DurationNanos, SnapshotSourceId, Bounded freshness and coherence policies for decision snapshots., _require_duration(), SnapshotPolicy, SourceFreshnessRule (+6 more)

### Community 121 - "Community 121"
Cohesion: 0.16
Nodes (10): BinanceProduct, StrEnum, Return a canonical instrument for an exact venue symbol., Explicit symbol table suitable for tests and immutable runtime snapshots., StaticInstrumentResolver, BinanceNormalizerTest, normalizer(), BinanceProduct (+2 more)

### Community 122 - "Community 122"
Cohesion: 0.33
Nodes (7): coordinator(), DecisionSnapshotAcceptanceTests, observation(), SnapshotSourceId, Offline acceptance scenarios for coherent decision snapshots., ThreeSourceAssembler, ThreeSourceDecisionInput

### Community 123 - "Community 123"
Cohesion: 0.11
Nodes (13): CollateralAssetSnapshot, MarginMode, MarginScopeSnapshot, PositionLiquidationReference, StrEnum, Execution-consistent position and normalized margin inputs for Portfolio Risk.…, Normalized collateral scope semantics., Venue-normalized margin facts; no venue payload leaks past adapters. (+5 more)

### Community 124 - "Community 124"
Cohesion: 0.07
Nodes (30): CarryPositionBook, DecisionSnapshotPublication, ExactRiskValue, JsonLinesOmsJournal, OrderEvent, PortfolioRiskCoordinator, PortfolioRiskEngine, PortfolioRiskPolicy (+22 more)

### Community 125 - "Community 125"
Cohesion: 0.22
Nodes (9): ExecutionConsistentPositionState, AccountId, One account's baseline plus only the not-yet-covered fill effects., ExecutionPositionEffectBatch, A complete scan of one contiguous OMS journal sequence range., account_snapshot(), baseline(), effect() (+1 more)

### Community 134 - "Community 134"
Cohesion: 0.09
Nodes (17): InvalidExecutionRequestError, ExecutionRoutingError, AccountId, CancelOrder, CancelResult, ExecutionGateway, InstrumentId, OrderReconciliationGateway (+9 more)

### Community 137 - "Community 137"
Cohesion: 0.09
Nodes (17): _bounded_values(), ExecutionPlannerBinding, ExecutionPlanningConfigurationError, ObjectiveExecutionPlanBinding, ObjectiveExecutionPlanResolver, OrderGroupPlanner, BasketTargetIntent, Protocol (+9 more)

### Community 140 - "Community 140"
Cohesion: 0.15
Nodes (23): AccountPositionRiskView, ExecutionPermitId, FixedPoint, PortfolioReconciliationId, _decode_approval_reservation(), _decode_basket(), _decode_confirmation(), _decode_permit() (+15 more)

### Community 141 - "Community 141"
Cohesion: 0.31
Nodes (4): DeterministicOfflineExecutionPort, OfflineExecutionDirective, _AllowSubmitGuard, GroupedExecutionRuntimeTests

### Community 142 - "Community 142"
Cohesion: 0.29
Nodes (5): CarryRecoveryKind, CarryRecoveryProposal, StrEnum, Carry economic recovery proposals, never execution instructions., A fresh economic preference with no OMS or Risk authority.

### Community 143 - "Community 143"
Cohesion: 0.17
Nodes (14): Deterministic project knowledge-graph tooling., BuildResult, canonical_json(), _clean_table_value(), _code_label_candidates(), _document_kind(), _generated_artifacts(), _graph_identity_set() (+6 more)

### Community 145 - "Community 145"
Cohesion: 0.20
Nodes (24): Edge, _ensure_reference_node(), _extend_unique_evidence(), _extract_adr(), _extract_architecture_constraints(), _extract_document_references(), _extract_state_ownership(), _extract_task_table() (+16 more)

### Community 146 - "Community 146"
Cohesion: 0.12
Nodes (7): Health, pipeline(), DecisionIntent, TestCase, Recorder, Risk, RuntimePipelineTests

### Community 147 - "Community 147"
Cohesion: 0.25
Nodes (18): ExecutionStageId, _blob(), _canonical(), _decode(), decode_execution_stage(), decode_execution_stage_permit(), _encode(), encode_execution_stage() (+10 more)

### Community 149 - "Community 149"
Cohesion: 0.14
Nodes (25): FeatureUpdate, FeatureUpdateDisposition, FeatureUpdateReport, InvalidFeatureEventError, StrEnum, Single-writer deterministic online feature engine., Raised when an event lacks canonical metadata., Registered online feature definitions, values, engines and state. Production… (+17 more)

### Community 150 - "Community 150"
Cohesion: 0.25
Nodes (7): Return a deterministic relationship identity., Hash ordered path/file-hash records using the Graphify convention., Return a lowercase SHA-256 digest., Return a lowercase SHA-256 digest for UTF-8 text., records_fingerprint(), sha256_bytes(), sha256_text()

### Community 151 - "Community 151"
Cohesion: 0.33
Nodes (3): Return a stable JSON representation., Return a stable JSON representation., Return the canonical federated project-graph descriptor.

### Community 152 - "Community 152"
Cohesion: 0.16
Nodes (12): _Accounts, _decision(), _Identities, _intent(), OmsRecoveryAcceptanceTests, OmsStartupReconciliationAcceptanceTests, _Orders, AccountId (+4 more)

### Community 153 - "Community 153"
Cohesion: 0.20
Nodes (15): ExecutionStagePermitId, create_execution_stage(), create_execution_stage_permit(), deterministic_execution_stage_id(), deterministic_execution_stage_permit_id(), _execution_plan_payload(), execution_stage_checksum(), DecisionSnapshotId (+7 more)

### Community 154 - "Community 154"
Cohesion: 0.27
Nodes (6): OrderStateMachine, ClientOrderId, Own one order's mutable state and expose only immutable snapshots., event(), OmsStateTests, request()

### Community 155 - "Community 155"
Cohesion: 0.25
Nodes (13): _basket(), cross_venue_basket(), four_leg_basket(), leg(), max_leg_basket(), AccountId, BasketTargetIntent, BasketTargetLeg (+5 more)

### Community 156 - "Community 156"
Cohesion: 0.25
Nodes (8): EnvironmentOperatorKeyProvider, Resolve fresh operator keys from explicit environment bindings., binding(), envelope(), OperatorAuthenticationTests, ManualClock, TestCase, RaisingEnvironment

### Community 157 - "Community 157"
Cohesion: 0.17
Nodes (12): ExecutionPositionEffectBatch, OmsJournal, Protocol, Durable ordered journal used by the single-writer OMS service., _effect_id(), OmsExecutionProjectionError, AccountId, Decimal (+4 more)

### Community 158 - "Community 158"
Cohesion: 0.24
Nodes (3): BinanceEnvironmentConfig, Complete, immutable endpoint selection for the trading runtime. Testnet is the…, BinanceEnvironmentConfigTests

### Community 159 - "Community 159"
Cohesion: 0.26
Nodes (6): DelayedGateway, FakeOms, IsolatedAsyncioTestCase, UnixNanos, request(), StartupReconciliationTests

### Community 160 - "Community 160"
Cohesion: 0.38
Nodes (5): instrument_id(), level(), MarketDataValidationTest, metadata(), TestCase

### Community 161 - "Community 161"
Cohesion: 0.20
Nodes (6): DurationNanos, Capped exponential backoff with caller-supplied deterministic jitter., Return delay for a one-based attempt. Randomness is deliberately supplied by…, ReconnectPolicy, TestCase, ReconnectPolicyTest

### Community 162 - "Community 162"
Cohesion: 0.22
Nodes (7): EventTimeSource, StrEnum, Metadata shared by immutable domain events., Precision supplied by an upstream source before nanosecond conversion., Origin of `event_time_ns`, independent of its storage unit., TimePrecision, Strong identifiers shared by domain contracts.

### Community 163 - "Community 163"
Cohesion: 0.27
Nodes (5): Instrument, Tradable product definition independent of venue payload formats., spot(), InstrumentTest, TestCase

### Community 164 - "Community 164"
Cohesion: 0.22
Nodes (3): SSLContext, StreamReader, Writer

### Community 165 - "Community 165"
Cohesion: 0.29
Nodes (3): _GroupedSubmitStateAdapter, OrderRequest, SubmitResult

### Community 166 - "Community 166"
Cohesion: 0.60
Nodes (3): ExternalSubmitGuardPort, OrderGroupId, UnixNanos

## Knowledge Gaps
- **2 isolated node(s):** `cex-quant`, `SecretPattern`
  These have ≤1 connection - possible missing edges or undocumented components.
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RecorderHandoff` connect `Community 52` to `Community 58`, `Community 79`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `AsyncExecutionPortBridge` connect `Community 109` to `Community 17`, `Community 114`, `Community 78`, `Community 103`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `ManualClock` connect `Community 60` to `Community 167`, `Community 141`, `Community 15`, `Community 19`, `Community 117`, `Community 155`, `Community 124`, `Community 63`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `InstrumentId` (e.g. with `perpetual()` and `spot()`) actually correct?**
  _`InstrumentId` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `OrderGroupRuntime` (e.g. with `GroupedAdmissionDisposition` and `GroupedAdmissionResult`) actually correct?**
  _`OrderGroupRuntime` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `BinanceProduct` (e.g. with `AuthenticatedBinanceExecutionAdapter` and `BinanceCredentialProvider`) actually correct?**
  _`BinanceProduct` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Quantity` (e.g. with `.test_same_instrument_across_accounts_and_zero_target_are_valid()` and `.test_exact_rescale_preserves_nominal_type()`) actually correct?**
  _`Quantity` has 11 INFERRED edges - model-reasoned connections that need verification._