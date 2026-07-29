# ADR-013 Financial Ledger and PnL Attribution

## Status

Proposed — 2026-07-28.

This ADR is prepared for the 2026-07-29 batch architecture review. It changes
no source contract and grants no implementation, Testnet or production
authorization.

Reviewed baseline:

`fa0df9e2a015db258457d226c7ed9fa5c689b8eb`

ADR-012 is now Accepted and implemented through its bounded offline gate.
ADR-013 remains independently reviewable because its source-fact and ledger
ownership decisions are inspectable without enabling grouped execution.
ADR-014 implementation remains dependent on accepted ADR-009 through ADR-013.

## Context

An order fill is not a strategy profit record.

Funding Carry can receive economic value from:

```text
funding settlement
+ realized trading/settlement PnL
+ rebates
- commissions
- borrow interest
- other explicit costs
+/- unrealized mark and basis change
```

The current repository stores:

- cumulative order fill quantity and average fill price in OMS;
- venue-supplied position cost basis and realized PnL in Portfolio snapshots;
- balances as absolute account state;
- Funding rate and next Funding time as Market Data;
- durable OMS and Recorder evidence.

It does not store:

- fill-level financial facts;
- commission asset and amount;
- actual Funding settlement cash flows;
- borrow interest, transfers, withdrawals or adjustments;
- a balanced immutable ledger;
- source completeness/reconciliation cursors;
- application/strategy allocation evidence;
- realized and unrealized PnL attribution.

Funding rate is a market observation. It is not proof that a Funding payment
occurred. An absolute balance change is also not sufficient evidence of why
cash moved.

## Current-Code Findings

### OMS is execution truth, not a financial ledger

`OrderEvent` contains:

```text
venue_update_id
client_order_id
status
cumulative_filled_quantity
average_fill_price
```

This is sufficient for order lifecycle and position overlay. It is
insufficient for Accounting because:

- cumulative quantity does not identify each fill;
- average price cannot reconstruct fill-level settlement exactly;
- commission amount and asset are absent;
- derivative realized PnL is absent;
- a later cumulative update overlaps earlier cumulative state.

Accounting must not reverse-engineer financial facts from OMS aggregates.

### Existing Binance fixtures already expose unused fill identity

Spot `executionReport` and Futures `ORDER_TRADE_UPDATE` contain a venue trade
ID and last-fill quantity/price. The current normalizer uses these fields only
to form an order-update identity and emits an aggregate reconciliation view.

Real Binance financial fields such as commission, commission asset and
realized PnL require additive canonical normalization and dedicated fixtures.

### Market Funding is not account Funding

`FundingRateUpdate` belongs to Market Data and represents rate/next-time
information. It must never be posted as income or expense.

Actual Funding settlement must come from an authenticated account/private-
stream or income-history source with an account-scoped venue transaction ID.

### Portfolio snapshots are reconciliation inputs

`Balance` and `Position.realized_pnl` are absolute venue values. They help
prove closing state and detect divergence. They do not provide an immutable
transaction history and cannot identify Funding, fee, transfer or adjustment
causes.

### Recorder is not the Financial Ledger

The Recorder persists canonical market events and replay evidence. It does not
own account financial truth, balanced postings, reconciliation or PnL
allocation.

## Decision Summary

Add an independent `cex_quant.accounting` domain with four layers:

1. canonical immutable financial source facts;
2. a balanced append-only multi-asset ledger;
3. venue/source reconciliation and completeness state;
4. derived allocation, valuation and PnL attribution views.

The core invariant is:

```text
venue/account source fact
  -> canonical FinancialFactId
  -> deterministic balanced LedgerTransaction
  -> append/fsync
  -> immutable ledger state
  -> reconciliation
  -> optional application/strategy attribution
```

Ledger truth does not replace:

- OMS order state;
- Portfolio positions/balances;
- Market Data;
- Risk exposure;
- Carry application lifecycle.

## 1. Terminology

### Financial source fact

One normalized account-scoped economic observation with stable venue
identity, exact amount/quantity, asset, time and provenance.

### Cash-flow fact

A source fact that directly changes one venue account asset balance, such as
Funding settlement, commission, interest or transfer.

### Fill fact

One fill-level execution fact with venue trade identity, last-fill quantity
and price, order causation and any financial components published with the
fill.

### Ledger transaction

One immutable, balanced set of postings caused by one source fact or explicit
accounting correction.

### Posting

One signed exact change to one internal ledger account in one asset.

### Ledger account

A versioned registered accounting bucket such as venue cash, asset inventory,
trade clearing, Funding income, commission expense or suspense.

### Allocation

Append-only evidence assigning all or part of a ledger amount to an economic
owner such as a strategy, Order Group or application position.

### Valuation

A point-in-time derived view using positions, marks and conversion rates. It
is not an immutable cash transaction.

### Reconciliation

Proof that ledger source coverage and per-asset balances agree with
authoritative venue history/snapshots for a declared scope and interval.

## 2. Package Topology

Planned after acceptance:

```text
src/cex_quant/
  core/
    identifiers.py               # financial and ledger IDs

  accounting/
    __init__.py
    facts.py                     # fill and account cash-flow facts
    model.py                     # accounts, transactions and postings
    policy.py                    # registered mapping/precision policy
    ledger.py                    # single-writer immutable ledger state
    journal.py                   # durable canonical evidence
    reconciliation.py            # source coverage and balance proof
    allocation.py                # append-only ownership evidence
    valuation.py                 # derived marked views
    attribution.py               # PnL component projections

  execution/adapters/
    ...                          # additive financial fact normalization

  runtime/
    financial_fact_handoff.py    # bounded durable side-path
    accounting_coordinator.py    # composition and health
```

### Dependency direction

```text
accounting.facts -> core, instruments
accounting.ledger -> accounting contracts, core
accounting.reconciliation -> accounting, Portfolio immutable views
accounting.valuation -> accounting views, Portfolio, instruments,
                        market/Feature snapshot contracts
accounting.attribution -> accounting views and generic owner identities
runtime -> adapters, OMS, Portfolio, accounting and health ports
applications -> immutable accounting/attribution views only
```

### Prohibited dependencies

- Accounting cannot import an application implementation.
- OMS cannot import Accounting.
- Portfolio cannot import Accounting ledger state.
- Execution adapters cannot post directly into mutable ledger state.
- Applications cannot write or edit ledger transactions.
- Market Data cannot create account cash flows.
- No module may inspect a Funding strategy name inside generic ledger mapping.

## 3. Identities

Add strong cross-domain identities after acceptance:

```python
FinancialFactId
FinancialObservationId
LedgerTransactionId
LedgerPostingId
LedgerAccountId
FinancialReconciliationId
AttributionAllocationId
```

`CashFlowId` from the planning document is refined to
`FinancialFactId` because not every source fact is a single cash flow. A fill
can produce multiple asset postings and multiple financial components.

Identity rules:

- venue fact identity includes venue, account, economic record/component type,
  venue business ID and any required product namespace;
- fact identity is independent of whether the fact arrived through private
  stream, REST history or reconciliation overlap;
- transport observations have their own identity and provenance;
- timestamp alone is never an idempotency key;
- local receive time is never an economic identity;
- exact redelivery is idempotent;
- same identity with changed content is a conflict and latches Accounting
  unhealthy;
- ledger transaction/posting IDs are deterministic from complete canonical
  content;
- IDs are causation/integrity references, not authentication tokens.

## 4. Canonical Financial Source Facts

### 4.1 Economic fact metadata

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialFactMetadata:
    fact_id: FinancialFactId
    venue: VenueId
    account_id: AccountId
    venue_reference: str
    effective_time_ns: UnixNanos
    schema_version: int
```

The venue reference is bounded, normalized and secret-free.

Transport provenance is stored separately:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialFactObservation:
    observation_id: FinancialObservationId
    fact_id: FinancialFactId
    source_kind: FinancialSourceKind
    observed_at_ns: UnixNanos
    source_cursor: str | None
    payload_fingerprint: str
```

This separation is mandatory. The same economic commission may be observed
once on a private stream and again in authenticated trade/income history. Both
observations must converge on one `FinancialFactId`; receive time, transport
and pagination cursor cannot create a second financial fact.

Exact account-affecting components use:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CashComponent:
    asset: AssetId
    signed_amount: Money
```

`signed_amount` is the exact change to the venue account asset: positive for
an inflow and negative for an outflow. PnL presentation later maps ledger
account semantics to positive gains and positive expense magnitudes; it does
not reinterpret this source sign.

### 4.2 Fill fact

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionFillFact:
    metadata: FinancialFactMetadata
    instrument_id: InstrumentId
    client_order_id: ClientOrderId
    venue_order_id: VenueOrderId
    venue_trade_id: TradeId
    side: OrderSide
    fill_quantity: Quantity
    fill_price: Price
    quote_amount: Money | None
    commission: tuple[CashComponent, ...]
    realized_pnl: tuple[CashComponent, ...]
    intent_id: IntentId | None
    order_group_id: OrderGroupId | None
    basket_leg_id: BasketLegId | None
```

Rules:

- quantity and price are last-fill values, not cumulative values;
- one venue trade ID identifies one fill within its documented venue scope;
- quote amount is exact venue-supplied value when available, otherwise a
  deterministic product-specific calculation with recorded model version;
- commission may use a different asset from quote/settlement;
- rebates are signed positive cash components, fees signed negative;
- realized PnL is separate from commission;
- absent group/leg causation is allowed for legacy/manual/external orders;
- Accounting does not invent causation that the platform cannot prove.

### 4.3 Account cash-flow fact

```python
class CashFlowType(StrEnum):
    FUNDING_SETTLEMENT = "funding_settlement"
    COMMISSION = "commission"
    COMMISSION_REBATE = "commission_rebate"
    REALIZED_PNL_SETTLEMENT = "realized_pnl_settlement"
    BORROW_INTEREST = "borrow_interest"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    INTERNAL_TRANSFER = "internal_transfer"
    LIQUIDATION = "liquidation"
    INSURANCE_CLEARING = "insurance_clearing"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountCashFlowFact:
    metadata: FinancialFactMetadata
    flow_type: CashFlowType
    asset: AssetId
    signed_amount: Money
    instrument_id: InstrumentId | None
    related_trade_id: TradeId | None
```

Positive means the venue account asset increased. Negative means it
decreased.

`ADJUSTMENT` requires explicit operator/reconciliation authority and a reason.
It cannot be used as a silent balancing plug.

### 4.4 Source fact union

```python
FinancialSourceFact = ExecutionFillFact | AccountCashFlowFact

@dataclass(frozen=True, slots=True, kw_only=True)
class ObservedFinancialFact:
    fact: FinancialSourceFact
    observation: FinancialFactObservation
```

Later venue-neutral source facts require additive schema versions and review.

### 4.5 Multi-source convergence

A versioned venue/source policy declares:

- the canonical business key for each financial component;
- which endpoint/stream fields form complete canonical content;
- when an auxiliary history record is only reconciliation evidence;
- how a fill-attached fee and a separate income record are proven to be the
  same economic component;
- which official venue correction creates a new correction identity.

Rules:

- two transports producing the same business key and same canonical content
  are one fact with multiple observations;
- a history overlap must never repost a stream-observed commission/Funding
  component;
- an incomplete transport record is retained as observation/reconciliation
  evidence but is not accepted or posted as a complete fact;
- the same business key with incompatible canonical content is a conflict
  unless the venue supplies an explicit correction relationship;
- ambiguous cross-source aliasing enters reconciliation mismatch; it cannot
  produce two postings or use timestamp proximity as proof.

## 5. One-Pass Private-Event Normalization

One raw private venue message must be parsed once into a bounded canonical
result:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedPrivateAccountEvent:
    source_event_id: str
    order_updates: tuple[OrderReconciliationSnapshot, ...]
    account_updates: tuple[AccountUpdate, ...]
    financial_facts: tuple[ObservedFinancialFact, ...]
```

Runtime fans immutable projections to their owners:

```text
order updates      -> OMS
account updates    -> Portfolio
financial facts    -> Accounting
```

This prevents separate parsers from disagreeing about trade ID, time,
quantity, commission or account scope.

Compatibility:

- existing order-only normalizer APIs remain as projections/wrappers;
- existing OMS contracts do not gain fee or ledger fields;
- existing private-stream tests remain valid;
- new Accounting fixtures must include complete commission/realized-PnL
  fields rather than assuming current minimal fixtures are sufficient.

## 6. Balanced Multi-Asset Ledger

### 6.1 Decision

Use an internal operational double-entry ledger, balanced independently per
asset.

It is not presented as a statutory/legal general ledger. It is the immutable
financial evidence and reconciliation layer for the trading platform.

### 6.2 Ledger account registry

Minimum account classes:

```text
VENUE_CASH
ASSET_INVENTORY
TRADE_CLEARING
FUNDING_INCOME
COMMISSION_EXPENSE
COMMISSION_REBATE
REALIZED_TRADING_PNL
BORROW_INTEREST_EXPENSE
TRANSFER_CLEARING
WITHDRAWAL_EXPENSE
LIQUIDATION_EXPENSE
ADJUSTMENT_SUSPENSE
UNALLOCATED
```

Definitions are versioned metadata, not arbitrary executable strings.

An account ID includes enough scope to distinguish venue account, asset and
economic bucket. A ledger account cannot silently combine two venue accounts.

### 6.3 Posting

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerPosting:
    posting_id: LedgerPostingId
    ledger_account_id: LedgerAccountId
    asset: AssetId
    signed_amount: Money
    memo: str = ""
```

`signed_amount` is the algebraic change to that ledger account. Zero postings
are forbidden.

### 6.4 Transaction

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerTransaction:
    transaction_id: LedgerTransactionId
    source_fact_ids: tuple[FinancialFactId, ...]
    transaction_type: LedgerTransactionType
    postings: tuple[LedgerPosting, ...]
    effective_time_ns: UnixNanos
    recorded_at_ns: UnixNanos
    schema_version: int
    reverses_transaction_id: LedgerTransactionId | None = None
```

Mandatory balance invariant:

```text
for every asset in one transaction:
    sum(posting.signed_amount for posting in asset) == 0
```

Amounts from different assets are never summed to satisfy balance.

### 6.5 Examples

Funding receipt of `+120 USDT`:

```text
VENUE_CASH:USDT       +120
FUNDING_INCOME:USDT   -120
```

Commission of `-2 USDT`:

```text
VENUE_CASH:USDT          -2
COMMISSION_EXPENSE:USDT  +2
```

Spot purchase of `1 BTC` for `60,000 USDT`, excluding fee:

```text
ASSET_INVENTORY:BTC   +1
TRADE_CLEARING:BTC    -1

VENUE_CASH:USDT       -60000
TRADE_CLEARING:USDT   +60000
```

The two assets balance independently.

Derivative fills do not invent principal cash settlement. Position quantity
remains Portfolio truth. Only venue-supported fee, realized-PnL, variation-
margin or settlement facts produce financial postings.

## 7. Deterministic Mapping Policy

One immutable versioned policy maps source facts to ledger transactions.

It declares:

- supported fact/schema versions;
- venue/product accounting model;
- account registry version;
- asset precision and rounding rules;
- Spot quote-amount derivation rule when venue value is absent;
- derivative realized-PnL and settlement handling;
- commission/rebate sign rules;
- correction/reversal rules;
- maximum postings per transaction.

The pure mapper:

```python
map_fact(
    fact: FinancialSourceFact,
    policy: LedgerMappingPolicy,
) -> tuple[LedgerTransaction, ...]
```

performs no I/O and reads no mutable state.

Unsupported product, missing amount, unknown asset, precision loss or
ambiguous mapping fails closed. No generic "other income" fallback is allowed.

## 8. Ledger State and Durability

The Accounting Engine is a single writer.

Ingestion order:

```text
validate fact
  -> reject duplicate/conflict
  -> pure deterministic mapping
  -> validate per-asset balance
  -> append fact + transaction evidence
  -> flush/fsync
  -> mutate in-memory ledger state
  -> publish immutable view
```

If append/fsync fails, no in-memory success is published. Accounting health
latches failed.

Minimum journal records:

```text
FinancialFactObserved
FinancialFactAccepted
LedgerTransactionPosted
LedgerTransactionReversed
AttributionAllocated
ReconciliationStarted
ReconciliationCompleted
AccountingPolicyActivated
```

Requirements:

- checksummed, sequenced and append-only;
- exact replay;
- bounded canonical records;
- mixed schema-version decoding;
- no in-place mutation/deletion;
- segment rotation/archival with a verified chain before capacity exhaustion;
- full/corrupt/truncated/external-modification failure is explicit;
- durable source fact and its mapped transaction cannot disagree;
- multiple transport observations for one accepted fact cannot create
  multiple ledger transactions.

Database projections may support queries and reporting. They are rebuildable
views, not the only recovery authority.

## 9. Corrections and Reversals

Accepted evidence is immutable.

An incorrect transaction is corrected by:

```text
original transaction
  -> exact reversing transaction
  -> corrected source fact/transaction with new identity
```

Rules:

- a reversal references exactly one original transaction;
- reversal postings are exact algebraic negatives;
- the original remains visible;
- operator-initiated corrections are authenticated and audited;
- a venue correction retains its venue correction identity;
- reuse of the original source ID with changed content remains a conflict, not
  an automatic correction;
- correction cannot bypass reconciliation or allocation invariants.

## 10. Reconciliation

### 10.1 Source completeness

Private streams are low-latency inputs, not assumed complete history.

Accounting reconciliation uses authenticated venue history for bounded
windows:

- trades/fills;
- commissions/rebates;
- Funding/income records;
- interest;
- deposits, withdrawals and transfers;
- liquidation/insurance/adjustment records where supported.

Every source has explicit cursor/window semantics. Inclusive/exclusive time
rules, pagination tokens, venue uniqueness scope and cross-source business-key
alias rules are adapter-owned and tested.

### 10.2 Balance proof

For each `(venue, account, asset, reconciliation interval)`:

```text
opening authoritative balance
+ accepted account-affecting source facts
= expected closing balance
```

The expected closing balance is compared with an authoritative closing
snapshot. Product-specific inventory/settlement equations are separately
versioned.

### 10.3 Reconciliation state

```text
NOT_STARTED
IN_PROGRESS
MATCHED
INCOMPLETE
MISMATCH
RECOVERY_REQUIRED
```

Only `MATCHED` means the declared interval and sources are complete.

Missing records are backfilled idempotently. Extra, conflicting or
unexplainable records enter mismatch/recovery. An adjustment requires explicit
evidence; reconciliation never edits totals silently.

### 10.4 Startup

Restart begins Accounting not ready:

```text
replay ledger journal
  -> verify checksums/sequences/policy
  -> rebuild source IDs, transactions and allocations
  -> resume source cursors
  -> reconcile open windows and recent overlap
  -> compare account balances
  -> publish healthy ledger view
```

Overlap refetch is safe because source identities are idempotent.

## 11. Hot-Path and Failure Policy

Accounting persistence does not sit between OMS durable preparation and the
external order submit.

Financial facts use a bounded durable side path:

```text
normalized private/account source
  -> bounded FinancialFactInbox
  -> durable Accounting append
  -> ledger mapping/state
```

Rules:

- OMS order lifecycle processing cannot wait on PnL calculation;
- Accounting cannot drop a fact to preserve throughput;
- inbox capacity, age and durable-spool size are bounded;
- backpressure, full spool, journal failure or reconciliation failure makes
  Accounting unhealthy;
- aggregate runtime health blocks new exposure when Accounting evidence cannot
  be retained;
- query, cancel, reconciliation and recovery continue while trading is
  halted;
- reconnect/redelivery uses the same fact identity;
- private-stream/history overlap converges before ledger mapping;
- Accounting failure is never reported as successful PnL.

This follows the existing bounded side-channel principle while treating
financial evidence as durable, not best-effort telemetry.

## 12. Economic Ownership and Allocation

### 12.1 Ledger completeness precedes attribution

Every source fact is posted even when strategy/application ownership is
unknown.

Ledger totals must never depend on whether attribution is available.

### 12.2 Direct causation

Platform-created fills may carry:

```text
IntentId
OrderGroupId
BasketLegId
ClientOrderId
StrategyId (resolved from immutable intent evidence)
```

Those identities can support deterministic fee/trade allocation.

### 12.3 Account-level cash flow

Funding and account income records may cover a net account/instrument
position shared by multiple strategies. The venue does not necessarily
provide platform group identity.

Accounting must not guess ownership from the latest strategy or nearest
timestamp.

Allocation options, in priority order:

1. dedicated venue account/subaccount with one economic owner;
2. complete position-ownership records over the settlement interval;
3. explicit versioned allocation policy with exact quantities and time
   coverage;
4. `UNALLOCATED` when proof is incomplete.

### 12.4 Allocation contract

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class AttributionAllocation:
    allocation_id: AttributionAllocationId
    transaction_id: LedgerTransactionId
    posting_id: LedgerPostingId
    owner: EconomicOwnerRef
    signed_amount: Money
    asset: AssetId
    policy_version: int
    evidence_ids: tuple[str, ...]
```

For every posting:

```text
sum(allocated amounts) + unallocated amount == posting amount
```

Allocations are append-only. Reallocation reverses prior allocation evidence
and posts a new version. It never edits the financial transaction.

`ApplicationPositionId` and Carry ownership semantics are defined by ADR-014.
ADR-013 defines only the generic allocation boundary.

## 13. Valuation

The immutable cash ledger does not post a new transaction every time a mark
moves.

A separate pure valuation view consumes:

- Portfolio effective positions;
- instrument definitions and multipliers;
- current authoritative marks/index values;
- system Feature values where required;
- explicit currency conversion rates;
- one coherent valuation snapshot ID.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ValuationSnapshot:
    valuation_snapshot_id: DecisionSnapshotId
    as_of_ns: UnixNanos
    reporting_asset: AssetId
    position_values: tuple[PositionValuation, ...]
    unrealized_pnl: Money
    policy_version: int
```

Rules:

- every amount retains original asset before explicit conversion;
- conversion source/time is evidence;
- unsupported/missing marks or models make valuation incomplete;
- incomplete valuation is never displayed as zero;
- valuation does not mutate ledger balances;
- option IV/Greeks remain Features, not ledger entries;
- no cross-asset total exists without explicit conversion.

## 14. PnL Attribution

### 14.1 Components

Generic realized components:

```text
funding
realized trading/settlement PnL
commission
rebate
borrow interest
liquidation/other explicit cost
```

Transfers, deposits and withdrawals are capital movements, not trading PnL.

Generic economic view:

```text
realized net PnL
  = allocated realized trading/settlement PnL
  + allocated funding
  + allocated rebates
  - allocated commissions
  - allocated interest
  - allocated explicit costs

total marked PnL
  = realized net PnL
  + change in allocated unrealized valuation
```

Sign presentation is derived from ledger account semantics; the underlying
postings remain algebraic.

### 14.2 Basis attribution

Basis/mark change is a derived valuation attribution across application legs.
It is not automatically a venue cash flow.

ADR-014 may define a Carry view such as:

```text
Carry total marked PnL
  = Funding component
  + Spot mark component
  + Perpetual mark/settlement component
  - commissions and other costs
```

The formula must reconcile to allocated ledger cash components plus valuation
change. It cannot count venue realized PnL and the same mark movement twice.

### 14.3 Attribution view

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PnlAttributionView:
    owner: EconomicOwnerRef
    interval_start_ns: UnixNanos
    interval_end_ns: UnixNanos
    reporting_asset: AssetId
    components: tuple[PnlComponent, ...]
    realized_net_pnl: Money
    unrealized_change: Money | None
    total_marked_pnl: Money | None
    ledger_sequence: int
    valuation_snapshot_ids: tuple[DecisionSnapshotId, ...]
    completeness: AttributionCompleteness
```

`None`/incomplete remains explicit. Missing evidence is never coerced to zero.

## 15. State Ownership

| State or evidence | Single writer | Readers |
|---|---|---|
| Order lifecycle/cumulative fill | OMS | Runtime, Risk, Portfolio |
| Financial transport observation | Accounting ingress after adapter normalization | Source convergence, reconciliation |
| Fill/account cash-flow source fact | Accounting fact owner | Ledger mapper, reconciliation |
| Absolute balances/positions | Portfolio/Account state | Risk, reconciliation, valuation |
| Ledger transactions/postings | Accounting Engine | Reconciliation, attribution, audit |
| Source coverage/reconciliation | Accounting reconciliation owner | Operations, health, attribution |
| Ownership allocation | Accounting allocation owner | Attribution, application views |
| Marks/Features | Existing owners | Valuation |
| Valuation snapshot | Accounting valuation projector | Attribution, application, operations |
| PnL attribution | Accounting attribution projector | Application, operations, reporting |
| Carry lifecycle/economic position | Carry application under ADR-014 | Strategy, Risk, Accounting allocation |

Accounting never mutates OMS, Portfolio, Risk or Carry state.

## 16. Runtime Interaction

### Fill

```text
private venue message
  -> one-pass canonical normalization
  -> OMS receives aggregate order update
  -> Portfolio receives account update if present
  -> Accounting inbox receives observed fill/commission/PnL facts
  -> source policy converges stream/history observations to economic facts
  -> Accounting fsyncs fact and balanced transactions
  -> reconciliation advances source coverage
  -> attribution resolves proven economic owner or UNALLOCATED
```

### Funding settlement

```text
authenticated income/private source
  -> AccountCashFlowFact(FUNDING_SETTLEMENT)
  -> exact venue/account/instrument/asset identity
  -> balanced ledger transaction
  -> account balance reconciliation
  -> ownership allocation
  -> PnL component
```

`FundingRateUpdate` does not enter this path.

### Query

Applications receive immutable ledger/attribution views through ports. They
cannot query a mutable Accounting engine or write adjustments.

## 17. Failure Matrix

| Condition | Required result |
|---|---|
| Duplicate identical source fact | Idempotent no-op |
| Same fact from stream and history | One economic fact; retain both observations; one posting |
| Reused fact ID with changed content | Latch Accounting unhealthy |
| Ambiguous stream/history alias | Reconciliation mismatch; no duplicate posting |
| Cumulative OMS update without fill fact | Cannot create financial posting |
| Funding rate event presented as settlement | Reject type/source |
| Missing venue trade/income ID | Reject or reconciliation-incomplete; never timestamp identity |
| Missing fee asset/amount | Fact incomplete; no guessed fee |
| Unknown product mapping | Fail closed |
| Per-asset posting imbalance | Reject transaction before append |
| Cross-asset amount summed without conversion | Reject |
| Unsupported precision/rounding | Reject |
| Journal append/fsync failure | No published mutation; halt new exposure through health |
| Inbox/spool full | Accounting unhealthy; no drop |
| Private stream gap | Backfill authenticated history |
| Venue/ledger balance mismatch | Reconciliation MISMATCH |
| Correction | Append exact reversal plus new transaction |
| Missing strategy ownership | Post ledger; allocate UNALLOCATED |
| Incomplete valuation | No total marked PnL |
| Missing conversion rate | No reporting-currency total |
| Restart | Replay, overlap refetch, reconcile before healthy |

## 18. Compatibility

- Existing OMS models and journals remain unchanged.
- Existing `OrderReconciliationSnapshot` remains an order-state projection.
- Existing Portfolio `Balance`, `Position` and `AccountSnapshot` remain
  authoritative state contracts.
- Existing `FundingRateUpdate` remains Market Data.
- Existing Recorder remains market/replay infrastructure.
- Existing Execution adapters stay venue-specific and application-neutral.
- Existing single-leg Pipeline behavior remains unchanged.
- Accounting additions are not required for existing offline single-leg tests
  unless explicitly composed.

## 19. Expansion Safety

### Funding Carry

Uses actual Funding settlement facts and exact commission components. It does
not infer income from announced rate.

### Market Making

Fill-level rebates/fees and inventory valuation reuse the same ledger. Quote
strategy logic remains outside Accounting.

### Options

Premium, fee and exercise/assignment/settlement facts require explicit
product mappings. Greeks and volatility surfaces remain Features. Options are
rejected by the ledger mapper until each financial lifecycle is implemented
and tested.

### Multi-venue

Each venue/account maintains explicit ledger scope. Aggregation requires
explicit asset conversion and never erases original-asset postings.

## 20. Boundedness, Retention and Performance

Implementation review must freeze hard and deployment caps for:

- facts per normalized private event;
- postings per transaction;
- source facts/transactions retained in memory;
- duplicate-ID index;
- inbox/spool count, bytes and age;
- active reconciliation windows and page count;
- allocations per posting;
- query result size;
- journal record and segment size.

Durable financial history is archived/rotated, not silently discarded.
Failure to rotate before a hard capacity limit makes Accounting unhealthy.

Pure mapping and incremental ledger mutation are linear in fact/posting count.
Reporting queries must use bounded indexes/projections and cannot scan
unbounded history on the trading-core thread.

## 21. Security and Audit

- authenticated account sources are adapter-only;
- credentials and signed requests never enter source facts or ledger;
- venue references are bounded and secret-free;
- corrections and policy activation require authenticated operator commands;
- ledger records are checksummed and tamper-evident;
- external audit receives bounded immutable projections;
- allocation cannot alter financial totals;
- ID/checksum values are not authentication tokens;
- raw private payload retention follows explicit security/retention policy,
  separate from canonical ledger evidence.

## 22. Alternatives Considered

### Store only one signed `CashFlow` table

Rejected as the sole ledger. It cannot express balanced multi-asset Spot
settlement or independently prove financial-account invariants.

Canonical cash-flow facts remain valid inputs to a balanced ledger.

### Use OMS fills as the ledger

Rejected. OMS state is cumulative and lacks required financial components.

### Derive Funding from rate times position

Rejected. That is an estimate, not venue settlement evidence.

### Derive every cash flow from balance differences

Rejected. It loses economic type, identity, causation and correction history.

### Put ledger fields into Portfolio positions

Rejected. Absolute position state and immutable transaction history have
different ownership and recovery semantics.

### Post unrealized PnL on every mark tick

Rejected for V1. It would create unbounded financial entries from reversible
market observations. Valuation remains a derived snapshot.

### Require complete strategy attribution before posting

Rejected. Ledger truth must not be lost because ownership mapping is late or
ambiguous.

### Let applications write custom ledger entries

Rejected. It would allow strategy code to manufacture PnL.

### Best-effort telemetry queue

Rejected. Financial evidence cannot be dropped. Backpressure must become a
health and trading-safety event.

## 23. Consequences

### Positive

- actual Funding and fee evidence becomes distinguishable from forecasts;
- balanced per-asset transactions expose mapping errors early;
- fills, cash flows and corrections are idempotent and auditable;
- ledger completeness is independent of attribution completeness;
- Spot, derivatives, Market Making and options can extend one model;
- missing evidence remains explicit;
- Financial Ledger does not leak into OMS or application strategy.

### Costs

- private account normalization becomes richer;
- authenticated history/backfill sources are required;
- a durable Accounting journal and spool are added;
- product-specific mapping and reconciliation policies must be maintained;
- strategy allocation requires ownership evidence;
- valuation and ledger semantics must be kept separate.

### Risks

- incorrect venue uniqueness scope can duplicate or suppress facts;
- fee assets and derivative settlement rules can be mis-normalized;
- balance reconciliation can imply false completeness if source categories are
  omitted;
- incorrect allocation can misstate strategy PnL while ledger totals remain
  correct;
- unbounded history/indexing can exhaust resources;
- downstream reports can double-count realized and mark components unless
  attribution invariants are tested.

## 24. Required Tests After Acceptance

### Contracts and identity

- invalid/bounded IDs, references, schema versions and times;
- exact fixed-point signed amounts;
- one fill identity per documented venue scope;
- deterministic fact, transaction and posting identity;
- exact duplicate idempotency and changed-content conflict;
- transport observation identity distinct from economic fact identity;
- immutable tuples and canonical ordering.

### Normalization

- Spot fill trade ID, last quantity/price, quote amount and commission asset;
- USD-M and COIN-M fill, fee and realized-PnL fields;
- Funding settlement from authenticated account source;
- Funding rate market event rejected as financial settlement;
- deposits, withdrawals, transfers, rebates and interest;
- missing/malformed/unsupported fields fail explicitly;
- existing order projection remains unchanged.

### Ledger

- every transaction balances independently per asset;
- multi-asset Spot trade;
- linear/inverse derivative settlement;
- fee in quote, base or third asset;
- rebate sign;
- Funding receipt/payment;
- zero posting and precision-loss rejection;
- mapping policy version and unsupported product;
- reversal is exact and original remains immutable.

### Durability and replay

- fsync before state publication;
- crash before/after fact/transaction append boundaries;
- journal corruption, truncation, sequence gap and external modification;
- exact replay;
- overlap redelivery after restart;
- same commission/Funding component from private stream and history posts
  exactly once;
- incomplete observation later completed by authoritative history creates one
  accepted fact, not an identity conflict;
- segment/capacity failure;
- inbox/spool backpressure never drops a fact.

### Reconciliation

- matched opening/flows/closing equation per asset;
- missing private event recovered from history;
- duplicate stream/history fact is idempotent;
- extra/conflicting fact enters mismatch;
- pagination/cursor boundary and window overlap;
- unexplained balance difference cannot auto-adjust;
- restart not healthy until reconciliation completes.

### Allocation and PnL

- direct group/leg fill allocation;
- account-level Funding with dedicated owner;
- shared position Funding remains unallocated without evidence;
- allocation plus unallocated equals posting;
- reallocation uses reversal/new evidence;
- transfers excluded from PnL;
- realized components reconcile to ledger;
- valuation change does not mutate ledger;
- incomplete mark/conversion produces incomplete total, not zero;
- no double-count between realized settlement and mark change.

### Compatibility and failure

- all existing regression/acceptance tests pass;
- OMS continues after Accounting side-path delay;
- Accounting failure blocks new exposure through health but permits
  query/cancel/recovery;
- no Funding/Carry application code is introduced;
- no network credentials are required for default tests.

## 25. Implementation and Promotion Gate

This Proposed ADR authorizes no code.

After Web GPT review and explicit project-owner acceptance:

1. assign implementation/acceptance task IDs;
2. implement immutable facts, IDs and balanced ledger contracts;
3. add complete offline Binance financial fixtures and normalization;
4. implement durable ledger, replay and bounded inbox;
5. implement reconciliation, allocation and valuation/attribution views;
6. run offline acceptance and architecture boundary review;
7. publish the accepted Accounting interface schema and package exports;
8. keep authenticated Testnet and production behind separate authorization.

ADR-014 Carry application code remains unauthorized until its own accepted
boundary and all dependencies are implemented/accepted.

## 26. Review Questions

1. Is a balanced per-asset operational double-entry ledger preferable to a
   cash-flow-only table?
2. Are fill-level and account cash-flow facts the correct canonical inputs?
3. Should one private message be normalized once and fanned out to OMS,
   Portfolio and Accounting projections?
4. Are economic fact identity and transport observation provenance correctly
   separated to prevent stream/history double posting?
5. Is `FinancialFactId` preferable to a narrower `CashFlowId`?
6. Are per-asset balance and explicit conversion rules sufficiently strict?
7. Is the durable bounded side path correct: never block the submit handoff,
   never drop evidence, halt new exposure on Accounting failure?
8. Are source completeness and balance reconciliation correctly separated?
9. Should ledger posting always precede strategy allocation?
10. Is `UNALLOCATED` preferable to inferred ownership when Funding covers a
   shared account position?
11. Are immutable ledger cash facts and derived valuation/PnL views correctly
    separated?
12. Does the proposal avoid double-counting realized settlement and basis/mark
    change?
13. Which product mappings and hard caps must be frozen before implementation?
