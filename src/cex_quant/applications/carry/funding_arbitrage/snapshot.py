"""Typed Funding Carry decision snapshots and semantic assembly."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from cex_quant.features import FeatureSnapshot
from cex_quant.market_data import (
    FundingView,
    IndexPriceUpdate,
    L1View,
    MarketStateStatus,
    MarkPriceUpdate,
)
from cex_quant.oms import OrderGroupView
from cex_quant.portfolio import (
    AccountPositionRiskView,
    MarginScopeSnapshot,
    PositionRiskReadiness,
)
from cex_quant.risk import PortfolioRiskDirective
from cex_quant.snapshots import (
    DecisionSnapshotMetadata,
    SnapshotSourceId,
    SourceObservation,
)

from ..model import CarryPositionView
from .features import require_funding_carry_features
from .model import FundingCarryPair

T = TypeVar("T")


class FundingCarrySnapshotKind(StrEnum):
    ENTRY = "entry"
    POSITION = "position"


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarrySourceIds:
    spot_market: SnapshotSourceId
    perpetual_market: SnapshotSourceId
    mark_price: SnapshotSourceId
    index_price: SnapshotSourceId
    funding: SnapshotSourceId
    portfolio: SnapshotSourceId
    features: SnapshotSourceId
    control: SnapshotSourceId | None = None

    def __post_init__(self) -> None:
        values = self.required
        if len(set(values)) != len(values):
            raise ValueError("Funding Carry Snapshot source IDs must be unique")
        if any(not str(item) for item in values):
            raise ValueError("Funding Carry Snapshot source ID cannot be empty")

    @property
    def required(self) -> tuple[SnapshotSourceId, ...]:
        values = (
            self.spot_market,
            self.perpetual_market,
            self.mark_price,
            self.index_price,
            self.funding,
            self.portfolio,
            self.features,
        )
        return values if self.control is None else (*values, self.control)


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryPortfolioInputs:
    positions: tuple[AccountPositionRiskView, ...]
    margins: tuple[MarginScopeSnapshot, ...]

    def __post_init__(self) -> None:
        account_ids = tuple(str(item.account_id) for item in self.positions)
        if account_ids != tuple(sorted(account_ids)):
            raise ValueError("Carry position views must be account ordered")
        if len(set(account_ids)) != len(account_ids):
            raise ValueError("Carry position accounts must be unique")
        if any(
            item.readiness is not PositionRiskReadiness.READY
            for item in self.positions
        ):
            raise ValueError("Carry position inputs must be READY")
        margin_ids = tuple(str(item.scope_id) for item in self.margins)
        if margin_ids != tuple(sorted(margin_ids)):
            raise ValueError("Carry margin views must be scope ordered")
        if len(set(margin_ids)) != len(margin_ids):
            raise ValueError("Carry margin scopes must be unique")


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryControlInputs:
    application_position: CarryPositionView
    risk_directives: tuple[PortfolioRiskDirective, ...]
    order_groups: tuple[OrderGroupView, ...]

    def __post_init__(self) -> None:
        group_ids = tuple(str(item.order_group_id) for item in self.order_groups)
        if group_ids != tuple(sorted(group_ids)):
            raise ValueError("Carry Order Group views must be ID ordered")
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("Carry Order Group views must be unique")
        linked = {str(item) for item in self.application_position.order_group_ids}
        if any(item not in linked for item in group_ids):
            raise ValueError("Carry control includes an unlinked Order Group")
        if any(
            str(item.group_id) not in set(group_ids)
            for item in self.risk_directives
        ):
            raise ValueError("Carry directive has no bounded Order Group view")


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryMarketInputs:
    pair: FundingCarryPair
    spot_market: L1View
    perpetual_market: L1View
    mark_price: MarkPriceUpdate
    index_price: IndexPriceUpdate
    funding: FundingView
    portfolio: FundingCarryPortfolioInputs
    features: FeatureSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryEntrySnapshot:
    market: FundingCarryMarketInputs


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryPositionSnapshot:
    market: FundingCarryMarketInputs
    control: FundingCarryControlInputs


FundingCarryDecisionSnapshot = (
    FundingCarryEntrySnapshot | FundingCarryPositionSnapshot
)


class FundingCarrySnapshotAssembler:
    """Pure semantic adapter over an ADR-009 ordered observation set."""

    def __init__(
        self,
        *,
        pair: FundingCarryPair,
        source_ids: FundingCarrySourceIds,
        kind: FundingCarrySnapshotKind,
    ) -> None:
        if (
            kind is FundingCarrySnapshotKind.ENTRY
            and source_ids.control is not None
        ):
            raise ValueError("entry Snapshot cannot configure control source")
        if (
            kind is FundingCarrySnapshotKind.POSITION
            and source_ids.control is None
        ):
            raise ValueError("position Snapshot requires control source")
        self._pair = pair
        self._source_ids = source_ids
        self._kind = kind

    def build(
        self,
        *,
        observations: tuple[SourceObservation[object], ...],
        metadata: DecisionSnapshotMetadata,
    ) -> FundingCarryDecisionSnapshot:
        by_source = {item.source_id: item for item in observations}
        if set(by_source) != set(self._source_ids.required):
            raise ValueError("Funding Carry Snapshot source set is incomplete")
        if len(by_source) != len(observations):
            raise ValueError("Funding Carry Snapshot sources are duplicated")

        spot = self._typed(
            by_source[self._source_ids.spot_market],
            L1View,
            name="spot market",
        )
        perpetual = self._typed(
            by_source[self._source_ids.perpetual_market],
            L1View,
            name="perpetual market",
        )
        mark = self._typed(
            by_source[self._source_ids.mark_price],
            MarkPriceUpdate,
            name="mark price",
        )
        index = self._typed(
            by_source[self._source_ids.index_price],
            IndexPriceUpdate,
            name="index price",
        )
        funding = self._typed(
            by_source[self._source_ids.funding],
            FundingView,
            name="Funding",
        )
        portfolio = self._typed(
            by_source[self._source_ids.portfolio],
            FundingCarryPortfolioInputs,
            name="Portfolio",
        )
        features = self._typed(
            by_source[self._source_ids.features],
            FeatureSnapshot,
            name="Features",
        )
        self._validate_market(
            spot=spot,
            perpetual=perpetual,
            mark=mark,
            index=index,
            funding=funding,
        )
        self._validate_observation_times(
            by_source=by_source,
            spot=spot,
            perpetual=perpetual,
            mark=mark,
            index=index,
            funding=funding,
        )
        self._validate_portfolio(portfolio)
        if features.scope != metadata.scope:
            raise ValueError("Feature scope differs from decision Snapshot")
        require_funding_carry_features(
            features,
            decision_time_ns=metadata.assembled_at_ns,
        )
        market = FundingCarryMarketInputs(
            pair=self._pair,
            spot_market=spot,
            perpetual_market=perpetual,
            mark_price=mark,
            index_price=index,
            funding=funding,
            portfolio=portfolio,
            features=features,
        )
        if self._kind is FundingCarrySnapshotKind.ENTRY:
            return FundingCarryEntrySnapshot(market=market)
        control_id = self._source_ids.control
        assert control_id is not None
        control = self._typed(
            by_source[control_id],
            FundingCarryControlInputs,
            name="Carry control",
        )
        if control.application_position.pair_id != self._pair.pair_id:
            raise ValueError("Carry position belongs to another pair")
        return FundingCarryPositionSnapshot(
            market=market,
            control=control,
        )

    @staticmethod
    def _typed(
        observation: SourceObservation[object],
        expected: type[T],
        *,
        name: str,
    ) -> T:
        if not isinstance(observation.value, expected):
            raise TypeError(f"{name} Snapshot source has the wrong type")
        return observation.value

    def _validate_market(
        self,
        *,
        spot: L1View,
        perpetual: L1View,
        mark: MarkPriceUpdate,
        index: IndexPriceUpdate,
        funding: FundingView,
    ) -> None:
        if spot.instrument_id != self._pair.spot_instrument_id:
            raise ValueError("Spot view differs from Funding Carry pair")
        if any(
            item != self._pair.perpetual_instrument_id
            for item in (
                perpetual.instrument_id,
                mark.instrument_id,
                index.instrument_id,
                funding.instrument_id,
            )
        ):
            raise ValueError("perpetual market view differs from Carry pair")
        if (
            spot.status is not MarketStateStatus.LIVE
            or perpetual.status is not MarketStateStatus.LIVE
            or funding.status is not MarketStateStatus.LIVE
        ):
            raise ValueError("Funding Carry market views must be LIVE")

    def _validate_portfolio(
        self,
        portfolio: FundingCarryPortfolioInputs,
    ) -> None:
        accounts = {item.account_id for item in portfolio.positions}
        required = {
            self._pair.spot_account_id,
            self._pair.perpetual_account_id,
        }
        if not required.issubset(accounts):
            raise ValueError("Carry Portfolio position scope is incomplete")
        if not any(
            item.account_id == self._pair.perpetual_account_id
            for item in portfolio.margins
        ):
            raise ValueError("Carry perpetual margin scope is missing")

    def _validate_observation_times(
        self,
        *,
        by_source: dict[SnapshotSourceId, SourceObservation[object]],
        spot: L1View,
        perpetual: L1View,
        mark: MarkPriceUpdate,
        index: IndexPriceUpdate,
        funding: FundingView,
    ) -> None:
        expected = (
            (self._source_ids.spot_market, spot.as_of_ns),
            (self._source_ids.perpetual_market, perpetual.as_of_ns),
            (self._source_ids.mark_price, mark.metadata.event_time_ns),
            (self._source_ids.index_price, index.metadata.event_time_ns),
            (self._source_ids.funding, funding.as_of_ns),
        )
        if any(by_source[source_id].as_of_ns != value for source_id, value in expected):
            raise ValueError("Snapshot wrapper time differs from source view")


__all__ = [
    "FundingCarryControlInputs",
    "FundingCarryDecisionSnapshot",
    "FundingCarryEntrySnapshot",
    "FundingCarryMarketInputs",
    "FundingCarryPortfolioInputs",
    "FundingCarryPositionSnapshot",
    "FundingCarrySnapshotAssembler",
    "FundingCarrySnapshotKind",
    "FundingCarrySourceIds",
]
