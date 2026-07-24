# Runtime Pipeline Composition

T013 defines a synchronous, single-writer composition root. It does not add
domain rules; it makes their mandatory ordering explicit:

`health → validation → market state → feature → strategy → risk → OMS → execution`

Every external capability is supplied through a small `Protocol`. In
particular, portfolio access is read-only and execution is a synchronous port;
a live asynchronous transport is bridged outside this deterministic path.

## Safety invariants

- Only `HealthStatus.HEALTHY` admits an event.
- Invalid market data and non-live market state stop the path.
- Every strategy intent receives a risk decision.
- OMS is called only for an allowed decision belonging to that exact intent.
- Execution is called only for an OMS request belonging to that exact intent.
- A normal health, validation, state, or risk rejection is observable but does
  not corrupt pipeline lifecycle state.
- An exception in any stage, including recording, is latched. The pipeline
  enters `FAILED` and refuses all subsequent events.
- Stage traces are monotonically numbered and preserve actual call order.

The pipeline intentionally performs no network I/O and obtains no implicit
time. Replay and live operation therefore share the same orchestration logic.
