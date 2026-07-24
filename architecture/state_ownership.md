# State Ownership

| State | Single writer | Readers |
|---|---|---|
| Market state | Market State Engine | Features, strategy, recorder |
| Feature state | Online Feature Engine | Strategy, monitoring |
| Strategy state | Owning strategy instance | Strategy runtime |
| Risk state | Risk Engine | Operations, monitoring |
| Order state | OMS | Risk, portfolio, operations |
| Account and position state | Portfolio/Account Engine | Risk, strategy |
| Connector health | Owning connector | Runtime, monitoring |

Mutable state never crosses a module boundary. Readers receive immutable views,
snapshots or events. Database records are historical evidence and recovery
inputs, not live trading state.

