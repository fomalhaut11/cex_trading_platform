# Order Schema

Order objects contain:

- client order ID and optional venue order ID;
- account, instrument, intent and approval identities;
- side, order type, quantity and exact prices;
- time-in-force, reduce-only, post-only and position-side instructions;
- canonical status, cumulative fill, remaining quantity and timestamps.

OMS owns lifecycle state.

`EXPIRED` is a distinct terminal status. It includes venue expiry outcomes such
as Binance `EXPIRED` and `EXPIRED_IN_MATCH`; it is not collapsed into
`CANCELED` or `REJECTED`.

Persistent recovery records use their own format version and encode exact
fixed-point values as integer `raw` plus decimal `scale`. REST responses and
user-stream reports must be normalized to `OrderReconciliationSnapshot`
before they cross into OMS.

The single-leg runtime uses a shared durable handoff:

```text
OrderCreated
  -> OrderSubmitting persisted and fsynced
  -> immediate runtime/operator health recheck
  -> external Execution submit
  -> immediate OrderSubmitOutcome persisted
  -> private-stream / reconciliation lifecycle facts
```

An accepted immediate result does not invent `OPEN`; the order stays
`SUBMITTING` until canonical venue evidence arrives. A definitely-not-sent
failure becomes local `FAILED`. A possibly-sent or untyped failure remains a
`SUBMITTING` reconciliation candidate.

The shared handoff requires an `ExternalSubmitGuardPort`; callers cannot
construct it without a post-durability/pre-I/O safety boundary. Guard
rejection and bridge failures known to occur before dispatch are recorded as
definitely not sent. A timeout or untyped failure after possible dispatch
remains unknown.

Multi-leg execution-control contracts are specified separately in
`interfaces/order_group_schema.md`. Existing `OrderRequest` and Execution
adapter input are unchanged.
