# A018 Offline Grouped Execution Acceptance

Status: accepted offline on 2026-08-02.

Tested code baseline:
`b7c99af127ae04b51fa9459df8d2d30297d53635` (`d-development`).

External effect: none. All execution used deterministic local ports. No
Binance credential was read, no network execution adapter was composed and no
Testnet or production order was submitted.

## 1. Decision

A018 passes. The mode-neutral grouped runtime is deterministic, durable at
every represented non-terminal boundary, fail-closed after restart and still
separated from every authenticated external execution route. The acceptance
did not change frozen Kernel v1 public ownership or add a Funding-specific
branch to OMS, Risk or Execution.

The offline technical gate is **GO**. Promotion to A019 Binance Testnet is
**NO-GO** until every external prerequisite in section 8 is recorded and the
project owner separately authorizes that bounded external action.

## 2. Accepted Runtime Sequence

```text
BasketTargetIntent
  -> PortfolioRiskEngine.assess_basket
  -> PortfolioRiskCoordinator.reserve_approval
  -> OrderGroupRuntime.create_group / activate_group
  -> deterministic residual-reducing ExecutionAction
  -> PortfolioRiskEngine.authorize_action
  -> PortfolioRiskCoordinator.issue_permit
  -> OrderGroupRuntime.prepare_child_submit       [durable]
  -> PortfolioRiskExecutionGuard                  [immediate recheck]
  -> permit consumption                           [durable]
  -> DeterministicOfflineExecutionPort             [no network]
  -> exact child outcome / OrderEvent              [OMS journal]
  -> OmsExecutionEffectProjector
  -> ExecutionConsistentPositionState
  -> CarryReadSideProjector
  -> CarryPositionBook                             [Carry journal]
```

Accounting remains independent. Only authenticated-style observed facts may
enter `FinancialFactHandoff`/`AccountingLedger`; market Funding rates and OMS
acknowledgements are not financial truth.

## 3. Restart Sequence

```text
replay Accounting, Carry, Portfolio Risk and OMS journals
  -> keep effective Portfolio state UNRECONCILED
  -> buffer external observations (A019 only)
  -> reconcile authoritative account and order baselines (A019 only)
  -> resolve every OMS recovery candidate
  -> project contiguous durable OMS effects into Portfolio
  -> drain authenticated financial facts into Accounting
  -> project Portfolio and Accounting views into Carry
  -> validate ordered GroupedBootstrapEvidence
  -> issue only fresh post-restart permits
```

A restarted runtime is never implicitly runnable. Unresolved child state
produces `RECOVERY_REQUIRED`; durable CREATED, SUSPENDED or CLOSING group state
produces `HALTED`; both reject the full bootstrap gate until the state is
explicitly reconciled. ACTIVE and CLOSED groups may pass healthy ordered
evidence; a RECOVERY_REQUIRED group must first be resumed with explicit
authorization evidence.

## 4. Identity, Causation and Writers

| Evidence | Stable binding | Single durable writer |
|---|---|---|
| `PortfolioApprovalId` / reservation | Basket checksum, Risk snapshot, policy and resources | `PortfolioRiskCoordinator` |
| `OrderGroupId` | Basket intent plus Portfolio approval | `OrderGroupRuntime` / OMS journal |
| `GroupActionId` | group revision, leg, plan and attempt | `OrderGroupRuntime` / OMS journal |
| `ExecutionPermitId` | exact action checksum, group revision, Risk generation and expiry | `PortfolioRiskCoordinator` |
| `ClientOrderId` | exact group action | `OrderGroupRuntime` / OMS journal |
| effective position effect | OMS journal sequence and cumulative-fill delta | one `ExecutionConsistentPositionState` writer per account |
| `FinancialFactId` | authenticated execution/account observation | `AccountingLedger` |
| `ApplicationPositionId` | Carry strategy, pair and opening snapshot | `CarryPositionBook` |

`GroupedExecutionRuntime` serializes commands but does not take ownership of
Risk, OMS, Portfolio, Accounting or Carry truth.

## 5. Deterministic Failure Matrix

| Scenario | Accepted result | Evidence |
|---|---|---|
| Both legs fill | Two exact permits and submissions; Portfolio converges; Carry becomes `ACTIVE/HEDGED` | `test_two_leg_loop_uses_exact_permits_and_no_network`, `test_two_leg_fill_converges_oms_portfolio_and_carry` |
| First leg fills, second rejects | Exact second action is rejected; runtime and group require recovery; Carry keeps signed residual | `test_first_leg_fill_then_second_reject_requires_recovery`, `test_rejected_second_leg_preserves_residual_and_requires_recovery` |
| Partial fill on either leg | Both child orders preserve cumulative signed fill and unresolved residual without an extra submission | `test_partial_fill_on_each_leg_is_durable_and_residual_safe`, OMS position projection tests |
| Timeout after possible send | Child becomes UNKNOWN, runtime requires recovery and blind retry is rejected | `test_timeout_after_send_latches_recovery_and_no_blind_retry` |
| Permit expiry or generation change | Immediate guard prevents external I/O; restart/material change invalidates the old permit | `test_permit_expiry_at_immediate_guard_prevents_external_io`, `test_material_change_and_restart_invalidate_old_permit` |
| Position or margin evidence changes | Unreconciled position and unhealthy/missing margin evidence fail current Risk checks before submission | `test_unreconciled_position_change_is_risk_rejected`, `test_margin_liquidation_and_health_fail_closed` |
| Operator halt | Durable preparation remains definitely-not-sent and no execution call occurs | `test_operator_halt_is_durable_definitely_not_sent` |
| Cancel transport failure | Group and runtime latch recovery; the cancel attempt remains explicit | `test_cancel_transport_failure_latches_group_recovery` |
| Restart with unresolved child | Submission stays blocked until authoritative resolution and complete ordered bootstrap evidence | `test_restart_blocks_submission_until_ordered_bootstrap_is_complete` |
| Every durable non-terminal boundary | CREATED, ACTIVE, SUSPENDED, CLOSING, PREPARED, TRANSMITTING, SUBMITTING, OPEN, PARTIALLY_FILLED, CANCEL_PENDING, RETRY_ELIGIBLE and UNKNOWN replay exactly and fail closed | `test_every_durable_non_terminal_boundary_replays_fail_closed` |
| Cross-domain restart | OMS group, effective Portfolio position, Carry state and Accounting ledger replay to their exact pre-restart views | `test_restart_rebuilds_oms_portfolio_carry_and_accounting_evidence` |
| Financial evidence before/after positions | Hedge and financial finality remain independent and converge only from authoritative views | `test_financial_evidence_can_arrive_before_position_reconciliation` and Carry projection tests |
| Funding reversal / normal close | Reversal produces a fresh zero-target close Basket; physical close may precede financial reconciliation | `test_funding_reversal_generates_fresh_close_economic_target`, `test_physical_close_can_precede_financial_reconciliation` |

## 6. Frozen-Boundary Audit

The A018 AST and behavior audit proves:

- OMS and Risk do not import `cex_quant.applications.carry`;
- T046 Runtime adapters import no Binance or network module;
- no production composition root constructs `GroupedExecutionRuntime`;
- `OrderGroupRuntime.submit_prepared_child()` remains hard-blocked;
- no frozen public Kernel v1 contract or state owner changed.

Evidence: `tests/acceptance/test_a018_frozen_boundary.py`.

## 7. Verification

Local verification on Windows, Python 3.14.2, exact tested code baseline above:

```text
python -B -m compileall -q src                         passed
python -B -m unittest discover -s tests -p "test*.py" 573 passed
ruff check src tests tools                             passed
mypy --strict src                                      passed, 140 source files
python -B -m tools.ci.scan_secrets                     passed
pytest --cov=cex_quant --cov-branch                    573 passed,
                                                       228 subtests passed,
                                                       85.16% total coverage
required branch-coverage gate                          85.00%, passed
```

This is local evidence. The A018 baseline has not been pushed and therefore
has no remote GitHub Actions run yet.

## 8. Remaining A019 External Prerequisites

A019 cannot start until all of the following exist:

- separate, explicit project-owner authorization for bounded grouped Binance
  Testnet execution;
- final ADR-013 implementation acceptance;
- user-provided Testnet credentials through `BinanceCredentialProvider`;
- a dedicated approved Testnet account, exact BTC Spot/USD-M symbols, fixed
  quantity, maximum gross notional and maximum loss;
- persistent approved host/venue clock evidence;
- a working kill switch and authenticated operator controls;
- approved submit/query/cancel, UNKNOWN recovery, rollback and incident
  procedures;
- target-host TLS/mTLS, protected identity forwarding, remote audit retention
  and soak evidence;
- confirmation that no production endpoint or credential is present.

## 9. Testnet Go/No-Go

Current decision: **NO-GO / HOLD A019**.

A018 removes the credential-free software acceptance dependency only. It does
not grant external authority. When all section 8 items are satisfied, the
project owner may explicitly authorize A019; the first run must remain bounded
to the dedicated Testnet account and must not use production endpoints.
