# Credential Delivery and Operator Recovery

Status: T022 implementation baseline.

## Scope

This stage closes two offline production-readiness gaps:

- deliver Binance credentials through an explicit account binding without
  storing values in source, configuration objects, logs or journals; and
- durably audit and restore operator trading authority across process restart.

It does not create real credentials or authorize production trading.

## Credential delivery

`EnvironmentBinanceCredentialProvider` maps each canonical `AccountId` to two
explicit environment variable names. There is no implicit name derived from
an account and no fallback account. Variable names must be uppercase,
bounded and unique across accounts.

Values are read for every `credentials_for` call rather than cached. An
external secret injector can therefore rotate a key between requests without
reconstructing the execution adapter. Missing, malformed or inaccessible
values produce a fixed `BinanceCredentialError`; source exceptions, variable
names and values are not copied into the error. Provider representation
redacts both bindings and the environment source.

Environment delivery is an adapter, not a vault. A deployment must inject
values using operating-system or orchestrator secret facilities, restrict
process and environment inspection, and rotate/revoke keys outside this
repository. Testnet and production accounts require distinct variables and
least-privilege API permissions.

## Durable operator commands

`JsonLinesOperatorCommandJournal` stores only operator command metadata and
the resulting immutable control snapshot. It never receives exchange
credentials. Each bounded JSONL record has:

- format and version;
- strict positive sequence;
- command id, action, actor and reason;
- resulting mode, generation and change time; and
- a SHA-256 checksum over canonical JSON.

Each append is flushed and `fsync` completes before `OperatorController`
changes its in-memory mode. A failed append therefore cannot enable trading.
The controller latches `HALTED`, reports `JOURNAL_FAILED`, and rejects every
later command after a durability failure.

At restart, every record is checked for sequence, checksum, unique command id,
generation, action/mode agreement and snapshot identity. The exact final
snapshot is restored. An old idempotency key is found by a bounded journal
scan even after it leaves the in-memory cache, so retrying it cannot roll back
newer authority.

The journal has explicit record-size and record-count limits. Operator
commands are cold-path operations; scanning the bounded journal is preferred
to unbounded process memory.

## Threat boundary

The checksum detects accidental corruption and partial writes. It is not a
signature against an attacker who can rewrite the file and recompute hashes.
A production deployment must additionally provide:

- restrictive file ACLs and single-process ownership;
- encrypted storage where required;
- an append-only or remote authenticated audit sink;
- backup and retention policy;
- authenticated operator transport and authorization; and
- alerting on corruption, append failure and every authority transition.

Any unexplained external journal change is treated as a durability failure
and trading remains halted.

## Acceptance

The offline acceptance scenario proves that:

1. authenticated adapter calls read credentials from the explicit provider;
2. a value rotation changes the next API key and signature;
3. no credential value is written to the operator journal;
4. activate followed by reduce-only is fsynced before mutation; and
5. a new controller restores the exact reduce-only snapshot after restart.
