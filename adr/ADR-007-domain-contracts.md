# ADR-007 Domain Contracts and Numeric Representation

## Status

Accepted.

## Decision

- Events, commands, mutable states and immutable snapshots are distinct.
- Cross-module objects are frozen, slotted and keyword-only by default.
- Event metadata is composed into strongly typed events; payload dictionaries
  are not domain contracts.
- UTC Unix nanoseconds stored as signed integers are the canonical timestamp.
- Prices, quantities and monetary amounts use decimal fixed-point values
  represented by `raw + scale`.
- Statistical and model features may use float64 values with explicit quality.
- Persistent schemas have versions independent of Python package versions.
- Core pipelines use explicit synchronous calls; side consumers use a bounded
  event bus.

Order-book implementations may convert prices to instrument-specific tick
indices internally, but this representation cannot leak into public contracts.

## Rationale

The representation is deterministic, serialization-safe and maps cleanly to
future Rust implementations without introducing binary floating-point errors
into orders and balances.

