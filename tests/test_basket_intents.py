import json
from dataclasses import FrozenInstanceError, replace
from unittest import TestCase

from cex_quant.core import (
    AccountId,
    BasketLegId,
    DurationNanos,
    ObjectiveTypeId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    MAX_BASKET_VALIDITY_NS,
    MAX_ENCODED_BASKET_BYTES,
    BasketIntentPolicy,
    BasketIntentPolicyError,
    BasketTargetIntent,
    BasketTargetLeg,
    ObjectiveTypeDefinition,
    ObjectiveTypeRef,
    ObjectiveTypeRegistrationError,
    ObjectiveTypeRegistry,
    basket_target_intent_checksum,
    create_basket_target_intent,
    decode_basket_target_intent,
    deterministic_basket_leg_id,
    encode_basket_target_intent,
)

SNAPSHOT_ID = DecisionSnapshotId("snapshot-27")
STRATEGY_ID = StrategyId("carry")
OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding"),
    version=1,
)
ACCOUNT_ID = AccountId("primary")


def instrument(kind: InstrumentKind, symbol: str) -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=kind,
        symbol=symbol,
    )


def leg(
    kind: InstrumentKind,
    symbol: str,
    target: str,
    *,
    account_id: AccountId = ACCOUNT_ID,
) -> BasketTargetLeg:
    instrument_id = instrument(kind, symbol)
    return BasketTargetLeg(
        leg_id=deterministic_basket_leg_id(
            decision_snapshot_id=SNAPSHOT_ID,
            account_id=account_id,
            instrument_id=instrument_id,
        ),
        account_id=account_id,
        instrument_id=instrument_id,
        target_quantity=Quantity.from_str(target),
    )


def basket(
    legs: tuple[BasketTargetLeg, ...],
    *,
    objective: ObjectiveTypeRef = OBJECTIVE,
) -> BasketTargetIntent:
    return create_basket_target_intent(
        strategy_id=STRATEGY_ID,
        decision_snapshot_id=SNAPSHOT_ID,
        objective=objective,
        legs=legs,
        decision_time_ns=UnixNanos(1_000),
        valid_until_ns=UnixNanos(2_000),
        policy_version=1,
        reason="portfolio target",
    )


class BasketIntentTests(TestCase):
    def test_two_leg_target_is_canonical_and_replay_stable(self) -> None:
        spot = leg(InstrumentKind.SPOT, "BTCUSDT", "10")
        perp = leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10")

        first = basket((spot, perp))
        replay = basket((perp, spot))

        self.assertEqual(first, replay)
        self.assertEqual(
            tuple(item.instrument_id.kind for item in first.legs),
            (InstrumentKind.PERPETUAL, InstrumentKind.SPOT),
        )
        self.assertEqual(
            tuple(item.target_quantity for item in first.legs),
            (Quantity.from_str("-10"), Quantity.from_str("10")),
        )

    def test_three_leg_option_spread_and_delta_hedge_is_supported(
        self,
    ) -> None:
        result = basket(
            (
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-0.35"),
                leg(InstrumentKind.OPTION, "BTC-30000-C", "10"),
                leg(InstrumentKind.OPTION, "BTC-35000-C", "-10"),
            )
        )

        self.assertEqual(len(result.legs), 3)
        self.assertEqual(
            {item.instrument_id.kind for item in result.legs},
            {InstrumentKind.OPTION, InstrumentKind.PERPETUAL},
        )

    def test_contract_is_immutable_and_rejects_invalid_shapes(self) -> None:
        result = basket(
            (
                leg(InstrumentKind.SPOT, "BTCUSDT", "10"),
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10"),
            )
        )
        with self.assertRaises(FrozenInstanceError):
            result.reason = "changed"  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "2 to 16"):
            replace(result, legs=(result.legs[0],))
        with self.assertRaisesRegex(ValueError, "canonical"):
            replace(result, legs=tuple(reversed(result.legs)))
        with self.assertRaisesRegex(ValueError, "scopes must be unique"):
            replace(
                result,
                legs=(
                    result.legs[0],
                    replace(
                        result.legs[0],
                        leg_id=BasketLegId("duplicate-scope"),
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            replace(result, decision_time_ns=UnixNanos(-1))
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            replace(result, valid_until_ns=UnixNanos(999))

    def test_content_change_changes_deterministic_intent_id(self) -> None:
        original = basket(
            (
                leg(InstrumentKind.SPOT, "BTCUSDT", "10"),
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10"),
            )
        )
        changed = basket(
            (
                leg(InstrumentKind.SPOT, "BTCUSDT", "11"),
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10"),
            )
        )

        self.assertNotEqual(original.intent_id, changed.intent_id)

    def test_same_instrument_across_accounts_and_zero_target_are_valid(
        self,
    ) -> None:
        close_primary = leg(
            InstrumentKind.PERPETUAL,
            "BTCUSDT",
            "0",
            account_id=AccountId("primary"),
        )
        hedge_secondary = leg(
            InstrumentKind.PERPETUAL,
            "BTCUSDT",
            "-1.2500",
            account_id=AccountId("secondary"),
        )

        result = basket((hedge_secondary, close_primary))

        self.assertEqual(result.legs[0].target_quantity, Quantity(raw=0, scale=0))
        self.assertEqual(
            result.legs[1].target_quantity,
            Quantity(raw=-12_500, scale=4),
        )

    def test_hard_and_deployment_bounds_are_enforced(self) -> None:
        too_many = tuple(
            leg(
                InstrumentKind.OPTION,
                f"BTC-{index}-C",
                "1",
            )
            for index in range(17)
        )
        with self.assertRaisesRegex(ValueError, "2 to 16"):
            basket(too_many)

        three_legs = basket(
            (
                leg(InstrumentKind.OPTION, "BTC-30000-C", "1"),
                leg(InstrumentKind.OPTION, "BTC-35000-C", "-1"),
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "0"),
            )
        )
        registry = ObjectiveTypeRegistry(
            (
                ObjectiveTypeDefinition(
                    ref=OBJECTIVE,
                    owner="applications.carry",
                ),
            )
        )
        with self.assertRaises(BasketIntentPolicyError):
            BasketIntentPolicy(
                max_legs=2,
                max_validity_ns=DurationNanos(1_000),
                allowed_objectives=(OBJECTIVE,),
            ).validate(three_legs, registry=registry)
        with self.assertRaisesRegex(ValueError, "hard safety"):
            replace(
                three_legs,
                valid_until_ns=UnixNanos(
                    1_000 + MAX_BASKET_VALIDITY_NS + 1
                ),
            )

    def test_codec_is_deterministic_bounded_and_detects_mutation(
        self,
    ) -> None:
        result = basket(
            (
                leg(InstrumentKind.SPOT, "BTCUSDT", "10.000"),
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10.000"),
            )
        )

        encoded = encode_basket_target_intent(result)
        replay = encode_basket_target_intent(result)

        self.assertEqual(encoded, replay)
        self.assertEqual(decode_basket_target_intent(encoded), result)
        self.assertEqual(
            basket_target_intent_checksum(result),
            json.loads(encoded)["checksum"],
        )

        mutated = json.loads(encoded)
        mutated["payload"]["reason"] = "tampered"
        with self.assertRaisesRegex(ArithmeticError, "checksum mismatch"):
            decode_basket_target_intent(
                json.dumps(
                    mutated,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            )
        with self.assertRaisesRegex(ValueError, "outside limits"):
            decode_basket_target_intent(
                b"x" * (MAX_ENCODED_BASKET_BYTES + 1)
            )
        with self.assertRaisesRegex(ValueError, "UTF-8 JSON"):
            decode_basket_target_intent(b"{")

    def test_objective_registry_is_metadata_only_and_versioned(self) -> None:
        v2 = ObjectiveTypeRef(
            objective_type_id=ObjectiveTypeId("carry.funding"),
            version=2,
        )
        definitions = (
            ObjectiveTypeDefinition(
                ref=OBJECTIVE,
                owner="applications.carry",
            ),
            ObjectiveTypeDefinition(
                ref=v2,
                owner="applications.carry",
                deprecated=True,
            ),
        )
        registry = ObjectiveTypeRegistry(definitions)

        self.assertTrue(registry.contains(OBJECTIVE))
        self.assertEqual(registry.require(v2), definitions[1])
        with self.assertRaises(FrozenInstanceError):
            registry._definitions = ()  # type: ignore[misc]
        with self.assertRaises(ObjectiveTypeRegistrationError):
            ObjectiveTypeRegistry(tuple(reversed(definitions)))
        with self.assertRaises(ObjectiveTypeRegistrationError):
            registry.require(
                ObjectiveTypeRef(
                    objective_type_id=ObjectiveTypeId("options.spread"),
                    version=1,
                )
            )
        with self.assertRaisesRegex(ValueError, "lowercase ASCII"):
            ObjectiveTypeRef(
                objective_type_id=ObjectiveTypeId("Carry.Funding"),
                version=1,
            )

    def test_policy_admits_registered_bounded_objective(self) -> None:
        registry = ObjectiveTypeRegistry(
            (
                ObjectiveTypeDefinition(
                    ref=OBJECTIVE,
                    owner="applications.carry",
                ),
            )
        )
        policy = BasketIntentPolicy(
            max_legs=3,
            max_validity_ns=DurationNanos(1_000),
            allowed_objectives=(OBJECTIVE,),
        )
        result = basket(
            (
                leg(InstrumentKind.SPOT, "BTCUSDT", "10"),
                leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10"),
            )
        )

        policy.validate(result, registry=registry)
        with self.assertRaises(BasketIntentPolicyError):
            replace(
                policy,
                max_validity_ns=DurationNanos(999),
            ).validate(result, registry=registry)
