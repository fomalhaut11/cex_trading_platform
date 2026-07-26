# Module Topology

## Core Flow

```text
Exchange -> market_data -> market_state -> features -> strategy
                                                     -> risk -> oms -> execution -> Exchange
```

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

## Process Boundaries

The initial `trading-core` process contains the core flow. A module becomes a
service only for measured scaling, language-runtime or fault-domain reasons.
