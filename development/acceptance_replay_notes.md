# Replay and recovery acceptance scenarios

This acceptance group is fully offline and uses fixed event data. It exercises
public APIs only and does not use wall-clock time or timing sleeps.

## Covered scenarios

- One canonical JSONL file is replayed into two fresh reconstructed books.
  Event counts, processing dispositions, final state, and a stable JSON/SHA-256
  digest must match.
- Snapshot/delta alignment, deletion, duplicate rejection, sequence gap,
  fail-closed `GAP`, crossed-book `INVALID`, `begin_resync`, buffered delta
  alignment, and return to `LIVE`.
- A truncated terminal JSONL record fails as `TRUNCATED_RECORD` at the exact
  line.
- Payload mutation without checksum regeneration fails as
  `CHECKSUM_MISMATCH` at the exact line, after earlier valid records are
  delivered.
- The bounded recorder handoff explicitly rejects overflow, preserves accepted
  event order, and stops without deadlock.
- A worker append failure is latched, observable in health state, propagated by
  `stop`, and does not strand the worker.

## Determinism boundary

The replay digest includes only canonical order-book values, sequence, status,
and update dispositions. It deliberately excludes object representations,
filesystem paths, thread scheduling, and system time.

## Public API gaps

None found for this acceptance group.
