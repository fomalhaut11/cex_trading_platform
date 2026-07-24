# Binance Reconciliation Adapter

## Scope

The Binance reconciliation adapter converts authenticated order-query
responses and private order updates into the venue-neutral
`OrderReconciliationSnapshot` consumed by OMS. Binance-native payloads,
status strings and product-specific field names stop at this boundary.

The supported products are Spot, USD-M Futures and COIN-M Futures. Binance
Options are intentionally outside this milestone.

## Query contract

`QueryOrder` always carries the original canonical `ClientOrderId`.
`AuthenticatedBinanceExecutionAdapter.query_order()` signs a `GET` request:

| Product | Path | Identity field |
| --- | --- | --- |
| Spot | `/api/v3/order` | `origClientOrderId` |
| USD-M | `/fapi/v1/order` | `origClientOrderId` |
| COIN-M | `/dapi/v1/order` | `origClientOrderId` |

A successful response is normalized immediately. Binance error code `-2013`
is returned as an explicit not-found observation (`None`); it does not invent
a rejected or cancelled terminal state. Other business errors, transport
failures and unknown post-send outcomes remain typed failures.

## Event normalization

Spot `executionReport` events and Futures `ORDER_TRADE_UPDATE` events normalize
through the same contract as REST queries. Both the direct Spot event and the
new WebSocket API `{subscriptionId, event}` envelope are accepted.

Status mapping includes pending-new, open, partially filled, filled,
cancel-pending, cancelled, rejected and expired states. Binance
`EXPIRED_IN_MATCH` maps to the distinct canonical `EXPIRED` terminal state.

Cumulative quantities use exact fixed-point parsing. Spot average fill price
is derived from cumulative quote quantity divided by cumulative base fill;
Futures uses the venue average-price field. Zero fill produces no average
price.

Every observation has a deterministic source update identifier built from
venue order and update/execution identity. If a REST response omits update
time, its status and cumulative fill form the stable fallback instead of the
local receive time. OMS can therefore discard duplicate REST or stream
observations without depending on arrival order.

Malformed messages, unsupported events and client-order identity mismatches
raise typed normalization errors. The adapter never silently accepts a report
for a different canonical order.

## Remaining live boundary

The deterministic mapping and offline restart scenario are complete. A live
authenticated private-stream subscription, listen-key/session renewal,
reconnect coordination and startup query orchestration remain part of the
Testnet and operational acceptance work.

## Protocol references

- [Binance Spot query order](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/account)
- [Binance Spot user data stream](https://developers.binance.com/en/docs/products/spot/user-data-stream)
- [Binance USD-M query order](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/trade#query-order)
- [Binance COIN-M query order](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/rest-api/trade#query-order)
