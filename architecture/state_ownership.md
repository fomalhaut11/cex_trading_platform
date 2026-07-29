# State Ownership

| State | Single writer | Readers |
|---|---|---|
| Market state | Market State Engine | Features, strategy, recorder |
| Feature state | Online Feature Engine | Strategy, monitoring |
| Strategy state | Owning strategy instance | Strategy runtime |
| Portfolio Risk reservations, permit generations and recovery evidence | Portfolio Risk Coordinator | Runtime, OMS evidence adapters, operations |
| Order state | OMS | Risk, portfolio, operations |
| Order Group execution control and child/action facts | OMS Order Group state machine | Runtime, Portfolio Risk, operations |
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

Order Group state is deliberately not portfolio state. OMS exposes immutable
per-leg signed fill and working-quantity vectors. Accepted ADR-012 keeps
generic Delta, basis, margin, liquidation, exposure and safety assessment in
Portfolio Risk. The Risk Coordinator is the single writer for reservations,
typed resource claims, authorization generations, permit liveness and
recovery evidence; the pure Risk Engine owns no mutable state. Proposed
ADR-014 keeps application-specific `HEDGED`
interpretation in the owning application aggregate. `RECOVERY_REQUIRED` is an
OMS execution-control state; `HEDGED` is not.
