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
