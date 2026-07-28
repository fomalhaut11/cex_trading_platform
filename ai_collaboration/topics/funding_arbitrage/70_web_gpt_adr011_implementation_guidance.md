# Web GPT Implementation Guidance - ADR-011

Date: 2026-07-28

Status: Architecture confirmed, implementation guidance

## Review Result

Web GPT reviewed the accepted ADR-011 architecture.

Conclusion:

ADR-011 design is accepted.

The separation between:

```text
Economic Intent
  -> Execution Control
  -> Execution Action
  -> Child Order Attempt
```

is architecturally correct.

## Confirmed Design Principles

### 1. Basket is not execution

ADR-010 `BasketTargetIntent` represents the economic objective.

ADR-011 Order Group represents execution control.

Do not merge these domains.

### 2. ExecutionActionPermit boundary

The proposed boundary is accepted.

`ExecutionAction` cannot reach `ExecutionGateway` without:

- valid permit;
- matching group revision;
- durable action record;
- unexpired authorization.

`ExecutionActionPermit` is not general order permission. It is permission for
one specific exposure-changing action.

### 3. UNKNOWN handling

Unknown outcome is not failure.

Unknown outcome means:

```text
RECOVERY_REQUIRED
```

Never:

- blindly retry;
- create a replacement economic action;
- reuse identity after possible submission.

### 4. State ownership

OMS owns:

- group execution state;
- child order facts;
- recovery state.

Portfolio Risk owns:

- Delta;
- basis;
- margin;
- hedging assessment;
- economic completion.

Do not introduce `HEDGED` or `PARTIALLY_HEDGED` into OMS.

## Implementation Boundary

Authorized:

### T029

- immutable identifiers;
- group/action/permit contracts.

### T030

- group state model;
- journal facts;
- replay;
- recovery framework.

### T031

- durable-before-external-I/O handoff;
- shared safety boundary.

### A014

- offline acceptance tests.

## Important Constraint

Before ADR-012 acceptance, the following are forbidden:

- real `ExecutionActionPermit` issuance;
- exposure-changing Order Group submission;
- Execution adapter integration for grouped orders;
- Funding Arbitrage execution;
- Testnet trading.

## Special Attention for T031

The current single-leg `TradingApplication` issue is important:

`SUBMITTING` must be durably recorded before external submission.

The solution must be shared infrastructure. Single-leg and multi-leg execution
must use the same durable handoff principle.

Do not create a safer multi-leg path while leaving legacy single-leg execution
weaker.

## ADR-012 Preparation

Implementation should expose the future boundary.

ADR-012 will provide:

- Portfolio Risk approval;
- `ExecutionActionPermit` authorization.

Do not implement the following inside ADR-011:

- Delta calculation;
- basis model;
- margin model;
- liquidation model.

## Prohibited Domain Leakage

OMS must not calculate Risk inside an operation such as:

```python
OrderGroup.can_execute()
```

The intended boundary is:

```text
ADR-012 Risk
  -> ExecutionActionPermit
  -> ADR-011 OMS
```

OMS must also remain application-neutral. It may know group, action and order
facts, but it must not contain Funding- or Carry-specific branches.

## Final Recommendation

Proceed with T029-T031 implementation.

Keep ADR-011 execution-focused.

Reserve economic Risk decisions for ADR-012.
