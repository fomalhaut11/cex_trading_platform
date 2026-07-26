# Operator Endpoint and Audit Boundary

Status: T024 implementation baseline.

## Scope

T024 provides the bounded adapter between an mTLS-capable network layer and
the authenticated operator service completed in T023. It adds:

- an explicit mutually authenticated transport identity;
- strict, bounded and duplicate-safe JSON decoding;
- bounded per-client request rate and retained client state;
- non-blocking command concurrency limits;
- a secret-free authenticated-audit port;
- endpoint health and failure latching; and
- deployment composition that durably halts trading when the endpoint loses
  audit or monotonic-clock integrity.

It deliberately does not implement a public Internet listener or act as a
certificate authority. TLS termination and the external audit backend belong
to the deployment environment.

## Trusted transport boundary

`MutualTlsIdentity` may only be constructed from a peer certificate already
validated by a trusted TLS terminator or by an in-process TLS server using a
protected integration path. Values copied from ordinary client-controlled
HTTP headers are not trusted identity.

The endpoint rejects any identity that is not explicitly marked mutually
authenticated. The certificate SHA-256 fingerprint and bounded client ID are
recorded for audit; neither is used as the HMAC actor. T023 still derives the
operator actor and permissions from the signed key binding.

## Request contract

The transport passes `OperatorHttpRequest` with:

- `Content-Type: application/json`;
- a byte body no larger than the configured limit; and
- the validated `MutualTlsIdentity`.

The top-level JSON object must contain exactly:

`version`, `key_id`, `command_id`, `action`, `reason`, `issued_at_ns`,
`expires_at_ns`, and `signature`.

Version is the integer `1`; booleans are not accepted as integers. Duplicate
or extra fields, invalid UTF-8/JSON, invalid enum values and incorrectly typed
values are rejected before authentication or authority mutation. Signature
and reason are never copied into endpoint audit records.

## Resource bounds

`OperatorRequestRateLimiter` is a thread-safe fixed-window limiter using the
monotonic clock. It retains at most `max_clients` histories and evicts the
least recently used identity when the bound is reached. A monotonic regression
latches the limiter failed.

`OperatorCommandEndpoint` uses a bounded semaphore and never waits for a
command slot. Saturation is returned as an explicit concurrency-limit error.
The endpoint is a cold-path control component and contains no unbounded queue.

## Audit ordering and failure semantics

For a structurally valid request, the endpoint appends `RECEIVED` before
calling the authenticated command service. It then appends one terminal
`APPLIED`, `REJECTED` or `FAILED` record. Exact command retries are audited on
every delivery, while the operator command journal changes authority only
once.

If audit append fails before execution, no command is applied. If the terminal
append fails after execution, the caller receives `OperatorAuditUnavailableError`
and must treat the response as an unknown control outcome. The T023 operator
journal remains authoritative.

`OperatorControlRuntime.create_endpoint` installs a mandatory failure handler.
Audit failure, executor uncertainty, operator-journal durability failure or
rate-limit monotonic regression creates a durable system `HALT`. If that
journal append also fails, the existing T022 durability latch still leaves
in-memory authority halted. Restart restores the durable halt when persistence
completed.

## Network integration

The concrete reverse proxy, service mesh or server must:

- require TLS 1.2 or newer and verified client certificates;
- pass identity only over a protected in-process or local authenticated path;
- enforce its own body, header, connection and request-time limits;
- expose only the operator route on a restricted management network;
- map endpoint errors to sanitized responses without exception details; and
- send audit records to a bounded, durable, access-controlled external sink.

Suggested response classes are success, invalid/rejected request, throttled,
and unavailable. Responses must not distinguish unknown key IDs from bad
signatures.

## Acceptance

A011 proves offline that:

1. mTLS identity and HMAC authentication are both mandatory;
2. malformed, extra, duplicate and oversized JSON cannot mutate authority;
3. rate and concurrency state remain bounded and non-blocking;
4. audit excludes signature, secret and free-text reason;
5. exact replay is audited but changes the durable journal once;
6. restart restores the same authority; and
7. audit loss after activation durably transitions the deployment to
   `HALTED`.
