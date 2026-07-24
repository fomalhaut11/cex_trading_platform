# Offline Performance and Stability Baseline

Date: 2026-07-23  
Scope: A002, offline only (no Binance Testnet)

## Purpose

This baseline verifies that the current synchronous core can process a
long, deterministic stream without retaining the stream in memory, leaking
threads, or changing its result. It is a development-machine measurement, not
a production latency SLA.

The benchmark is opt-in and uses only the Python standard library plus the
project itself:

```powershell
$env:PYTHONPATH = "src"
python -m tools.performance.run_baseline --events 100000
```

Heavy workloads live under `tools/performance/` and are not run by ordinary
`unittest discover`. `tests/performance/` contains only small harness tests.

## Workloads

### Reconstructed order book

- Loads one sequence-bearing snapshot.
- Applies 100,000 continuous canonical `OrderBookDelta` events.
- Uses a fixed ten-level ladder per side, so retained state must be independent
  of event count.
- Uses a fixed pseudo-random seed.
- Hashes every applied update and the final immutable view.
- Checks for threads created by the workload and still present at completion.

### Recorder round trip

- Creates, encodes, and appends 100,000 canonical `MarketTrade` events.
- Flushes/closes the recorder, then replays with a streaming iterator.
- Does not collect replayed events in a list.
- Compares the SHA-256 digest of the written canonical encodings with the
  digest of replayed encodings.
- Measures the combined record plus replay time.
- Checks for threads left behind.

Both workloads use `tracemalloc`; reported throughput therefore includes
memory-instrumentation overhead.

## Measured environment

| Item | Value |
|---|---|
| OS | Windows 11, build 10.0.26200 |
| Python | CPython 3.14.2 |
| Processor | AMD64 Family 25 Model 68, AuthenticAMD |
| Logical CPUs | 16 |
| Seed | 20260723 |

## Results

| Workload | Events | Elapsed | Throughput | Peak traced | Retained traced | Output size | Thread leaks |
|---|---:|---:|---:|---:|---:|---:|---:|
| Order book | 100,000 | 5.163 s | 19,369 events/s | 10,547 B | 4,994 B | n/a | 0 |
| Recorder + replay | 100,000 | 80.469 s | 1,243 events/s | 155,146 B | 3,141 B | 69,266,966 B | 0 |

Deterministic digests:

- Order book:
  `5e8e6171605801817938941f84e4c2fcdd49c6239f8cae1b8b1c175685bd238d`
- Recorder/replay:
  `31f3f712b1c9df90de661a6dfb3719b3cf6cc30ae1cdf04115c96533d1b53a7e`

The recorder workload's matching pre-write and post-replay digest proves
round-trip ordering/content for this stream. The low retained traced memory and
fixed order-book ladder demonstrate bounded retained Python allocations for
these scenarios. This does not measure operating-system page cache or native
allocator memory.

## Acceptance interpretation

This run passes the A002 offline baseline:

- 100,000 events completed in each workload.
- Recorder replay count and digest match the recorded stream.
- The order-book digest is reproducible for the same seed.
- Neither workload leaves a thread behind.
- Retained traced memory is below the lightweight harness guard of 2 MB.
- Recorder/replay is streaming; the 69 MB artifact is not retained in memory.

No hard p99 latency claim is made. The current harness measures aggregate
throughput with memory tracing enabled and does not yet collect per-event
latency histograms.

## Setting production gates

Establish performance gates only on the selected deployment hardware, Python
version, storage class, durability policy, and representative event mix:

1. Run at least five warm repetitions with and without `tracemalloc`.
2. Separate recorder write, flush/fsync, and replay measurements.
3. Record median and p95/p99 distributions using monotonic nanosecond timing,
   while limiting instrumentation overhead.
4. Test normal load, expected peak load, and an agreed burst multiplier.
5. Set the gate from the slower confidence bound plus an explicit safety
   margin; store the raw JSON with the build metadata.
6. Repeat the memory test at increasing event counts and compare retained
   memory slopes, not just one absolute peak.

The baseline should be rerun after changes to event encoding, order-book state,
Python runtime, disk durability settings, or target hardware.

