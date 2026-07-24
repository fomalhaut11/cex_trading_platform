# Online Feature Engine

## Boundary

The Feature Engine owns deterministic, versioned calculations derived from
canonical events. Implied volatility, Greeks and volatility surfaces belong
here, not in Market Data.

`VenueOptionAnalyticsUpdate` is an explicitly labelled venue observation. It
may trigger or inform a registered calculation, but its values are not renamed
or forwarded as authoritative system IV or Greeks. Every value emitted by the
engine records its triggering event, version, dependencies, scope, validity and
quality. Values derived directly or transitively from venue analytics use
`origin=system_computed_with_venue_reference` and retain the reference event
identifiers, so this provenance cannot masquerade as an independent model
calculation.

## Execution Model

- A registry validates unique identifiers, dependency existence and cycles.
- Registry build produces a deterministic topological order.
- One engine instance owns one explicit scope, normally one instrument.
- The owner serializes canonical events into the engine.
- Definitions update synchronously without I/O.
- A calculation reads immutable dependency values and its previous value.
- Missing dependencies skip the calculation without mutating prior state.
- Snapshots are immutable and sorted by feature identifier and version.

This initial implementation intentionally supports scalar features only.
Option pricing models, curve construction, surface interpolation, cross-scope
coordination and persistence are later modules built on these contracts.

## Determinism and Replay

For the same ordered event stream and registered definitions, calculation order
and snapshots are identical. `as_of_ns` comes from canonical event time, while
`computed_at_ns` uses canonical receive time. Calculators must not read wall
clock time, perform I/O or mutate shared state.
