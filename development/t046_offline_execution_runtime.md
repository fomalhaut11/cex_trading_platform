# T046 Mode-Neutral Offline Execution Runtime

Status: complete on 2026-08-01. A018 was subsequently accepted on 2026-08-02.

Code baseline entering T046: `9ae43f8` (`d-development`).

External I/O: disabled. This implementation uses only deterministic local
ports and does not authorize Binance Testnet or production execution.

## Delivered Composition

`cex_quant.runtime.GroupedExecutionRuntime` is the owner-thread coordinator
for one generic Basket execution loop. It now composes:

1. whole-Basket Portfolio Risk assessment and durable reservation;
2. deterministic Order Group creation and activation;
3. current-position residual selection in canonical leg order;
4. exact per-action Risk authorization and permit issuance;
5. durable preparation, immediate platform recheck and permit consumption;
6. deterministic submit/cancel outcome routing back to the exact group child;
7. fail-closed `HALTED` and `RECOVERY_REQUIRED` states;
8. ordered restart evidence before execution can resume.

Supporting Runtime adapters:

- `DeterministicOfflineExecutionPort` scripts accepted, rejected,
  definitely-not-sent and UNKNOWN submit/cancel outcomes without network I/O;
- `OmsExecutionEffectProjector` converts cumulative durable OMS fills into
  contiguous, signed Portfolio effects without double counting;
- `CarryReadSideProjector` durably links Basket and Order Group causation,
  reads Portfolio hedge truth and Accounting financial truth independently,
  and writes Carry lifecycle evidence;
- `GroupedBootstrapEvidence` requires journal replay, Portfolio
  reconciliation, order reconciliation, OMS effect projection, Accounting
  drain and Carry projection in that exact order.

No Funding-specific branch was added to Risk, OMS or grouped execution. No
frozen Kernel v1 public contract changed.

## Safety Semantics

- UNKNOWN immediately latches runtime and Order Group recovery; the same
  runtime cannot issue a blind retry.
- Immediate rejection and adverse terminal child events require recovery.
- Operator/platform halt and permit expiry occur after durable preparation
  but before external I/O and leave the runtime halted.
- Cancel intent first durably suspends the group; cancel reject, transport
  failure or UNKNOWN then requires recovery.
- A restarted runtime with any existing group starts halted, or
  recovery-required when unresolved children exist. Complete ordered evidence
  is mandatory before resumption.
- Portfolio effects advance one global OMS sequence watermark per account,
  including empty batches for entries belonging to another account.
- Carry becomes `ACTIVE` only when every owned leg reaches its opening target,
  not merely when net Delta is zero. It becomes `CLOSED` only when every leg
  returns to its ownership baseline. Financial reconciliation remains an
  independent state.

## Deterministic Evidence

New focused coverage includes:

- exact two-leg permit/submission order;
- end-to-end BTC Spot `+10` / perpetual `-10` convergence through OMS,
  Portfolio and Carry `ACTIVE/HEDGED`;
- immediate rejection, timeout-after-send UNKNOWN and no blind retry;
- operator halt and permit expiry before dispatch;
- unreconciled position change handled by current Portfolio Risk;
- cancel transport failure and group recovery;
- durable OMS partial/final fill increments and Portfolio watermarks;
- restart with an UNKNOWN child, authoritative resolution and ordered
  bootstrap completion;
- Accounting evidence before and after Portfolio reconciliation;
- distinction between hedged-empty, hedged-open and physically closed Carry.

Verification on Python 3.14.2:

```text
compileall                         passed
unittest discover                 565 passed
Ruff src tests tools              passed (0.16.0)
MyPy --strict src                 passed (140 source files, 2.3.0)
pytest branch coverage            85.03%, gate 85% passed
```

## Subsequent A018 Acceptance

T046 supplies the runtime and fault harness. A018 subsequently consolidated
the full restart matrix at every non-terminal boundary, ran the
frozen-boundary audit and produced the self-contained Testnet go/no-go handoff.
Evidence: `development/a018_offline_execution_acceptance.md`.

Even after A018, A019 remains external and unauthorized until the project
owner separately approves bounded Binance Testnet execution and supplies the
required external prerequisites. Production execution remains prohibited.
