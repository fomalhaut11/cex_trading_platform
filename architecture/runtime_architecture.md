# Runtime Architecture

## Process Model

First version:

trading-core: - market connectors - state engines - online features -
strategy runtime - risk - OMS

Independent processes: - recorder - operations API - monitoring -
storage services

## Concurrency Model

Use asyncio for IO.

Keep core state transitions synchronous and deterministic.

Avoid: - unlimited tasks - blocking IO - database access in hot path

## State Ownership

Each state has a single writer.

Examples: - Market State - Feature State - Order State - Position State

## Grouped Execution Composition

Runtime owns execution composition; OMS and Execution do not select an
algorithm or infer a venue route.

At Basket admission, `ObjectiveExecutionPlanResolver` maps the exact,
versioned Objective Type to an immutable `ExecutionPlanRef`. Runtime verifies
that the complete reference, including its parameters checksum, exists in the
bounded `ExecutionPlannerRegistry`. At each execution step it asks the
registered `OrderGroupPlanner` for one bounded deterministic `ExecutionStage`
or no proposal. The planner owns no Risk, operator or external-I/O authority.

`SequentialResidualExecutionPlanner` is the generic width-one reference
implementation. Other algorithms are additive Runtime components; they do not
require changes to Basket, individual Action/Child, Gateway, Portfolio or
ledger contracts.

`runtime.adapters.ExactExecutionGatewayRouter` dispatches submit, cancel and
query by the exact `(account_id, instrument_id)` scope. It has no strategy-leg,
product or venue policy and no fallback route. Its configuration is bounded
to prevent accidental unbounded composition, but that bound is independent of
the Basket leg limit. Binance, OKX or future gateway implementations remain
responsible for their own protocol validation and external I/O.

## Execution Concurrency Evolution

N-leg intent and execution concurrency are independent. The current V1
planner/group path is the valid width-one mode; it is not the permanent
platform-wide concurrency ceiling. The project-owner-approved evolution
direction is a bounded Stage model in which one Stage contains one or more
exact Actions and declares a dispatch width no greater than its Stage width.

The Stage host must preserve single-writer state while allowing concurrent
venue I/O. Complete Stage, Action and Child identity evidence is durable before
fan-out; Risk authorizes a conservative partial-execution envelope; results
remain per Child; UNKNOWN blocks automatic compensation until reconciliation.
Cross-venue dispatch never claims all-or-none atomicity.

Terminal-serial Funding Carry is represented as a width-one Stage. A
fill-driven hedge may overlap a working leader order with bounded hedge
Actions. Triangular arbitrage and option parity may use wider Stages without
changing Basket, Portfolio, Accounting or individual Gateway contracts.

ADR-015 accepts the detailed Stage, aggregate permit, atomic preparation,
mixed-version replay and per-Child result-vector contracts. T051/A022 implement
the compatibility host with `max_stage_width = 1` and
`max_dispatch_width = 1`. Wider Risk envelopes and parallel dispatch remain a
separate activation gate. Neither ADR-015 nor the offline implementation
authorizes Testnet or external execution.
