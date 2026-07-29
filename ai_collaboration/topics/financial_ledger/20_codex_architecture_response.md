---
id: AI-20260729-013
title: Codex Financial Ledger and PnL Architecture Response
origin: codex
status: READY_FOR_REVIEW
created: 2026-07-29
code_baseline: b082af0618e180f98441af5dc6d49c906994a012
supersedes: none
related:
  - 10_web_gpt_input.md
  - ../funding_arbitrage/84_codex_adr013_current_code_audit.md
  - ../funding_arbitrage/85_codex_adr013_proposal_handoff.md
  - ../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md
  - ../carry_application/20_codex_architecture_response.md
external_share: allowed
sensitivity: public-project
---

# Codex Architecture Response: Financial Ledger and PnL Attribution

## Executive Result

ADR-013 should remain an independent `cex_quant.accounting` domain.

The correct pipeline is:

```text
authenticated venue financial evidence
  -> canonical immutable source facts
  -> durable fact convergence
  -> deterministic versioned mapping
  -> balanced append-only per-asset ledger
  -> source and balance reconciliation
  -> append-only ownership allocation
  -> derived valuation and PnL attribution
```

No accepted ADR-009 through ADR-012 contract requires redesign.

ADR-013 design is ready for Web GPT review. Source implementation remains
unauthorized. ADR-014 formal review should use the generic ownership and
attribution boundary defined here; Accounting must never import Carry.

## 1. Current-Code Audit

### Reusable platform capabilities

| Current capability | Accounting use |
|---|---|
| strong venue/account/order/group identities | source causation and audit references |
| Binance private message access and reconciliation fixtures | future one-pass financial projection |
| OMS order journal and immutable group facts | execution causation, not ledger truth |
| Portfolio account snapshots | authoritative balance/position reconciliation anchors |
| Recorder/journal patterns | durability and replay design precedent |
| Feature/market snapshot contracts | explicit valuation evidence |
| Runtime health and operator gating | fail-closed new-exposure policy |
| ADR-012 Risk coordinator | consumer of Accounting health, not PnL |

### Missing capabilities

There is no `cex_quant.accounting` package and no:

- fill-level financial fact with venue trade identity;
- actual Funding/interest/transfer history fact;
- commission component retaining charged asset;
- economic fact convergence across stream and REST history;
- balanced financial ledger;
- source-completeness or balance-reconciliation state;
- allocation or `UNALLOCATED` remainder;
- valuation/PnL attribution read model.

### Facts that must not be reused as substitutes

- OMS cumulative fill and average price cannot reconstruct individual fills.
- `FundingRateUpdate` is a market expectation, not proof of account Funding.
- current Portfolio balances are state, not transaction history.
- Recorder evidence is not a ledger account/posting model.
- Strategy labels and timestamps are not ownership proof.

## 2. Package Topology

Proposed after ADR acceptance:

```text
src/cex_quant/
  core/
    identifiers.py                  # cross-domain opaque ID types

  accounting/
    __init__.py
    identifiers.py                  # deterministic ID derivation/validation
    facts.py
    convergence.py
    model.py
    policy.py
    mapping.py
    journal.py
    ledger.py
    reconciliation.py
    allocation.py
    valuation.py
    attribution.py
    health.py

  execution/adapters/
    binance_financial.py

  runtime/
    financial_fact_handoff.py
    accounting_coordinator.py
```

Exact filenames may change after review. Ownership may not.

Cross-domain `NewType` definitions follow the repository convention and live
once in `core.identifiers`. `accounting.identifiers` may provide deterministic
construction and validation helpers; it must not redefine the same types.

Dependency direction:

```text
private adapter
  -> canonical financial observations
  -> runtime durable handoff
  -> accounting convergence/ledger

OMS immutable facts -----------\
Portfolio immutable snapshots --+-> Accounting read-side operations
Market/Feature snapshots -------/

applications
  -> immutable Accounting attribution/read views only

Risk
  -> Accounting health/readiness only
```

Forbidden:

- Accounting importing `applications` or venue payload classes;
- applications posting or correcting ledger transactions;
- OMS treating its aggregate state as financial truth;
- Portfolio mutating ledger state;
- Market Data creating account cash flows;
- Execution adapters directly mutating the ledger;
- Risk evaluating strategy PnL;
- Funding-specific branches in generic mapping, reconciliation or allocation.

## 3. Canonical Source Facts

Canonical input:

```text
FinancialSourceFact
  = ExecutionFillFact
  | AccountCashFlowFact

ObservedFinancialFact
  = FinancialSourceFact
  + transport/source provenance
```

### ExecutionFillFact

Required information:

- venue, account, product and instrument;
- venue order ID, client order ID and venue trade ID;
- exact last-fill quantity and price;
- exact quote amount when authoritative, otherwise deterministic derivation
  policy and precision evidence;
- zero or more commission components with asset and amount;
- realized settlement PnL when supplied by the venue;
- optional immutable Intent, Basket leg, Order Group and child causation;
- economic time and schema version.

The fact is one economic fill, not an OMS status update.

### AccountCashFlowFact

Required categories include:

- actual Funding settlement;
- commission/rebate not attached to a fill;
- borrow interest;
- realized derivative settlement;
- deposit, withdrawal and transfer;
- liquidation/insurance movement;
- explicit venue adjustment.

Every fact requires account scope, asset, signed amount, venue business
reference, effective time and source schema.

Actual Funding always comes from authenticated account evidence. Market
Funding rate never posts a transaction.

## 4. Identity and Stream/History Convergence

Two identities remain separate:

```text
FinancialObservationId
  transport delivery, source, cursor and receive provenance

FinancialFactId
  one economic venue fact independent of delivery channel
```

Canonical business keys are product/source specific and versioned. Examples:

```text
fill:
  venue + account + product namespace + venue trade ID

account income:
  venue + account + income type + venue transaction ID

transfer:
  venue + account/location scope + transfer business ID
```

Rules:

- timestamp proximity is never identity;
- receive time is never identity;
- exact redelivery is idempotent;
- stream/history overlap retains multiple observations but one fact;
- same fact identity with changed economic content is a conflict;
- ambiguous venue aliasing becomes reconciliation failure, not auto-merge;
- one economic fact maps to ledger transactions once.

## 5. One-Pass Private-Message Projection

One raw private message should be decoded and schema-validated once:

```text
raw private message
  -> versioned canonical private event
      -> OMS projection
      -> Portfolio projection
      -> Accounting observation projection
```

Each projection is independently typed and may be absent. The adapter does not
call mutable domain services. Runtime routes projections to their owners.

This avoids three incompatible venue parsers while preserving domain
independence.

## 6. Ledger Model

The canonical invariant is double entry per asset:

```text
for every LedgerTransaction and AssetId:
    sum(LedgerPosting.signed_amount for that asset) == 0
```

Unlike assets are never added inside the immutable ledger.

Examples:

```text
Funding receipt in USDT
  Dr venue cash:USDT
  Cr funding income clearing:USDT

Commission charged in BNB
  Dr commission expense:BNB
  Cr venue cash:BNB

Spot BTC purchase
  Dr venue inventory:BTC
  Cr trade clearing:BTC
  Dr trade clearing:USDT
  Cr venue cash:USDT
```

Reporting-currency conversion is a derived view with explicit mark, source and
time evidence. It never changes original-asset postings.

### Mapping

Mapping policy is versioned by venue/product/fact schema. A transaction records
the exact mapping-policy version and source fact IDs.

Unknown or unsupported facts do not enter a generic suspense posting
automatically. They remain durable unposted facts, make reconciliation
incomplete and latch Accounting unhealthy for new exposure.

### Corrections

Posted facts are immutable:

```text
incorrect transaction
  -> exact reversal transaction
  -> corrected new transaction
```

No edit, deletion or silent backfill is allowed.

## 7. Durability and Hot-Path Boundary

Accounting is not inserted into synchronous order submission:

```text
private financial observation
  -> bounded durable Accounting inbox
  -> convergence journal
  -> mapping
  -> ledger journal
  -> published read views
```

Required semantics:

- durable retention before acknowledging Accounting ingestion;
- single writer for canonical fact and ledger state;
- checksummed sequence/replay;
- bounded records, payloads, queues and batch sizes;
- no dropped evidence;
- corruption, gaps, identity conflict or exhausted durable capacity fail
  closed;
- slow Accounting does not retroactively change submit outcome.

If evidence cannot be retained:

- Accounting health becomes unhealthy;
- new exposure is blocked through Runtime/Risk health;
- query, cancel, reduce-only and recovery remain available;
- the incident is not displayed as successful or zero PnL.

## 8. Reconciliation

Two proofs must remain distinct.

### Source completeness

For an explicit venue/account/product/time-or-cursor scope:

```text
private stream facts
  + authenticated trade/income/transfer history
  = complete canonical financial fact set
```

Completeness records source windows/cursors, gaps, query coverage and
conflicts.

### Balance proof

Per asset and account location:

```text
opening authoritative balance
  + ledger movements during interval
  = closing authoritative balance
```

A source-complete interval can still fail balance proof. A matching balance
does not prove source completeness. Neither proof may silently post an
“adjustment” to make the other pass.

Startup remains financially unhealthy until the configured reconciliation
scope completes.

## 9. Generic Ownership and ADR-014 Alignment

Ledger completeness precedes attribution. Every proven financial fact posts
even if ownership is unknown.

Accounting exposes a generic owner boundary:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class EconomicOwnerTypeRef:
    name: str
    version: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EconomicOwnerRef:
    owner_type: EconomicOwnerTypeRef
    owner_id: str
```

ADR-014 may convert a Carry `ApplicationPositionId` into:

```text
EconomicOwnerRef(
  owner_type = application.position@1,
  owner_id = <canonical ApplicationPositionId>
)
```

Accounting does not import or interpret Carry lifecycle, pair type, objective
or hedge state.

Allocation records:

- transaction/posting identity;
- owner reference;
- original-asset amount;
- policy version;
- exact ownership/time-coverage evidence;
- append-only reversal/reallocation lineage.

Invariant:

```text
sum(allocated original-asset amounts)
  + explicit unallocated amount
  = posting amount
```

`UNALLOCATED` is a remainder, not a fake application. When shared-account
Funding ownership is incomplete, attribution stays incomplete.

## 10. Valuation and PnL

### Ledger facts

- actual Funding settlement;
- commissions/rebates;
- borrow interest;
- realized venue settlement;
- explicit liquidation/other cost;
- deposits, withdrawals and transfers as non-PnL capital flows.

### Derived valuation

- current marked value;
- unrealized Spot/perpetual/futures/options change;
- basis change;
- explicit currency conversion;
- application-level marked view.

Valuation consumes a coherent snapshot and never writes mark ticks into the
ledger. Missing marks/conversion/models produce `INCOMPLETE`, not zero.

### Signed PnL

A generic view may present:

```text
realized net PnL
  = realized trading/settlement PnL
  + signed Funding
  + rebates
  - commissions
  - borrow interest
  - other explicit costs

total marked PnL
  = realized net PnL
  + allocated unrealized valuation change
```

Funding received is positive; Funding paid is negative. The immutable ledger
retains algebraic posting signs and account semantics.

### Slippage boundary

Slippage is normally not a venue cash-flow fact. It is a derived
execution-quality attribution relative to a versioned benchmark snapshot.

If actual trading PnL already uses executed prices, subtracting slippage again
would double count. Slippage may:

- explain a portion of trading performance relative to a benchmark; or
- remain an expected Feature before execution.

It must not become an additional ledger expense unless a separate real venue
cash flow exists.

### No realized/unrealized double count

When a derivative mark movement becomes venue-realized settlement, the
attribution projector must move the component from unrealized to realized
under a versioned policy. It cannot retain both.

## 11. Public Contract Shape

Proposal-level ports:

```python
class FinancialObservationIngressPort(Protocol):
    def ingest(self, observation: ObservedFinancialFact) -> IngressResult: ...


class AccountingHealthReadPort(Protocol):
    def snapshot(self) -> AccountingHealthView: ...


class LedgerReadPort(Protocol):
    def transactions(
        self, scope: LedgerQueryScope
    ) -> tuple[LedgerTransactionView, ...]: ...


class ReconciliationReadPort(Protocol):
    def status(
        self, scope: FinancialReconciliationScope
    ) -> FinancialReconciliationView: ...


class AttributionReadPort(Protocol):
    def view(
        self,
        owner: EconomicOwnerRef,
        interval: AttributionInterval,
        reporting_asset: AssetId,
    ) -> PnlAttributionView: ...
```

These names and schemas freeze only after ADR review. Applications receive
immutable views; they cannot access a mutable ledger service.

### Package exports

`cex_quant.accounting.__init__` should document the domain boundary and export
only accepted public contracts:

- strong financial/ledger IDs from `core`;
- immutable source-fact and observation contracts;
- immutable transaction/posting/read views;
- reconciliation and health views;
- `EconomicOwnerTypeRef`, `EconomicOwnerRef` and allocation views;
- valuation/PnL attribution views;
- explicitly accepted ingress/read protocols.

It should not export mutable ledger state, journal implementation classes,
venue parsers, mapping internals or application-specific helpers. This keeps
the `__init__.py` surface an interface declaration rather than a shortcut
around ownership.

## 12. Interaction with ADR-012

ADR-012 may consume:

- Accounting health;
- required source/reconciliation readiness;
- a typed indication that financial state is safe for new exposure.

ADR-012 must not consume strategy PnL to decide whether one execution action
is authorized, and Accounting cannot issue or invalidate permits directly.
Runtime translates platform health into the existing fail-closed authority
chain.

Existing recovery behavior remains:

```text
Accounting unhealthy
  -> reject new exposure
  -> preserve query/cancel/reduce/recovery
```

## 13. Implementation and Promotion Sequence

Current authorization:

```text
ADR-013 design/review             AUTHORIZED
ADR-013 source implementation     NOT AUTHORIZED
ADR-014 formal review             WAITING FOR SCOPE ALIGNMENT
Carry/Funding implementation      NOT AUTHORIZED
Grouped external execution        BLOCKED
Testnet / Production              NOT AUTHORIZED
```

After explicit ADR-013 acceptance:

1. assign bounded task and acceptance IDs;
2. implement identities and immutable fact contracts;
3. add complete offline Binance financial fixtures;
4. implement one-pass projections and durable fact convergence;
5. implement balanced ledger, replay and corrections;
6. implement reconciliation, allocation, valuation and attribution views;
7. complete offline fault-injection and restart acceptance;
8. publish final Accounting public exports;
9. align and review ADR-014;
10. keep external environments separately gated.

## 14. Review Request

Classify findings as:

- **A. ADR-013 design error** — required before acceptance;
- **B. ADR-014 application alignment issue** — valid but owned by the Carry
  boundary after the generic Accounting contract is frozen;
- **C. long-term optimization** — non-blocking beyond the safe first
  implementation.

Specific questions:

1. Are the source-fact union and business-key rules sufficient?
2. Is per-asset double entry the correct canonical invariant?
3. Is one-pass private-event fan-out compatible with domain ownership?
4. Are the durable side path and health semantics correct?
5. Are source completeness and balance proof correctly independent?
6. Does `EconomicOwnerRef` remove the Accounting-to-Carry dependency?
7. Is `UNALLOCATED` mandatory under incomplete ownership?
8. Are realized facts, valuation, basis and slippage separated without double
   counting?
9. Are the proposed public ports sufficient for ADR-014?
10. Which item, if any, blocks ADR-013 acceptance?
