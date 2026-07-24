# Event Schema

All events contain:

-   event_id
-   event_type
-   timestamp
-   source
-   version

Canonical events compose `EventMetadata` containing:

-   event_id
-   event_time_ns
-   receive_time_ns
-   source (`VenueId`, channel and optional connection ID)
-   schema_version
-   source_time_precision
-   event_time_source (`venue` or explicit `receive_clock` fallback)
-   optional sequence, correlation and causation IDs

Events are immutable.

Python package versions and persistent schema versions are independent.
