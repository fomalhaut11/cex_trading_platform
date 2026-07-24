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
