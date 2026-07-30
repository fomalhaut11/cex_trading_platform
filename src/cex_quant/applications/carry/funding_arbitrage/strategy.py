"""Pure Funding Carry economic policy producing generic Basket targets."""

from __future__ import annotations

from typing import cast

from cex_quant.core import AccountId, Quantity, StrategyId, UnixNanos
from cex_quant.instruments import InstrumentId
from cex_quant.portfolio import AccountPositionRiskView
from cex_quant.snapshots import DecisionSnapshotPublication
from cex_quant.strategy import (
    BasketTargetIntent,
    BasketTargetLeg,
    DecisionIntent,
    ObjectiveTypeRef,
    StrategyContext,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)

from ..model import CarryLifecycle
from .features import (
    BASIS_RATE,
    EXPECTED_FUNDING_RATE,
    EXPECTED_NET_CARRY_RATE,
    funding_feature_value,
)
from .model import base_to_instrument_quantity
from .objectives import (
    FUNDING_CLOSE_OBJECTIVE,
    FUNDING_OPEN_OBJECTIVE,
)
from .policy import FundingCarryEconomicPolicy
from .snapshot import (
    FundingCarryDecisionSnapshot,
    FundingCarryEntrySnapshot,
    FundingCarryPositionSnapshot,
)


class FundingCarryStrategy:
    """Stateless replay-deterministic economic decision policy."""

    def __init__(
        self,
        *,
        strategy_id: StrategyId,
        policy: FundingCarryEconomicPolicy,
    ) -> None:
        if not strategy_id:
            raise ValueError("Funding Carry strategy_id cannot be empty")
        self._strategy_id = strategy_id
        self._policy = policy

    @property
    def strategy_id(self) -> StrategyId:
        return self._strategy_id

    def on_start(self) -> None:
        pass

    def on_input(
        self,
        context: StrategyContext,
    ) -> tuple[DecisionIntent, ...]:
        publication = context.input
        if not isinstance(publication, DecisionSnapshotPublication):
            raise TypeError("Funding Carry requires a decision Snapshot")
        value = publication.value
        if not isinstance(
            value,
            (FundingCarryEntrySnapshot, FundingCarryPositionSnapshot),
        ):
            raise TypeError("Funding Carry received another application Snapshot")
        typed_publication = cast(
            DecisionSnapshotPublication[FundingCarryDecisionSnapshot],
            publication,
        )
        return decide_funding_carry(
            strategy_id=self._strategy_id,
            publication=typed_publication,
            policy=self._policy,
        )

    def on_stop(self) -> None:
        pass


def decide_funding_carry(
    *,
    strategy_id: StrategyId,
    publication: DecisionSnapshotPublication[FundingCarryDecisionSnapshot],
    policy: FundingCarryEconomicPolicy,
) -> tuple[DecisionIntent, ...]:
    value = publication.value
    features = value.market.features
    net_rate = funding_feature_value(features, EXPECTED_NET_CARRY_RATE)
    funding_rate = funding_feature_value(features, EXPECTED_FUNDING_RATE)
    basis_rate = funding_feature_value(features, BASIS_RATE)
    if isinstance(value, FundingCarryEntrySnapshot):
        if (
            funding_rate <= 0
            or net_rate < policy.minimum_entry_net_rate
            or abs(basis_rate) > policy.maximum_entry_abs_basis_rate
        ):
            return ()
        return (
            _open_intent(
                strategy_id=strategy_id,
                publication=publication,
                policy=policy,
            ),
        )
    position = value.control.application_position
    if (
        position.lifecycle is CarryLifecycle.ACTIVE
        and (
            funding_rate <= 0
            or net_rate <= policy.exit_net_rate
        )
    ):
        return (
            _close_intent(
                strategy_id=strategy_id,
                publication=publication,
                policy=policy,
            ),
        )
    return ()


def _open_intent(
    *,
    strategy_id: StrategyId,
    publication: DecisionSnapshotPublication[FundingCarryDecisionSnapshot],
    policy: FundingCarryEconomicPolicy,
) -> BasketTargetIntent:
    value = publication.value
    pair = value.market.pair
    spot_baseline = _position(
        value.market.portfolio.positions,
        account_id=pair.spot_account_id,
        instrument_id=pair.spot_instrument_id,
    )
    perpetual_baseline = _position(
        value.market.portfolio.positions,
        account_id=pair.perpetual_account_id,
        instrument_id=pair.perpetual_instrument_id,
    )
    spot_delta = base_to_instrument_quantity(
        policy.target_base_quantity,
        base_units_per_quantity=pair.spot_base_units_per_quantity,
    )
    perpetual_delta = base_to_instrument_quantity(
        policy.target_base_quantity,
        base_units_per_quantity=pair.perpetual_base_units_per_quantity,
    )
    return _intent(
        strategy_id=strategy_id,
        publication=publication,
        policy=policy,
        objective=FUNDING_OPEN_OBJECTIVE,
        targets=(
            (
                pair.spot_account_id,
                pair.spot_instrument_id,
                _add(spot_baseline, spot_delta),
            ),
            (
                pair.perpetual_account_id,
                pair.perpetual_instrument_id,
                _subtract(perpetual_baseline, perpetual_delta),
            ),
        ),
        reason="open positive-Funding Carry target",
    )


def _close_intent(
    *,
    strategy_id: StrategyId,
    publication: DecisionSnapshotPublication[FundingCarryDecisionSnapshot],
    policy: FundingCarryEconomicPolicy,
) -> BasketTargetIntent:
    value = publication.value
    assert isinstance(value, FundingCarryPositionSnapshot)
    targets = tuple(
        (
            item.account_id,
            item.instrument_id,
            item.baseline_quantity,
        )
        for item in value.control.application_position.leg_ownership
    )
    return _intent(
        strategy_id=strategy_id,
        publication=publication,
        policy=policy,
        objective=FUNDING_CLOSE_OBJECTIVE,
        targets=targets,
        reason="close Carry to proven baselines",
    )


def _intent(
    *,
    strategy_id: StrategyId,
    publication: DecisionSnapshotPublication[FundingCarryDecisionSnapshot],
    policy: FundingCarryEconomicPolicy,
    objective: ObjectiveTypeRef,
    targets: tuple[tuple[AccountId, InstrumentId, Quantity], ...],
    reason: str,
) -> BasketTargetIntent:
    metadata = publication.metadata
    legs = tuple(
        BasketTargetLeg(
            leg_id=deterministic_basket_leg_id(
                decision_snapshot_id=metadata.snapshot_id,
                account_id=account_id,
                instrument_id=instrument_id,
            ),
            account_id=account_id,
            instrument_id=instrument_id,
            target_quantity=quantity,
            reason=reason,
        )
        for account_id, instrument_id, quantity in targets
    )
    return create_basket_target_intent(
        strategy_id=strategy_id,
        decision_snapshot_id=metadata.snapshot_id,
        objective=objective,
        legs=legs,
        decision_time_ns=metadata.assembled_at_ns,
        valid_until_ns=UnixNanos(
            metadata.assembled_at_ns + policy.basket_validity_ns
        ),
        policy_version=policy.version,
        reason=reason,
    )


def _position(
    views: tuple[AccountPositionRiskView, ...],
    *,
    account_id: AccountId,
    instrument_id: InstrumentId,
) -> Quantity:
    account = next(
        (item for item in views if item.account_id == account_id),
        None,
    )
    if account is None:
        raise ValueError("Funding Carry account position view is missing")
    instrument = next(
        (
            item
            for item in account.positions
            if item.instrument_id == instrument_id
        ),
        None,
    )
    return (
        Quantity.from_str("0")
        if instrument is None
        else instrument.effective_quantity
    )


def _add(first: Quantity, second: Quantity) -> Quantity:
    return Quantity.from_str(
        format(first.as_decimal() + second.as_decimal(), "f")
    )


def _subtract(first: Quantity, second: Quantity) -> Quantity:
    return Quantity.from_str(
        format(
            first.as_decimal() - second.as_decimal(),
            "f",
        )
    )


__all__ = [
    "FundingCarryStrategy",
    "decide_funding_carry",
]
