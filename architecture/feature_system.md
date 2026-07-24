# Online Feature System

## Principle

Feature is a registered data asset.

Strategies do not create production features internally.

## Feature Lifecycle

Request → Definition → Validation → Registration → Production

## Online Feature Engine

Contains:

-   Window Manager
-   Incremental Aggregator
-   Feature Calculator
-   Feature State Store

Rolling windows are internal computation states.

Published values are Features.
