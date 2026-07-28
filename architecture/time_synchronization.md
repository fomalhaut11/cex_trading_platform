# Time Synchronization and Clock Health

## Clock Roles

- UTC Unix nanoseconds timestamp externally comparable events.
- Monotonic nanoseconds measure durations, timeouts and connection age.
- Connector receive time is captured once at the process boundary.

## Production Requirement

Trading hosts must run an operational clock-synchronization service and expose
offset health. A market event beyond the configured future-skew tolerance is
rejected from live state updates rather than silently rewriting its timestamp.

Clock offset thresholds are operational policy. The canonical validator
currently defaults to one second; production configuration may be stricter
after the host timing infrastructure is measured.

## Degraded Behavior

- Receive and record the raw message.
- Emit a structured `EVENT_FROM_FUTURE` validation issue.
- Do not update authoritative live market state.
- Alert operations with measured venue-to-host offset.
- Do not substitute receive time when a venue timestamp exists.

Monotonic clock regressions are programming or platform failures and cannot be
treated as normal market-data degradation.

## Decision Snapshot Time

Decision snapshots use three explicit time questions:

```text
event_age = now_unix_ns - source.as_of_ns
arrival_age = now_monotonic_ns - source.accepted_at_monotonic_ns
coherence_skew = max(group.as_of_ns) - min(group.as_of_ns)
```

UTC is used for source event freshness and cross-source coherence. Monotonic
time is used only for local silence and elapsed arrival age. Every source
keeps its own time; `assembled_at_ns` does not replace those timestamps or
claim physical simultaneity.
