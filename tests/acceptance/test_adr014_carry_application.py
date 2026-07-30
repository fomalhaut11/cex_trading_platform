import tempfile
from pathlib import Path
from unittest import TestCase

from carry_test_support import (
    POSITION_SCOPE,
    POSITION_SOURCES,
    SCOPE,
    SOURCES,
    STRATEGY_ID,
    entry_observations,
    pair,
    position_observations,
)
from test_carry_state import ownership
from test_funding_carry_policy import economic_policy

from cex_quant.applications.carry import (
    CarryFinancialState,
    CarryHedgeState,
    CarryLifecycle,
)
from cex_quant.applications.carry.funding_arbitrage import (
    FUNDING_CLOSE_OBJECTIVE,
    FUNDING_OPEN_OBJECTIVE,
    FundingCarryDecisionSnapshot,
    FundingCarrySnapshotAssembler,
    FundingCarrySnapshotKind,
    FundingCarryStrategy,
    funding_objective_registry,
)
from cex_quant.applications.carry.journal import JsonLinesCarryJournal
from cex_quant.applications.carry.state import CarryPositionBook
from cex_quant.core import (
    AccountId,
    DurationNanos,
    ObjectiveTypeId,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.observability import HealthStatus
from cex_quant.runtime import (
    CarryApplicationRuntime,
    CarryRuntimeDisposition,
    SnapshotCoordinator,
)
from cex_quant.snapshots import (
    DecisionSnapshotId,
    SnapshotPolicy,
    SnapshotSourceId,
    SourceFreshnessRule,
)
from cex_quant.strategy import (
    BasketIntentPolicy,
    BasketTargetLeg,
    ObjectiveTypeRef,
    StrategyRuntime,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)


def snapshot_policy(
    source_ids: tuple[SnapshotSourceId, ...],
) -> SnapshotPolicy:
    return SnapshotPolicy(
        source_rules=tuple(
            SourceFreshnessRule(
                source_id=source_id,
                max_event_age_ns=DurationNanos(500),
                max_arrival_age_ns=DurationNanos(500),
                max_future_skew_ns=DurationNanos(10),
            )
            for source_id in source_ids
        ),
        coherence_groups=(),
        policy_version=1,
    )


def coordinator(
    *,
    scope: str,
    sources,
    kind: FundingCarrySnapshotKind,
) -> SnapshotCoordinator[FundingCarryDecisionSnapshot]:
    return SnapshotCoordinator(
        scope=scope,
        policy=snapshot_policy(sources.required),
        assembler=FundingCarrySnapshotAssembler(
            pair=pair(),
            source_ids=sources,
            kind=kind,
        ),
    )


def strategy_runtime(*, objective):
    return StrategyRuntime(
        strategy=FundingCarryStrategy(
            strategy_id=STRATEGY_ID,
            policy=economic_policy(),
        ),
        accepted_scopes=frozenset({SCOPE, POSITION_SCOPE}),
        basket_policy=BasketIntentPolicy(
            max_legs=2,
            max_validity_ns=DurationNanos(1_000),
            allowed_objectives=(objective,),
        ),
        objective_registry=funding_objective_registry(),
    )


def evaluate(target: CarryApplicationRuntime):
    return target.evaluate(
        now_ns=UnixNanos(1_100),
        now_monotonic_ns=200,
        clock_status=HealthStatus.HEALTHY,
    )


class Adr014CarryAcceptanceTests(TestCase):
    def test_positive_funding_open_stops_at_offline_basket_boundary(self) -> None:
        target = CarryApplicationRuntime(
            snapshots=coordinator(
                scope=SCOPE,
                sources=SOURCES,
                kind=FundingCarrySnapshotKind.ENTRY,
            ),
            strategy=strategy_runtime(objective=FUNDING_OPEN_OBJECTIVE),
        )
        target.start()
        for item in entry_observations():
            target.accept(item)

        result = evaluate(target)

        self.assertEqual(
            result.disposition,
            CarryRuntimeDisposition.BASKET_RECORDED_EXTERNAL_BLOCKED,
        )
        self.assertTrue(result.external_execution_blocked)
        self.assertEqual(
            {
                item.instrument_id.kind: item.target_quantity
                for item in result.baskets[0].legs
            },
            {
                InstrumentKind.SPOT: Quantity.from_str("10"),
                InstrumentKind.PERPETUAL: Quantity.from_str("-10"),
            },
        )

    def test_funding_reversal_generates_fresh_close_economic_target(self) -> None:
        target = CarryApplicationRuntime(
            snapshots=coordinator(
                scope=POSITION_SCOPE,
                sources=POSITION_SOURCES,
                kind=FundingCarrySnapshotKind.POSITION,
            ),
            strategy=strategy_runtime(objective=FUNDING_CLOSE_OBJECTIVE),
        )
        target.start()
        for item in position_observations(funding_rate="-0.001"):
            target.accept(item)

        result = evaluate(target)

        self.assertEqual(
            result.disposition,
            CarryRuntimeDisposition.BASKET_RECORDED_EXTERNAL_BLOCKED,
        )
        self.assertEqual(result.baskets[0].objective, FUNDING_CLOSE_OBJECTIVE)
        self.assertTrue(
            all(
                item.target_quantity == Quantity.from_str("0")
                for item in result.baskets[0].legs
            )
        )
        self.assertEqual(
            result.baskets[0].decision_snapshot_id,
            result.publication.metadata.snapshot_id,  # type: ignore[union-attr]
        )

    def test_unknown_outcome_survives_restart_without_retry_or_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "carry.jsonl"
            first_journal = JsonLinesCarryJournal(path)
            first = CarryPositionBook(
                first_journal,
                now_ns=lambda: UnixNanos(2_000),
            )
            created = first.create_position(
                strategy_id=STRATEGY_ID,
                pair_id=pair().pair_id,
                opening_snapshot_id=DecisionSnapshotId("opening-snapshot"),
                ownership=ownership(),
                occurred_at_ns=UnixNanos(1_000),
                policy_version=1,
            )
            recovery = first.require_recovery(
                created.application_position_id,
                source_snapshot_id=DecisionSnapshotId("recovery-snapshot"),
                occurred_at_ns=UnixNanos(1_100),
                policy_version=1,
                reason="child outcome unknown",
            )
            first_journal.close()

            replay_journal = JsonLinesCarryJournal(path)
            replayed = CarryPositionBook(
                replay_journal,
                now_ns=lambda: UnixNanos(2_001),
            ).position(created.application_position_id)
            replay_journal.close()

        self.assertEqual(replayed, recovery)
        self.assertEqual(replayed.lifecycle, CarryLifecycle.RECOVERY_REQUIRED)
        self.assertEqual(replayed.hedge_state, CarryHedgeState.UNKNOWN)
        self.assertFalse(hasattr(replayed, "order_request"))
        self.assertFalse(hasattr(replayed, "execution_permit"))

    def test_physical_close_can_precede_financial_reconciliation(self) -> None:
        class MemoryJournal:
            def __init__(self) -> None:
                self.items = []

            def read(self):
                yield from self.items

            def append(self, fact) -> None:
                self.items.append(fact)

        book = CarryPositionBook(
            MemoryJournal(),
            now_ns=lambda: UnixNanos(2_000),
        )
        created = book.create_position(
            strategy_id=STRATEGY_ID,
            pair_id=pair().pair_id,
            opening_snapshot_id=DecisionSnapshotId("opening-snapshot"),
            ownership=ownership(),
            occurred_at_ns=UnixNanos(1_000),
            policy_version=1,
        )
        phases = (
            (
                CarryLifecycle.OPENING,
                CarryHedgeState.UNHEDGED,
                "opening",
            ),
            (CarryLifecycle.ACTIVE, CarryHedgeState.HEDGED, "active"),
            (CarryLifecycle.CLOSING, CarryHedgeState.HEDGED, "closing"),
            (CarryLifecycle.CLOSED, CarryHedgeState.HEDGED, "closed"),
        )
        current = created
        for index, (lifecycle, hedge, snapshot) in enumerate(phases, start=1):
            current = book.transition(
                created.application_position_id,
                lifecycle=lifecycle,
                hedge_state=hedge,
                financial_state=CarryFinancialState.PROVISIONAL,
                source_snapshot_id=DecisionSnapshotId(snapshot),
                occurred_at_ns=UnixNanos(1_000 + index),
                policy_version=1,
            )

        self.assertEqual(current.lifecycle, CarryLifecycle.CLOSED)
        self.assertEqual(
            current.financial_state,
            CarryFinancialState.PROVISIONAL,
        )

    def test_generic_platform_contract_remains_n_leg(self) -> None:
        snapshot_id = DecisionSnapshotId("option-carry-snapshot")
        objective = ObjectiveTypeRef(
            objective_type_id=ObjectiveTypeId("options.delta_hedged_spread"),
            version=1,
        )
        candidates = (
            (
                InstrumentKind.OPTION,
                "BTC-30000-C",
                "10",
            ),
            (
                InstrumentKind.OPTION,
                "BTC-35000-C",
                "-10",
            ),
            (
                InstrumentKind.PERPETUAL,
                "BTCUSDT",
                "-0.35",
            ),
        )
        legs = tuple(
            BasketTargetLeg(
                leg_id=deterministic_basket_leg_id(
                    decision_snapshot_id=snapshot_id,
                    account_id=AccountId("options-account"),
                    instrument_id=instrument_id,
                ),
                account_id=AccountId("options-account"),
                instrument_id=instrument_id,
                target_quantity=Quantity.from_str(quantity),
            )
            for kind, symbol, quantity in candidates
            for instrument_id in (
                InstrumentId(
                    venue=VenueId("BINANCE"),
                    kind=kind,
                    symbol=symbol,
                ),
            )
        )

        basket = create_basket_target_intent(
            strategy_id=STRATEGY_ID,
            decision_snapshot_id=snapshot_id,
            objective=objective,
            legs=legs,
            decision_time_ns=UnixNanos(1_000),
            valid_until_ns=UnixNanos(2_000),
            policy_version=1,
        )

        self.assertEqual(len(basket.legs), 3)
        self.assertEqual(
            {item.instrument_id.kind for item in basket.legs},
            {InstrumentKind.OPTION, InstrumentKind.PERPETUAL},
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
