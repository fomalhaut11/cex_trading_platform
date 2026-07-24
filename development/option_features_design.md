# Option Feature Foundations

## Boundary and provenance

Implied volatility, Greeks and volatility-surface snapshots in this module are
system-computed feature data. They are derived only from explicit model inputs.
`VenueOptionAnalyticsUpdate` is deliberately not accepted and cannot be
silently relabelled as a system calculation.

## Model selection

- A European option whose canonical underlying is Spot uses Black-Scholes.
- A European option whose canonical underlying is Perpetual or Future uses
  Black-76; `underlying_price` is therefore a forward/futures price.
- American exercise is rejected because neither closed-form implementation is
  valid for it.
- Black-Scholes `carry_rate` represents the continuous dividend or foreign
  rate. Black-76 rejects non-zero carry.

The canonical option contract does not currently expose inverse or quanto
payoff semantics. This layer therefore prices the quoted European payoff only;
inverse/quanto payoff transformations must not be inferred from venue symbols.

## Numerical contract

Time to expiry is computed from integer Unix nanoseconds using a 365-day model
year. Pricing handles expiry and zero volatility explicitly. Analytical Greeks
require positive time and volatility.

IV uses deterministic bounded bisection. The supplied volatility is ignored;
the explicit inclusive bounds define the search domain. Failures distinguish
invalid input, expiry, price outside the bounded model range and convergence
exhaustion.

The solver first enforces the European no-arbitrage interval. For
Black-Scholes this interval uses discounted spot/carry and strike; for
Black-76 it uses the discounted forward/futures price and strike. It then
checks the narrower interval reachable through the configured volatility
bounds.

Black-76 delta is defined as the derivative of the discounted option value
with respect to the quoted forward/futures price. It therefore contains the
risk-free discount factor. An exchange's undiscounted "forward delta" is a
different reporting convention and is not emitted by this contract.

## Surface contract

A surface snapshot is an immutable, sorted, duplicate-free tuple of raw IV
points keyed by expiry, strike and option side. Every expiry must follow the
snapshot `as_of_ns`. Interpolation, smoothing and arbitrage repair are outside
this foundation.
