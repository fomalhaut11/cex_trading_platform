# Project Knowledge Graph Report

This report describes the deterministic project graph. The federated
Graphify code graph remains in `graphify-out/graph.json`.

## Summary

- Project nodes: 1671
- Project edges: 3161
- Project source fingerprint: `bada2e78faecbf3ae4127f226e23d070eeeb00f0656dd9debba82ae25222d46b`
- Code source fingerprint: `e275e7d36cd40fd6a47c17e7f56b67ca25812b96911d7fef1f7812b6753ef7c9`
- Validation: PASS

## Node Types

- `AcceptanceCriterion`: 25
- `ApplicationBoundary`: 1
- `ArchitectureConstraint`: 32
- `ArchitectureDecision`: 14
- `ArchitectureDecisionDocument`: 14
- `ArchitectureDocument`: 11
- `CodeSymbol`: 191
- `CommitReference`: 51
- `ContinuousIntegrationJob`: 2
- `ContinuousIntegrationWorkflow`: 1
- `DeliveryDocument`: 45
- `DeliveryTask`: 53
- `DocumentSection`: 1119
- `DomainBoundary`: 4
- `DomainContract`: 2
- `ExternalAuthorizationGate`: 3
- `InterfaceDocument`: 10
- `KnowledgeGraphDefinition`: 1
- `OperationsDocument`: 4
- `OwnedState`: 13
- `ProductObjective`: 1
- `ProjectDocument`: 2
- `RepositoryArtifact`: 40
- `RuntimeComponent`: 2
- `StateOwner`: 13
- `StateReader`: 17

## Edge Authority

- `authoritative`: 186
- `extracted`: 2975

## Status Distribution

- `accepted`: 11
- `accepted-offline`: 3
- `active`: 35
- `blocked`: 1
- `complete`: 67
- `deferred`: 3
- `external`: 2
- `implemented-offline`: 2
- `offline-accepted`: 1
- `offline-implemented`: 1
- `planned`: 2
- `proposed`: 1
- `single-leg-existing`: 1
- `unauthorized`: 4
- `unresolved`: 2
- `unspecified_legacy`: 4

## Critical Current Facts

- T045-T046 and A018 are complete offline.
- Runtime owns registered execution planning and exact gateway routing.
- A019 is the next external promotion gate and remains unauthorized.
- Grouped external execution is blocked.
- Binance grouped Testnet execution is unauthorized.
- Production and real-money execution are unauthorized.
- Carry produces a generic Basket target and owns no venue I/O.

## Validation Warnings

- legacy ADR has no explicit status heading: adr:ADR-002
- legacy ADR has no explicit status heading: adr:ADR-003
- legacy ADR has no explicit status heading: adr:ADR-004
- legacy ADR has no explicit status heading: adr:ADR-005

Graph-derived facts never override source code, passing tests or
accepted repository authority. Inferred/proposal facts cannot be
promoted without explicit review.
