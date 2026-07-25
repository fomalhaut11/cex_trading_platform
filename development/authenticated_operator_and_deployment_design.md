# Authenticated Operator Boundary and Deployment Assembly

Status: T023 implementation baseline.

## Scope

T023 closes the offline gap between durable operator authority and a deployable
trading composition. It adds:

- a signed, protocol-neutral operator command envelope;
- deployment-owned identity, least-privilege authorization and key rotation;
- bounded command freshness and durable replay safety;
- concrete operator-control resource ownership; and
- a trading deployment root that always includes operator health and risk
  gates.

It does not expose a network listener, terminate TLS, create secrets or
authorize production trading.

## Authentication and authorization

`OperatorCommandEnvelope` contains the key identifier, command identifier,
action, reason and Unix-nanosecond issue/expiry times. Its canonical,
versioned JSON is signed with HMAC-SHA256. The signature covers every field
that can change trading authority.

`EnvironmentOperatorKeyProvider` maps an opaque key identifier to:

- an actor identity controlled by deployment configuration;
- a unique environment variable containing the signing secret; and
- an explicit tuple of permitted operator actions.

The actor is never accepted from an untrusted envelope. Key values are read
for every command so an external secret injector can rotate them without a
process rebuild. Provider and key-material representations redact bindings and
values. Lookup and verification failures expose sanitized errors.

`HmacOperatorCommandAuthenticator` checks a bounded validity interval, clock
skew, signature and allowed action before creating an `OperatorCommand`.
Authentication failure cannot call `OperatorController`.

## Replay safety

The signed `command_id` is the durable idempotency key. The validity window
limits capture-and-delay attacks. The T022 journal guarantees that an exact
retry returns the original snapshot and is not appended twice, including
after restart. Reusing the identifier with different content is rejected and
cannot roll authority back.

This design deliberately permits exact delivery retries; it prevents a retry
from becoming a second state transition.

## Deployment composition

`OperatorControlRuntime` owns:

- the fsynced operator journal;
- the fail-closed `OperatorController`;
- environment-backed key resolution;
- authentication and command execution;
- aggregate operator health; and
- construction of the mandatory `OperatorRiskGate`.

`TradingDeploymentRuntime` composes `TradingApplication` with aggregate health
that always includes operator control and with risk that is always wrapped by
the operator gate. It starts halted, so a correctly authenticated activation
is required before an event can reach OMS or execution. Closing the deployment
closes the application bridge and operator journal.

Exchange gateways, private-stream supervisors and public clock probes remain
explicit constructor dependencies or host-managed lifecycles. This keeps
domain ownership clear and avoids hidden I/O in package imports.

## Deployment obligations

A real operator endpoint must additionally provide:

- TLS or mTLS termination and restrictive network policy;
- request-size, rate and concurrency limits;
- protected environment or orchestrator secret injection;
- an external authenticated audit sink and alerts;
- synchronized host time; and
- key issuance, overlap, rotation and revocation procedures.

HMAC operator keys must be separate from exchange API credentials and from
one another. Production and Testnet require distinct keys.

## Acceptance

A010 proves offline that:

1. identity is derived from deployment binding rather than request input;
2. all authority fields are signature protected;
3. expired, invalid and unauthorized commands leave authority unchanged;
4. exact replay is idempotent before and after restart;
5. key rotation is observed on the next command;
6. no signing secret enters the durable journal; and
7. the complete deployment root cannot omit operator health or risk gating.
