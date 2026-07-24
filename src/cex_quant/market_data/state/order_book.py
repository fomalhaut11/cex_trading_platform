"""Sequence-aware reconstructed order book for one instrument."""

from decimal import Decimal

from cex_quant.core import UnixNanos
from cex_quant.instruments import InstrumentId
from cex_quant.market_data.events import (
    BookLevel,
    OrderBookDelta,
    PartialBookFrame,
)

from .model import (
    InstrumentMismatchError,
    MarketStateStatus,
    OrderBookView,
    StateBufferOverflowError,
    StateUpdateResult,
    UpdateDisposition,
)


class ReconstructedOrderBook:
    """Build a local book from a REST snapshot and ordered depth deltas.

    The engine is deliberately single-writer. A gap or crossed result makes the
    state non-live until ``begin_resync`` and a fresh snapshot are supplied.
    """

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        max_buffered_deltas: int = 10_000,
    ) -> None:
        if max_buffered_deltas <= 0:
            raise ValueError("max_buffered_deltas must be positive")
        self._instrument_id = instrument_id
        self._max_buffered_deltas = max_buffered_deltas
        self._bids: dict[Decimal, BookLevel] = {}
        self._asks: dict[Decimal, BookLevel] = {}
        self._buffer: list[OrderBookDelta] = []
        self._sequence: int | None = None
        self._as_of_ns: UnixNanos | None = None
        self._status = MarketStateStatus.EMPTY

    @property
    def status(self) -> MarketStateStatus:
        return self._status

    @property
    def sequence(self) -> int | None:
        return self._sequence

    @property
    def buffered_delta_count(self) -> int:
        return len(self._buffer)

    def apply(self, delta: OrderBookDelta) -> StateUpdateResult:
        """Buffer before initialization or atomically apply to a live book."""

        self._require_instrument(delta.instrument_id)
        if self._status in (MarketStateStatus.GAP, MarketStateStatus.INVALID):
            return self._result(
                UpdateDisposition.REJECTED,
                "state requires begin_resync and a fresh snapshot",
            )
        if self._sequence is None:
            self._buffer_delta(delta)
            self._status = MarketStateStatus.BUFFERING
            return self._result(UpdateDisposition.BUFFERED)
        return self._apply_live_delta(delta)

    def load_snapshot(self, snapshot: PartialBookFrame) -> StateUpdateResult:
        """Install a sequence-bearing snapshot and replay buffered deltas."""

        self._require_instrument(snapshot.instrument_id)
        if snapshot.sequence is None:
            raise ValueError("reconstructed-book snapshot requires a sequence")
        candidate_bids = _levels_by_price(snapshot.bids)
        candidate_asks = _levels_by_price(snapshot.asks)
        if _is_crossed(candidate_bids, candidate_asks):
            self._status = MarketStateStatus.INVALID
            return self._result(
                UpdateDisposition.REJECTED,
                "snapshot produces a crossed order book",
            )

        self._bids = candidate_bids
        self._asks = candidate_asks
        self._sequence = snapshot.sequence
        self._as_of_ns = snapshot.metadata.event_time_ns
        self._status = MarketStateStatus.LIVE

        buffered = self._buffer
        self._buffer = []
        for delta in buffered:
            if delta.last_sequence <= self._sequence:
                continue
            result = self._apply_live_delta(delta)
            if result.disposition in (
                UpdateDisposition.GAP_DETECTED,
                UpdateDisposition.REJECTED,
            ):
                return result
        return self._result(UpdateDisposition.INITIALIZED)

    def begin_resync(self) -> None:
        """Discard invalid state so new deltas and a fresh snapshot can align."""

        self._bids.clear()
        self._asks.clear()
        self._buffer.clear()
        self._sequence = None
        self._as_of_ns = None
        self._status = MarketStateStatus.EMPTY

    def view(self, *, depth: int | None = None) -> OrderBookView | None:
        """Return a frozen, sorted view; ``None`` until a snapshot is loaded."""

        if depth is not None and depth <= 0:
            raise ValueError("depth must be positive")
        if self._sequence is None or self._as_of_ns is None:
            return None
        bids = tuple(
            self._bids[key] for key in sorted(self._bids, reverse=True)
        )
        asks = tuple(self._asks[key] for key in sorted(self._asks))
        if depth is not None:
            bids = bids[:depth]
            asks = asks[:depth]
        return OrderBookView(
            instrument_id=self._instrument_id,
            bids=bids,
            asks=asks,
            as_of_ns=self._as_of_ns,
            sequence=self._sequence,
            status=self._status,
        )

    def _apply_live_delta(
        self,
        delta: OrderBookDelta,
    ) -> StateUpdateResult:
        assert self._sequence is not None
        if delta.last_sequence <= self._sequence:
            return self._result(
                UpdateDisposition.IGNORED_STALE,
                "delta does not advance the current sequence",
            )

        expected = self._sequence + 1
        if not delta.first_sequence <= expected <= delta.last_sequence:
            self._status = MarketStateStatus.GAP
            return self._result(
                UpdateDisposition.GAP_DETECTED,
                f"expected sequence {expected}, received "
                f"{delta.first_sequence}-{delta.last_sequence}",
            )
        if (
            delta.previous_sequence is not None
            and delta.previous_sequence != self._sequence
        ):
            self._status = MarketStateStatus.GAP
            return self._result(
                UpdateDisposition.GAP_DETECTED,
                f"expected previous sequence {self._sequence}, received "
                f"{delta.previous_sequence}",
            )

        candidate_bids = self._bids.copy()
        candidate_asks = self._asks.copy()
        _apply_levels(candidate_bids, delta.bids)
        _apply_levels(candidate_asks, delta.asks)
        if _is_crossed(candidate_bids, candidate_asks):
            self._status = MarketStateStatus.INVALID
            return self._result(
                UpdateDisposition.REJECTED,
                "delta produces a crossed order book",
            )

        self._bids = candidate_bids
        self._asks = candidate_asks
        self._sequence = delta.last_sequence
        self._as_of_ns = delta.metadata.event_time_ns
        self._status = MarketStateStatus.LIVE
        return self._result(UpdateDisposition.APPLIED)

    def _buffer_delta(self, delta: OrderBookDelta) -> None:
        if len(self._buffer) >= self._max_buffered_deltas:
            raise StateBufferOverflowError(
                f"buffer limit {self._max_buffered_deltas} exceeded"
            )
        self._buffer.append(delta)

    def _result(
        self,
        disposition: UpdateDisposition,
        reason: str | None = None,
    ) -> StateUpdateResult:
        return StateUpdateResult(
            disposition=disposition,
            status=self._status,
            sequence=self._sequence,
            reason=reason,
        )

    def _require_instrument(self, incoming: InstrumentId) -> None:
        if incoming != self._instrument_id:
            raise InstrumentMismatchError(
                f"state owns {self._instrument_id}, received {incoming}"
            )


def _levels_by_price(
    levels: tuple[BookLevel, ...],
) -> dict[Decimal, BookLevel]:
    return {level.price.as_decimal(): level for level in levels}


def _apply_levels(
    side: dict[Decimal, BookLevel],
    levels: tuple[BookLevel, ...],
) -> None:
    for level in levels:
        key = level.price.as_decimal()
        if level.quantity.raw == 0:
            side.pop(key, None)
        else:
            side[key] = level


def _is_crossed(
    bids: dict[Decimal, BookLevel],
    asks: dict[Decimal, BookLevel],
) -> bool:
    return bool(bids and asks and max(bids) > min(asks))


__all__ = ["ReconstructedOrderBook"]
