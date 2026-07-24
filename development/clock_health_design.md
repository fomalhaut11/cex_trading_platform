# Clock Health Design

## Scope

Clock health observes host and venue time. It does not synchronize the host,
contact NTP services, or own a venue HTTP client. Connectors supply venue UTC
timestamps to the probe boundary.

## Time Sources

- `Clock.wall_time_ns()` returns UTC Unix nanoseconds for externally comparable
  timestamps.
- `Clock.monotonic_time_ns()` returns process-local monotonic nanoseconds for
  RTT and duration measurement.
- `SystemClock` is the production adapter. Tests inject a deterministic clock.
- Monotonic values must never be persisted as event time.

## Venue Sample

A connector calls `start_probe()` immediately before sending a venue-time
request and `finish_probe(..., venue_time_ns=...)` immediately after receiving
the response.

The sample records:

- monotonic RTT;
- signed venue-minus-host offset, estimated against the midpoint between the
  wall-clock send and receive timestamps;
- wall jump, calculated as wall elapsed time minus monotonic elapsed time.

The midpoint estimate assumes symmetric network delay. Offset is therefore an
operational signal, not a precision synchronization measurement.

## Health Policy

Thresholds are explicit injected policy and have warning and critical levels
for absolute offset, RTT, and sample age. Exceeding the wall-jump tolerance or
observing monotonic regression is immediately unhealthy. A monotonic regression
is latched because later measurements cannot make the affected process
durations trustworthy.

Status meanings:

- `UNKNOWN`: no sample exists.
- `HEALTHY`: latest sample is within every warning threshold.
- `DEGRADED`: at least one warning threshold is reached.
- `UNHEALTHY`: a critical threshold, wall jump, or monotonic regression occurs.

Boundary comparison is inclusive: a value equal to a warning or critical
threshold enters that state.

## Integration

One monitor is intended per venue endpoint or venue clock domain. Callers expose
the immutable report through the runtime health endpoint and export individual
sample fields as metrics. Trading policy decides whether degraded health blocks
new orders; the monitor only reports facts and severity.
