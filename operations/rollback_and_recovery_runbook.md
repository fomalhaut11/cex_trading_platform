# Rollback and Recovery Runbook

## Safe rollback

1. Issue and verify a durable `HALT`.
2. Stop strategies from producing new intents.
3. Query every non-terminal or unknown order using its original client order
   identifier. Cancel only after venue state is known.
4. Capture health, logs, audit correlation, account state and journal copies.
5. Stop the current deployment using bounded drain and shutdown.
6. Install the previously approved artifact. Do not downgrade or rewrite OMS
   or operator journals unless its documented schema is compatible.
7. Start the previous version `HALTED`, restore journals and run complete
   startup reconciliation.
8. Compare balances, positions and non-terminal orders with venue truth.
9. Activate only after two-person review of reconciliation and health.

Never use `git reset --hard`, delete journals or create replacement client
order IDs as an operational rollback technique.

## Unknown execution outcome

When a request may have reached Binance but no valid response arrived:

1. keep the OMS state uncertain and block duplicate business intent;
2. query by the original client order ID;
3. merge REST and private-stream facts through reconciliation;
4. cancel only a confirmed live order;
5. preserve request timing and transport classification; and
6. restart only after the unknown set is empty or explicitly accepted under
   incident control.

## Operator audit failure

The assembled endpoint durably requests `HALT` when audit fails. A caller that
receives `OperatorAuditUnavailableError` must treat the command outcome as
unknown:

1. check the operator journal and current snapshot locally;
2. verify trading is `HALTED`;
3. isolate and recover the audit backend;
4. reconcile missing terminal audit records against the operator journal;
5. rotate operator keys if audit integrity is in doubt; and
6. create a new endpoint/process only after audit writes are proven.

## Journal corruption or storage failure

- Do not truncate, edit or recompute checksums in place.
- Preserve the failed bytes and filesystem metadata.
- Keep trading halted and make a read-only forensic copy.
- Restore only from a verified backup or deterministic venue reconciliation.
- Record the recovery decision, lost sequence range and responsible approvers.

## Clock failure

- Halt trading when offset, RTT, sample age, wall jump or monotonic health is
  outside policy.
- Restore the approved persistent time source.
- Require a new stable sample window across every enabled Binance product.
- Do not widen thresholds merely to make the health check pass.

## Network and private-stream recovery

- Keep readiness closed during reconnect and stream gaps.
- Start the stream before REST reconciliation to avoid the startup race.
- Preserve buffered events within the configured bound.
- Treat buffer overflow or repeated lease renewal failure as degraded/failed,
  not as a reason to continue with stale state.
