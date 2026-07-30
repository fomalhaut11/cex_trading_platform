"""Stable Objective Type registrations for Funding Carry economics."""

from cex_quant.core import ObjectiveTypeId
from cex_quant.strategy import (
    ObjectiveTypeDefinition,
    ObjectiveTypeRef,
    ObjectiveTypeRegistry,
)

FUNDING_CLOSE_OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding.close"),
    version=1,
)
FUNDING_OPEN_OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding.open"),
    version=1,
)
FUNDING_REBALANCE_OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding.rebalance"),
    version=1,
)
FUNDING_RECOVER_OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding.recover"),
    version=1,
)

FUNDING_OBJECTIVE_DEFINITIONS = (
    ObjectiveTypeDefinition(
        ref=FUNDING_CLOSE_OBJECTIVE,
        owner="cex_quant.applications.carry",
        description="Return a Funding Carry position to proven baselines.",
    ),
    ObjectiveTypeDefinition(
        ref=FUNDING_OPEN_OBJECTIVE,
        owner="cex_quant.applications.carry",
        description="Open a Spot/linear-perpetual Carry economic target.",
    ),
    ObjectiveTypeDefinition(
        ref=FUNDING_REBALANCE_OBJECTIVE,
        owner="cex_quant.applications.carry",
        description="Restore an admitted Carry economic target.",
    ),
    ObjectiveTypeDefinition(
        ref=FUNDING_RECOVER_OBJECTIVE,
        owner="cex_quant.applications.carry",
        description="Propose a fresh recovery economic target.",
    ),
)


def funding_objective_registry() -> ObjectiveTypeRegistry:
    return ObjectiveTypeRegistry(FUNDING_OBJECTIVE_DEFINITIONS)


__all__ = [
    "FUNDING_CLOSE_OBJECTIVE",
    "FUNDING_OBJECTIVE_DEFINITIONS",
    "FUNDING_OPEN_OBJECTIVE",
    "FUNDING_REBALANCE_OBJECTIVE",
    "FUNDING_RECOVER_OBJECTIVE",
    "funding_objective_registry",
]
