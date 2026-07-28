# Testing Strategy

## Layers

- Unit tests verify value objects and deterministic state transitions.
- Contract tests verify adapter-to-canonical mappings and schema compatibility.
- Integration tests verify bounded module pipelines and recovery behavior.
- Replay tests feed recorded events and compare deterministic state outputs.
- Security-boundary tests mutate signed fields, identities, validity windows
  and authorization scopes, and prove rejection occurs before state mutation.

## Baseline

Every public domain type requires construction, invariant and serialization
tests. Every state engine requires ordering, duplicate, gap and recovery tests.
No live exchange or network access is required by the default test suite.

## A012 Decision Snapshot Acceptance

The accepted ADR-009 implementation must add offline tests for:

- immutable typed IDs, observations, policies, assessments and metadata;
- duplicate/missing source rules and deterministic issue ordering;
- event-age, arrival-age, future-skew and coherence boundaries;
- unhealthy clock and monotonic regression fail-closed behavior;
- source scope, schema, sequence and observation-identity conflicts;
- single-writer coordinator behavior and bounded latest-only retention;
- exactly-once publication per ordered observation fingerprint;
- assembler exceptions and readiness loss after a prior ready snapshot;
- deterministic recording/replay and restart beginning not ready;
- a synthetic typed application with at least three sources, proving the
  infrastructure is neither Carry-specific nor limited to two sources.

All existing single-instrument regression and acceptance tests remain
mandatory. A012 requires no network or exchange credential.
