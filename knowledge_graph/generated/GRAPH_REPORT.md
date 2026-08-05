# Project Knowledge Graph Report

This report describes the deterministic project graph. The federated
Graphify code graph remains in `graphify-out/graph.json`.

## Summary

- Project nodes: 1637
- Project edges: 3051
- Project source fingerprint: `1c9dca8fdaf01cdf8497b19fda2fe6f7fa34c2892af6b3fab042cb2175a3ecf7`
- Code source fingerprint: `1068e9291b32fe765fcf09a43de50d5e4615ce6905e9da196620fdd0a937e4a5`
- Validation: PASS

## Node Types

- `AcceptanceCriterion`: 24
- `ApplicationBoundary`: 1
- `ArchitectureConstraint`: 32
- `ArchitectureDecision`: 14
- `ArchitectureDecisionDocument`: 13
- `ArchitectureDocument`: 11
- `CodeSymbol`: 186
- `CommitReference`: 50
- `ContinuousIntegrationJob`: 2
- `ContinuousIntegrationWorkflow`: 1
- `DeliveryDocument`: 45
- `DeliveryTask`: 52
- `DocumentSection`: 1095
- `DomainBoundary`: 4
- `DomainContract`: 1
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

- `authoritative`: 180
- `extracted`: 2871

## Status Distribution

- `accepted`: 9
- `accepted-offline`: 2
- `active`: 35
- `approved-direction`: 1
- `blocked`: 1
- `complete`: 65
- `deferred`: 3
- `external`: 2
- `implemented-offline`: 2
- `offline-accepted`: 1
- `offline-implemented`: 1
- `planned`: 2
- `proposed`: 1
- `single-leg-existing`: 1
- `unauthorized`: 4
- `unresolved`: 3
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
