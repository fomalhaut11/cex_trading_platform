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
