# Recorder Design

## Ownership and Boundary

Recorder owns the append-only historical representation of canonical events.
It does not own live state and must not be queried as a real-time state store.
The supplied JSON Lines adapter performs blocking filesystem I/O; runtime
assembly must isolate it from trading state transitions with a bounded handoff.

## Record Format

Each line is one independently decodable UTF-8 JSON object:

- `format`: `cex_quant.market_event`;
- `format_version`: persistent format version, initially `1`;
- `event_type`: canonical event class name;
- `payload`: lossless event fields;
- `checksum`: SHA-256 over the canonical JSON encoding of `payload`.

Keys are sorted and compact separators are fixed, making serialization
deterministic. Unix nanoseconds, sequences and fixed-point `raw`/`scale` values
remain integers. A trailing newline is the commit marker for a complete record.

## Failure and Recovery

- Append never truncates or overwrites an existing file.
- Records have a configurable byte limit before write and during read.
- Missing trailing newline is reported as a truncated record.
- Invalid JSON, unsupported versions/types and checksum mismatch are distinct
  typed failures.
- Readers stop at the first invalid record; silent skipping is prohibited.
- Replay is synchronous and preserves file order. Reader and sink failures
  propagate at the exact failing event.

`flush()` drains Python buffers. With `sync_on_flush=True`, it also calls
`fsync`; this is the explicit durability boundary. Filesystems can still expose
platform-specific behavior for process or device failure during one append.
