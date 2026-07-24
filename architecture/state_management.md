# State Management

## State Categories

1.  Market State
2.  Feature State
3.  Model Output State
4.  Order State
5.  Account Position State
6.  Health State

## Event vs State

Event: what happened.

State: current system knowledge.

Storage: historical record.

Events update states.

## Market-State Lifecycle

L1 state stores the latest best bid/ask. Exchange partial depth is an atomic
replace-only view. Reconstructed depth has the following lifecycle:

`EMPTY -> BUFFERING -> LIVE -> GAP | INVALID -> EMPTY`

- `BUFFERING` is bounded and exists while a snapshot is being fetched.
- `LIVE` is the only state eligible for trading reads.
- `GAP` means sequence continuity was lost.
- `INVALID` means applying a candidate update would violate book invariants.
- recovery is explicit: clear with `begin_resync`, then align a fresh snapshot
  with newly buffered deltas.

Mutable maps and buffers have one writer. Published views are immutable.
Failed, crossed or discontinuous deltas never partially mutate the last
known-good book.
