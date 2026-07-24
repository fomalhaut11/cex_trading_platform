"""Deterministic, standard-library-only offline performance harness."""

from __future__ import annotations

import gc
import hashlib
import json
import platform
import random
import sys
import tempfile
import threading
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    Price,
    Quantity,
    SchemaVersion,
    TimePrecision,
    TradeId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import (
    AggressorSide,
    BookLevel,
    MarketTrade,
    OrderBookDelta,
    PartialBookFrame,
    ReconstructedOrderBook,
)
from cex_quant.recorder import JsonLinesReader, JsonLinesRecorder, encode_event

DEFAULT_SEED = 20_260_723


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    event_count: int
    elapsed_seconds: float
    events_per_second: float
    peak_traced_bytes: int
    retained_traced_bytes: int
    digest: str
    thread_leaks: tuple[str, ...]
    artifact_bytes: int = 0


def environment_snapshot() -> dict[str, str | int]:
    """Return enough environment detail to make a sample interpretable."""

    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "logical_cpus": os_cpu_count(),
    }


def os_cpu_count() -> int:
    # Isolated for a cheap unit test without patching the stdlib.
    import os

    return os.cpu_count() or 1


def run_order_book_benchmark(
    event_count: int,
    *,
    seed: int = DEFAULT_SEED,
) -> BenchmarkResult:
    """Apply sequential deltas while retaining only a bounded price ladder."""

    if event_count <= 0:
        raise ValueError("event_count must be positive")
    instrument = _instrument()
    book = ReconstructedOrderBook(instrument_id=instrument)
    book.load_snapshot(
        PartialBookFrame(
            metadata=_metadata(0, "snapshot"),
            instrument_id=instrument,
            bids=tuple(_level(99_990 - offset, 100) for offset in range(10)),
            asks=tuple(_level(100_010 + offset, 100) for offset in range(10)),
            sequence=0,
        )
    )
    rng = random.Random(seed)
    digest = hashlib.sha256()
    before_threads = _thread_ids()
    gc.collect()
    tracemalloc.start()
    start_current, _ = tracemalloc.get_traced_memory()
    started = time.perf_counter()
    for sequence in range(1, event_count + 1):
        side = rng.getrandbits(1)
        slot = rng.randrange(10)
        quantity = 1 + rng.randrange(1_000)
        price = (99_990 - slot) if side == 0 else (100_010 + slot)
        level = _level(price, quantity)
        delta = OrderBookDelta(
            metadata=_metadata(sequence, "depth"),
            instrument_id=instrument,
            bids=(level,) if side == 0 else (),
            asks=(level,) if side == 1 else (),
            first_sequence=sequence,
            last_sequence=sequence,
            previous_sequence=sequence - 1,
        )
        result = book.apply(delta)
        digest.update(
            f"{sequence}:{side}:{slot}:{quantity}:{result.disposition}\n".encode()
        )
    elapsed = time.perf_counter() - started
    view = book.view()
    assert view is not None
    digest.update(repr(view).encode())
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    leaks = _thread_leaks(before_threads)
    return _result(
        "order_book",
        event_count,
        elapsed,
        peak - start_current,
        max(0, current - start_current),
        digest.hexdigest(),
        leaks,
    )


def run_recorder_benchmark(
    event_count: int,
    *,
    directory: Path,
    seed: int = DEFAULT_SEED,
) -> BenchmarkResult:
    """Record and stream-replay canonical events without retaining the stream."""

    if event_count <= 0:
        raise ValueError("event_count must be positive")
    if not directory.is_dir():
        raise ValueError("directory must already exist")
    rng = random.Random(seed)
    with tempfile.NamedTemporaryFile(
        dir=directory,
        prefix="performance-events-",
        suffix=".jsonl",
        delete=False,
    ) as temporary:
        path = Path(temporary.name)
    written_digest = hashlib.sha256()
    replay_digest = hashlib.sha256()
    before_threads = _thread_ids()
    gc.collect()
    tracemalloc.start()
    start_current, _ = tracemalloc.get_traced_memory()
    started = time.perf_counter()
    with JsonLinesRecorder(path) as recorder:
        for sequence in range(event_count):
            event = _trade(sequence, 99_000 + rng.randrange(2_000))
            encoded = encode_event(event)
            written_digest.update(encoded)
            recorder.append(event)
    write_elapsed = time.perf_counter() - started

    replay_started = time.perf_counter()
    replay_count = 0
    for event in JsonLinesReader(path).read():
        replay_digest.update(encode_event(event))
        replay_count += 1
    elapsed = write_elapsed + (time.perf_counter() - replay_started)
    if replay_count != event_count:
        raise AssertionError(f"replayed {replay_count}, expected {event_count}")
    if replay_digest.digest() != written_digest.digest():
        raise AssertionError("record/replay digest mismatch")
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    leaks = _thread_leaks(before_threads)
    return _result(
        "recorder_round_trip",
        event_count,
        elapsed,
        peak - start_current,
        max(0, current - start_current),
        replay_digest.hexdigest(),
        leaks,
        artifact_bytes=path.stat().st_size,
    )


def run_suite(
    *,
    event_count: int,
    seed: int = DEFAULT_SEED,
    directory: Path | None = None,
) -> dict[str, object]:
    """Run both workloads and return a JSON-serializable report."""

    if directory is None:
        with tempfile.TemporaryDirectory(prefix="cex-quant-perf-") as name:
            return run_suite(
                event_count=event_count,
                seed=seed,
                directory=Path(name),
            )
    results = (
        run_order_book_benchmark(event_count, seed=seed),
        run_recorder_benchmark(event_count, directory=directory, seed=seed),
    )
    return {
        "environment": environment_snapshot(),
        "seed": seed,
        "results": [asdict(result) for result in results],
    }


def report_json(report: dict[str, object]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def _result(
    name: str,
    count: int,
    elapsed: float,
    peak: int,
    retained: int,
    digest: str,
    leaks: tuple[str, ...],
    *,
    artifact_bytes: int = 0,
) -> BenchmarkResult:
    return BenchmarkResult(
        name=name,
        event_count=count,
        elapsed_seconds=elapsed,
        events_per_second=count / elapsed,
        peak_traced_bytes=peak,
        retained_traced_bytes=retained,
        digest=digest,
        thread_leaks=leaks,
        artifact_bytes=artifact_bytes,
    )


def _instrument() -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=InstrumentKind.PERPETUAL,
        symbol="BTCUSDT",
    )


def _metadata(sequence: int, channel: str) -> EventMetadata:
    timestamp = UnixNanos(1_700_000_000_000_000_000 + sequence)
    return EventMetadata(
        event_id=EventId(f"perf-{channel}-{sequence}"),
        event_time_ns=timestamp,
        receive_time_ns=UnixNanos(timestamp + 100),
        source=EventSource(venue=VenueId("BINANCE"), channel=channel),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.NANOSECOND,
        sequence=sequence,
    )


def _level(price_raw: int, quantity_raw: int) -> BookLevel:
    return BookLevel(
        price=Price(raw=price_raw, scale=2),
        quantity=Quantity(raw=quantity_raw, scale=3),
    )


def _trade(sequence: int, price_raw: int) -> MarketTrade:
    return MarketTrade(
        metadata=_metadata(sequence, "trade"),
        instrument_id=_instrument(),
        trade_id=TradeId(f"perf-trade-{sequence}"),
        price=Price(raw=price_raw, scale=2),
        quantity=Quantity(raw=100 + sequence % 900, scale=3),
        aggressor_side=(
            AggressorSide.BUY if sequence % 2 == 0 else AggressorSide.SELL
        ),
    )


def _thread_ids() -> set[int]:
    return {
        thread.ident
        for thread in threading.enumerate()
        if thread.ident is not None
    }


def _thread_leaks(before: set[int]) -> tuple[str, ...]:
    return tuple(
        sorted(
            thread.name
            for thread in threading.enumerate()
            if thread.ident is not None and thread.ident not in before
        )
    )


__all__ = [
    "DEFAULT_SEED",
    "BenchmarkResult",
    "environment_snapshot",
    "report_json",
    "run_order_book_benchmark",
    "run_recorder_benchmark",
    "run_suite",
]
