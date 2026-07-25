# Binance Transport Ownership and Clock Probing

## Scope

T020 closes the concrete I/O gap below the authenticated execution, private
stream and clock-health contracts. It adds:

- a bounded asyncio TLS/HTTP 1.1 transport for Binance REST requests;
- public server-time adapters for Spot, USD-M and COIN-M;
- an interruptible periodic clock-probe service with bounded evidence;
- owned Spot signature-subscription and Futures listen-key WebSocket
  transports.

The default suite remains deterministic and offline. T020 neither stores
credentials nor authorizes production or real-money trading.

## HTTP transport

`AsyncioBinanceHttpTransport` receives a product-to-REST-origin resolver from
the runtime composition layer. This preserves the dependency rule that
`execution` cannot import `runtime`.

Each request uses a fresh TLS connection and has independent connect, read and
total time limits. Response headers and bodies are bounded. Content-Length,
chunked and connection-close framing are supported; ambiguous or malformed
framing fails explicitly.

The transport validates the HTTPS origin, method, path, query and headers
before opening a socket. It owns the Host, Connection and Content-Length
headers. Control characters, authority-form paths, transport-owned headers and
URL credentials are rejected.

Failure classification is tied to the write boundary:

- endpoint resolution, DNS, TCP or TLS failure: `request_sent=False`;
- write, drain, response timeout, malformed response or total timeout after
  write begins: `request_sent=True`.

Errors use fixed messages and never include endpoint values, headers, query
strings, response bodies or underlying exception text.

## Server-time probing

The runtime adapter maps products to the public endpoints:

| Product | Path |
| --- | --- |
| Spot | `/api/v3/time` |
| USD-M | `/fapi/v1/time` |
| COIN-M | `/dapi/v1/time` |

Only HTTP 200 with a JSON object containing a non-negative integer
`serverTime` is accepted. The adapter starts and finishes the existing
`ClockHealthMonitor` probe around the request, preserving its wall/monotonic
midpoint calculation. Venue offset is observed for health; it does not rewrite
domain-event time.

`BinanceClockProbeService` probes immediately, then uses a fixed success
interval or capped exponential failure backoff. Stop interrupts an active
probe or delay. Its immutable snapshot retains bounded success/failure records
without response bodies or transport exception text.

## Private WebSocket ownership

Spot connects to the configured WebSocket API origin, sends the sensitive
`userDataStream.subscribe.signature` frame, waits within a bound for the
matching success response and consumes that handshake internally. Only later
account events cross the stream boundary.

Futures treats listen key, WebSocket connection and renewal task as one
resource. It opens a lease, connects to `/ws/<listenKey>`, renews in the
background and closes the lease in every normal, exceptional and cancellation
path. Renewal failure interrupts a blocked receive so the outer supervisor can
reconnect.

API keys, signatures and listen keys do not appear in representations or
errors. The connector is injected, so production can use the existing
`websockets` client while tests use deterministic fakes.

## Verification

Offline tests cover:

- all endpoint-selection and request-framing paths;
- connect/read/total timeout and before/after-send classification;
- response size, chunk and header failure paths;
- three-product clock paths, midpoint sampling, backoff and stop;
- Spot handshake isolation, failure redaction and timeout;
- Futures lease, renewal, cancellation and connection-failure cleanup;
- end-to-end Testnet profile to concrete HTTP transport to clock health.

The 2026-07-25 credential-free live smoke confirmed TLS/HTTP exchange with all
three configured Testnet origins, but Spot, USD-M and COIN-M each returned
HTTP 451. No clock sample was accepted. This is retained as external network
evidence, not converted into a passing Testnet gate or bypassed with production
endpoints.

## Protocol references

- [Binance Spot REST API](https://developers.binance.com/en/docs/products/spot/rest-api)
- [Binance Spot WebSocket API](https://developers.binance.com/en/docs/products/spot/web-socket-api)
- [Binance USD-M general information](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info)
- [Binance USD-M user data streams](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/user-data-streams)
- [Binance COIN-M general information](https://developers.binance.com/en/docs/products/derivatives-trading-coin-futures/general-info)
- [Binance COIN-M user data streams](https://developers.binance.com/en/docs/products/derivatives-trading-coin-futures/user-data-streams)
