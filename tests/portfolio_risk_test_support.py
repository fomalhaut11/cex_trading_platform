"""Deterministic ADR-012 fixtures shared by unit and acceptance tests."""

from __future__ import annotations

from cex_quant.core import (
    AccountId,
    AssetId,
    FixedPoint,
    MarginScopeId,
    Money,
    MonotonicNanos,
    PortfolioReconciliationId,
    Price,
    Quantity,
    Rate,
    RiskFactorId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import (
    ContractValueType,
    ExerciseStyle,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    OptionSide,
    OptionSpecification,
    PerpetualSpecification,
    SettlementType,
    SpotSpecification,
)
from cex_quant.observability import HealthReport, HealthStatus
from cex_quant.oms import OrderGroupView
from cex_quant.portfolio import (
    AccountPositionRiskView,
    ExecutionCoverage,
    InstrumentPositionRiskView,
    MarginMode,
    MarginScopeSnapshot,
    PositionRiskReadiness,
)
from cex_quant.risk import (
    ExactRiskValue,
    InstrumentRiskModelPolicy,
    InstrumentSensitivity,
    PortfolioRiskPolicy,
    PortfolioRiskReservationView,
    PortfolioRiskSnapshot,
    RiskFactorLimit,
    RiskMark,
    WorkingOrderRiskView,
)
from cex_quant.snapshots import (
    DecisionSnapshotId,
    DecisionSnapshotMetadata,
    DecisionSnapshotPublication,
    ObservationId,
    SnapshotAssessment,
    SnapshotReadiness,
)
from tests.group_test_support import ACCOUNT_ID, DECISION_SNAPSHOT_ID, instrument

NOW = UnixNanos(2_000)
RISK_SNAPSHOT_ID = DecisionSnapshotId("portfolio-risk-snapshot-012")
REPORTING_ASSET = AssetId("USDT")
BTC_FACTOR = RiskFactorId("BTC")
CROSS_SCOPE = MarginScopeId("primary-cross-usdt")


def product(kind: InstrumentKind, symbol: str) -> Instrument:
    instrument_id = instrument(kind, symbol)
    if kind is InstrumentKind.SPOT:
        specification = SpotSpecification()
    elif kind is InstrumentKind.PERPETUAL:
        specification = PerpetualSpecification(
            settlement_asset=REPORTING_ASSET,
            margin_asset=REPORTING_ASSET,
            contract_size=Quantity.from_str("1"),
            contract_size_asset=AssetId("BTC"),
            value_type=ContractValueType.LINEAR,
        )
    elif kind is InstrumentKind.OPTION:
        specification = OptionSpecification(
            underlying_id=instrument(InstrumentKind.PERPETUAL, "BTCUSDT"),
            settlement_asset=REPORTING_ASSET,
            margin_asset=REPORTING_ASSET,
            contract_size=Quantity.from_str("1"),
            contract_size_asset=AssetId("BTC"),
            strike=Price.from_str("100"),
            option_side=OptionSide.CALL,
            exercise_style=ExerciseStyle.EUROPEAN,
            expiry_time_ns=UnixNanos(9_000),
            settlement_type=SettlementType.CASH,
        )
    else:
        raise ValueError("test fixture supports spot, perpetual and option")
    return Instrument(
        instrument_id=instrument_id,
        base_asset=AssetId("BTC"),
        quote_asset=REPORTING_ASSET,
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.01"),
        status=InstrumentStatus.ACTIVE,
        specification=specification,
    )


def exact(
    value: str,
    *,
    unit: str,
    asset: AssetId | None = None,
    observation: str = "risk-input",
) -> ExactRiskValue:
    return ExactRiskValue(
        value=FixedPoint.from_str(value),
        unit=unit,
        asset=asset,
        observation_id=ObservationId(observation),
        as_of_ns=UnixNanos(1_950),
        valid_until_ns=UnixNanos(3_000),
    )


def sensitivity(
    instrument_id: InstrumentId,
    *,
    delta: str,
    margin: str,
    gamma: str | None = None,
    vega: str | None = None,
) -> InstrumentSensitivity:
    return InstrumentSensitivity(
        instrument_id=instrument_id,
        model_version=1,
        risk_factor_id=BTC_FACTOR,
        margin_scope_id=(
            None
            if Money.from_str(margin).raw == 0
            else CROSS_SCOPE
        ),
        delta_per_quantity=exact(delta, unit="BTC/qty"),
        initial_margin_per_quantity=exact(
            margin,
            unit="USDT/qty",
            asset=REPORTING_ASSET,
        ),
        gamma_per_quantity=(
            None if gamma is None else exact(gamma, unit="BTC/USDT/qty")
        ),
        vega_per_quantity=(
            None
            if vega is None
            else exact(
                vega,
                unit="USDT/vol/qty",
                asset=REPORTING_ASSET,
            )
        ),
    )


def position_view(
    quantities: dict[InstrumentId, str] | None = None,
    *,
    readiness: PositionRiskReadiness = PositionRiskReadiness.READY,
) -> AccountPositionRiskView:
    values = quantities or {}
    positions = tuple(
        InstrumentPositionRiskView(
            instrument_id=instrument_id,
            baseline_quantity=Quantity.from_str(quantity),
            post_baseline_fill_delta=Quantity.from_str("0"),
            effective_quantity=Quantity.from_str(quantity),
        )
        for instrument_id, quantity in sorted(
            values.items(),
            key=lambda item: str(item[0]),
        )
    )
    return AccountPositionRiskView(
        account_id=ACCOUNT_ID,
        reconciliation_id=(
            PortfolioReconciliationId("risk-view-reconciliation")
            if readiness is PositionRiskReadiness.READY
            else None
        ),
        observation_id=(
            ObservationId("risk-view-account")
            if readiness is PositionRiskReadiness.READY
            else None
        ),
        coverage=ExecutionCoverage(through_oms_journal_sequence=20),
        as_of_ns=UnixNanos(1_995),
        positions=positions,
        readiness=readiness,
        reason=(
            "" if readiness is PositionRiskReadiness.READY else "not reconciled"
        ),
    )


def margin_scope(*, available: str = "1000") -> MarginScopeSnapshot:
    return MarginScopeSnapshot(
        scope_id=CROSS_SCOPE,
        observation_id=ObservationId("margin-1"),
        account_id=ACCOUNT_ID,
        venue=VenueId("BINANCE"),
        mode=MarginMode.CROSS,
        reporting_asset=REPORTING_ASSET,
        equity=Money.from_str("1200"),
        collateral=(),
        initial_margin=Money.from_str("0"),
        maintenance_margin=Money.from_str("0"),
        available_margin=Money.from_str(available),
        margin_ratio=Rate.from_str("0"),
        as_of_ns=UnixNanos(1_950),
        source_update_id="margin-update-1",
    )


def portfolio_snapshot(
    instruments: tuple[Instrument, ...],
    sensitivities: tuple[InstrumentSensitivity, ...],
    *,
    positions: AccountPositionRiskView | None = None,
    working_orders: tuple[WorkingOrderRiskView, ...] = (),
    groups: tuple[OrderGroupView, ...] = (),
    reservations: tuple[PortfolioRiskReservationView, ...] = (),
) -> PortfolioRiskSnapshot:
    return PortfolioRiskSnapshot(
        original_decision_snapshot_ids=(DECISION_SNAPSHOT_ID,),
        positions=(positions or position_view(),),
        working_orders=working_orders,
        groups=groups,
        margins=(margin_scope(),),
        liquidation_references=(),
        instruments=instruments,
        marks=tuple(
            RiskMark(
                instrument_id=item.instrument_id,
                price=exact(
                    "100",
                    unit="USDT",
                    asset=REPORTING_ASSET,
                    observation=f"mark-{index}",
                ),
            )
            for index, item in enumerate(instruments)
        ),
        sensitivities=sensitivities,
        spread_inputs=(),
        active_reservations=reservations,
        health=HealthReport(
            component="portfolio-risk-inputs",
            status=HealthStatus.HEALTHY,
            observed_at_ns=NOW,
        ),
    )


def publication(
    value: PortfolioRiskSnapshot,
) -> DecisionSnapshotPublication[PortfolioRiskSnapshot]:
    return DecisionSnapshotPublication(
        metadata=DecisionSnapshotMetadata(
            snapshot_id=RISK_SNAPSHOT_ID,
            scope="portfolio-risk",
            snapshot_sequence=1,
            assembled_at_ns=UnixNanos(1_980),
            assembled_at_monotonic_ns=MonotonicNanos(500),
            policy_version=1,
            observation_ids=(ObservationId("risk-publication"),),
            coherence=(),
        ),
        assessment=SnapshotAssessment(
            readiness=SnapshotReadiness.READY,
            issues=(),
            policy_version=1,
        ),
        value=value,
    )


def policy(instruments: tuple[Instrument, ...]) -> PortfolioRiskPolicy:
    models = tuple(
        InstrumentRiskModelPolicy(
            instrument_id=item.instrument_id,
            model_version=1,
            delta_unit="BTC/qty",
            initial_margin_unit="USDT/qty",
            gamma_unit=(
                "BTC/USDT/qty"
                if item.instrument_id.kind is InstrumentKind.OPTION
                else None
            ),
            vega_unit=(
                "USDT/vol/qty"
                if item.instrument_id.kind is InstrumentKind.OPTION
                else None
            ),
        )
        for item in sorted(instruments, key=lambda item: str(item.instrument_id))
    )
    return PortfolioRiskPolicy(
        version=1,
        reporting_asset=REPORTING_ASSET,
        required_account_ids=(AccountId(ACCOUNT_ID),),
        required_instrument_ids=tuple(
            sorted(
                (item.instrument_id for item in instruments),
                key=str,
            )
        ),
        required_margin_scope_ids=(CROSS_SCOPE,),
        required_liquidation_references=(),
        supported_model_versions=(1,),
        instrument_models=models,
        factor_limits=(
            RiskFactorLimit(
                risk_factor_id=BTC_FACTOR,
                max_abs_net_delta=FixedPoint.from_str("100"),
                max_gross_delta=FixedPoint.from_str("1000"),
                max_abs_gamma=FixedPoint.from_str("100"),
                max_abs_vega=FixedPoint.from_str("10000"),
            ),
        ),
        spread_limits=(),
        max_gross_notional=Money.from_str("1000000"),
        max_initial_margin=Money.from_str("100000"),
        min_available_margin=Money.from_str("0"),
        min_liquidation_buffer=Rate.from_str("0"),
        max_snapshot_age_ns=1_000,
        max_mark_age_ns=1_000,
        max_sensitivity_age_ns=1_000,
        max_margin_age_ns=1_000,
        max_liquidation_age_ns=1_000,
        approval_lifetime_ns=500,
        permit_lifetime_ns=100,
        reservation_lifetime_ns=400,
        max_active_reservations=8,
    )


__all__ = [
    "BTC_FACTOR",
    "CROSS_SCOPE",
    "NOW",
    "REPORTING_ASSET",
    "RISK_SNAPSHOT_ID",
    "exact",
    "margin_scope",
    "policy",
    "portfolio_snapshot",
    "position_view",
    "product",
    "publication",
    "sensitivity",
]
