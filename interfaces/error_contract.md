# Error Contract

## Boundary Failures

Raw-message decoding failures raise `NormalizationError` with a stable code,
source, reason and optional field. Raw payloads are not embedded in exceptions
or logs by default.

Codes currently include malformed payload, unsupported message, unknown
instrument, missing/invalid field and invalid timestamp.

## Canonical Validation

Canonical market facts return `ValidationResult` rather than throwing for data
quality problems. Each `ValidationIssue` has a stable code, severity, message
and optional field.

- `ERROR` means the event cannot update live market state.
- `WARNING` allows the event to continue while emitting observability data.

Validation never mutates or repairs an event. Venue-specific rules belong to
the venue adapter; cross-venue rules belong to the canonical validator.

