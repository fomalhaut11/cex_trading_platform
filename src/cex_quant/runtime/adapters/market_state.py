"""Convert detailed market-state updates into pipeline admission gates."""

from typing import Protocol

from cex_quant.market_data import MarketEvent
from cex_quant.market_data.state import (
    MarketStateStatus,
    StateUpdateResult,
    UpdateDisposition,
)

from ..pipeline import StateGate


class MarketStateUpdater(Protocol):
    def apply(self, event: MarketEvent) -> StateUpdateResult: ...


class MarketStateGateAdapter:
    """Admit only updates that leave the owned state usable and live."""

    _ACCEPTED = frozenset(
        {
            UpdateDisposition.APPLIED,
            UpdateDisposition.INITIALIZED,
            UpdateDisposition.IGNORED_STALE,
        }
    )

    def __init__(self, updater: MarketStateUpdater) -> None:
        self._updater = updater

    def apply(self, event: MarketEvent) -> StateGate:
        result = self._updater.apply(event)
        accepted = (
            result.status is MarketStateStatus.LIVE
            and result.disposition in self._ACCEPTED
        )
        reason = "" if accepted else (
            result.reason
            or f"market state is {result.status.value} "
            f"({result.disposition.value})"
        )
        return StateGate(accepted=accepted, reason=reason)


__all__ = ["MarketStateGateAdapter", "MarketStateUpdater"]
