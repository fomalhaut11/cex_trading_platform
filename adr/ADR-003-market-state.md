# ADR-003 Market State Design

## Decision

Market State Engine supports multiple state views.

Examples:

-   L1
-   Partial Depth
-   Reconstructed Order Book

## Reason

Different strategies require different market information.

Full reconstruction is optional, not mandatory.
