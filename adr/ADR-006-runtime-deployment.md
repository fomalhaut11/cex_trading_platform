# ADR-006 Runtime Deployment Model

## Status

Accepted.

## Decision

The first production runtime is a modular monolith named `trading-core`.
Market data, market state, online features, strategy, risk, OMS and execution
run as strictly separated modules in one process. Recorder, monitoring,
operations API and historical storage run out of process.

Core state transitions use explicit synchronous calls through bounded
pipelines. An event bus is reserved for non-blocking side consumers.

Modules may be moved to independent processes only after profiling or a
documented fault-isolation requirement. Public domain contracts must remain
stable when a transport boundary changes.

## Consequences

- Hot-path ordering and backpressure remain explicit.
- Each state has one writer.
- Domain modules cannot depend on runtime assembly or transport details.
- Cross-module values are immutable events, commands, views or snapshots.

