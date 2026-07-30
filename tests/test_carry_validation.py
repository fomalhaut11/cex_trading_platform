from dataclasses import replace
from math import nan
from unittest import TestCase

from carry_test_support import (
    POSITION_SOURCES,
    SCOPE,
    SOURCES,
    entry_observations,
    feature_snapshot,
    instruments,
    pair,
    portfolio,
)

from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeAssessment,
    CarryHedgeState,
    CarryRecoveryKind,
    CarryRecoveryProposal,
    assess_carry_financial_state,
)
from cex_quant.applications.carry.funding_arbitrage import (
    FundingCarryEconomicPolicy,
    FundingCarryFeaturePolicy,
    FundingCarryPortfolioInputs,
    FundingCarrySnapshotAssembler,
    FundingCarrySnapshotKind,
    base_to_instrument_quantity,
    create_funding_carry_pair,
    quantity_to_base,
)
from cex_quant.applications.carry.funding_arbitrage.features import (
    FundingCarryFeatureInput,
    funding_carry_feature_definitions,
    funding_feature_value,
    require_funding_carry_features,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    DurationNanos,
    MarginScopeId,
    Quantity,
    UnixNanos,
)
from cex_quant.features import (
    FeatureContext,
    FeatureQuality,
    FeatureSnapshot,
)
from cex_quant.instruments import (
    ContractValueType,
    InstrumentKind,
    PerpetualSpecification,
)
from cex_quant.market_data import MarketStateStatus
from cex_quant.snapshots import (
    DecisionSnapshotId,
    DecisionSnapshotMetadata,
)
from cex_quant.strategy import MAX_BASKET_VALIDITY_NS


class CarryPolicyValidationTests(TestCase):
    def test_feature_policy_rejects_invalid_bounds(self) -> None:
        invalid = (
            {"estimated_round_trip_cost_rate": -1.0},
            {"estimated_round_trip_cost_rate": nan},
            {"funding_periods_per_year": 0},
            {"funding_periods_per_year": 24 * 366 + 1},
            {"version": 0},
        )
        baseline = {
            "estimated_round_trip_cost_rate": 0.001,
            "funding_periods_per_year": 1_095,
            "version": 1,
        }
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                FundingCarryFeaturePolicy(**{**baseline, **change})

    def test_economic_policy_rejects_invalid_bounds(self) -> None:
        baseline = {
            "target_base_quantity": Quantity.from_str("1"),
            "minimum_entry_net_rate": 0.001,
            "maximum_entry_abs_basis_rate": 0.02,
            "exit_net_rate": 0.0001,
            "hedge_tolerance_base_quantity": Quantity.from_str("0.001"),
            "basket_validity_ns": DurationNanos(1_000),
            "version": 1,
        }
        invalid = (
            {"target_base_quantity": Quantity.from_str("0")},
            {"minimum_entry_net_rate": nan},
            {"maximum_entry_abs_basis_rate": nan},
            {"exit_net_rate": nan},
            {"minimum_entry_net_rate": 0.0001},
            {"maximum_entry_abs_basis_rate": -0.1},
            {"hedge_tolerance_base_quantity": Quantity.from_str("-0.1")},
            {"basket_validity_ns": DurationNanos(0)},
            {
                "basket_validity_ns": DurationNanos(
                    MAX_BASKET_VALIDITY_NS + 1
                )
            },
            {"version": 0},
        )
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                FundingCarryEconomicPolicy(**{**baseline, **change})


class FundingCarryContractValidationTests(TestCase):
    def test_pair_contract_rejects_invalid_persisted_shapes(self) -> None:
        configured = pair()
        invalid = (
            {"pair_id": ""},
            {
                "spot_instrument_id": replace(
                    configured.spot_instrument_id,
                    kind=InstrumentKind.PERPETUAL,
                )
            },
            {
                "perpetual_instrument_id": replace(
                    configured.perpetual_instrument_id,
                    kind=InstrumentKind.SPOT,
                )
            },
            {"spot_base_units_per_quantity": Quantity.from_str("0")},
            {"perpetual_base_units_per_quantity": Quantity.from_str("0")},
            {"quantity_conversion_policy_ref": ""},
            {"quantity_conversion_policy_ref": "x" * 129},
            {"schema_version": 0},
        )
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(configured, **change)

    def test_pair_factory_and_exact_conversion_reject_unsupported_models(
        self,
    ) -> None:
        spot, perpetual = instruments()
        with self.assertRaisesRegex(ValueError, "spot instrument"):
            create_funding_carry_pair(
                underlying_asset_id=AssetId("BTC"),
                spot_account_id=AccountId("spot"),
                spot_instrument=perpetual,
                perpetual_account_id=AccountId("perp"),
                perpetual_instrument=perpetual,
                quantity_conversion_policy_ref="linear@1",
            )
        with self.assertRaisesRegex(ValueError, "derivative"):
            create_funding_carry_pair(
                underlying_asset_id=AssetId("BTC"),
                spot_account_id=AccountId("spot"),
                spot_instrument=spot,
                perpetual_account_id=AccountId("perp"),
                perpetual_instrument=spot,
                quantity_conversion_policy_ref="linear@1",
            )
        wrong_contract_asset = replace(
            perpetual,
            specification=PerpetualSpecification(
                settlement_asset=AssetId("USDT"),
                margin_asset=AssetId("USDT"),
                contract_size=Quantity.from_str("1"),
                contract_size_asset=AssetId("ETH"),
                value_type=ContractValueType.LINEAR,
            ),
        )
        with self.assertRaisesRegex(ValueError, "contract size"):
            create_funding_carry_pair(
                underlying_asset_id=AssetId("BTC"),
                spot_account_id=AccountId("spot"),
                spot_instrument=spot,
                perpetual_account_id=AccountId("perp"),
                perpetual_instrument=wrong_contract_asset,
                quantity_conversion_policy_ref="linear@1",
            )
        with self.assertRaisesRegex(ValueError, "multiplier"):
            base_to_instrument_quantity(
                Quantity.from_str("1"),
                base_units_per_quantity=Quantity.from_str("0"),
            )
        with self.assertRaisesRegex(ValueError, "exact decimal"):
            base_to_instrument_quantity(
                Quantity.from_str("1"),
                base_units_per_quantity=Quantity.from_str("3"),
            )
        self.assertEqual(
            quantity_to_base(
                Quantity.from_str("-2"),
                base_units_per_quantity=Quantity.from_str("0.5"),
            ),
            Quantity.from_str("-1.0"),
        )


class FundingFeatureValidationTests(TestCase):
    def test_feature_input_rejects_mismatched_or_non_live_sources(self) -> None:
        configured_pair = pair()
        spot, perpetual, _, _, funding = _markets()
        changes = (
            {
                "spot_market": replace(
                    spot,
                    instrument_id=configured_pair.perpetual_instrument_id,
                )
            },
            {
                "perpetual_market": replace(
                    perpetual,
                    instrument_id=configured_pair.spot_instrument_id,
                )
            },
            {
                "funding": replace(
                    funding,
                    instrument_id=configured_pair.spot_instrument_id,
                )
            },
            {
                "spot_market": replace(
                    spot,
                    status=MarketStateStatus.EMPTY,
                )
            },
        )
        baseline = {
            "metadata": _metadata(),
            "pair": configured_pair,
            "spot_market": spot,
            "perpetual_market": perpetual,
            "funding": funding,
        }
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                FundingCarryFeatureInput(**{**baseline, **change})

    def test_required_feature_quality_expiry_and_calculator_type(self) -> None:
        snapshot = feature_snapshot()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            require_funding_carry_features(
                FeatureSnapshot(scope=SCOPE, values=()),
                decision_time_ns=1_000,
            )
        degraded = replace(snapshot.values[0], quality=FeatureQuality.DEGRADED)
        with self.assertRaisesRegex(ValueError, "quality"):
            require_funding_carry_features(
                replace(snapshot, values=(degraded, *snapshot.values[1:])),
                decision_time_ns=1_000,
            )
        expired_metadata = replace(
            snapshot.values[0].metadata,
            valid_until_ns=UnixNanos(1_050),
        )
        expired = replace(snapshot.values[0], metadata=expired_metadata)
        with self.assertRaisesRegex(ValueError, "expired"):
            require_funding_carry_features(
                replace(snapshot, values=(expired, *snapshot.values[1:])),
                decision_time_ns=1_100,
            )
        with self.assertRaisesRegex(ValueError, "missing"):
            funding_feature_value(
                FeatureSnapshot(scope=SCOPE, values=()),
                snapshot.values[0].metadata.ref,
            )
        calculator = funding_carry_feature_definitions(
            FundingCarryFeaturePolicy(
                estimated_round_trip_cost_rate=0.001,
                funding_periods_per_year=1_095,
                version=1,
            )
        )[0].calculator
        with self.assertRaises(TypeError):
            calculator(
                FeatureContext(
                    event=object(),
                    dependencies={},
                    previous=None,
                )
            )


class FundingCarrySnapshotValidationTests(TestCase):
    def test_source_and_mode_contracts_reject_ambiguous_shapes(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            replace(SOURCES, features=SOURCES.funding)
        with self.assertRaisesRegex(ValueError, "cannot configure"):
            FundingCarrySnapshotAssembler(
                pair=pair(),
                source_ids=POSITION_SOURCES,
                kind=FundingCarrySnapshotKind.ENTRY,
            )
        with self.assertRaisesRegex(ValueError, "requires control"):
            FundingCarrySnapshotAssembler(
                pair=pair(),
                source_ids=SOURCES,
                kind=FundingCarrySnapshotKind.POSITION,
            )

    def test_portfolio_contract_rejects_order_duplicate_and_readiness(self) -> None:
        inputs = portfolio()
        with self.assertRaisesRegex(ValueError, "account ordered"):
            replace(inputs, positions=tuple(reversed(inputs.positions)))
        with self.assertRaisesRegex(ValueError, "unique"):
            replace(inputs, positions=(inputs.positions[0], inputs.positions[0]))
        with self.assertRaisesRegex(ValueError, "READY"):
            replace(
                inputs,
                positions=(
                    replace(
                        inputs.positions[0],
                        readiness=inputs.positions[0].readiness.UNRECONCILED,
                        reason="not ready",
                    ),
                    inputs.positions[1],
                ),
            )
        second_margin = replace(
            inputs.margins[0],
            scope_id=MarginScopeId("another-margin"),
        )
        with self.assertRaisesRegex(ValueError, "scope ordered"):
            FundingCarryPortfolioInputs(
                positions=inputs.positions,
                margins=(inputs.margins[0], second_margin),
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            replace(inputs, margins=(inputs.margins[0], inputs.margins[0]))

    def test_assembler_rejects_missing_type_scope_and_semantic_mismatch(
        self,
    ) -> None:
        assembler = FundingCarrySnapshotAssembler(
            pair=pair(),
            source_ids=SOURCES,
            kind=FundingCarrySnapshotKind.ENTRY,
        )
        observations = entry_observations()
        metadata = _snapshot_metadata(observations)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            assembler.build(
                observations=observations[:-1],
                metadata=metadata,
            )
        wrong_type = (
            replace(observations[0], value=object()),
            *observations[1:],
        )
        with self.assertRaises(TypeError):
            assembler.build(observations=wrong_type, metadata=metadata)
        wrong_scope = list(observations)
        wrong_scope[-1] = replace(
            wrong_scope[-1],
            value=feature_snapshot(scope="another-scope"),
        )
        with self.assertRaisesRegex(ValueError, "Feature scope"):
            assembler.build(
                observations=tuple(wrong_scope),
                metadata=metadata,
            )
        missing_account = list(observations)
        missing_account[-2] = replace(
            missing_account[-2],
            value=replace(
                portfolio(),
                positions=(portfolio().positions[0],),
            ),
        )
        with self.assertRaisesRegex(ValueError, "scope is incomplete"):
            assembler.build(
                observations=tuple(missing_account),
                metadata=metadata,
            )
        missing_margin = list(observations)
        missing_margin[-2] = replace(
            missing_margin[-2],
            value=replace(portfolio(), margins=()),
        )
        with self.assertRaisesRegex(ValueError, "margin"):
            assembler.build(
                observations=tuple(missing_margin),
                metadata=metadata,
            )


class CarryProjectionValidationTests(TestCase):
    def test_hedge_recovery_and_financial_contract_negative_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            CarryHedgeAssessment(
                state=CarryHedgeState.HEDGED,
                signed_residual_base_quantity=Quantity.from_str("0"),
                assessed_at_ns=UnixNanos(-1),
                policy_version=1,
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            CarryHedgeAssessment(
                state=CarryHedgeState.HEDGED,
                signed_residual_base_quantity=Quantity.from_str("0"),
                assessed_at_ns=UnixNanos(1),
                policy_version=0,
            )
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            CarryHedgeAssessment(
                state=CarryHedgeState.UNKNOWN,
                signed_residual_base_quantity=Quantity.from_str("0"),
                assessed_at_ns=UnixNanos(1),
                policy_version=1,
                reason="unknown",
            )
        with self.assertRaisesRegex(ValueError, "requires a reason"):
            CarryHedgeAssessment(
                state=CarryHedgeState.UNKNOWN,
                signed_residual_base_quantity=None,
                assessed_at_ns=UnixNanos(1),
                policy_version=1,
            )
        with self.assertRaisesRegex(ValueError, "requires a residual"):
            CarryHedgeAssessment(
                state=CarryHedgeState.HEDGED,
                signed_residual_base_quantity=None,
                assessed_at_ns=UnixNanos(1),
                policy_version=1,
            )
        with self.assertRaises(ValueError):
            CarryRecoveryProposal(
                application_position_id="",
                kind=CarryRecoveryKind.WAIT_FOR_FACT_RECONCILIATION,
                source_snapshot_id=DecisionSnapshotId("snapshot"),
                proposed_target=None,
                proposed_at_ns=UnixNanos(1),
                policy_version=1,
                reason="wait",
            )
        ledger = _ledger()
        self.assertEqual(
            assess_carry_financial_state(
                attribution=None,
                source_proofs=(),
                balance_proofs=(),
                allocation_ids=(),
                ledger=ledger,
            ),
            CarryFinancialState.NOT_READY,
        )


def _markets():
    from carry_test_support import markets

    return markets()


def _metadata():
    from carry_test_support import metadata

    return metadata("validation-feature")


def _snapshot_metadata(observations):
    return DecisionSnapshotMetadata(
        snapshot_id=DecisionSnapshotId("validation-snapshot"),
        scope=SCOPE,
        snapshot_sequence=1,
        assembled_at_ns=UnixNanos(1_100),
        assembled_at_monotonic_ns=200,
        policy_version=1,
        observation_ids=tuple(item.observation_id for item in observations),
        coherence=(),
    )


def _ledger():
    from cex_quant.accounting import AccountingLedgerView

    return AccountingLedgerView(
        fact_count=0,
        observation_count=0,
        transactions=(),
        balances=(),
        ledger_sequence=0,
        healthy=True,
        error_type=None,
        error_message=None,
    )


if __name__ == "__main__":
    import unittest

    unittest.main()
