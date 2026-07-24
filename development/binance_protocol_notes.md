# Binance Market Data Protocol Notes

Verified against official Binance documentation on 2026-07-23.

## Product Routes

The adapter distinguishes spot, USD-M futures, COIN-M futures and options at
construction time. Venue symbols resolve through an explicit product-aware
instrument table; symbol parsing is not used as domain identity.

## Initial Stream Support

- Spot `trade`
- Spot and futures `aggTrade`
- Spot and futures `bookTicker`
- Spot and futures `depthUpdate`
- Spot combined partial-depth frames
- Spot and futures `kline`
- Futures `markPriceUpdate`, split into mark, index and funding facts

Raw and combined stream wrappers are supported. Canonical book sides are sorted
after decoding. Binance's buyer-maker flag is converted to aggressor side: true
means the aggressive side sold; false means it bought.

## Time Semantics

Venue transaction time is preferred over event publication time when present.
Spot JSON streams default to milliseconds and may be configured for
microseconds. Spot `bookTicker` does not publish an event timestamp, so its
canonical event time explicitly uses the local receive clock and records
`EventTimeSource.RECEIVE_CLOCK`.

## Depth Semantics

Diff-depth events preserve first and final update IDs. Futures `pu` is retained
as `previous_sequence`. Zero quantity remains a deletion instruction. Snapshot
plus delta synchronization belongs to the Market State Engine and is not
performed by the normalizer.

## Instrument Discovery

Spot, USD-M and COIN-M `exchangeInfo` payloads map to canonical instruments.
Price and quantity increments come only from `PRICE_FILTER.tickSize` and
`LOT_SIZE.stepSize`; Binance precision display fields are never used as trading
increments.

USD-M contracts are linear. COIN-M contracts are inverse and retain
`contractSize` with its quote-asset unit through `contract_size_asset`.

## Connection Runtime

Combined-stream URIs are validated and bounded. The production transport uses
`websockets` 16.1.x with a bounded receive queue and sequential downstream
awaits. Client-initiated heartbeat pings are disabled; the library still
automatically answers Binance server ping frames.

Connections use an explicit lifecycle state machine, capped exponential
backoff, caller-supplied deterministic jitter and proactive rotation before the
documented 24-hour Spot connection limit.

## Official References

- https://developers.binance.com/en/docs/products/spot/testnet/web-socket-streams
- https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/Introduction
- https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#exchange-information
- https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/rest-api/market-data#exchange-information
- https://developers.binance.com/en/docs/catalog
