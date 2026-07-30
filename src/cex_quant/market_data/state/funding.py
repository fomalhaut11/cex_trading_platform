"""Single-writer latest Funding market state for one perpetual instrument."""

from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data.events import FundingRateUpdate

from .model import (
    FundingView,
    InstrumentMismatchError,
    MarketStateStatus,
    StateUpdateResult,
    UpdateDisposition,
)


class FundingRateState:
    """Own the latest normalized Funding fact and publish an immutable view."""

    def __init__(self, *, instrument_id: InstrumentId) -> None:
        if instrument_id.kind is not InstrumentKind.PERPETUAL:
            raise ValueError("Funding state requires a perpetual instrument")
        self._instrument_id = instrument_id
        self._view: FundingView | None = None

    @property
    def status(self) -> MarketStateStatus:
        return (
            MarketStateStatus.EMPTY
            if self._view is None
            else MarketStateStatus.LIVE
        )

    def apply(self, event: FundingRateUpdate) -> StateUpdateResult:
        if event.instrument_id != self._instrument_id:
            raise InstrumentMismatchError(
                f"state owns {self._instrument_id}, received "
                f"{event.instrument_id}"
            )
        if (
            event.next_funding_time_ns is not None
            and event.next_funding_time_ns < event.metadata.event_time_ns
        ):
            raise ValueError("next Funding time precedes the observation")
        sequence = event.metadata.sequence
        if self._view is not None and _is_stale(
            current_sequence=self._view.source_sequence,
            current_time_ns=self._view.as_of_ns,
            incoming_sequence=sequence,
            incoming_time_ns=event.metadata.event_time_ns,
        ):
            return StateUpdateResult(
                disposition=UpdateDisposition.IGNORED_STALE,
                status=MarketStateStatus.LIVE,
                sequence=self._view.source_sequence,
                reason="Funding event does not advance sequence or event time",
            )
        disposition = (
            UpdateDisposition.INITIALIZED
            if self._view is None
            else UpdateDisposition.APPLIED
        )
        self._view = FundingView(
            instrument_id=self._instrument_id,
            funding_rate=event.funding_rate,
            next_funding_time_ns=event.next_funding_time_ns,
            event_id=event.metadata.event_id,
            as_of_ns=event.metadata.event_time_ns,
            received_at_ns=event.metadata.receive_time_ns,
            source_sequence=sequence,
            status=MarketStateStatus.LIVE,
        )
        return StateUpdateResult(
            disposition=disposition,
            status=MarketStateStatus.LIVE,
            sequence=sequence,
        )

    def view(self) -> FundingView | None:
        return self._view


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


__all__ = ["FundingRateState"]
