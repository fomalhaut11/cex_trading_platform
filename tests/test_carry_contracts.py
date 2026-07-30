from dataclasses import FrozenInstanceError, replace
from unittest import TestCase

from cex_quant.applications.carry import (
    APPLICATION_POSITION_OWNER_TYPE,
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
    CarryPositionView,
    accounting_owner_for_position,
    create_carry_leg_ownership,
    deterministic_application_position_id,
)
from cex_quant.applications.carry.funding_arbitrage import (
    create_funding_carry_pair,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import (
    ContractValueType,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.snapshots import DecisionSnapshotId

BTC = AssetId("BTC")


def instruments(
    *,
    perpetual_base: AssetId = BTC,
    value_type: ContractValueType = ContractValueType.LINEAR,
) -> tuple[Instrument, Instrument]:
    spot = Instrument(
        instrument_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=InstrumentKind.SPOT,
            symbol="BTCUSDT",
        ),
        base_asset=AssetId("BTC"),
        quote_asset=AssetId("USDT"),
        price_increment=_price("0.01"),
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
        base_asset=perpetual_base,
        quote_asset=AssetId("USDT"),
        price_increment=_price("0.01"),
        quantity_increment=Quantity.from_str("0.001"),
        status=InstrumentStatus.ACTIVE,
        specification=PerpetualSpecification(
            settlement_asset=AssetId("USDT"),
            margin_asset=AssetId("USDT"),
            contract_size=Quantity.from_str("1"),
            contract_size_asset=perpetual_base,
            value_type=value_type,
        ),
    )
    return spot, perpetual


def pair():
    spot, perpetual = instruments()
    return create_funding_carry_pair(
        underlying_asset_id=AssetId("BTC"),
        spot_account_id=AccountId("spot-account"),
        spot_instrument=spot,
        perpetual_account_id=AccountId("perp-account"),
        perpetual_instrument=perpetual,
        quantity_conversion_policy_ref="linear-base-quantity@1",
    )


def _price(value: str):
    from cex_quant.core import Price

    return Price.from_str(value)


class CarryContractTests(TestCase):
    def test_pair_is_metadata_validated_and_identity_is_replay_stable(
        self,
    ) -> None:
        first = pair()
        second = pair()

        self.assertEqual(first, second)
        self.assertEqual(first.spot_base_units_per_quantity, Quantity.from_str("1"))
        self.assertEqual(
            first.perpetual_base_units_per_quantity,
            Quantity.from_str("1"),
        )
        with self.assertRaises(FrozenInstanceError):
            first.schema_version = 2  # type: ignore[misc]

    def test_pair_rejects_symbol_similarity_without_underlying_proof(
        self,
    ) -> None:
        spot, wrong_underlying = instruments(perpetual_base=AssetId("ETH"))
        with self.assertRaisesRegex(ValueError, "different underlying"):
            create_funding_carry_pair(
                underlying_asset_id=AssetId("BTC"),
                spot_account_id=AccountId("spot-account"),
                spot_instrument=spot,
                perpetual_account_id=AccountId("perp-account"),
                perpetual_instrument=wrong_underlying,
                quantity_conversion_policy_ref="linear-base-quantity@1",
            )
        _, inverse = instruments(value_type=ContractValueType.INVERSE)
        with self.assertRaisesRegex(ValueError, "linear"):
            create_funding_carry_pair(
                underlying_asset_id=AssetId("BTC"),
                spot_account_id=AccountId("spot-account"),
                spot_instrument=spot,
                perpetual_account_id=AccountId("perp-account"),
                perpetual_instrument=inverse,
                quantity_conversion_policy_ref="linear-base-quantity@1",
            )

    def test_position_identity_ownership_and_accounting_mapping(self) -> None:
        configured_pair = pair()
        opening_snapshot_id = DecisionSnapshotId("snapshot-open")
        position_id = deterministic_application_position_id(
            strategy_id=StrategyId("carry-btc"),
            pair_id=configured_pair.pair_id,
            opening_snapshot_id=opening_snapshot_id,
        )
        ownership = tuple(
            create_carry_leg_ownership(
                application_position_id=position_id,
                account_id=account_id,
                instrument_id=instrument_id,
                baseline_quantity=Quantity.from_str("0"),
                intended_owned_delta=Quantity.from_str(delta),
                effective_from_ns=UnixNanos(1_000),
                source_snapshot_id=opening_snapshot_id,
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
        view = CarryPositionView(
            application_position_id=position_id,
            strategy_id=StrategyId("carry-btc"),
            pair_id=configured_pair.pair_id,
            revision=1,
            lifecycle=CarryLifecycle.PROPOSED,
            hedge_state=CarryHedgeState.UNKNOWN,
            financial_state=CarryFinancialState.NOT_READY,
            opening_snapshot_id=opening_snapshot_id,
            latest_snapshot_id=opening_snapshot_id,
            intent_ids=(),
            order_group_ids=(),
            leg_ownership=ownership,
            last_transition_ns=UnixNanos(1_000),
        )

        self.assertEqual(
            ownership[0].absolute_target,
            Quantity.from_str("10"),
        )
        owner = accounting_owner_for_position(position_id)
        self.assertEqual(owner.owner_type, APPLICATION_POSITION_OWNER_TYPE)
        self.assertEqual(owner.owner_id, str(position_id))
        self.assertEqual(view.leg_ownership, ownership)

    def test_lifecycle_contract_keeps_hedge_and_recovery_orthogonal(
        self,
    ) -> None:
        configured_pair = pair()
        snapshot_id = DecisionSnapshotId("snapshot-open")
        position_id = deterministic_application_position_id(
            strategy_id=StrategyId("carry-btc"),
            pair_id=configured_pair.pair_id,
            opening_snapshot_id=snapshot_id,
        )
        ownership = (
            create_carry_leg_ownership(
                application_position_id=position_id,
                account_id=configured_pair.spot_account_id,
                instrument_id=configured_pair.spot_instrument_id,
                baseline_quantity=Quantity.from_str("0"),
                intended_owned_delta=Quantity.from_str("10"),
                effective_from_ns=UnixNanos(1_000),
                source_snapshot_id=snapshot_id,
                policy_version=1,
            ),
        )
        base = CarryPositionView(
            application_position_id=position_id,
            strategy_id=StrategyId("carry-btc"),
            pair_id=configured_pair.pair_id,
            revision=1,
            lifecycle=CarryLifecycle.OPENING,
            hedge_state=CarryHedgeState.UNHEDGED,
            financial_state=CarryFinancialState.PROVISIONAL,
            opening_snapshot_id=snapshot_id,
            latest_snapshot_id=snapshot_id,
            intent_ids=(),
            order_group_ids=(),
            leg_ownership=ownership,
            last_transition_ns=UnixNanos(1_000),
        )

        with self.assertRaisesRegex(ValueError, "must be HEDGED"):
            replace(base, lifecycle=CarryLifecycle.ACTIVE)
        with self.assertRaisesRegex(ValueError, "needs a reason"):
            replace(base, lifecycle=CarryLifecycle.RECOVERY_REQUIRED)
        recovered = replace(
            base,
            lifecycle=CarryLifecycle.RECOVERY_REQUIRED,
            recovery_reason="child outcome unknown",
        )
        self.assertEqual(
            recovered.lifecycle,
            CarryLifecycle.RECOVERY_REQUIRED,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
