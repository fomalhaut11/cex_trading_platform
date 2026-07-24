# OMS Recovery and Reconciliation Design

## Scope

The OMS recovery layer makes canonical order ownership restart-safe without
turning storage or a venue response into live mutable state. It provides:

- a strict append-only recovery journal;
- deterministic reconstruction of every canonical order state machine;
- explicit discovery of non-terminal reconciliation candidates;
- one venue-neutral observation contract for REST queries and user streams;
- fail-closed behavior after any durability failure.

Concrete Binance REST query and user-data-stream normalization are implemented
in the execution adapter. Credentials, HTTP payloads and Binance status
strings do not enter this module.

## Journal

`JsonLinesOmsJournal` persists four mutation facts:

1. `OrderCreatedEntry`;
2. `OrderSubmittingEntry`;
3. `CancelRequestedEntry`;
4. `VenueEventEntry`.

Each JSONL record contains the persistent format name and version, a contiguous
sequence number, an explicitly encoded payload and a SHA-256 checksum over
canonical JSON. Readers reject missing newlines, oversized records, checksum
failures, unsupported versions and sequence gaps. Appends flush immediately
and use `fsync` by default.

The journal stores UTC Unix nanoseconds and exact fixed-point raw/scale pairs.
It never persists monotonic time, credentials or venue-native payloads.

## Recovery

`CanonicalOmsApplicationService` replays journal entries in order during
construction. Replay uses the same `OrderStateMachine` transition methods as
the live path, so duplicate identifiers, illegal transitions and invalid fill
progress cannot be silently accepted during restart.

The recovered service exposes immutable sorted order views.
`reconciliation_candidates()` returns only `SUBMITTING`, `OPEN`,
`PARTIALLY_FILLED` and `CANCEL_PENDING` orders. Recovery never automatically
resubmits them, because a submit timeout may mean the venue already accepted
the original client order identifier.

## Durability failure

New order creation is journaled before the request is returned to execution.
Accepted state transitions are journaled before their result is returned to
the caller. If append, flush or `fsync` fails, the service latches persistence
as unhealthy and rejects every later mutation until restart and
reconciliation. Reads remain available for diagnosis.

A truncated final record is not automatically ignored. Production recovery
must preserve the damaged file as evidence and follow an operator-approved
repair procedure.

## Reconciliation

Both REST queries and user-stream execution reports normalize to
`OrderReconciliationSnapshot`. Its source and source update identifier form a
stable OMS update key.

Reconciliation:

- adopts an observed venue order from `CREATED` through a persisted
  `SUBMITTING` transition;
- applies forward lifecycle and cumulative-fill progress idempotently;
- rejects observations that move fill backwards, exceed requested quantity or
  conflict with terminal canonical state;
- treats REST `not found` only as an observation, never as proof of rejection
  or cancellation;
- does not resubmit an uncertain order.

This completes the deterministic offline recovery and convergence kernel.
Binance query responses and private order events are covered by offline
restart acceptance. Live authenticated stream lifecycle, reconnect/startup
orchestration and Testnet evidence remain external gates.
