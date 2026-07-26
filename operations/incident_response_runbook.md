# Incident Response Runbook

## Immediate containment

1. Issue `HALT` through the authenticated mTLS operator route.
2. Independently verify the durable operator snapshot and aggregate health.
3. If the route is unavailable, stop the trading process and revoke venue API
   trading permission using the exchange account controls.
4. Preserve OMS, operator and recorder journals; do not modify evidence.
5. Record incident start time, detection source, affected accounts,
   instruments, strategies and last known good sequence.

## Severity guide

- **SEV-1:** unauthorized orders, uncontrolled exposure, credential
  compromise, inability to halt, or corrupted authoritative state.
- **SEV-2:** degraded reconciliation, persistent stream/clock/audit failure,
  unknown orders with bounded exposure, or repeated process failure.
- **SEV-3:** contained Testnet failure or non-trading observability defect with
  no authority or account-state impact.

## Investigation

- Correlate certificate fingerprint, operator command ID, actor, journal
  generation, OMS client order ID and venue order ID.
- Compare operator audit with the durable operator journal.
- Compare OMS journal and private-stream events with Binance REST truth.
- Check host time, venue offset, transport failures and VPN route changes.
- Check artifact/configuration digests and recent deployments.
- Search for credential exposure without copying values into the incident
  report.

## Credential response

On suspected compromise:

1. revoke the affected Binance key and operator signing key;
2. keep the account halted;
3. create least-privilege replacement credentials through the secret manager;
4. rotate mTLS certificates or trust roots when identity is implicated;
5. confirm old credentials fail; and
6. run reconciliation and Testnet validation before any reactivation.

## Recovery authorization

Recovery requires:

- identified or safely bounded root cause;
- restored durable audit and journal writes;
- healthy persistent time and venue connectivity;
- zero unexplained orders, balances or positions;
- successful restart reconciliation;
- reviewed rollback/deployment evidence; and
- explicit authenticated activation by an authorized operator.

## Post-incident

- Retain evidence according to policy.
- Publish a timeline using nanosecond timestamps only where actually observed.
- Document contributing controls, detection gaps and corrective tasks.
- Add deterministic regression or fault tests for every reproducible failure.
- Rotate temporary credentials and remove emergency access.
