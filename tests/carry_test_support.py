from __future__ import annotations

from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
    CarryPositionView,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.applications.carry.funding_arbitrage import (
    FundingCarryControlInputs,
    FundingCarryPortfolioInputs,
    FundingCarrySourceIds,
    create_funding_carry_pair,
)
from cex_quant.applications.carry.funding_arbitrage.features import (
    FundingCarryFeatureInput,
    funding_carry_feature_definitions,
)
from cex_quant.applications.carry.funding_arbitrage.policy import (
    FundingCarryFeaturePolicy,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    EventId,
    EventMetadata,
    EventSource,
    MarginScopeId,
    Money,
    PortfolioReconciliationId,
    Price,
    Quantity,
    Rate,
    SchemaVersion,
    StrategyId,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.features import OnlineFeatureEngine
from cex_quant.instruments import (
    ContractValueType,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.market_data import (
    BookLevel,
    FundingRateState,
    FundingRateUpdate,
    IndexPriceUpdate,
    L1View,
    MarketStateStatus,
    MarkPriceUpdate,
)
from cex_quant.portfolio import (
    AccountPositionRiskView,
    ExecutionCoverage,
    InstrumentPositionRiskView,
    MarginMode,
    MarginScopeSnapshot,
    PositionRiskReadiness,
)
from cex_quant.snapshots import (
    ObservationId,
    SnapshotSourceId,
    SourceObservation,
)

SCOPE = "carry.btc.entry"
POSITION_SCOPE = "carry.btc.position"
STRATEGY_ID = StrategyId("funding-carry-btc")
SPOT_ACCOUNT = AccountId("spot-account")
PERPETUAL_ACCOUNT = AccountId("perp-account")

SOURCES = FundingCarrySourceIds(
    spot_market=SnapshotSourceId("spot-market"),
    perpetual_market=SnapshotSourceId("perpetual-market"),
    mark_price=SnapshotSourceId("mark-price"),
    index_price=SnapshotSourceId("index-price"),
    funding=SnapshotSourceId("funding"),
    portfolio=SnapshotSourceId("portfolio"),
    features=SnapshotSourceId("features"),
)
POSITION_SOURCES = FundingCarrySourceIds(
    spot_market=SnapshotSourceId("position-spot-market"),
    perpetual_market=SnapshotSourceId("position-perpetual-market"),
    mark_price=SnapshotSourceId("position-mark-price"),
    index_price=SnapshotSourceId("position-index-price"),
    funding=SnapshotSourceId("position-funding"),
    portfolio=SnapshotSourceId("position-portfolio"),
    features=SnapshotSourceId("position-features"),
    control=SnapshotSourceId("position-control"),
)


def metadata(
    event_id: str,
    *,
    event_time_ns: int = 1_000,
    sequence: int | None = None,
) -> EventMetadata:
    return EventMetadata(
        event_id=EventId(event_id),
        event_time_ns=UnixNanos(event_time_ns),
        receive_time_ns=UnixNanos(event_time_ns + 1),
        source=EventSource(
            venue=VenueId("BINANCE"),
            channel="carry-test",
        ),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.NANOSECOND,
        sequence=sequence,
    )


def instruments() -> tuple[Instrument, Instrument]:
    spot = Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSDT",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USDT"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.001"),
        status=InstrumentStatus.ACTIVE,
        specification=SpotSpecification(),
    )
    perpetual = Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=InstrumentKind.PERPETUAL,
            symbol="BTCUSDT",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USDT"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.001"),
        status=InstrumentStatus.ACTIVE,
        specification=PerpetualSpecification(
            settlement_asset=AssetId("USDT"),
            margin_asset=AssetId("USDT"),
            contract_size=Quantity.from_str("1"),
            contract_size_asset=AssetId("BTC"),
            value_type=ContractValueType.LINEAR,
        ),
    )
    return spot, perpetual


def pair():
    spot, perpetual = instruments()
    return create_funding_carry_pair(
        underlying_asset_id=AssetId("BTC"),
        spot_account_id=SPOT_ACCOUNT,
        spot_instrument=spot,
        perpetual_account_id=PERPETUAL_ACCOUNT,
        perpetual_instrument=perpetual,
        quantity_conversion_policy_ref="linear-base-quantity@1",
    )


def markets(
    *,
    funding_rate: str = "0.0010",
) -> tuple[L1View, L1View, MarkPriceUpdate, IndexPriceUpdate, object]:
    configured_pair = pair()
    spot = L1View(
        instrument_id=configured_pair.spot_instrument_id,
        bid=BookLevel(
            price=Price.from_str("99"),
            quantity=Quantity.from_str("20"),
        ),
        ask=BookLevel(
            price=Price.from_str("100"),
            quantity=Quantity.from_str("20"),
        ),
        as_of_ns=UnixNanos(1_000),
        sequence=1,
        status=MarketStateStatus.LIVE,
    )
    perpetual = L1View(
        instrument_id=configured_pair.perpetual_instrument_id,
        bid=BookLevel(
            price=Price.from_str("101"),
            quantity=Quantity.from_str("20"),
        ),
        ask=BookLevel(
            price=Price.from_str("102"),
            quantity=Quantity.from_str("20"),
        ),
        as_of_ns=UnixNanos(1_000),
        sequence=1,
        status=MarketStateStatus.LIVE,
    )
    mark = MarkPriceUpdate(
        metadata=metadata("mark-1"),
        instrument_id=configured_pair.perpetual_instrument_id,
        mark_price=Price.from_str("101.5"),
    )
    index = IndexPriceUpdate(
        metadata=metadata("index-1"),
        instrument_id=configured_pair.perpetual_instrument_id,
        index_price=Price.from_str("100.5"),
    )
    state = FundingRateState(
        instrument_id=configured_pair.perpetual_instrument_id
    )
    state.apply(
        FundingRateUpdate(
            metadata=metadata("funding-1", sequence=1),
            instrument_id=configured_pair.perpetual_instrument_id,
            funding_rate=Rate.from_str(funding_rate),
            next_funding_time_ns=UnixNanos(2_000),
        )
    )
    funding = state.view()
    assert funding is not None
    return spot, perpetual, mark, index, funding


def portfolio(
    *,
    spot_quantity: str = "0",
    perpetual_quantity: str = "0",
) -> FundingCarryPortfolioInputs:
    configured_pair = pair()
    positions = tuple(
        sorted(
            (
                _account_position(
                    PERPETUAL_ACCOUNT,
                    configured_pair.perpetual_instrument_id,
                    perpetual_quantity,
                ),
                _account_position(
                    SPOT_ACCOUNT,
                    configured_pair.spot_instrument_id,
                    spot_quantity,
                ),
            ),
            key=lambda item: str(item.account_id),
        )
    )
    margin = MarginScopeSnapshot(
        scope_id=MarginScopeId("perp-cross"),
        observation_id=ObservationId("margin-1"),
        account_id=PERPETUAL_ACCOUNT,
        venue=VenueId("BINANCE"),
        mode=MarginMode.CROSS,
        reporting_asset=AssetId("USDT"),
        equity=Money.from_str("100000"),
        collateral=(),
        initial_margin=Money.from_str("0"),
        maintenance_margin=Money.from_str("0"),
        available_margin=Money.from_str("100000"),
        margin_ratio=None,
        as_of_ns=UnixNanos(1_000),
        source_update_id="margin-update-1",
    )
    return FundingCarryPortfolioInputs(
        positions=positions,
        margins=(margin,),
    )


def feature_snapshot(
    *,
    funding_rate: str = "0.0010",
    scope: str = SCOPE,
):
    spot, perpetual, _, _, funding = markets(funding_rate=funding_rate)
    engine = OnlineFeatureEngine(
        scope=scope,
        definitions=funding_carry_feature_definitions(
            FundingCarryFeaturePolicy(
                estimated_round_trip_cost_rate=0.0002,
                funding_periods_per_year=1_095,
                version=1,
            )
        ),
    )
    engine.on_event(
        FundingCarryFeatureInput(
            metadata=metadata("carry-feature-1"),
            pair=pair(),
            spot_market=spot,
            perpetual_market=perpetual,
            funding=funding,  # type: ignore[arg-type]
        )
    )
    return engine.snapshot()


def entry_observations(
    *,
    funding_rate: str = "0.0010",
    scope: str = SCOPE,
    sources: FundingCarrySourceIds = SOURCES,
) -> tuple[SourceObservation[object], ...]:
    spot, perpetual, mark, index, funding = markets(
        funding_rate=funding_rate
    )
    values: tuple[tuple[SnapshotSourceId, object, int], ...] = (
        (sources.spot_market, spot, int(spot.as_of_ns)),
        (sources.perpetual_market, perpetual, int(perpetual.as_of_ns)),
        (sources.mark_price, mark, int(mark.metadata.event_time_ns)),
        (sources.index_price, index, int(index.metadata.event_time_ns)),
        (sources.funding, funding, int(funding.as_of_ns)),  # type: ignore[attr-defined]
        (sources.portfolio, portfolio(), 1_000),
        (
            sources.features,
            feature_snapshot(funding_rate=funding_rate, scope=scope),
            1_000,
        ),
    )
    return tuple(
        SourceObservation(
            observation_id=ObservationId(f"{source_id}-observation"),
            source_id=source_id,
            scope=scope,
            as_of_ns=UnixNanos(as_of_ns),
            received_at_ns=UnixNanos(as_of_ns + 1),
            accepted_at_monotonic_ns=100,
            schema_version=1,
            value=value,
            source_sequence=1,
        )
        for source_id, value, as_of_ns in values
    )


def position_observations(
    *,
    funding_rate: str = "-0.0010",
) -> tuple[SourceObservation[object], ...]:
    values = list(
        entry_observations(
            funding_rate=funding_rate,
            scope=POSITION_SCOPE,
            sources=POSITION_SOURCES,
        )
    )
    control_id = POSITION_SOURCES.control
    assert control_id is not None
    values.append(
        SourceObservation(
            observation_id=ObservationId("position-control-observation"),
            source_id=control_id,
            scope=POSITION_SCOPE,
            as_of_ns=UnixNanos(1_000),
            received_at_ns=UnixNanos(1_001),
            accepted_at_monotonic_ns=100,
            schema_version=1,
            value=active_control(),
            source_sequence=1,
        )
    )
    return tuple(values)


def active_control():
    configured_pair = pair()
    snapshot_id = "opening-snapshot"
    position_id = deterministic_application_position_id(
        strategy_id=STRATEGY_ID,
        pair_id=configured_pair.pair_id,
        opening_snapshot_id=snapshot_id,
    )
    ownership = tuple(
        create_carry_leg_ownership(
            application_position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
            baseline_quantity=Quantity.from_str("0"),
            intended_owned_delta=Quantity.from_str(delta),
            effective_from_ns=UnixNanos(900),
            source_snapshot_id=snapshot_id,
            policy_version=1,
        )
        for account_id, instrument_id, delta in (
            (
                configured_pair.spot_account_id,
                configured_pair.spot_instrument_id,
                "10",
            ),
            (
                configured_pair.perpetual_account_id,
                configured_pair.perpetual_instrument_id,
                "-10",
            ),
        )
    )
    return FundingCarryControlInputs(
        application_position=CarryPositionView(
            application_position_id=position_id,
            strategy_id=STRATEGY_ID,
            pair_id=configured_pair.pair_id,
            revision=3,
            lifecycle=CarryLifecycle.ACTIVE,
            hedge_state=CarryHedgeState.HEDGED,
            financial_state=CarryFinancialState.PROVISIONAL,
            opening_snapshot_id=snapshot_id,
            latest_snapshot_id=snapshot_id,
            intent_ids=(),
            order_group_ids=(),
            leg_ownership=ownership,
            last_transition_ns=UnixNanos(950),
        ),
        risk_directives=(),
        order_groups=(),
    )


def _account_position(
    account_id: AccountId,
    instrument_id: InstrumentId,
    quantity: str,
) -> AccountPositionRiskView:
    value = Quantity.from_str(quantity)
    return AccountPositionRiskView(
        account_id=account_id,
        reconciliation_id=PortfolioReconciliationId(
            f"reconciliation-{account_id}"
        ),
        observation_id=ObservationId(f"position-{account_id}"),
        coverage=ExecutionCoverage(through_oms_journal_sequence=0),
        as_of_ns=UnixNanos(1_000),
        positions=(
            InstrumentPositionRiskView(
                instrument_id=instrument_id,
                baseline_quantity=value,
                post_baseline_fill_delta=Quantity.from_str("0"),
                effective_quantity=value,
            ),
        ),
        readiness=PositionRiskReadiness.READY,
    )
