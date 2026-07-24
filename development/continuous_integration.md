# Continuous Integration Baseline

## Meaning

Continuous Integration (CI) is an automated quality gate that runs from a
clean checkout whenever code is proposed or pushed. It gives every change the
same repeatable checks instead of relying on one developer's local environment.

CI does not deploy the trading system and does not authorize real-money
trading. Continuous Deployment (CD) is a separate capability and is outside
the current baseline.

## Required Checks

The initial pipeline should run on pull requests and pushes to `main`:

1. Install the package and pinned development tools on a supported Python
   version.
2. Compile all source modules.
3. Run the complete deterministic offline regression suite.
4. Run Ruff without warnings.
5. Run MyPy in strict mode.
6. Generate a coverage report.
7. Scan committed content for secrets.

The pipeline must not require exchange credentials or live network calls for
the default test suite.

## Merge Policy

A change may merge only when every required check passes. A failing or missing
check is evidence to investigate, not a gate to bypass.

Coverage should first be measured and reviewed by module. A repository-wide
minimum may be introduced only after the initial report exists; it must not
encourage shallow tests written only to increase a percentage.

## Future Testnet Workflow

Authenticated Binance Testnet acceptance should be a separately authorized,
manually triggered workflow using protected repository secrets and a dedicated
test account. It must never run against real-money endpoints.

## Status

Planned. No GitHub Actions workflow has been added yet.
