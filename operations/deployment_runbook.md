# Deployment Runbook

This runbook prepares Testnet or a production-release review. It does not
authorize real-money trading.

## Preconditions

- The selected Git commit has successful required CI checks.
- The deployment host runs a supported Python version and has restricted
  service accounts, directories and process inspection.
- Host time is synchronized from an approved persistent source; all configured
  venue-clock monitors are healthy.
- Binance credentials and operator HMAC keys are injected by the OS or
  orchestrator. Values are absent from files, command lines, logs and Git.
- Testnet and production use different accounts, keys, variables and
  certificate trust roots.
- The operator journal directory exists, is writable only by the service
  identity and is on durable storage.
- The external operator-audit sink is reachable, bounded, durable and subject
  to retention and access-control policy.
- TLS termination requires a validated client certificate and the management
  route is network-restricted.

## Deployment sequence

1. Record the commit, artifact digest, configuration version, operator,
   environment and intended rollback commit.
2. Put the existing deployment in `HALTED`; verify the durable operator
   snapshot and stop new strategy intents.
3. Resolve or explicitly record all non-terminal orders. Do not infer that a
   timed-out submission failed.
4. Drain recorder and audit buffers using their bounded shutdown procedures.
5. Stop the application and private-stream supervisors cleanly.
6. Back up operator and OMS journals without modifying the originals.
7. Install the exact CI-tested artifact and non-secret configuration.
8. Start external audit, clock monitoring and venue connectivity before the
   trading application.
9. Start private streams first, then run REST reconciliation. Readiness must
   remain closed until reconciliation succeeds.
10. Assemble the operator endpoint once through
    `OperatorControlRuntime.create_endpoint`; do not create parallel endpoint
    instances that bypass shared rate state.
11. Start the trading application. Confirm it starts `HALTED`.
12. Verify aggregate health, clock offset/RTT/sample age, audit writes,
    journal writes, private-stream readiness and account reconciliation.
13. Send a signed no-surprise control sequence through the mTLS route:
    `HALT`, exact retry, then—only after review—`ACTIVATE`.
14. Observe the canary window. Confirm no unexpected orders, memory growth,
    reconnect loop, audit gap or clock degradation.

## Required evidence

- Git commit and successful CI URL.
- Artifact/configuration digests.
- Host and service identity.
- Clock-health samples.
- OMS and operator recovery summaries.
- mTLS certificate subject/fingerprint and operator audit correlation.
- Start, readiness, activation and rollback timestamps.

## Abort conditions

Remain or return `HALTED` if any required health check is not healthy, audit
cannot append, journals cannot fsync, reconciliation is incomplete, the clock
is outside policy, credentials are ambiguous, or the deployed commit differs
from the approved artifact.
