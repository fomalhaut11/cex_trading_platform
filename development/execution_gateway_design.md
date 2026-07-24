# Execution Gateway Design

## Responsibility

The Execution Gateway translates canonical OMS commands into venue requests.
It does not own canonical order state, signing keys, clocks, retries, HTTP
connections, or exchange response reconciliation.

`ExecutionGateway` consumes the OMS-owned `OrderRequest` and is an
asynchronous protocol with two operations:

- `submit(OrderRequest) -> SubmitResult`
- `cancel(CancelOrder) -> CancelResult`

Every submission carries a non-empty `ClientOrderId`. This identifier is the
idempotency key and adapters must pass it across the venue boundary unchanged.
Cancellation uses that same original client identifier.

## Canonical command rules

- The OMS owns side, type, time-in-force and position-side enums and validates
  their canonical combinations; Execution does not duplicate those types.
- The initial Binance mapper accepts `MARKET` and `LIMIT`.
- `STOP_MARKET`, `STOP_LIMIT` and post-only/`GTX` remain explicit unsupported
  features until their full trigger and product semantics are implemented.
- `PositionSide.NET` maps to Binance Futures `BOTH`.
- `LONG` and `SHORT` represent hedge-mode position legs.

Typed gateway failures distinguish invalid input, unsupported features,
definite transport failure, and an unknown post-send execution state. An
unknown state must be reconciled by client order ID and must not be treated as
a safe instruction to submit a fresh identity. Immediate results contain only
definite `ACCEPTED` or `REJECTED` outcomes; unknown state is exclusively a
typed exception so callers cannot accidentally handle it as a venue response.

## Binance pure mapping boundary

The Binance mapper emits immutable method, path and string parameters only:

| Product | Submit / cancel path | Client ID fields |
| --- | --- | --- |
| Spot | `/api/v3/order` | `newClientOrderId` / `origClientOrderId` |
| USD-M | `/fapi/v1/order` | `newClientOrderId` / `origClientOrderId` |
| COIN-M | `/dapi/v1/order` | `newClientOrderId` / `origClientOrderId` |

Exact fixed-point formatting preserves the canonical scale; binary floats
never enter request construction. Timestamp, receive window, API key,
signature, encoding and network I/O are deliberately added by a later
transport layer.

Spot requires the OMS-valid non-reducing `NET` semantics. Futures maps
`positionSide`; `reduceOnly=true` is emitted only when requested. Binance
Futures forbids `reduceOnly` in hedge position mode, so the mapper rejects that
combination before transport.

The canonical interface can carry option orders, but no Binance Options
request mapper is provided in this milestone. This avoids inventing API
semantics without an explicitly verified product contract.

## Verification

Offline tests cover command invariants, closed enum validation, exact decimal
strings, product endpoints, idempotent client ID propagation, immutable
request parameters, Spot/Futures feature differences, hedge-mode legality,
instrument/product mismatches and the intentional absence of an options
mapping.

## Protocol references

- [Binance Spot REST trading endpoints](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- [Binance USD-M Futures API](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/Introduction)
- [Binance COIN-M Futures API reference](https://binance-docs.github.io/apidocs/delivery/en/)
