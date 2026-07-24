"""Acceptance scenarios for replay, recovery, and recorder failure handling."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    Price,
    Quantity,
    SchemaVersion,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    BookLevel,
    MarketEvent,
    MarketStateStatus,
    OrderBookDelta,
    PartialBookFrame,
    ReconstructedOrderBook,
    UpdateDisposition,
)
from cex_quant.recorder import (
    AppendResult,
    JsonLinesReader,
    JsonLinesRecorder,
    RecorderError,
    RecorderErrorCode,
    encode_event,
    replay,
)
from cex_quant.runtime import (
    RecorderHandoff,
    RecorderHandoffOverflowError,
    RecorderHandoffStatus,
    RecorderWorkerFailedError,
)

INSTRUMENT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)


def metadata(event_number: int) -> EventMetadata:
    return EventMetadata(
        event_id=EventId(f"acceptance-{event_number}"),
        event_time_ns=UnixNanos(1_700_000_000_000_000_000 + event_number),
        receive_time_ns=UnixNanos(1_700_000_000_000_001_000 + event_number),
        source=EventSource(venue=VenueId("BINANCE"), channel="depth"),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.NANOSECOND,
        sequence=event_number,
    )


def level(price: str, quantity: str) -> BookLevel:
    return BookLevel(
        price=Price.from_str(price),
        quantity=Quantity.from_str(quantity),
    )


def snapshot(sequence: int, *, event_number: int | None = None) -> PartialBookFrame:
    return PartialBookFrame(
        metadata=metadata(sequence if event_number is None else event_number),
        instrument_id=INSTRUMENT,
        bids=(level("100", "2"), level("99", "3")),
        asks=(level("101", "4"), level("102", "5")),
        sequence=sequence,
    )


def delta(
    first: int,
    last: int,
    *,
    previous: int | None,
    bids: tuple[BookLevel, ...] = (),
    asks: tuple[BookLevel, ...] = (),
) -> OrderBookDelta:
    return OrderBookDelta(
        metadata=metadata(last),
        instrument_id=INSTRUMENT,
        bids=bids,
        asks=asks,
        first_sequence=first,
        last_sequence=last,
        previous_sequence=previous,
    )


def canonical_stream() -> tuple[MarketEvent, ...]:
    return (
        snapshot(100),
        delta(
            101,
            101,
            previous=100,
            bids=(level("100", "0"), level("98", "7")),
            asks=(level("101", "6"),),
        ),
        delta(
            102,
            103,
            previous=101,
            bids=(level("99", "8"),),
            asks=(level("103", "9"),),
        ),
    )


class BookReplaySink:
    def __init__(self) -> None:
        self.book = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        self.dispositions: list[str] = []

    def on_event(self, event: MarketEvent) -> None:
        if isinstance(event, PartialBookFrame):
            result = self.book.load_snapshot(event)
        elif isinstance(event, OrderBookDelta):
            result = self.book.apply(event)
        else:
            raise AssertionError(f"unexpected event: {type(event).__name__}")
        self.dispositions.append(result.disposition.value)

    def digest(self) -> str:
        view = self.book.view()
        if view is None:
            raise AssertionError("replay did not initialize the order book")
        summary = {
            "asks": [
                [str(item.price.as_decimal()), str(item.quantity.as_decimal())]
                for item in view.asks
            ],
            "bids": [
                [str(item.price.as_decimal()), str(item.quantity.as_decimal())]
                for item in view.bids
            ],
            "dispositions": self.dispositions,
            "sequence": view.sequence,
            "status": view.status.value,
        }
        stable = json.dumps(
            summary,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(stable).hexdigest()


class GatedRecorder:
    """Recorder whose append completion is controlled without timing sleeps."""

    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.started = Event()
        self.release = Event()
        self.failure = failure
        self.events: list[MarketEvent] = []

    def append(self, event: MarketEvent) -> AppendResult:
        self.started.set()
        if not self.release.wait(timeout=2):
            raise AssertionError("acceptance test failed to release recorder")
        if self.failure is not None:
            raise self.failure
        self.events.append(event)
        return AppendResult(offset=len(self.events) - 1, byte_length=1)

    def flush(self) -> None:
        return None


class ReplayAndRecoveryAcceptanceTests(unittest.TestCase):
    def test_same_canonical_jsonl_replays_to_identical_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "canonical.jsonl"
            with JsonLinesRecorder(path) as recorder:
                for event in canonical_stream():
                    recorder.append(event)

            first = BookReplaySink()
            second = BookReplaySink()
            first_result = replay(JsonLinesReader(path), first)
            second_result = replay(JsonLinesReader(path), second)

        self.assertEqual(first_result.event_count, 3)
        self.assertEqual(first_result, second_result)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(
            first.dispositions,
            ["initialized", "applied", "applied"],
        )
        self.assertEqual(
            first.digest(),
            "1463649c55687d80087d04d5f3417a071b9ff7eedbc6b82504a935cfb634a7f5",
        )

    def test_book_duplicate_gap_invalid_and_resync_recovery(self) -> None:
        book = ReconstructedOrderBook(instrument_id=INSTRUMENT)
        book.load_snapshot(snapshot(100))
        advancing = delta(
            101,
            101,
            previous=100,
            bids=(level("100", "0"),),
        )
        self.assertEqual(book.apply(advancing).disposition, UpdateDisposition.APPLIED)
        self.assertEqual(
            book.apply(advancing).disposition,
            UpdateDisposition.IGNORED_STALE,
        )

        last_good = book.view()
        gap = book.apply(delta(103, 103, previous=102))
        self.assertEqual(gap.disposition, UpdateDisposition.GAP_DETECTED)
        self.assertEqual(book.status, MarketStateStatus.GAP)
        after_gap = book.view()
        self.assertEqual(after_gap.sequence, last_good.sequence)
        self.assertEqual(after_gap.bids, last_good.bids)
        self.assertEqual(after_gap.asks, last_good.asks)
        self.assertEqual(
            book.apply(delta(102, 102, previous=101)).disposition,
            UpdateDisposition.REJECTED,
        )

        book.begin_resync()
        book.load_snapshot(snapshot(200))
        crossed = book.apply(
            delta(201, 201, previous=200, bids=(level("103", "1"),))
        )
        self.assertEqual(crossed.disposition, UpdateDisposition.REJECTED)
        self.assertEqual(book.status, MarketStateStatus.INVALID)

        book.begin_resync()
        buffered = book.apply(
            delta(301, 301, previous=300, asks=(level("101", "7"),))
        )
        self.assertEqual(buffered.disposition, UpdateDisposition.BUFFERED)
        recovered = book.load_snapshot(snapshot(300))
        self.assertEqual(recovered.disposition, UpdateDisposition.INITIALIZED)
        self.assertEqual(book.status, MarketStateStatus.LIVE)
        self.assertEqual(book.sequence, 301)
        self.assertEqual(book.view().asks[0].quantity.as_decimal(), 7)

    def test_truncation_and_checksum_corruption_fail_at_exact_record(self) -> None:
        first, second = canonical_stream()[:2]
        with tempfile.TemporaryDirectory() as directory:
            truncated_path = Path(directory) / "truncated.jsonl"
            truncated_path.write_bytes(encode_event(first))
            with self.assertRaises(RecorderError) as truncated:
                tuple(JsonLinesReader(truncated_path).read())
            self.assertEqual(
                truncated.exception.code,
                RecorderErrorCode.TRUNCATED_RECORD,
            )
            self.assertEqual(truncated.exception.line_number, 1)

            corrupt_path = Path(directory) / "corrupt.jsonl"
            raw = json.loads(encode_event(second))
            raw["payload"]["last_sequence"] += 1
            corrupt = json.dumps(
                raw,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            corrupt_path.write_bytes(encode_event(first) + b"\n" + corrupt + b"\n")
            reader = iter(JsonLinesReader(corrupt_path).read())
            self.assertEqual(next(reader), first)
            with self.assertRaises(RecorderError) as checksum:
                next(reader)
            self.assertEqual(
                checksum.exception.code,
                RecorderErrorCode.CHECKSUM_MISMATCH,
            )
            self.assertEqual(checksum.exception.line_number, 2)

    def test_bounded_handoff_overflow_is_explicit_and_stop_completes(self) -> None:
        recorder = GatedRecorder()
        handoff = RecorderHandoff(recorder, capacity=1)
        handoff.start()
        events = canonical_stream()
        handoff.submit(events[0])
        self.assertTrue(recorder.started.wait(timeout=2))
        handoff.submit(events[1])
        with self.assertRaises(RecorderHandoffOverflowError):
            handoff.submit(events[2])

        stopped = Event()
        stop_errors: list[BaseException] = []

        def stop_handoff() -> None:
            try:
                handoff.stop()
            except BaseException as error:
                stop_errors.append(error)
            finally:
                stopped.set()

        stopper = Thread(target=stop_handoff)
        stopper.start()
        recorder.release.set()
        self.assertTrue(stopped.wait(timeout=2), "handoff stop deadlocked")
        stopper.join(timeout=2)
        self.assertEqual(stop_errors, [])
        self.assertEqual(recorder.events, list(events[:2]))
        state = handoff.snapshot()
        self.assertEqual(state.status, RecorderHandoffStatus.STOPPED)
        self.assertEqual(state.rejected_overflow, 1)
        self.assertFalse(state.worker_alive)

    def test_worker_failure_is_latched_and_stop_does_not_deadlock(self) -> None:
        failure = OSError("acceptance disk failure")
        recorder = GatedRecorder(failure=failure)
        handoff = RecorderHandoff(recorder, capacity=1)
        handoff.start()
        handoff.submit(canonical_stream()[0])
        self.assertTrue(recorder.started.wait(timeout=2))
        recorder.release.set()

        stop_done = Event()
        stop_errors: list[BaseException] = []

        def stop_handoff() -> None:
            try:
                handoff.stop()
            except BaseException as error:
                stop_errors.append(error)
            finally:
                stop_done.set()

        stopper = Thread(target=stop_handoff)
        stopper.start()
        self.assertTrue(stop_done.wait(timeout=2), "failed worker stop deadlocked")
        stopper.join(timeout=2)
        self.assertEqual(len(stop_errors), 1)
        self.assertIsInstance(stop_errors[0], RecorderWorkerFailedError)
        self.assertIs(stop_errors[0].cause, failure)
        state = handoff.snapshot()
        self.assertEqual(state.status, RecorderHandoffStatus.FAILED)
        self.assertFalse(state.healthy)
        self.assertFalse(state.worker_alive)
        self.assertEqual(state.abandoned_after_failure, 1)


if __name__ == "__main__":
    unittest.main()
