# CEX Quant Trading System Architecture

## Scope

This document defines the target production architecture. Implemented and
accepted scope is tracked separately in `development/progress.md`.

The research platform is separated from the live runtime and only publishes
approved artifacts.

## Core Runtime Flow

```text
Exchange
  -> Market Data Gateway
  -> Normalizer
  -> Validator
  -> Market State Engine
  -> Online Feature Engine
  -> Strategy Runtime
  -> Risk Engine
  -> OMS
  -> Execution Gateway
  -> Exchange
```

Risk is mandatory and cannot be bypassed. Strategy produces venue-neutral
intents; only the execution adapter may produce venue requests.

Applications that correlate multiple independently owned states use the
accepted Decision Snapshot Infrastructure:

```text
Immutable source views
  -> per-source freshness and schema policy
  -> coherence-group skew assessment
  -> runtime single-writer coordinator
  -> application-specific typed snapshot
  -> Strategy
```

This path remains synchronous and deterministic. It does not introduce a
generic hot-path Event Bus or transfer source-state ownership.

ADR-010 adds an immutable decision union:

```text
Strategy
  -> PositionTargetIntent
   | BasketTargetIntent (2..16 canonical portfolio targets)
```

Basket output is caused by one matching typed decision snapshot. The current
single-leg Pipeline rejects Basket before Risk and OMS. ADR-011 now provides
the bounded offline execution-control layer:

```text
BasketTargetIntent
  -> OrderGroupAdmission
  -> Order Group + ExecutionPlanRef
  -> exact ExecutionAction
  -> synthetic ExecutionActionPermit
  -> durable child OrderRequest / OrderStateMachine
```

OMS owns group control, child facts, journal replay and recovery. It does not
own Delta, basis, margin, hedge assessment or Carry semantics. The runtime
hard-blocks grouped external submission. Proposed ADR-012 defines the review
candidate for execution-consistent position truth, whole-Basket approval,
durable Risk reservations, current per-action authorization and continuous
supervision. No real permit issuer or grouped external route exists yet.

Proposed ADR-013 adds a separate Accounting flow:

```text
authenticated fill/account financial facts
  -> balanced immutable per-asset ledger
  -> reconciliation and allocation
  -> derived valuation/PnL views
```

Proposed ADR-014 places Funding Carry in
`applications.carry.funding_arbitrage`. The application owns economic
lifecycle and hedge interpretation, consumes immutable Platform views and
emits only generic Basket targets. It cannot issue Risk permits, mutate OMS,
write ledger transactions or call Execution. Both proposals await review and
authorize no implementation.

## Design Principles

- Python-first, Rust-ready.
- Event, State and Storage separation.
- Real-time trading path separated from research.
- Metadata-driven governance.
- Registered features only in production.
- Immutable public contracts and single-writer state.
- Bounded side channels and no blocking storage in the hot path.

## Runtime Domains

1. Market Data: connectors, normalization and validation.
2. State: market, order and account/position state.
3. Information: registered online features and provenance.
4. Decision: strategy and fail-closed risk decisions.
5. Execution: OMS lifecycle and venue execution adapters.

## Product Coverage

Canonical instruments cover spot, perpetuals, dated futures and options.
Venue-specific payloads remain inside adapters.

Observable option quotes are market data. Implied volatility, Greeks, smiles,
term structures and volatility surfaces are versioned features. Venue-provided
analytics are retained only with explicit venue provenance and are not the
authoritative internal feature values.

## Process Model

The first implementation keeps the deterministic trading flow in one
`trading-core` process. Recorder, monitoring, operations API and storage may
be separated only for measured scaling or fault-domain reasons and must
communicate through bounded channels.

## Production Boundary

Passing offline regression is necessary but insufficient for production.
Production review also requires authenticated Testnet evidence, restart
recovery, exchange reconciliation, target-host latency and soak results,
secrets management, supervision, operator controls and operational runbooks.
