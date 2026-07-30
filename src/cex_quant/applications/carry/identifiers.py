"""Strong and deterministic identities for Carry application evidence."""

from __future__ import annotations

import hashlib
import json
from typing import NewType

from cex_quant.core import StrategyId
from cex_quant.snapshots import DecisionSnapshotId

ApplicationPositionId = NewType("ApplicationPositionId", str)
CarryApplicationFactId = NewType("CarryApplicationFactId", str)
CarryOwnershipId = NewType("CarryOwnershipId", str)
CarryPairId = NewType("CarryPairId", str)


def deterministic_application_position_id(
    *,
    strategy_id: StrategyId,
    pair_id: CarryPairId,
    opening_snapshot_id: DecisionSnapshotId,
) -> ApplicationPositionId:
    """Derive a replay-stable aggregate identity from its opening cause."""

    return ApplicationPositionId(
        "carry-position-"
        + _sha256(
            {
                "opening_snapshot_id": str(opening_snapshot_id),
                "pair_id": str(pair_id),
                "strategy_id": str(strategy_id),
            }
        )
    )


def deterministic_carry_fact_id(payload: object) -> CarryApplicationFactId:
    return CarryApplicationFactId("carry-fact-" + _sha256(payload))


def deterministic_carry_ownership_id(payload: object) -> CarryOwnershipId:
    return CarryOwnershipId("carry-ownership-" + _sha256(payload))


def deterministic_carry_pair_id(payload: object) -> CarryPairId:
    return CarryPairId("carry-pair-" + _sha256(payload))


def _sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ApplicationPositionId",
    "CarryApplicationFactId",
    "CarryOwnershipId",
    "CarryPairId",
    "deterministic_application_position_id",
    "deterministic_carry_fact_id",
    "deterministic_carry_ownership_id",
    "deterministic_carry_pair_id",
]
