# Runtime Health and Operator Controls

Status: T021 implementation baseline.

## Scope

This boundary provides protocol-neutral application services for:

- stable aggregate health queries;
- explicit operator activation;
- a fail-closed kill switch;
- strict reduce-only operation;
- bounded command idempotency; and
- deterministic pre-trade enforcement.

It deliberately does not embed an HTTP server, CLI parser or GUI. Those
deployment adapters must authenticate and authorize an operator before
constructing an `OperatorCommand`.

## Ownership

`RuntimeHealthService` owns a fixed ordered tuple of `HealthCheck` instances.
It returns both the child reports and their worst-status aggregate. Duplicate
component names are rejected. A thrown exception or malformed report becomes
a sanitized `UNHEALTHY` report; exception messages are never copied because
they may contain credentials or venue payloads.

`OperatorController` owns only in-process operator authority. It starts in
`HALTED`, so constructing or restarting a controlled runtime cannot silently
enable trading. Every state change requires a non-empty command id, actor and
reason. Repeating an identical command id is idempotent; reusing it with
different content is rejected. The in-memory history is bounded.

The controller modes are:

| Mode | Operational health | Trading effect |
|---|---|---|
| `ACTIVE` | `HEALTHY` | ordinary risk policy applies |
| `REDUCE_ONLY` | `DEGRADED` | only strict exposure reduction may pass |
| `HALTED` | `UNHEALTHY` | every intent is rejected |

An external operations health view may aggregate the operator check with
infrastructure checks. The synchronous pipeline's infrastructure health gate
must not treat `REDUCE_ONLY` as a reason to stop before risk, because reduction
orders must still reach `OperatorRiskGate`.

## Reduce-only semantics

`OperatorRiskGate` always retains the delegate's ordinary risk decision. Under
reduce-only mode, both projected strategy exposure and projected global
exposure must:

- have absolute size no greater than the current exposure;
- keep the same sign; or
- become exactly zero.

Opening from zero, increasing size, crossing through zero, or reducing a
strategy while increasing/flipping global net exposure is rejected with
`REDUCE_ONLY_VIOLATION`.

The controller is sampled before and after delegate risk evaluation. The most
restrictive observed mode applies, closing the race where an operator halts
trading while an intent is being evaluated.

## Deployment requirements

This module is not the security perimeter. A production adapter must add:

- authenticated and authorized operator identity;
- encrypted transport and replay protection;
- durable append-only command audit;
- restoration of the last approved mode before any activation;
- separation of command and health-query permissions; and
- alerts for every transition into or out of `HALTED`.

Until durable restoration exists, every process restart remains safely
`HALTED` and requires a new explicit activation command.

## Acceptance

The offline scenario composes the real trading pipeline and risk engine:

1. explicit activation permits an expanding intent;
2. reduce-only permits a smaller same-sign target;
3. reduce-only rejects an expanding target before OMS/execution;
4. halt rejects even a flattening target before OMS/execution; and
5. the operations aggregate reports healthy, degraded and unhealthy in the
   corresponding modes.
