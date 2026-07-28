# Module Topology

## Core Flow

```text
Exchange -> market_data -> market_state -> features -> strategy
                                                     -> risk -> oms -> execution -> Exchange
```

For applications that require correlated state, the accepted additive path is:

```text
authoritative immutable source views
  -> snapshots policy/assessment
  -> runtime SnapshotCoordinator
  -> application-specific typed decision snapshot
  -> strategy
```

`snapshots` owns generic observation, readiness and coherence contracts.
`runtime` owns serialized coordination. An application owns its typed
assembler and payload. Snapshot coordination does not replace source state or
the mandatory Strategy -> Risk -> OMS -> Execution boundary.

`runtime` assembles the flow. `recorder`, `monitoring`, `operations_api` and
`storage` consume bounded side channels and cannot block the trading path.

`runtime.operator_endpoint` is the protocol-neutral `operations_api` adapter.
It accepts identity only after external mTLS validation and owns no public
listener. Concrete TLS termination remains a deployment boundary.

## Dependency Rules

1. `core` depends on no business domain.
2. `instruments` depends only on `core`.
3. `market_data` depends on `core` and `instruments`.
4. `features` consumes canonical market facts and state views, never connectors.
5. `strategy` produces trade intents and cannot create venue orders.
6. `risk` approves, modifies or rejects intents.
7. `oms` exclusively owns order lifecycle state.
8. `execution` adapts commands and reports; it does not own canonical orders.
9. `portfolio` exclusively owns account and position state.
10. Domain modules cannot depend on `runtime`.
11. Venue-specific objects cannot escape their adapter package.
12. `snapshots` depends only on foundational types and minimal health status;
    it cannot depend on source domains, applications or runtime.
13. Application-specific snapshot assemblers may read public immutable domain
    views but cannot depend on runtime or venue adapters.

## Process Boundaries

The initial `trading-core` process contains the core flow. A module becomes a
service only for measured scaling, language-runtime or fault-domain reasons.
