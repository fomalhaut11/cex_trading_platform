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

T024 implementation commit
`ca4590541aae7736372bddf321167aac65f6fa61` passed remote run
`30186079369` on 2026-07-26. Local and remote gates cover 357 regressions on
Python 3.11 and 3.14, 29 acceptance scenarios, strict MyPy across 81 source
files, Ruff, secret scanning and the 85% branch-coverage threshold; local
coverage measured 86.19%.

ADR-011 implementation commit
`9c1b0afb09744759b98429f7d8e99542bebd0aa1` and documentation head
`9ccf0c5438ebf37eb47fef5132e3bea8698e7a5e` passed remote run
`30345476372` on 2026-07-28. The run passed quality/coverage plus regression
on Python 3.11 and 3.14. Local evidence is 420 tests, 132 subtests, 36
acceptance scenarios, strict MyPy across 93 source files and 86.10% branch
coverage.

ADR-011 remediation commit
`c2c306dbe7675076ae200021d2c98f127736f09e` passes the complete local gate:
430 tests, 133 subtests, 37 acceptance tests, strict MyPy across 93 source
files, Ruff, compileall, secret scanning and 86.25% branch coverage.
Documentation head `df2fd83ab7bae89e35da819e7671f79eeb20dbc0`
passed remote run `30351998834`: quality/coverage and regression on Python
3.11 and 3.14 all succeeded.

Final ADR-011 remediation documentation head
`a752d3bff06a1b73b1103f543c64a2b6b64d2016` passed remote run
`30352133743`: quality/coverage and regression on Python 3.11 and 3.14 all
succeeded.

ADR-012 Portfolio Risk implementation commit
`69297d52e764822a1bdd60a23a9b7fca8446a520` and documentation head
`1a86b84cee50cbe9c57dcb719bdb66aec31ee008` passed remote run
`30431970845`: quality/coverage and regression on Python 3.11 and 3.14 all
succeeded. Local evidence is 462 tests, 141 subtests, 39 isolated acceptance
tests, strict MyPy across 100 source files and 85.12% branch coverage.
