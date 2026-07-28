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
| Latest observations for one decision scope | Runtime Snapshot Coordinator | Application assembler, monitoring |
| Decision snapshot publication | Runtime coordinator using a pure application assembler | Strategy, Risk, recorder |

Mutable state never crosses a module boundary. Readers receive immutable views,
snapshots or events. Database records are historical evidence and recovery
inputs, not live trading state.

The Snapshot Coordinator owns only bounded references and derived readiness.
It is not a second writer for any source state. It starts empty after restart;
old publications remain evidence and never authorize a new decision.
