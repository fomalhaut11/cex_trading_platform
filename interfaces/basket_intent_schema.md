# Basket Intent Schema

Status: Accepted by ADR-010; implemented by T027/T028; accepted by A013

## Purpose

`BasketTargetIntent` is one immutable, venue-neutral portfolio target. It
expresses what a strategy wants the portfolio to become; it is not an order,
an execution plan or a lifecycle state.

The contract supports any bounded two-to-16-leg objective. It is not specific
to Funding Arbitrage and does not encode a two-leg assumption.

## Public Packages

```text
cex_quant.core
  IntentId                 # shared Position/Basket decision identity
  BasketLegId
  ObjectiveTypeId

cex_quant.strategy
  ObjectiveTypeRef
  ObjectiveTypeDefinition
  ObjectiveTypeRegistry
  BasketTargetLeg
  BasketTargetIntent
  BasketIntentPolicy
  create_basket_target_intent
  deterministic_basket_leg_id
  deterministic_basket_intent_id
  encode_basket_target_intent
  decode_basket_target_intent
  basket_target_intent_checksum
```

`DecisionIntent` is:

```python
PositionTargetIntent | BasketTargetIntent
```

The existing `PositionTargetIntent` remains unchanged and is not converted
into a one-leg Basket.

## Objective Type

An objective is metadata for policy and audit:

```python
ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("carry.funding"),
    version=1,
)
```

IDs use lowercase ASCII namespace segments. Versions are positive and never
reinterpreted. The immutable registry stores definitions and ownership only;
it cannot contain callbacks, imports, Risk rules or application code.

## Leg Contract

Each `BasketTargetLeg` contains:

- deterministic or caller-approved `BasketLegId`;
- canonical internal `AccountId`;
- canonical `InstrumentId`;
- exact signed target position as `Quantity`;
- optional bounded diagnostic reason.

The target is the desired final position, not an order size. Zero is valid for
closing an existing position. Duplicate `(account_id, instrument_id)` scopes
inside one Basket are invalid, while the same Instrument across distinct
accounts is allowed.

## Basket Contract

Each `BasketTargetIntent` contains:

- shared `IntentId`;
- `StrategyId`;
- causal `DecisionSnapshotId`;
- versioned objective reference;
- canonical tuple of two to 16 legs;
- decision and mandatory expiry timestamps;
- positive policy version;
- optional bounded reason.

Canonical leg order is:

```text
account_id, venue, instrument kind, symbol
```

The public dataclass rejects non-canonical order. The construction helper
sorts candidate legs before creating the immutable value.

The hard validity cap is seven days. Deployment policy can impose lower leg,
validity and objective limits but cannot raise contract hard limits.

## Identity and Replay

Default leg IDs are SHA-256 digests over:

```text
DecisionSnapshotId + AccountId + canonical InstrumentId
```

Default Basket IDs are SHA-256 digests over all immutable decision content,
including ordered legs, exact fixed-point values, objective, policy, times and
reason. Exact replay therefore reproduces an identity-equal Basket; changed
content produces a different default `IntentId`.

These hashes are identities, not authentication tokens.

## Serialization

`encode_basket_target_intent` produces deterministic canonical UTF-8 JSON:

```text
format = cex_quant.basket_target_intent
format_version = 1
payload = complete Basket contract
checksum = SHA-256(canonical payload)
```

Encoded evidence is capped at 65,536 bytes. Decoding validates the exact
envelope and payload schema, format version, checksum, fixed-point fields and
all Basket invariants. Unknown versions, mutations and oversized records fail
closed.

## Strategy and Pipeline Boundary

`StrategyInput` additively accepts `DecisionSnapshotPublication[object]`.
When a strategy emits a Basket:

- the input must be a decision-snapshot publication;
- the Basket `decision_snapshot_id` must match the publication;
- decision time cannot predate snapshot assembly;
- the runtime must be explicitly configured with both an immutable Objective
  Type Registry and a Basket admission policy;
- the complete Basket must pass that policy before leaving Strategy Runtime;
- strategy identity and per-decision `IntentId` uniqueness remain mandatory.

Configuring only the Registry or only the policy is invalid. A runtime without
both continues to support Position intents but fails closed on Basket output.

The current `TradingPipeline` is explicitly single-leg. If it receives a
Basket, it rejects at the Strategy stage before Portfolio, Risk, OMS or
Execution. It never splits the Basket into independent intents.

ADR-010 creates no Parent/Child Order Group, child order, exchange request,
portfolio-risk approval or economic application state. Those belong to later
ADRs.

## Acceptance Evidence

A013 proves offline that:

- existing Position Target strategy behavior remains compatible;
- BTC Spot `+10` and BTC Perpetual `-10` form one two-leg Basket;
- a two-option spread plus Perpetual Delta hedge forms one three-leg Basket;
- mismatched Snapshot identity is rejected;
- the single-leg Pipeline rejects Basket before Risk/OMS/Execution;
- deterministic serialization, replay, bounds and objective policy hold.
