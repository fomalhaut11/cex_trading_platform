# Trading pipeline acceptance scenarios

This suite is an offline, deterministic acceptance layer for the synchronous
trading path. It lives in `tests/acceptance/test_trading_pipeline.py` and uses
no network calls, sleeps, wall clock reads, credentials, or mutable global
state.

## Covered scenarios

- Happy path with the exact mandatory stage order:
  `health -> validation -> state -> feature -> strategy -> risk -> OMS ->
  execution`.
- Composition of the real market-data validator, L1 state, online feature
  engine, risk engine, OMS order state, and Binance request mapper.
- Fail-closed behavior for system health, risk-context clock health, canonical
  validation errors, and risk-limit rejection. None of these paths may invoke
  execution.
- Venue update idempotency, conflicting reuse of an update ID, cancel/fill
  racing, and terminal canceled-order behavior.
- Golden Binance Spot, USD-M, and COIN-M request mappings with exact
  fixed-point decimal strings and unchanged client order IDs.

## Deterministic ports

The composition root intentionally accepts protocols rather than concrete
application services. The tests therefore provide deterministic ports for:

- aggregate health;
- strategy policy;
- portfolio risk-context projection;
- synchronous execution acknowledgement.

These ports only supply data or bridge a runtime boundary. Domain behavior is
exercised through existing public APIs. The synchronous execution port calls
the real Binance mapper before returning its deterministic acknowledgement.

## Interface gaps observed

- `TradingPipeline` accepts a `FeaturePort` returning `FeatureSnapshot`, while
  `OnlineFeatureEngine.on_event()` returns `FeatureUpdateReport`. The acceptance
  adapter performs the natural two-step call: update, then `snapshot()`.
- There is no concrete application OMS service implementing
  `OmsPort.create_order(PositionTargetIntent, RiskDecision)`. The acceptance
  adapter creates the canonical `OrderRequest` and immediately instantiates
  the real `OrderStateMachine`.
- The runtime execution port is synchronous, whereas `ExecutionGateway` is
  asynchronous. The acceptance adapter validates the request with the real
  mapper and supplies an immediate deterministic `SubmitResult`.
- Market-state implementations return `StateUpdateResult`, while the runtime
  port expects `StateGate`. The adapter maps the real L1 `LIVE` status to the
  admission gate.

These are composition-layer adapter responsibilities, not reasons to modify
domain modules.
