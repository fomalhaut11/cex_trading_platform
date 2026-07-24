# Remaining External Gates

These are production-readiness or environment-dependent acceptance gates.
They are not evidence that the deterministic offline domain foundation is
unfinished, and none may be waived for a production release.

## Resolved Baseline Distribution

The project is available in both of these locations:

- working copy: `D:\cex_quant_codex_docs_v2`;
- Git remote: `https://github.com/fomalhaut11/cex_trading_platform`.

The Git baseline is commit
`889572c3b62b2833143084b4eea79bf5a4bf7468` on `main`. The local and remote
commit identifiers were verified equal after the initial push.

The earlier release archive remains a historical offline artifact, but Git is
now the authoritative version history. A fresh checkout must pass:

```powershell
$env:PYTHONPATH = "src"
python -B -m unittest discover -s tests
```

## CI Baseline

The GitHub Actions workflow and local preflight now run:

- source compilation;
- the complete deterministic regression suite;
- Ruff;
- MyPy in strict mode;
- branch coverage with an 85% minimum;
- high-confidence secret scanning.

Any reported type errors must be fixed before production acceptance; the gate
must not be waived merely because runtime tests pass.

The first local baseline passes 221 tests, strict MyPy and Ruff, with 87.07%
branch coverage. The first remote workflow run and protected-branch enforcement
must still be confirmed in GitHub.

## Host Clock

The earlier public Binance smoke test measured the host about 13 seconds
behind venue time. Before Testnet or production:

1. synchronize the Windows host using an approved NTP source;
2. verify the venue clock monitor reports `HEALTHY`;
3. record offset, RTT and sample-age distributions;
4. calibrate warning and critical thresholds from those measurements.

Risk remains fail-closed whenever clock health is not acceptable.

## Binance Testnet

Testnet requires a user-provided test account and credentials. Credentials
must enter through `BinanceCredentialProvider`; they must not be written to
source, fixtures, logs, exception messages or the recorder.

The Testnet gate must cover:

- signed account request and server-time validation;
- submit, query and cancel using the same client order identifier;
- duplicate submit/query recovery;
- timeout after send producing explicit unknown execution state;
- reconciliation between REST acknowledgement and user-data events;
- confirmation that no secret appears in captured logs or failures.

No real-money endpoint is authorized by this runbook.

## Target-Host Performance

The 100,000-event offline baseline checks determinism, bounded retained memory
and thread cleanup. It does not establish a production latency service level.

A002B must measure representative normal, peak and burst loads on the selected
host and storage configuration. It must report p50, p95 and p99 latency,
backpressure behavior, recorder durability costs, retained-memory slopes and
thread/process health over a sustained soak.

## Recovery and Operations

Production acceptance also requires:

- persistent OMS recovery and restart reconstruction;
- reconciliation of REST acknowledgements and user-data events;
- operator kill switch and an explicitly controlled reduce-only mode;
- supervised process restart and health reporting;
- credential storage and rotation procedures;
- deployment, rollback, reconciliation and incident runbooks;
- fault tests for slow or full storage, network loss and process termination.
