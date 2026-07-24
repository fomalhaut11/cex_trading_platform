"""Single-writer level-one market state."""

from cex_quant.instruments import InstrumentId
from cex_quant.market_data.events import BestBidAsk

from .model import (
    InstrumentMismatchError,
    L1View,
    MarketStateStatus,
    StateUpdateResult,
    UpdateDisposition,
)


class L1State:
    """Maintain the latest canonical best bid and ask for one instrument."""

    def __init__(self, *, instrument_id: InstrumentId) -> None:
        self._instrument_id = instrument_id
        self._view: L1View | None = None

    @property
    def status(self) -> MarketStateStatus:
        return (
            MarketStateStatus.EMPTY
            if self._view is None
            else MarketStateStatus.LIVE
        )

    def apply(self, event: BestBidAsk) -> StateUpdateResult:
        self._require_instrument(event.instrument_id)
        sequence = event.metadata.sequence
        if self._view is not None and _is_stale(
            current_sequence=self._view.sequence,
            current_time_ns=self._view.as_of_ns,
            incoming_sequence=sequence,
            incoming_time_ns=event.metadata.event_time_ns,
        ):
            return StateUpdateResult(
                disposition=UpdateDisposition.IGNORED_STALE,
                status=MarketStateStatus.LIVE,
                sequence=self._view.sequence,
                reason="event does not advance sequence or event time",
            )
        disposition = (
            UpdateDisposition.INITIALIZED
            if self._view is None
            else UpdateDisposition.APPLIED
        )
        self._view = L1View(
            instrument_id=self._instrument_id,
            bid=event.bid,
            ask=event.ask,
            as_of_ns=event.metadata.event_time_ns,
            sequence=sequence,
            status=MarketStateStatus.LIVE,
        )
        return StateUpdateResult(
            disposition=disposition,
            status=MarketStateStatus.LIVE,
            sequence=sequence,
        )

    def view(self) -> L1View | None:
        return self._view

    def _require_instrument(self, incoming: InstrumentId) -> None:
        if incoming != self._instrument_id:
            raise InstrumentMismatchError(
                f"state owns {self._instrument_id}, received {incoming}"
            )


def _is_stale(
    *,
    current_sequence: int | None,
    current_time_ns: int,
    incoming_sequence: int | None,
    incoming_time_ns: int,
) -> bool:
    if current_sequence is not None and incoming_sequence is not None:
        return incoming_sequence <= current_sequence
    return incoming_time_ns <= current_time_ns


__all__ = ["L1State"]
