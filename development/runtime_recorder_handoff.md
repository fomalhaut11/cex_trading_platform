# Runtime Recorder Handoff

## Boundary

`RecorderHandoff` isolates the market-data hot path from the synchronous
`EventRecorder` storage contract. Producers only perform a bounded,
non-blocking queue insertion. Exactly one worker invokes `append` and `flush`,
so accepted event order is preserved without requiring recorder thread safety.

## Capacity and Overflow

Capacity is mandatory and positive. The explicit default policy is `REJECT`:
when full, `submit` raises `RecorderHandoffOverflowError` and increments the
rejection counter. Blocking producers, unbounded growth, overwriting old data
and silent drops are intentionally unsupported.

## Lifecycle

- `NEW -> RUNNING`: `start()` creates the sole recorder worker.
- `RUNNING -> DRAINING -> RUNNING`: `drain()` prevents new submissions, waits
  for all previously accepted events, then flushes.
- `RUNNING -> DRAINING -> STOPPED`: `stop()` drains, flushes and joins.
- A recorder exception moves the handoff to terminal `FAILED`.

Stopping a never-started handoff is safe, and stopping an already stopped
handoff is idempotent. After a failed worker has been joined, repeated
`stop()` calls immediately re-raise the latched failure and never enqueue work
to the terminated worker. Submissions outside `RUNNING` fail explicitly.

## Failure Visibility

The first append or flush exception is latched. The failed event and any
already-accepted events that cannot be persisted are counted as
`abandoned_after_failure`; later `submit`, `drain` and `stop` calls raise
`RecorderWorkerFailedError` with the original cause. The immutable snapshot
reports lifecycle, queue depth, accepted/appended/rejected/abandoned counters,
worker liveness, and the latched error type and message.

The snapshot is operational health evidence, not an acknowledgement of
durability. An event is durable only according to the recorder's configured
flush/fsync policy.
