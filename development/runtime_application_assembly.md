# Runtime Application Assembly

## Purpose

T015 closes the gap between the domain components and the synchronous
`TradingPipeline`. The composition root remains in `cex_quant.runtime`; domain
packages do not import runtime code.

## Concrete port adapters

### Feature engine

`FeatureEngineAdapter` invokes `OnlineFeatureEngine.on_event` and only then
returns `snapshot()`. Strategies therefore receive an immutable snapshot that
includes the current event's feature updates.

### Market state

`MarketStateGateAdapter` converts `StateUpdateResult` into `StateGate`.
Admission requires both:

- state status is `LIVE`; and
- disposition is `INITIALIZED`, `APPLIED`, or `IGNORED_STALE`.

Buffering, gaps, invalid state, and explicit rejection fail closed before
features or strategy code runs.

### OMS application service

`CanonicalOmsApplicationService` accepts only an allowed `RiskDecision` whose
intent exactly matches the supplied `PositionTargetIntent`. It does not guess
how a target position should become an order. The following policies are
mandatory constructor dependencies:

- `AccountPolicy`: selects the canonical account;
- `OmsIdentityPolicy`: creates approval and client-order identifiers;
- `OrderPolicy`: determines side, order type, quantity, prices, TIF, and
  derivative flags;
- `now_ns`: supplies the explicit order-creation time.

The service creates `ApprovedOrderIntent`, then `OrderRequest`, and owns one
`OrderStateMachine` for every unique client order ID. Duplicate IDs and
rejected or mismatched decisions are rejected before state creation.

### Async execution bridge

`AsyncExecutionPortBridge` gives the synchronous pipeline an `ExecutionPort`
while preserving the asynchronous `ExecutionGateway`.

The bridge owns a dedicated daemon thread and an asyncio event loop in that
thread. A synchronous caller submits with `run_coroutine_threadsafe` and waits
with a bounded timeout. Lifecycle is explicit through `start()` and `close()`.

Calling blocking `submit()` from a thread that already has a running asyncio
loop is rejected. An async host must run `TradingApplication.process` in a
worker/executor, or use the asynchronous gateway directly. This prevents
implicit blocking of an application event loop.

## Trading application

`TradingApplication` owns the bridge and assembles every mandatory
`TradingPipeline` dependency:

`health -> validation -> market state -> feature -> strategy -> portfolio ->
risk -> OMS -> execution`

Risk is a required constructor argument and there is no assembly path that
connects strategy directly to OMS or execution. A rejected risk decision ends
processing without creating an order or invoking the gateway.

The application must be started before `process`; its context-manager form is
the preferred lifecycle:

```python
with TradingApplication(...) as application:
    result = application.process(event)
```

No network implementation is required by this assembly. Tests use an
in-memory asynchronous gateway and verify the execution thread boundary.
