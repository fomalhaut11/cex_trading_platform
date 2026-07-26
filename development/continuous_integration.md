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

The workflow also supports manual execution and runs the deterministic
regression on Python 3.11 and 3.14. It uses read-only repository permissions,
bounded job timeouts and GitHub-authored actions pinned to immutable commit
identifiers.

## Merge Policy

A change may merge only when every required check passes. A failing or missing
check is evidence to investigate, not a gate to bypass.

The first branch-coverage baseline is 87.07%. CI enforces a minimum of 85%.

The T018 local preflight passes 256 tests and strict MyPy across 70 source
files with 86.03% branch coverage. It adds private-stream and startup-race
scenarios without lowering the 85% gate. The historical first baseline
remains recorded below for traceability.
The threshold protects against broad regressions while leaving room to add
meaningful failure-path tests. It must not encourage shallow tests written only
to increase a percentage.

The generated `coverage.xml` report is retained as a workflow artifact for 14
days.

## Secret Scanning

The repository-local scanner rejects a small set of high-confidence credential
formats and is covered by deterministic unit tests. It is intentionally not a
replacement for GitHub Secret Protection. Repository administrators should
also enable GitHub Push Protection.

## Future Testnet Workflow

Authenticated Binance Testnet acceptance should be a separately authorized,
manually triggered workflow using protected repository secrets and a dedicated
test account. It must never run against real-money endpoints.

## Status

Implemented in `.github/workflows/ci.yml`.

Local preflight on Python 3.14:

- compilation: passed;
- deterministic regression: 221 tests passed;
- Ruff: passed;
- strict MyPy: passed for 64 source files;
- branch coverage: 87.07%, above the 85% gate;
- high-confidence secret scan: passed.

Remote GitHub Actions run `30086189167` passed all three jobs on 2026-07-24:

- quality and coverage;
- regression on Python 3.11;
- regression on Python 3.14.

The run produced the `coverage-python-3.11` artifact. Official actions use
their Node.js 24 releases and remain pinned to immutable commit identifiers.

T023 implementation commit
`52b6b9f829da71da25fe5744efd4c71d5786eac1` passed remote run
`30157323695` on 2026-07-25. The run passed 346 regressions on Python 3.11 and
3.14, strict MyPy across 80 source files, Ruff, high-confidence secret
scanning and the 85% branch-coverage gate.

T024 local preflight passes 357 regressions on Python 3.11 and 3.14, 29
acceptance scenarios, strict MyPy across 81 source files, Ruff, secret
scanning and 86.19% branch coverage. Remote evidence is recorded after push.
