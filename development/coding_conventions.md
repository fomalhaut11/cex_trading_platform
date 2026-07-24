# Coding Conventions

## Python

- Support Python 3.11 and newer.
- Public APIs require complete type annotations.
- Cross-module domain values use frozen, slotted, keyword-only dataclasses.
- `__init__.py` documents package responsibility and exports the supported API
  explicitly through `__all__`.
- `__init__.py` performs no I/O, registration or runtime assembly.
- Wildcard imports and unbounded `dict` payloads are prohibited in domain code.
- Avoid generic `utils.py`, `models.py` and `services.py` dumping grounds.

## Numeric and Time Rules

- Order, market and balance precision never uses binary float.
- Fixed-point rounding is always explicit; silent truncation is prohibited.
- UTC Unix nanoseconds represent externally comparable time.
- Monotonic nanoseconds are used for local duration and timeout measurement.
- Feature floats must define unit, validity and quality metadata.

## Boundaries

- Raw exchange JSON is decoded inside a venue adapter.
- Domain errors are typed and secrets never enter logs or events.
- Core state transitions are deterministic and avoid blocking I/O.
- Documentation and ADR changes accompany contract or ownership changes.

