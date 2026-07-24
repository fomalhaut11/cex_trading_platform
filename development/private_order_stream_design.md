# Private Order Stream and Startup Reconciliation

## Scope

T018 closes the deterministic application boundary between authenticated
Binance private order events and the restart-safe OMS. It provides:

- current Spot WebSocket API signature-subscription mapping;
- USD-M and COIN-M listenKey creation, renewal and closure;
- private event classification and order normalization;
- bounded renewal and reconnect supervision;
- a bounded startup race buffer;
- REST query and buffered-stream convergence before trading readiness.

The default test suite remains offline. Actual credentials, endpoint selection
and Testnet evidence are external acceptance concerns.

## Product-specific authentication

Spot and Futures deliberately do not share a fictional authentication flow.

Spot uses the current WebSocket API
`userDataStream.subscribe.signature` request. The request contains the API key,
timestamp, receive window and signature and must therefore be handled as
sensitive operational data. The returned `subscriptionId` is validated against
the caller's request identity.

USD-M and COIN-M use API-key-authenticated listenKey control endpoints:

| Product | Endpoint |
| --- | --- |
| USD-M | `/fapi/v1/listenKey` |
| COIN-M | `/dapi/v1/listenKey` |

`POST`, `PUT` and `DELETE` create, extend and close the lease. Listen keys are
opaque, redacted from representations and only exposed when constructing the
configured WebSocket URI. Binance error `-1125` is a typed lease-expired
outcome that requires a new lease.

## Session and reconnect behavior

`PrivateOrderStreamSession` processes one authorized physical connection.
Order events are normalized sequentially and delivered with backpressure.
Account-only events are ignored by the order path. `serverShutdown`,
`eventStreamTerminated` and `listenKeyExpired` request connection rotation.

Futures keepalive is scheduled concurrently with message consumption. Renewal
failure closes the connection and transitions the lifecycle to reconnect
waiting. `PrivateOrderStreamSupervisor` recreates the authorized transport
using the existing capped reconnect policy. Factory/authentication failures
use the same backoff path.

T019 made the supervisor stop path interruptible. A stop request now cancels
an active connection or reconnect delay, joins consumer and renewal tasks, and
converges the connection lifecycle to `STOPPED`.

## Startup ordering

The startup coordinator uses this order:

1. enter bounded stream buffering before REST recovery queries;
2. query every recovered non-terminal OMS order by original client order ID;
3. merge REST observations and buffered stream observations by venue time;
4. apply them through the normal durable OMS reconciliation method;
5. switch the stream callback to live application.

Buffer overflow, identity mismatch or reconciliation conflict fails closed.
REST not-found and typed query failures produce `DEGRADED`, not trading-ready.
A successful query may still report an open order; readiness means its state
was observed and converged, not that every order is terminal.

## Verification

Offline tests cover:

- Spot signature and subscription-response identity;
- Futures create/renew/close paths and secret redaction;
- order, ignored-account and forced-rotation frames;
- keepalive success and failure;
- reconnect after stream rotation and authorization failure;
- events arriving while REST queries are in flight;
- not-found/query-failure degradation;
- bounded-buffer overflow;
- durable restart after REST plus buffered-stream convergence.

## Protocol references

- [Binance Spot WebSocket API](https://developers.binance.com/en/docs/products/spot/web-socket-api)
- [Binance Spot user data streams](https://developers.binance.com/en/docs/products/spot/user-data-stream)
- [Official Spot API changelog](https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md)
- [Binance COIN-M user data streams](https://developers.binance.com/en/docs/products/derivatives-trading-coin-futures/user-data-streams)
