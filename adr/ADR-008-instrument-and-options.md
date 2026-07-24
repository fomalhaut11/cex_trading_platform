# ADR-008 Instrument Coverage and Option Analytics

## Status

Accepted.

## Decision

The domain model supports spot, perpetual futures, dated futures and options.
Product-specific fields are represented by separate specification types rather
than one object containing many optional fields.

Market data contains observable market facts. Implied volatility, Greeks,
smiles, term structures and volatility surfaces are registered features.
Venue-provided IV or Greeks are retained only as explicitly labelled venue
analytics and are not the system's authoritative feature values.

## Consequences

- Binance-specific symbols and payloads remain inside its adapter.
- Linear, inverse and quanto contracts must be distinguishable.
- Option feature definitions record model, inputs, parameters and versions.
- Strategies consume registered analytics, not unversioned venue calculations.

