import unittest
from dataclasses import replace

from cex_quant.accounting import EconomicOwnerRef, EconomicOwnerTypeRef
from cex_quant.accounting.valuation import (
    ConversionQuoteConvention,
    ConversionRateEvidence,
    ConversionTimeBasis,
    PositionValueInput,
    ValuationCompleteness,
    ValuationPolicyRef,
    ValuationRoundingMode,
    build_valuation_snapshot,
    value_amount,
)
from cex_quant.core import AssetId, Money, PositionId, Rate, UnixNanos
from cex_quant.snapshots import DecisionSnapshotId

SNAPSHOT_ID = DecisionSnapshotId("valuation-1")
OWNER = EconomicOwnerRef(
    owner_type=EconomicOwnerTypeRef(name="application.position", version=1),
    owner_id="carry-1",
)


def policy() -> ValuationPolicyRef:
    return ValuationPolicyRef(
        name="reporting.standard",
        version=1,
        reporting_asset=AssetId("USD"),
        allowed_source_ids=("official-btc-usd", "official-usdt-usd"),
        path_priority=(
            (AssetId("BTC"), AssetId("USD")),
            (AssetId("BTC"), AssetId("USDT"), AssetId("USD")),
            (AssetId("USDT"), AssetId("USD")),
        ),
        maximum_age_ns=100,
        maximum_coherence_ns=10,
        maximum_hops=2,
        output_scale=2,
        rounding_mode=ValuationRoundingMode.HALF_EVEN,
        time_basis=ConversionTimeBasis.SNAPSHOT_TIME,
    )


def rate(
    *,
    path: tuple[AssetId, ...],
    hop: int,
    value: str,
    source_id: str,
    as_of_ns: int = 950,
) -> ConversionRateEvidence:
    return ConversionRateEvidence(
        valuation_snapshot_id=SNAPSHOT_ID,
        policy_version=1,
        source_asset=path[hop],
        destination_asset=path[hop + 1],
        rate=Rate.from_str(value),
        quote_convention=ConversionQuoteConvention.DESTINATION_PER_SOURCE,
        source_id=source_id,
        source_as_of_ns=UnixNanos(as_of_ns),
        observed_at_ns=UnixNanos(960),
        path=path,
        hop_index=hop,
    )


class AccountingValuationTests(unittest.TestCase):
    def test_policy_and_conversion_evidence_validation_fail_closed(self) -> None:
        selected = policy()
        invalid_policies = (
            lambda: replace(selected, name="BAD"),
            lambda: replace(selected, version=0),
            lambda: replace(
                selected,
                allowed_source_ids=("z-source", "a-source"),
            ),
            lambda: replace(selected, allowed_source_ids=("",)),
            lambda: replace(selected, maximum_age_ns=-1),
            lambda: replace(selected, maximum_hops=0),
            lambda: replace(selected, output_scale=19),
            lambda: replace(
                selected,
                path_priority=(
                    (AssetId("BTC"), AssetId("USD")),
                    (AssetId("BTC"), AssetId("USD")),
                ),
            ),
            lambda: replace(
                selected,
                path_priority=((AssetId("BTC"),),),
            ),
            lambda: replace(
                selected,
                path_priority=((AssetId("BTC"), AssetId("USDT")),),
            ),
            lambda: replace(
                selected,
                path_priority=(
                    (
                        AssetId("BTC"),
                        AssetId("USDT"),
                        AssetId("BTC"),
                        AssetId("USD"),
                    ),
                ),
                maximum_hops=3,
            ),
        )
        for case in invalid_policies:
            with self.subTest(case=case), self.assertRaises(ValueError):
                case()

        direct = (AssetId("BTC"), AssetId("USD"))
        valid_rate = rate(
            path=direct,
            hop=0,
            value="60000",
            source_id="official-btc-usd",
        )
        invalid_rates = (
            lambda: replace(valid_rate, policy_version=0),
            lambda: replace(
                valid_rate,
                destination_asset=AssetId("BTC"),
            ),
            lambda: replace(valid_rate, rate=Rate.from_str("0")),
            lambda: replace(valid_rate, source_as_of_ns=UnixNanos(-1)),
            lambda: replace(valid_rate, observed_at_ns=UnixNanos(900)),
            lambda: replace(valid_rate, hop_index=-1),
        )
        for case in invalid_rates:
            with self.subTest(case=case), self.assertRaises(ValueError):
                case()

    def test_declared_direct_path_wins_over_triangular_path(self) -> None:
        direct = (AssetId("BTC"), AssetId("USD"))
        triangular = (
            AssetId("BTC"),
            AssetId("USDT"),
            AssetId("USD"),
        )
        evidence = (
            rate(
                path=direct,
                hop=0,
                value="60000",
                source_id="official-btc-usd",
            ),
            rate(
                path=triangular,
                hop=0,
                value="61000",
                source_id="official-btc-usd",
            ),
            rate(
                path=triangular,
                hop=1,
                value="1",
                source_id="official-usdt-usd",
            ),
        )

        valued = value_amount(
            original_asset=AssetId("BTC"),
            original_amount=Money.from_str("0.5"),
            valuation_snapshot_id=SNAPSHOT_ID,
            reference_time_ns=UnixNanos(1_000),
            policy=policy(),
            evidence=evidence,
        )

        self.assertEqual(valued.reporting_amount, Money.from_str("30000.00"))
        self.assertEqual(valued.evidence, (evidence[0],))

    def test_missing_or_stale_evidence_is_incomplete_not_zero(self) -> None:
        direct = (AssetId("BTC"), AssetId("USD"))
        valued = value_amount(
            original_asset=AssetId("BTC"),
            original_amount=Money.from_str("1"),
            valuation_snapshot_id=SNAPSHOT_ID,
            reference_time_ns=UnixNanos(1_000),
            policy=policy(),
            evidence=(
                rate(
                    path=direct,
                    hop=0,
                    value="60000",
                    source_id="official-btc-usd",
                    as_of_ns=800,
                ),
            ),
        )

        self.assertIsNone(valued.reporting_amount)
        self.assertEqual(
            valued.completeness,
            ValuationCompleteness.INCOMPLETE,
        )

    def test_snapshot_total_is_withheld_when_any_position_is_incomplete(self) -> None:
        usdt_path = (AssetId("USDT"), AssetId("USD"))
        snapshot = build_valuation_snapshot(
            valuation_snapshot_id=SNAPSHOT_ID,
            as_of_ns=UnixNanos(1_000),
            positions=(
                PositionValueInput(
                    position_id=PositionId("position-usdt"),
                    owner=OWNER,
                    original_asset=AssetId("USDT"),
                    unrealized_value=Money.from_str("10"),
                ),
                PositionValueInput(
                    position_id=PositionId("position-btc"),
                    owner=OWNER,
                    original_asset=AssetId("BTC"),
                    unrealized_value=Money.from_str("0.1"),
                ),
            ),
            policy=policy(),
            evidence=(
                rate(
                    path=usdt_path,
                    hop=0,
                    value="0.999",
                    source_id="official-usdt-usd",
                ),
            ),
        )

        self.assertIsNone(snapshot.unrealized_pnl)
        self.assertEqual(
            snapshot.completeness,
            ValuationCompleteness.INCOMPLETE,
        )
        self.assertEqual(
            snapshot.position_values[0].reporting_value,
            Money.from_str("9.99"),
        )


if __name__ == "__main__":
    unittest.main()
