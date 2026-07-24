"""Single-writer exchange-supplied partial-depth state."""

from cex_quant.instruments import InstrumentId
from cex_quant.market_data.events import PartialBookFrame

from .l1 import _is_stale
from .model import (
    InstrumentMismatchError,
    MarketStateStatus,
    PartialBookView,
    StateUpdateResult,
    UpdateDisposition,
)


class PartialBookState:
    """Replace the current partial-depth view atomically with each frame."""

    def __init__(self, *, instrument_id: InstrumentId) -> None:
        self._instrument_id = instrument_id
        self._view: PartialBookView | None = None

    @property
    def status(self) -> MarketStateStatus:
        return (
            MarketStateStatus.EMPTY
            if self._view is None
            else MarketStateStatus.LIVE
        )

    def apply(self, frame: PartialBookFrame) -> StateUpdateResult:
        self._require_instrument(frame.instrument_id)
        if self._view is not None and _is_stale(
            current_sequence=self._view.sequence,
            current_time_ns=self._view.as_of_ns,
            incoming_sequence=frame.sequence,
            incoming_time_ns=frame.metadata.event_time_ns,
        ):
            return StateUpdateResult(
                disposition=UpdateDisposition.IGNORED_STALE,
                status=MarketStateStatus.LIVE,
                sequence=self._view.sequence,
                reason="frame does not advance sequence or event time",
            )
        disposition = (
            UpdateDisposition.INITIALIZED
            if self._view is None
            else UpdateDisposition.APPLIED
        )
        self._view = PartialBookView(
            instrument_id=self._instrument_id,
            bids=frame.bids,
            asks=frame.asks,
            as_of_ns=frame.metadata.event_time_ns,
            sequence=frame.sequence,
            status=MarketStateStatus.LIVE,
        )
        return StateUpdateResult(
            disposition=disposition,
            status=MarketStateStatus.LIVE,
            sequence=frame.sequence,
        )

    def view(self) -> PartialBookView | None:
        return self._view

    def _require_instrument(self, incoming: InstrumentId) -> None:
        if incoming != self._instrument_id:
            raise InstrumentMismatchError(
                f"state owns {self._instrument_id}, received {incoming}"
            )


__all__ = ["PartialBookState"]
