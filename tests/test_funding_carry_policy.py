from dataclasses import replace
from unittest import TestCase

from carry_test_support import (
    SCOPE,
    SOURCES,
    STRATEGY_ID,
    entry_observations,
    feature_snapshot,
    pair,
)

from cex_quant.applications.carry.funding_arbitrage import (
    FUNDING_OPEN_OBJECTIVE,
    FundingCarryEconomicPolicy,
    FundingCarryEntrySnapshot,
    FundingCarrySnapshotAssembler,
    FundingCarrySnapshotKind,
    FundingCarryStrategy,
    funding_objective_registry,
)
from cex_quant.applications.carry.funding_arbitrage.features import (
    BASIS_RATE,
    EXPECTED_NET_CARRY_APR,
    EXPECTED_NET_CARRY_RATE,
)
from cex_quant.core import DurationNanos, Quantity, UnixNanos
from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    SnapshotCoordinator,
    SnapshotCoordinatorFailedError,
)
from cex_quant.snapshots import (
    CoherenceGroup,
    CoherenceGroupId,
    SnapshotIssueCode,
    SnapshotPolicy,
    SnapshotReadiness,
    SourceFreshnessRule,
)
from cex_quant.strategy import BasketIntentPolicy, StrategyRuntime


def snapshot_policy() -> SnapshotPolicy:
    return SnapshotPolicy(
        source_rules=tuple(
            SourceFreshnessRule(
                source_id=source_id,
                max_event_age_ns=DurationNanos(500),
                max_arrival_age_ns=DurationNanos(500),
                max_future_skew_ns=DurationNanos(10),
            )
            for source_id in SOURCES.required
        ),
        coherence_groups=(
            CoherenceGroup(
                group_id=CoherenceGroupId("carry-market"),
                source_ids=(
                    SOURCES.spot_market,
                    SOURCES.perpetual_market,
                    SOURCES.mark_price,
                    SOURCES.index_price,
                    SOURCES.funding,
                ),
                max_event_time_skew_ns=DurationNanos(20),
            ),
        ),
        policy_version=1,
    )


def coordinator() -> SnapshotCoordinator[FundingCarryEntrySnapshot]:
    return SnapshotCoordinator(
        scope=SCOPE,
        policy=snapshot_policy(),
        assembler=FundingCarrySnapshotAssembler(
            pair=pair(),
            source_ids=SOURCES,
            kind=FundingCarrySnapshotKind.ENTRY,
        ),
    )


def economic_policy() -> FundingCarryEconomicPolicy:
    return FundingCarryEconomicPolicy(
        target_base_quantity=Quantity.from_str("10"),
        minimum_entry_net_rate=0.0005,
        maximum_entry_abs_basis_rate=0.02,
        exit_net_rate=0.0001,
        hedge_tolerance_base_quantity=Quantity.from_str("0.001"),
        basket_validity_ns=DurationNanos(1_000),
        version=1,
    )


def publish(*, funding_rate: str = "0.0010"):
    target = coordinator()
    for item in entry_observations(funding_rate=funding_rate):
        target.accept(item)
    return target.evaluate(
        now_ns=UnixNanos(1_100),
        now_monotonic_ns=200,
        clock_status=HealthStatus.HEALTHY,
    ).publication


class FundingCarryFeatureAndSnapshotTests(TestCase):
    def test_generic_feature_engine_builds_expected_economics(self) -> None:
        snapshot = feature_snapshot()

        basis = snapshot.get(BASIS_RATE)
        net = snapshot.get(EXPECTED_NET_CARRY_RATE)
        apr = snapshot.get(EXPECTED_NET_CARRY_APR)

        assert basis is not None
        assert net is not None
        assert apr is not None
        self.assertAlmostEqual(basis.value, 0.01)
        self.assertAlmostEqual(net.value, 0.0008)
        self.assertAlmostEqual(apr.value, 0.876)

    def test_coherent_sources_publish_typed_entry_snapshot(self) -> None:
        publication = publish()

        assert publication is not None
        self.assertIsInstance(publication.value, FundingCarryEntrySnapshot)
        self.assertEqual(
            publication.value.market.pair.pair_id,
            pair().pair_id,
        )
        self.assertEqual(
            publication.metadata.observation_ids,
            tuple(item.observation_id for item in entry_observations()),
        )

    def test_missing_and_stale_sources_do_not_publish(self) -> None:
        target = coordinator()
        observations = entry_observations()
        for item in observations[:-1]:
            target.accept(item)
        missing = target.evaluate(
            now_ns=UnixNanos(1_100),
            now_monotonic_ns=200,
            clock_status=HealthStatus.HEALTHY,
        )
        self.assertEqual(missing.assessment.readiness, SnapshotReadiness.NOT_READY)
        self.assertEqual(
            missing.assessment.issues[0].code,
            SnapshotIssueCode.MISSING_SOURCE,
        )

        target.accept(observations[-1])
        stale = target.evaluate(
            now_ns=UnixNanos(2_000),
            now_monotonic_ns=1_100,
            clock_status=HealthStatus.HEALTHY,
        )
        self.assertEqual(stale.assessment.readiness, SnapshotReadiness.NOT_READY)
        self.assertIsNone(stale.publication)

    def test_wrapper_and_embedded_source_time_mismatch_fails_closed(self) -> None:
        target = coordinator()
        observations = list(entry_observations())
        observations[0] = replace(
            observations[0],
            as_of_ns=UnixNanos(1_001),
        )
        for item in observations:
            target.accept(item)

        with self.assertRaisesRegex(
            SnapshotCoordinatorFailedError,
            "wrapper time",
        ):
            target.evaluate(
                now_ns=UnixNanos(1_100),
                now_monotonic_ns=200,
                clock_status=HealthStatus.HEALTHY,
            )


class FundingCarryStrategyTests(TestCase):
    def test_profitable_entry_emits_exact_generic_two_leg_basket(self) -> None:
        publication = publish()
        assert publication is not None
        runtime = StrategyRuntime(
            strategy=FundingCarryStrategy(
                strategy_id=STRATEGY_ID,
                policy=economic_policy(),
            ),
            accepted_scopes=frozenset({SCOPE}),
            basket_policy=BasketIntentPolicy(
                max_legs=2,
                max_validity_ns=DurationNanos(1_000),
                allowed_objectives=(FUNDING_OPEN_OBJECTIVE,),
            ),
            objective_registry=funding_objective_registry(),
        )
        runtime.start()

        decision = runtime.on_input(publication)

        self.assertEqual(len(decision.intents), 1)
        basket = decision.intents[0]
        self.assertEqual(basket.objective, FUNDING_OPEN_OBJECTIVE)  # type: ignore[attr-defined]
        targets = {
            item.instrument_id.kind.value: item.target_quantity  # type: ignore[union-attr]
            for item in basket.legs  # type: ignore[union-attr]
        }
        self.assertEqual(targets["spot"], Quantity.from_str("10"))
        self.assertEqual(targets["perpetual"], Quantity.from_str("-10"))
        self.assertEqual(
            basket.decision_snapshot_id,  # type: ignore[union-attr]
            publication.metadata.snapshot_id,
        )

    def test_unprofitable_or_negative_funding_emits_no_basket(self) -> None:
        publication = publish(funding_rate="-0.001")
        assert publication is not None
        strategy = FundingCarryStrategy(
            strategy_id=STRATEGY_ID,
            policy=economic_policy(),
        )
        runtime = StrategyRuntime(
            strategy=strategy,
            accepted_scopes=frozenset({SCOPE}),
            basket_policy=BasketIntentPolicy(
                max_legs=2,
                max_validity_ns=DurationNanos(1_000),
                allowed_objectives=(FUNDING_OPEN_OBJECTIVE,),
            ),
            objective_registry=funding_objective_registry(),
        )
        runtime.start()

        self.assertEqual(runtime.on_input(publication).intents, ())


if __name__ == "__main__":
    import unittest

    unittest.main()
