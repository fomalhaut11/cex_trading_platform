# Codex ADR-010 Implementation Acceptance

Date: 2026-07-28

Scope: T027, T028 and A013 only

## Result

ADR-010 implementation acceptance is complete.

The change adds a generic, bounded N-leg decision contract. It does not add
Funding Arbitrage application logic, Parent/Child OMS, Portfolio Risk, child
execution, Testnet access or production authorization.

## Architecture Result

The implemented decision path is:

```text
DecisionSnapshotPublication
  -> StrategyRuntime
  -> BasketTargetIntent
  -> explicit pipeline capability boundary
```

The existing path remains:

```text
market event / FeatureSnapshot
  -> StrategyRuntime
  -> PositionTargetIntent
  -> existing single-leg Pipeline
  -> Risk -> OMS -> Execution
```

`PositionTargetIntent` was not modified, wrapped or migrated.

## T027

Implemented:

- shared existing `IntentId` for Basket identity;
- new `BasketLegId` and `ObjectiveTypeId`;
- versioned `ObjectiveTypeRef`;
- immutable metadata-only `ObjectiveTypeRegistry`;
- immutable `BasketTargetLeg` and `BasketTargetIntent`;
- canonical account/venue/kind/symbol leg order;
- two-to-16-leg hard bounds;
- unique leg and account/instrument scopes;
- same Instrument across different accounts;
- exact signed fixed-point targets, including zero;
- mandatory expiry and seven-day hard validity cap;
- lower deployment limits through `BasketIntentPolicy`;
- deterministic leg and Basket identity;
- bounded canonical JSON evidence codec with schema version and SHA-256
  payload checksum.

## T028

Implemented:

- additive `StrategyInput` support for
  `DecisionSnapshotPublication[object]`;
- unchanged `StrategyDecision` dataclass shape;
- additive `DecisionIntent` union;
- Basket Strategy ID and common Intent ID validation;
- mandatory matching `DecisionSnapshotId`;
- rejection when decision time predates snapshot assembly;
- explicit Basket enablement through both Objective Registry and Basket
  admission policy;
- explicit single-leg `TradingPipeline` rejection at Strategy stage;
- no Portfolio, Risk, OMS or Execution call after that rejection.

## A013 Required Scenarios

| Scenario | Result |
|---|---|
| Existing `PositionTargetIntent` remains compatible | Passed |
| BTC Spot `+10` + BTC Perpetual `-10` Basket generation | Passed |
| Two-option spread + Perpetual Delta hedge three-leg generation | Passed |
| Basket Snapshot ID mismatch | Rejected and latched fail-closed |
| Single-leg Pipeline receives Basket | Explicitly rejected before Risk/OMS/Execution |

Additional evidence covers bounds, canonical ordering, duplicate scopes,
different accounts, zero targets, Objective versions and registry admission,
deterministic replay, serialization mutation and size limits.

## Verification

```text
compileall: passed
Ruff: passed
strict MyPy: passed, 88 source files
secret scan: passed
full regression: 397 passed
subtests: 129 passed
acceptance suite: 34 passed
branch coverage: 86.34%
coverage gate: 85%
```

## Files for Review

Core implementation:

- `src/cex_quant/strategy/basket.py`
- `src/cex_quant/strategy/basket_codec.py`
- `src/cex_quant/strategy/model.py`
- `src/cex_quant/strategy/runtime.py`
- `src/cex_quant/runtime/pipeline.py`

Acceptance evidence:

- `tests/test_basket_intents.py`
- `tests/test_basket_strategy_runtime.py`
- `tests/test_runtime_pipeline.py`
- `tests/acceptance/test_basket_intents.py`

Stable interface:

- `interfaces/basket_intent_schema.md`

## Boundary for the Next Review

ADR-011 should decide how one completely approved Basket becomes a durable
Parent Order Group with bounded child actions, unknown-state recovery and
restart replay.

ADR-010 does not answer that execution question and intentionally contains no
Basket lifecycle.
