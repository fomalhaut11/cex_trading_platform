# Binance Runtime Environment and Private-Stream Supervision

## Scope

T019 makes the T018 recovery boundary deployable without making production
trading the default. It owns:

- one immutable environment profile for Spot, USD-M and COIN-M endpoints;
- explicit acknowledgement before production endpoints can be constructed;
- process-level private-stream startup, readiness and shutdown state;
- interruptible private-stream reconnect supervision;
- a fail-closed gate around startup reconciliation.

Credentials are not configuration fields. They remain resolved through
`BinanceCredentialProvider` at the authenticated adapter boundary.

## Endpoint profiles

`BinanceEnvironmentConfig()` selects a Demo-backed non-production sandbox by
default. The public enum retains the compatibility value `TESTNET`, but the
selected endpoints are Binance Demo Mode for Spot, USD-M and COIN-M.
Production requires both `environment=PRODUCTION` and
`allow_production=True`; that acknowledgement is consumed during construction
and is not retained in the immutable value.

Each product profile contains REST, public WebSocket and private WebSocket
origins. Values must use `https` or `wss`, contain no URL credentials, query or
fragment, and match the allowlisted host for the selected product and
environment. Product slots and environments cannot be mixed.

The non-production hosts follow Binance's current documented Demo endpoints:
Spot uses `demo-api.binance.com`, `demo-stream.binance.com` and
`demo-ws-api.binance.com`; USD-M uses `demo-fapi.binance.com` and
`demo-fstream.binance.com`; COIN-M uses `demo-dapi.binance.com` and
`demo-dstream.binance.com`.

Binance still documents the independent `testnet.binance.vision` Spot network,
but describes it as a place to integrate upcoming Spot features. Demo Mode is
the default here because Binance describes it as matching live features and
using market data similar to the live exchange. This choice does not imply
that simulated fills or strategy returns predict production results.

## Lifecycle and readiness

`PrivateStreamApplication` is the asynchronous composition boundary:

1. transition from `NEW` to `STARTING`;
2. enable the bounded startup stream buffer;
3. start the private-stream supervisor and wait within a bound for a confirmed
   physical `ACTIVE` connection;
4. transition to `RECONCILING` and query recovered orders;
5. enter `READY` only when reconciliation reports `LIVE`;
6. otherwise enter `DEGRADED` or `FAILED` and keep trading closed.

An unexpected supervisor exit after readiness changes the application to
`FAILED`. A reconnect gap dynamically reports `DEGRADED` until the physical
connection is active again. Snapshots are immutable and expose state,
reconciliation evidence, an error summary and the derived `ready` flag.

Shutdown requests supervisor stop, cancels any active connection or backoff,
waits within a configured bound and converges the connection lifecycle to
`STOPPED`. A task that does not stop in time produces `FAILED`, never a false
successful shutdown.

## Reconnect behavior

The private-stream session records an injected monotonic connection time.
Factory and connected-session failures share a one-based consecutive-failure
counter and capped exponential backoff. A stop request interrupts both an
active transport and a pending delay. Consumer and keepalive tasks are always
cancelled and joined before the session returns.

Connection-age rotation remains a subsequent wiring task: the lifecycle now
contains a correct connection timestamp, but a production transport owner must
schedule rotation before Binance's connection-age limit.

## Verification

Offline unit and acceptance tests cover:

- default Demo-backed non-production selection and explicit production
  acknowledgement;
- all three product endpoint profiles and environment-mixing rejection;
- unsafe schemes, credentials in URLs and incorrect hosts;
- monotonic connection timestamps and consecutive exponential backoff;
- stop during an active connection and during reconnect delay;
- stream-first startup ordering and `LIVE`-only readiness;
- connection-start timeout and reconnect-gap degradation;
- degraded reconciliation, unexpected stream exit and bounded shutdown.

Authenticated endpoint handshakes, lease renewal and order recovery remain in
external gate A002C and require user-provided Demo credentials.

## Protocol references

- [Binance Spot Demo Mode](https://github.com/binance/binance-spot-api-docs/blob/master/demo-mode/general-info.md)
- [Binance Demo Trading access and API management](https://www.binance.com/en/support/faq/detail/9be58f73e5e14338809e3b705b9687dd)
- [Binance Spot Testnet comparison](https://developers.binance.com/en/docs/products/spot/testnet/general-info)
- [Binance USD-M general information](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info)
- [Binance COIN-M general information](https://developers.binance.com/en/docs/products/derivatives-trading-coin-futures/general-info)
