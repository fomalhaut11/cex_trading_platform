# Binance authenticated execution adapter

## Scope

`AuthenticatedBinanceExecutionAdapter` is the authenticated boundary for
Binance Spot, USD-M Futures, and COIN-M Futures. It reuses the pure parameter
mapper and adds:

- account-scoped credential resolution;
- deterministic URL query encoding;
- HMAC-SHA256 signing;
- `timestamp` and bounded `recvWindow`;
- the `X-MBX-APIKEY` header;
- typed immediate acceptance, rejection, query, and unknown-state outcomes.

It does not implement an HTTP client, retry orders, send real orders during
tests, or infer Binance Options semantics.

## Security decisions

- Credentials are supplied by a `BinanceCredentialProvider`; they are not
  adapter configuration strings.
- `BinanceCredentials.__repr__` redacts both API key and secret.
- The secret is used only inside the signing operation and is never included
  in the HTTP request.
- Known transport errors and HTTP 5xx diagnostics are redacted before they
  cross the execution boundary.
- Request query strings contain signatures and must be treated as sensitive
  operational data even though they do not contain the secret.

## Determinism and timing

Parameters are sorted by key and percent-encoded before signing. The same
encoded byte sequence is transmitted, avoiding a mismatch between signing and
transport serialization. The clock is injected as a millisecond callable so
offline tests and deterministic replay do not read wall-clock time.

`recvWindow` must be from 1 through 60000 milliseconds and defaults to 5000.
Production configuration should normally use 5000 or less and only submit
when clock health is acceptable.

## Failure semantics

- HTTP 4xx with Binance error JSON is an immediate typed rejection.
- HTTP 5xx, including Binance `-1007`, is `ExecutionStateUnknownError`.
- A transport failure before any request bytes were sent is
  `ExecutionTransportError`.
- A transport failure after bytes may have been sent is
  `ExecutionStateUnknownError`.
- Malformed successful responses are transport errors.

Unknown state must be reconciled by query/user-data processing. It must not be
blindly retried as a new client order.

## Order query

The adapter implements a signed product-specific `GET` query using the
original client order identifier. Successful Spot, USD-M and COIN-M responses
are normalized to `OrderReconciliationSnapshot`. Binance error code `-2013`
means an explicit not-found observation and returns `None`; other HTTP 4xx
responses remain typed `ExecutionQueryError` failures.

The injected HTTP transport remains responsible for actual network I/O. Live
private-stream lifecycle and restart orchestration are separate application
responsibilities.

## References

- Binance Spot REST API, Request Security and signed HMAC examples:
  https://developers.binance.com/en/docs/products/spot/rest-api
- Binance USD-M Futures documentation:
  https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures
- Binance COIN-M Futures documentation:
  https://developers.binance.com/en/docs/products/derivatives-trading-coin-futures
