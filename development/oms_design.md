# OMS Foundation Design

## Boundary

OMS accepts only `ApprovedOrderIntent`, an immutable venue-neutral contract.
It intentionally lives in `cex_quant.oms` and has no import from a concrete
risk implementation. The approval contains the exact account, instrument,
side, order type, quantity, price instructions and derivatives flags that risk
approved. OMS rejects expired approvals when creating an `OrderRequest`.

`ClientOrderId` remains the strong identifier owned by `cex_quant.core`. OMS
adds it when converting an approval into an immutable request. Venue adapters
must normalize acknowledgements, fills and terminal outcomes into immutable
`OrderEvent` values before calling the state machine.

## Product coverage

All products use the same `InstrumentId`, including options. Spot orders must
use `PositionSide.NET` and cannot be reduce-only. Perpetuals, futures and
options may carry `reduce_only` and `NET`, `LONG` or `SHORT` position sides.
This foundation does not interpret contract multipliers; that belongs to
instrument, risk and portfolio calculations.

## State ownership

`OrderStateMachine` is the sole mutable owner of one canonical order. Its
creating thread owns all mutations; calls from another thread fail explicitly.
Readers receive a new frozen `OrderView`, so they cannot mutate canonical
state.

Lifecycle:

```text
CREATED -> SUBMITTING -> OPEN -> PARTIALLY_FILLED -> FILLED
                    \       \            \
                     \       +-------------> CANCEL_PENDING -> CANCELED
                      +---------------------> REJECTED / FAILED
```

Cancellation races are represented explicitly. A fill may move an order from
`CANCEL_PENDING` to `PARTIALLY_FILLED` or `FILLED`; a caller may request
cancellation again after a partial fill.

## Determinism and idempotency

- `venue_update_id` is the venue-update idempotency key.
- Replaying byte-for-byte equivalent normalized content returns `DUPLICATE`
  and makes no state change.
- Reusing an update ID with different content is a hard conflict.
- Cumulative fill is exact fixed-point data, never decreases and never exceeds
  requested quantity.
- Illegal transitions and mismatched client order IDs are rejected before
  mutation.
- Event time is retained as observation metadata but does not override venue
  lifecycle and cumulative-fill invariants; the visible last time never moves
  backwards.

## Deferred work

This foundation does not perform venue I/O, generate venue-specific payloads,
persist recovery journals, reconcile open orders after restart, or calculate
fees and portfolio positions. Those belong to later execution, recovery and
portfolio tasks.
