from dataclasses import FrozenInstanceError, replace
from unittest import TestCase

from cex_quant.core import (
    AssetId,
    IntentId,
    Money,
    Price,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.features import FeatureQuality
from cex_quant.instruments import (
    ContractValueType,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.observability import HealthStatus
from cex_quant.risk import (
    RiskContext,
    RiskDecisionStatus,
    RiskEngine,
    RiskLimits,
    RiskRejectReason,
)
from cex_quant.strategy import PositionTargetIntent

NOW = UnixNanos(10_000)
STRATEGY = StrategyId("maker")


def spot() -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("TEST"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSD",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USD"),
        price_increment=Price.from_str("0.01"),
        quantity_increment=Quantity.from_str("0.001"),
        status=InstrumentStatus.ACTIVE,
        specification=SpotSpecification(),
    )


def perpetual(value_type: ContractValueType) -> Instrument:
    inverse = value_type is ContractValueType.INVERSE
    return Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("TEST"),
            kind=InstrumentKind.PERPETUAL,
            symbol="BTCUSD-INVERSE" if inverse else "BTCUSD-LINEAR",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USD"),
        price_increment=Price.from_str("0.1"),
        quantity_increment=Quantity.from_str("1"),
        status=InstrumentStatus.ACTIVE,
        specification=PerpetualSpecification(
            settlement_asset=AssetId("BTC" if inverse else "USD"),
            margin_asset=AssetId("BTC" if inverse else "USD"),
            contract_size=Quantity.from_str("100" if inverse else "0.001"),
            contract_size_asset=AssetId("USD" if inverse else "BTC"),
            value_type=value_type,
        ),
    )


def intent(instrument: Instrument, target: str = "2") -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId("intent-1"),
        strategy_id=STRATEGY,
        instrument_id=instrument.instrument_id,
        target_quantity=Quantity.from_str(target),
        decision_time_ns=UnixNanos(9_900),
        valid_until_ns=UnixNanos(10_100),
    )


def context(
    instrument: Instrument,
    *,
    strategy_position: str = "0",
    global_position: str = "0",
) -> RiskContext:
    return RiskContext(
        now_ns=NOW,
        strategy_id=STRATEGY,
        instrument=instrument,
        current_strategy_position=Quantity.from_str(strategy_position),
        current_global_position=Quantity.from_str(global_position),
        reference_price=Price.from_str("20000"),
        market_data_as_of_ns=UnixNanos(9_950),
        feature_data_as_of_ns=UnixNanos(9_940),
        feature_data_valid_until_ns=UnixNanos(10_050),
        feature_quality=FeatureQuality.GOOD,
        clock_status=HealthStatus.HEALTHY,
    )


class RiskEngineTests(TestCase):
    def test_allows_exact_boundaries_and_is_immutable(self) -> None:
        instrument = spot()
        limits = RiskLimits(
            max_abs_strategy_position=Quantity.from_str("2"),
            max_abs_global_position=Quantity.from_str("5"),
            max_strategy_notional=Money.from_str("40000"),
            max_global_notional=Money.from_str("100000"),
            max_strategy_intents_per_window=3,
            max_global_intents_per_window=10,
            max_market_data_age_ns=50,
            max_feature_data_age_ns=60,
        )
        decision = RiskEngine(limits).evaluate(
            intent(instrument),
            replace(
                context(instrument, global_position="3"),
                strategy_intents_in_window=2,
                global_intents_in_window=9,
            ),
        )

        self.assertEqual(decision.status, RiskDecisionStatus.ALLOW)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, ())
        self.assertEqual(
            decision.projected_global_position.as_decimal(),
            Quantity.from_str("5").as_decimal(),
        )
        self.assertEqual(
            decision.projected_strategy_notional.as_decimal(),
            Money.from_str("40000").as_decimal(),
        )
        with self.assertRaises(FrozenInstanceError):
            decision.status = RiskDecisionStatus.REJECT  # type: ignore[misc]

    def test_global_projection_replaces_strategy_contribution(self) -> None:
        instrument = spot()
        decision = RiskEngine(RiskLimits()).evaluate(
            intent(instrument, "4"),
            context(
                instrument,
                strategy_position="2",
                global_position="7",
            ),
        )
        self.assertEqual(
            decision.projected_global_position.as_decimal(),
            Quantity.from_str("9").as_decimal(),
        )

    def test_collects_exposure_and_rate_rejections_deterministically(self) -> None:
        instrument = spot()
        decision = RiskEngine(
            RiskLimits(
                max_abs_strategy_position=Quantity.from_str("1"),
                max_abs_global_position=Quantity.from_str("1"),
                max_strategy_notional=Money.from_str("100"),
                max_global_notional=Money.from_str("100"),
                max_strategy_intents_per_window=2,
                max_global_intents_per_window=3,
            )
        ).evaluate(
            intent(instrument, "-2"),
            replace(
                context(instrument),
                strategy_intents_in_window=2,
                global_intents_in_window=3,
            ),
        )
        self.assertEqual(
            decision.reasons,
            (
                RiskRejectReason.STRATEGY_POSITION_LIMIT,
                RiskRejectReason.GLOBAL_POSITION_LIMIT,
                RiskRejectReason.STRATEGY_NOTIONAL_LIMIT,
                RiskRejectReason.GLOBAL_NOTIONAL_LIMIT,
                RiskRejectReason.STRATEGY_INTENT_RATE_LIMIT,
                RiskRejectReason.GLOBAL_INTENT_RATE_LIMIT,
            ),
        )

    def test_fail_closed_on_missing_stale_or_unhealthy_inputs(self) -> None:
        instrument = spot()
        decision = RiskEngine(
            RiskLimits(
                max_market_data_age_ns=100,
                max_feature_data_age_ns=100,
            )
        ).evaluate(
            intent(instrument),
            replace(
                context(instrument),
                reference_price=None,
                market_data_as_of_ns=None,
                feature_data_as_of_ns=UnixNanos(9_899),
                feature_data_valid_until_ns=UnixNanos(9_999),
                clock_status=HealthStatus.DEGRADED,
            ),
        )
        self.assertEqual(
            decision.reasons,
            (
                RiskRejectReason.CLOCK_UNHEALTHY,
                RiskRejectReason.REFERENCE_PRICE_MISSING,
                RiskRejectReason.MARKET_DATA_MISSING,
                RiskRejectReason.FEATURE_DATA_STALE,
            ),
        )
        self.assertIsNone(decision.projected_strategy_notional)

    def test_rejects_future_or_expired_intent_and_inactive_instrument(self) -> None:
        instrument = replace(spot(), status=InstrumentStatus.HALTED)
        future = replace(
            intent(instrument),
            decision_time_ns=UnixNanos(10_001),
            valid_until_ns=UnixNanos(10_001),
        )
        future_decision = RiskEngine(RiskLimits()).evaluate(
            future,
            context(instrument),
        )
        self.assertEqual(
            future_decision.reasons,
            (
                RiskRejectReason.INTENT_FROM_FUTURE,
                RiskRejectReason.INSTRUMENT_NOT_ACTIVE,
            ),
        )

        expired = replace(
            intent(replace(instrument, status=InstrumentStatus.ACTIVE)),
            valid_until_ns=UnixNanos(9_999),
        )
        expired_decision = RiskEngine(RiskLimits()).evaluate(
            expired,
            context(replace(instrument, status=InstrumentStatus.ACTIVE)),
        )
        self.assertEqual(
            expired_decision.reasons,
            (RiskRejectReason.INTENT_EXPIRED,),
        )

    def test_features_may_be_explicitly_not_required(self) -> None:
        instrument = spot()
        decision = RiskEngine(
            RiskLimits(require_fresh_features=False)
        ).evaluate(
            intent(instrument),
            replace(
                context(instrument),
                feature_data_as_of_ns=None,
                feature_data_valid_until_ns=None,
                feature_quality=None,
            ),
        )
        self.assertTrue(decision.allowed)

    def test_non_good_feature_quality_is_rejected(self) -> None:
        instrument = spot()
        decision = RiskEngine(RiskLimits()).evaluate(
            intent(instrument),
            replace(
                context(instrument),
                feature_quality=FeatureQuality.DEGRADED,
            ),
        )
        self.assertEqual(
            decision.reasons,
            (RiskRejectReason.FEATURE_DATA_INVALID,),
        )

    def test_linear_contract_notional_uses_price_and_contract_size(self) -> None:
        instrument = perpetual(ContractValueType.LINEAR)
        decision = RiskEngine(RiskLimits()).evaluate(
            intent(instrument, "10"),
            context(instrument),
        )
        self.assertEqual(
            decision.projected_strategy_notional.as_decimal(),
            Money.from_str("200").as_decimal(),
        )

    def test_inverse_contract_quote_notional_is_price_independent(self) -> None:
        instrument = perpetual(ContractValueType.INVERSE)
        decision = RiskEngine(RiskLimits()).evaluate(
            intent(instrument, "-10"),
            context(instrument),
        )
        self.assertEqual(
            decision.projected_strategy_notional.as_decimal(),
            Money.from_str("1000").as_decimal(),
        )

    def test_invalid_limits_and_context_counts_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            RiskLimits(max_global_notional=Money.from_str("-1"))
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            replace(context(spot()), strategy_intents_in_window=-1)


if __name__ == "__main__":
    import unittest

    unittest.main()
