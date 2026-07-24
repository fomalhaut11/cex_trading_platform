# Market Data Architecture

## Data Flow

Exchange WebSocket / REST

→ Connector

→ Raw Message

→ Normalizer

→ Validator

→ Market State Engine

## Boundary Contracts

Connectors capture immutable `RawMarketMessage` values containing raw bytes,
source and the first local receive timestamp. Venue-owned normalizers decode
these messages into canonical events. Decode failures use typed
`NormalizationError` codes and do not include raw payloads in logs by default.

Canonical validation is deterministic and never repairs an event. Errors block
live state updates; warnings continue to the state engine while being emitted
to observability. Venue-specific checks remain inside the venue adapter.

Order-book frames use canonical ordering: bids descending and asks ascending.
Delta quantity zero means delete; frame quantities must be positive.

## Market State Modes

### L1

Best bid/ask only.

### Partial Book

Exchange-supplied depth snapshots such as depth 5, 10 or 20. Each accepted
frame atomically replaces the previous view; it is not merged as a delta.

### Reconstructed Book

Snapshot plus delta stream.

The state engine buffers a bounded number of deltas while the snapshot is in
flight. After loading a sequence-bearing snapshot it discards covered deltas
and requires the first applicable delta range to contain
`snapshot_sequence + 1`. Subsequent ranges must contain the next sequence and,
when the venue supplies it, `previous_sequence` must equal the current local
sequence.

Zero quantity deletes a level. Price identity uses exact decimal value, so
equivalent representations such as `100.0` and `100.00` address the same level.
Updates are applied to a candidate copy and published atomically only if the
result is not crossed.

Duplicate or fully covered deltas are ignored idempotently. A sequence gap
moves the state to `GAP`; a crossed candidate moves it to `INVALID`. Both
states reject further deltas until the owner calls `begin_resync`, obtains a
fresh snapshot and realigns the stream. Immutable views may retain the last
known-good levels for diagnosis, but their non-live status means they must not
drive trading.

Used for high-frequency market making, order-flow research and deep-book
strategies.

## Principle

Not every strategy requires full order book reconstruction. Market state
capability should match strategy requirements.

Each state instance owns exactly one `InstrumentId` and assumes a single
writer. Cross-instrument updates fail immediately. Readers receive frozen,
sorted views and cannot mutate authoritative state.
