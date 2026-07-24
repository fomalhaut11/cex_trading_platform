# Options and clock-health acceptance scenarios

This acceptance group exercises deterministic safety properties above the
unit-test level. It is fully offline, uses an injected manual clock, and never
sleeps.

## Option analytics

- Black-Scholes parity is checked as
  `call - put = spot*exp(-carry*T) - strike*exp(-rate*T)`.
- Black-76 parity is checked as
  `call - put = exp(-rate*T)*(forward - strike)`.
- Price-to-IV-to-price round trips cover both models, calls and puts, three
  strikes (ITM/ATM/OTM), and three expiries (7 days, 6 months, 2 years).
- Delta, gamma, and vega are compared with symmetric finite differences for
  both models and both option sides.
- A market price above the European upper bound must produce the typed
  `PRICE_OUT_OF_BOUNDS` failure.

Parity uses `1e-12` relative/absolute tolerance because both sides use the
same closed-form discount factors. The IV scenario asserts the solved value
remains inside the configured `[0, 5]` bracket and repricing is within `2e-9`
absolute price error. It intentionally does not require recovery of the
original IV for short-dated deep ITM/OTM cases: when vega approaches zero,
many volatilities are price-equivalent at the solver tolerance. The repricing
criterion is the stable definition of a valid price-to-IV-to-price round
trip. Finite-difference tolerances account for subtractive cancellation:
delta `2e-7`, gamma `2e-5` relative, and vega `2e-8` relative, with small
absolute floors.

## Clock health and fail-closed risk

Fixed integer nanosecond scenarios independently trigger:

- critical venue offset;
- critical request RTT;
- stale venue-time sample;
- wall/monotonic elapsed-time divergence;
- monotonic-clock regression.

Each health report must be `UNHEALTHY` with its stable issue code. The report
status is then passed into a complete pre-trade `RiskContext`; every scenario
must result in `REJECT` containing `CLOCK_UNHEALTHY`. This proves the safety
boundary, rather than merely checking monitor diagnostics.
