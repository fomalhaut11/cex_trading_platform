"""Generic Feature-engine definitions for Funding Carry economics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cex_quant.core import EventMetadata, FeatureId
from cex_quant.features import (
    FeatureContext,
    FeatureDefinition,
    FeatureOutput,
    FeatureQuality,
    FeatureRef,
    FeatureRegistry,
    FeatureSnapshot,
    FeatureVersion,
)
from cex_quant.market_data import FundingView, L1View, MarketStateStatus

from .model import FundingCarryPair
from .policy import FundingCarryFeaturePolicy

BASIS_RATE = FeatureRef(
    feature_id=FeatureId("carry.funding.basis_rate"),
    version=FeatureVersion(1),
)
ESTIMATED_COST_RATE = FeatureRef(
    feature_id=FeatureId("carry.funding.estimated_cost_rate"),
    version=FeatureVersion(1),
)
EXPECTED_FUNDING_RATE = FeatureRef(
    feature_id=FeatureId("carry.funding.expected_funding_rate"),
    version=FeatureVersion(1),
)
EXPECTED_NET_CARRY_APR = FeatureRef(
    feature_id=FeatureId("carry.funding.expected_net_carry_apr"),
    version=FeatureVersion(1),
)
EXPECTED_NET_CARRY_RATE = FeatureRef(
    feature_id=FeatureId("carry.funding.expected_net_carry_rate"),
    version=FeatureVersion(1),
)

REQUIRED_FUNDING_FEATURES = tuple(
    sorted(
        (
            BASIS_RATE,
            ESTIMATED_COST_RATE,
            EXPECTED_FUNDING_RATE,
            EXPECTED_NET_CARRY_APR,
            EXPECTED_NET_CARRY_RATE,
        )
    )
)


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingCarryFeatureInput:
    """Coherent application input consumed by the generic Feature engine."""

    metadata: EventMetadata
    pair: FundingCarryPair
    spot_market: L1View
    perpetual_market: L1View
    funding: FundingView

    def __post_init__(self) -> None:
        if self.spot_market.instrument_id != self.pair.spot_instrument_id:
            raise ValueError("spot market does not match Funding Carry pair")
        if (
            self.perpetual_market.instrument_id
            != self.pair.perpetual_instrument_id
        ):
            raise ValueError("perpetual market does not match Funding Carry pair")
        if self.funding.instrument_id != self.pair.perpetual_instrument_id:
            raise ValueError("Funding view does not match perpetual leg")
        if (
            self.spot_market.status is not MarketStateStatus.LIVE
            or self.perpetual_market.status is not MarketStateStatus.LIVE
            or self.funding.status is not MarketStateStatus.LIVE
        ):
            raise ValueError("Funding Carry feature input requires LIVE views")


def funding_carry_feature_definitions(
    policy: FundingCarryFeaturePolicy,
) -> tuple[FeatureDefinition, ...]:
    registry = FeatureRegistry()
    registry.register(
        FeatureDefinition(
            ref=BASIS_RATE,
            event_types=(FundingCarryFeatureInput,),
            calculator=_basis,
            description="Executable short-perpetual basis over Spot ask.",
        )
    )
    registry.register(
        FeatureDefinition(
            ref=ESTIMATED_COST_RATE,
            event_types=(FundingCarryFeatureInput,),
            calculator=lambda context: _estimated_cost(context, policy),
            description="Configured round-trip cost estimate.",
        )
    )
    registry.register(
        FeatureDefinition(
            ref=EXPECTED_FUNDING_RATE,
            event_types=(FundingCarryFeatureInput,),
            calculator=_expected_funding,
            description="Expected next Funding rate for short perpetual.",
        )
    )
    registry.register(
        FeatureDefinition(
            ref=EXPECTED_NET_CARRY_RATE,
            event_types=(FundingCarryFeatureInput,),
            dependencies=tuple(
                sorted((ESTIMATED_COST_RATE, EXPECTED_FUNDING_RATE))
            ),
            calculator=_net_carry,
            description="Expected Funding less configured costs.",
        )
    )
    registry.register(
        FeatureDefinition(
            ref=EXPECTED_NET_CARRY_APR,
            event_types=(FundingCarryFeatureInput,),
            dependencies=(EXPECTED_NET_CARRY_RATE,),
            calculator=lambda context: _annualized(context, policy),
            description="Simple annualized expected net carry.",
        )
    )
    return registry.build()


def require_funding_carry_features(
    snapshot: FeatureSnapshot,
    *,
    decision_time_ns: int,
) -> None:
    values = {item.metadata.ref: item for item in snapshot.values}
    missing = tuple(ref for ref in REQUIRED_FUNDING_FEATURES if ref not in values)
    if missing:
        raise ValueError("Funding Carry FeatureSnapshot is incomplete")
    for ref in REQUIRED_FUNDING_FEATURES:
        value = values[ref]
        if value.quality is not FeatureQuality.GOOD:
            raise ValueError("Funding Carry feature quality is not GOOD")
        valid_until = value.metadata.valid_until_ns
        if valid_until is not None and valid_until < decision_time_ns:
            raise ValueError("Funding Carry feature is expired")


def funding_feature_value(snapshot: FeatureSnapshot, ref: FeatureRef) -> float:
    value = snapshot.get(ref)
    if value is None:
        raise ValueError(f"required Funding Carry feature is missing: {ref}")
    return value.value


def _event(context: FeatureContext) -> FundingCarryFeatureInput:
    if not isinstance(context.event, FundingCarryFeatureInput):
        raise TypeError("Funding Carry calculator received an invalid input")
    return context.event


def _basis(context: FeatureContext) -> FeatureOutput:
    event = _event(context)
    spot_ask = event.spot_market.ask.price.as_decimal()
    perpetual_bid = event.perpetual_market.bid.price.as_decimal()
    basis = (perpetual_bid - spot_ask) / spot_ask
    return _output(event, basis, unit="ratio")


def _estimated_cost(
    context: FeatureContext,
    policy: FundingCarryFeaturePolicy,
) -> FeatureOutput:
    return _output(
        _event(context),
        Decimal(str(policy.estimated_round_trip_cost_rate)),
        unit="ratio",
    )


def _expected_funding(context: FeatureContext) -> FeatureOutput:
    event = _event(context)
    return _output(
        event,
        event.funding.funding_rate.as_decimal(),
        unit="ratio",
    )


def _net_carry(context: FeatureContext) -> FeatureOutput:
    event = _event(context)
    funding = context.dependencies[EXPECTED_FUNDING_RATE].value
    cost = context.dependencies[ESTIMATED_COST_RATE].value
    return _output(event, Decimal(str(funding - cost)), unit="ratio")


def _annualized(
    context: FeatureContext,
    policy: FundingCarryFeaturePolicy,
) -> FeatureOutput:
    event = _event(context)
    net = context.dependencies[EXPECTED_NET_CARRY_RATE].value
    return _output(
        event,
        Decimal(str(net * policy.funding_periods_per_year)),
        unit="annualized_ratio",
    )


def _output(
    event: FundingCarryFeatureInput,
    value: Decimal,
    *,
    unit: str,
) -> FeatureOutput:
    return FeatureOutput(
        value=float(value),
        unit=unit,
        valid_until_ns=event.funding.next_funding_time_ns,
    )


__all__ = [
    "BASIS_RATE",
    "ESTIMATED_COST_RATE",
    "EXPECTED_FUNDING_RATE",
    "EXPECTED_NET_CARRY_APR",
    "EXPECTED_NET_CARRY_RATE",
    "REQUIRED_FUNDING_FEATURES",
    "FundingCarryFeatureInput",
    "funding_carry_feature_definitions",
    "funding_feature_value",
    "require_funding_carry_features",
]
