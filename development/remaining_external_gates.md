# Remaining External Gates

These items cannot be completed safely by the current offline sandbox. They
are external acceptance gates rather than unfinished domain implementation.

## D Drive Deployment

The sandbox can read `D:\cex_quant_codex_docs_v2`, but every authorized write
attempt is rejected before Windows file permissions are evaluated.

Verified fallback artifact:

- file: `outputs/cex_quant_foundation_2026-07-23.zip`
- files: 160
- bytes: 197812
- SHA-256:
  `AE228939BA90F3C6CE3274D70DD7E5BA9427977B21FD775A23A660251DA00A45`

The archive was extracted into a fresh directory and all 218 tests passed.
Copy or extract it to the D drive from a normal user process, then run:

```powershell
$env:PYTHONPATH = "src"
python -B -m unittest discover -s tests
```

## MyPy Strict

The project configuration already enables strict checking. Installation failed
through both available routes:

- pip index requests stalled without package data;
- direct official PyPI wheel download was rejected by the sandbox network
  identity.

When normal PyPI access is available:

```powershell
python -m pip install "mypy==2.3.0"
python -m mypy
```

Any reported type errors must be fixed before production acceptance; the gate
must not be waived merely because runtime tests pass.

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
