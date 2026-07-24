# Portfolio and Account State

## Scope and ownership

`AccountState` is the single writer for one `(venue, account)` pair. It binds
mutation to its construction thread, is lock-free, and performs no I/O. Other
components consume immutable `AccountSnapshot` values rather than internal
dictionaries.

The module stores normalized values supplied by a venue adapter. It does not
calculate margin, mark-to-market value, Greeks, option surfaces, liquidation
prices, or cross-asset collateral value.

## Update contract

`AccountUpdate` is an atomic collection of absolute balance and position
values. An omitted entity is unchanged; a supplied entity replaces its prior
value. Absolute values prevent double accounting when fill events and account
streams overlap.

`venue_update_id` is the idempotency key:

- identical reuse is a duplicate and has no effect;
- reuse with different content raises `AccountUpdateConflictError`;
- remembered IDs are bounded; sequence/time ordering remains the backstop.

If the feed supplies sequence numbers, they become mandatory after the first
sequenced update and must increase strictly. Before that, unsequenced updates
use event time and reject only strictly older values. Equal timestamps are
allowed because independent venue updates can share timestamp precision.
Sequence is authoritative after activation; the snapshot `as_of_time_ns`
nevertheless never regresses when a later sequence carries an older timestamp.

## Numeric semantics

- Balance amounts are exact fixed point, non-negative, and require
  `total == available + locked`.
- Position quantity is signed: positive is long and negative is short.
- Cost basis is a non-negative venue-supplied absolute amount denominated in
  `pnl_asset`.
- Realized PnL is a signed venue-supplied amount denominated in `pnl_asset`.
- A non-flat position requires a positive average entry price.
- Spot, linear, inverse, and option accounting are represented explicitly.
- Quanto position accounting raises `NotImplementedError` at the contract
  boundary until its multiplier, currency, and PnL rules are designed.

Snapshots sort balances by asset and positions by canonical instrument ID, so
serialization and offline replay comparisons are deterministic.
