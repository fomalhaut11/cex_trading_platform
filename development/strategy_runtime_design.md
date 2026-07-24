# Strategy Runtime Design

## Scope

The first strategy runtime is a synchronous, single-writer component. It
delivers canonical market events and immutable `FeatureSnapshot` values to one
strategy in caller-provided order. It contains no queue, clock, network,
filesystem or database capability.

Concrete trading strategies are intentionally out of scope.

## Boundary

```text
canonical market event / FeatureSnapshot
                  |
                  v
          StrategyRuntime
                  |
                  v
       PositionTargetIntent
                  |
                  v
          risk -> OMS
```

A `PositionTargetIntent` states a signed desired position. It is not an order:
it has no venue, order type, time-in-force or venue order identifier. Risk may
approve, reject or modify the decision before OMS determines how to realize it.

## Determinism

- `start`, `on_input` and `stop` execute synchronously.
- Every accepted input receives a strictly increasing sequence number.
- Sequence is based only on call order, not event timestamps.
- By default, the first input locks the runtime scope. A strategy that
  intentionally consumes multiple instruments must declare `accepted_scopes`.
- Time values used in decisions must come from explicit inputs.
- Strategy callbacks must perform no I/O.
- Intent order is preserved exactly as returned by the strategy.

The caller owns serialization. Concurrent calls to the same runtime instance
are outside the contract. Synchronous callback re-entry is rejected, so a
strategy cannot call `stop` or deliver another input from inside `on_input`.

## Lifecycle and Failure

```text
CREATED -> RUNNING -> STOPPED
    |          |         ^
    v          v         |
  FAILED     FAILED <----+
```

Only a newly created runtime may start, only a running runtime accepts input,
and only a running runtime may stop. Lifecycle hooks or input callbacks that
raise cause an irreversible transition to `FAILED`. The failure phase, input
sequence, exception type and message are latched. No later input is delivered.

Malformed strategy output is treated as strategy failure because it crossed
the strategy boundary: output must be a tuple, use the runtime strategy ID and
contain no duplicate intent IDs within one decision.
