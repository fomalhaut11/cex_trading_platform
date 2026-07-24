# Risk Engine Design

## Scope

T009 is a deterministic, fail-closed pre-trade policy for
`PositionTargetIntent`. It approves or rejects an intent and never creates,
routes, or mutates an order. Portfolio snapshots, rolling intent counters,
clock health, and market/feature timestamps are supplied by the caller; the
engine performs no I/O and owns no mutable state.

## Contracts

- `RiskLimits` is an immutable policy snapshot. Position, notional, intent
  frequency, and freshness limits are explicit.
- `RiskContext` is the complete point-in-time evaluation input.
- `RiskDecision` is immutable and exactly `ALLOW` or `REJECT`. Rejections have
  stable machine-readable reasons.
- A target replaces the strategy's current contribution. Therefore:
  `projected_global = current_global + target - current_strategy`.
- Equality at an exposure limit is allowed. An intent-rate count equal to its
  maximum is rejected because that count represents already accepted intents
  in the current caller-owned window.

## Fail-closed inputs

Evaluation rejects an absent/non-positive reference price, absent or stale
market data, absent/stale/expired/non-good required features, any non-healthy
clock state, inactive instruments, mismatched identities, and future or
expired intents. A strategy that genuinely requires no features must opt out
through `require_fresh_features=False`; this choice is explicit in the policy.

## Exact notional semantics

All comparisons use `Decimal` obtained from fixed-point domain values.

- Spot: `abs(target base quantity) * reference price`.
- Linear future/perpetual:
  `abs(contract quantity) * contract_size(base) * reference price`.
- Inverse future/perpetual:
  `abs(contract quantity) * contract_size(quote)`; reference price is still
  mandatory as market-health evidence but does not change quote notional.
- Option: `abs(contract quantity) * contract_size(underlying) *
  underlying reference price`.
- Quanto contracts are rejected as unsupported until an explicit conversion
  price and settlement-asset convention are added.

Notional caps are expressed in the instrument quote/reference asset. Cross-
asset global aggregation is intentionally outside this core; the caller must
provide a consistently denominated aggregate or evaluate per asset.

## Deliberate follow-ups

- Position and accepted-intent stores, rolling-window accounting, portfolio
  aggregation, and kill switches belong to runtime/portfolio integration.
- Delta/order sizing, venue filters, and order construction belong to OMS.
- Options portfolio Greeks and scenario limits can extend `RiskContext` and
  `RiskLimits` without changing the binary decision boundary.
