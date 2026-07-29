# Portfolio Risk Authorization Schema

Status: Implemented offline under accepted ADR-012 on 2026-07-29; Web GPT
conditional implementation findings A-01 through A-07 are
remediated/confirmed at `b082af0` and await focused re-review.

## Topology

```text
AccountSnapshot + OMS journal coverage
  -> ReconciledAccountBaseline
  -> post-watermark ExecutionPositionEffect batches
  -> AccountPositionRiskView

AccountPositionRiskView
  + MarginScopeSnapshot / PositionLiquidationReference
  + marks / registered exact sensitivities / spread inputs
  + working orders / active reservations / OrderGroupView
  -> DecisionSnapshotPublication[PortfolioRiskSnapshot]
  -> PortfolioRiskEngine
  -> whole-Basket approval or exact-action permit decision
  -> PortfolioRiskCoordinator + durable Risk journal
  -> PortfolioRiskExecutionGuard
  -X-> grouped external Execution
```

The final route is intentionally disabled. The schema is offline authority
evidence, not Testnet authorization.

## Snapshot Freshness

Generic identity, assembly time and coherence remain owned by ADR-009
`DecisionSnapshotMetadata`.

ADR-012 derives `RiskSnapshotMetadata` for each assessment:

```text
snapshot_id
generated_at_ns
market_data_as_of_ns
portfolio_state_as_of_ns
valid_until_ns
risk_policy_version
```

`valid_until_ns` is the earliest deadline across snapshot, positions, marks,
spreads, sensitivities, margin and liquidation evidence. Approval and permit
deadlines cannot exceed it.

## Package Ownership

`cex_quant.portfolio` owns:

- `ExecutionCoverage`;
- `ReconciledAccountBaseline`;
- `ExecutionPositionEffect` and complete scan batches;
- `ExecutionConsistentPositionState`;
- `AccountPositionRiskView`;
- normalized collateral, margin scope and liquidation inputs.

`cex_quant.risk` owns:

- immutable `PortfolioRiskSnapshot` and versioned data-only policy;
- exact unit-labelled marks and instrument sensitivities;
- pure `PortfolioRiskEngine`;
- whole-Basket approval and exact action decisions;
- durable `PortfolioRiskCoordinator`;
- Risk journal, reservation lifecycle, authorization generation;
- directives, recovery authorization and target confirmation.

`cex_quant.oms` continues to own group/action/child execution facts.
`cex_quant.runtime` owns ordered composition through
`PortfolioRiskExecutionGuard`. Strategy and applications own neither permits
nor reservations.

## Position Truth

```text
effective quantity
  = authoritative account baseline quantity
  + accepted fill increments after baseline OMS coverage
```

Rules:

- the baseline carries an inclusive durable OMS journal watermark;
- a batch proves a complete scan from the previous watermark to a later one;
- cumulative child fill must increase monotonically;
- signed delta must equal the cumulative increment;
- exact batch redelivery is idempotent;
- a gap, changed identity, changed direction or divergence is fail-closed;
- a newer authoritative baseline resets the overlay because its covered fills
  must not be counted twice.

Only `READY` position views with reconciliation and observation evidence enter
Portfolio Risk.

## Whole-Basket Admission

```python
PortfolioRiskEngine.assess_basket(
    basket,
    risk_snapshot,
    policy,
    now_ns=...,
) -> BasketPortfolioRiskDecision
```

The engine:

- preserves unrelated current positions;
- applies other active reservations;
- replaces every Basket leg target atomically;
- computes current, projected and conservative-working exposure;
- returns one ALLOW or one REJECT for the complete identity-equal Basket.

ALLOW contains `PortfolioApprovalEvidence`. It is not publishable until
`PortfolioRiskCoordinator.reserve_approval()` has durably appended the
approval/reservation evidence.

Approval also carries canonical `RiskResourceClaim` values. Position targets
are exclusive resources. Available margin, gross/initial margin and configured
factor Delta/Gamma/Vega limits are shared-capacity resources. The coordinator
serializes claims by `RiskResourceKey`; disjoint instruments may proceed while
shared capacity permits.

## Per-Action Authorization

```python
PortfolioRiskEngine.authorize_action(
    group,
    action,
    risk_snapshot,
    policy,
    now_ns=...,
) -> ExecutionActionRiskDecision
```

An allowed decision contains the existing OMS `ExecutionActionPermit` bound
to:

- exact `OrderGroupId`;
- expected pre-preparation group revision;
- exact `GroupActionId` and action checksum;
- current Portfolio Risk snapshot;
- current policy version;
- finite expiry.

The coordinator records the issuance generation before returning the permit.
Every material position, order, margin, market, policy, health, operator,
reservation or reconciliation change must call `record_material_change()`
with a typed `RiskInvalidationTrigger`. That trigger is journaled, advances
the durable generation and invalidates unconsumed permits.

Immediately before future external I/O, the runtime guard proves:

- the platform/operator guard still passes;
- the request belongs to the exact prepared child;
- the prepared group revision is exactly the authorized revision plus the
  durable preparation transition;
- permit generation is current;
- action, checksum and permit identity are unchanged;
- the permit is unexpired and unconsumed.

It then durably consumes the permit. Any failure stops before external I/O.

## Reservation Lifecycle

```text
ACTIVE
  -> ATTACHED_TO_GROUP
  -> RELEASED | EXPIRED | RECOVERY_REQUIRED
```

Reservations are keyed by `PortfolioApprovalId`. Exact redelivery is
idempotent; changed content is a conflict. Active scope overlap and concurrent
margin-capacity overspend are rejected by the single-writer coordinator.

## Recovery Evidence

`GroupRecoveryAuthorization` never impersonates operator resume authority.
It requires:

- a group already in `RECOVERY_REQUIRED`;
- no unresolved UNKNOWN child;
- ready reconciled Portfolio positions;
- a reconstructable attached reservation;
- a current Risk snapshot and finite deadline.

`PortfolioTargetConfirmation` requires:

- a closing group;
- no unresolved action or signed working quantity;
- ready effective positions equal to every Basket target;
- no conflicting active reservation.

Position equality uses a versioned `TargetMatchPolicy` with a default and
optional per-instrument absolute quantity tolerance. Confirmation evidence
persists the policy version and checksum. Price and Greek tolerances do not
belong to this position-target boundary.

Confirmation does not create application `HEDGED` or `ACTIVE` state.

## Compatibility

- Existing `PositionTargetIntent`, `RiskEngine`, single-order OMS journals and
  the single-leg Pipeline are unchanged.
- Portfolio Risk has no Funding, Carry, Market Making or two-leg branch.
- Option Greeks remain system Feature inputs converted to exact, unit-labelled
  evidence; Risk does not construct volatility surfaces or calculate Greeks.
- Quanto and unregistered models fail closed.
- Risk directives never call OMS or Execution.
- Decision status distinguishes `REJECT`, `STALE`, `INSUFFICIENT_DATA` and
  `RECOVERY_REQUIRED`; missing or old evidence is not mislabeled as an
  economic limit rejection.
