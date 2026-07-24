# ADR-005 Rust Migration Strategy

## Decision

Use Python-first implementation.

Replace modules with Rust only after profiling.

Candidates:

-   decoder
-   order book engine
-   rolling feature kernel
-   OMS components

Interfaces must remain stable.
