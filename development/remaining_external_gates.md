# Remaining External Gates

These are production-readiness or environment-dependent acceptance gates.
They are not evidence that the deterministic offline domain foundation is
unfinished, and none may be waived for a production release.

## Resolved Baseline Distribution

The project is available in both of these locations:

- working copy: `D:\cex_quant_codex_docs_v2`;
- Git remote: `https://github.com/fomalhaut11/cex_trading_platform`.

Git `origin/main` is the authoritative current baseline. The initial
`889572c3b62b2833143084b4eea79bf5a4bf7468` commit is retained only as
historical baseline evidence; it must not be described as the current release
candidate. Before acceptance, local `HEAD` and `origin/main` must be verified
equal and the successful CI run must reference that exact commit.

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
branch coverage. Remote GitHub Actions run `30086189167` passed quality and
coverage plus regression on Python 3.11 and 3.14.

Protected-branch enforcement remains a repository-policy decision because it
changes whether maintainers may push directly to `main`.

## Host Clock

On 2026-07-25 the Singapore-VPN public probes initially measured the host
about 18.9 seconds from venue time. Windows Time was stopped. It is now
running with automatic startup, but the VPN's Fake-IP mode maps NTP hosts to
`198.18.1.x` and does not currently pass UDP/123, so ordinary NTP polling
remains unavailable through that route.

The host was corrected once from the Binance Spot Testnet HTTPS time endpoint
using the request midpoint. Immediate independent probes then reported:

- Spot: -23.967 ms offset, 318.610 ms RTT, `HEALTHY`;
- USD-M: +32.652 ms offset, 436.006 ms RTT, `HEALTHY`;
- COIN-M: +44.133 ms offset, 472.832 ms RTT, `HEALTHY`.

Before authenticated Testnet or production:

1. provide a persistent approved time source outside the VPN's blocked NTP
   path, or explicitly route NTP outside that VPN;
2. retain venue-clock monitoring and fail closed if offset drifts;
3. record offset, RTT and sample-age distributions;
4. calibrate warning and critical thresholds from those measurements.

Risk remains fail-closed whenever clock health is not acceptable.

## Binance Testnet

Testnet requires a user-provided test account and credentials. Credentials
must enter through `BinanceCredentialProvider`; they must not be written to
source, fixtures, logs, exception messages or the recorder.

The earlier credential-free server-time smoke returned HTTP 451 from all
three Testnet origins. After selecting a Singapore VPN route on 2026-07-25,
the project transport reached the configured Spot, USD-M and COIN-M Testnet
origins successfully and all three public clock monitors reported `HEALTHY`.
The public connectivity prerequisite is therefore resolved for the current
route. A route change requires this smoke to be repeated; switching to
production endpoints is not an authorized workaround.

The Testnet gate must cover:

- signed account request and server-time validation;
- submit, query and cancel using the same client order identifier;
- duplicate submit/query recovery;
- timeout after send producing explicit unknown execution state;
- reconciliation between REST acknowledgement and user-data events;
- confirmation that no secret appears in captured logs or failures.

No real-money endpoint is authorized by this runbook.

## Grouped Execution Promotion

ADR-014 design and offline implementation acceptance do not unblock grouped
external submission. Before the first Funding Carry Testnet loop:

1. T045/T046/A018 must prove the complete grouped path with a deterministic,
   fault-injectable in-memory gateway;
2. ADR-013 final implementation acceptance must be recorded;
3. the project owner must explicitly authorize A019 grouped Testnet execution;
4. the exact Testnet account, Spot/perpetual instruments, quantity and
   notional/loss bounds must be approved;
5. Testnet credentials must enter only through `BinanceCredentialProvider`;
6. persistent host/venue clock health, operator halt and restart procedures
   must be ready;
7. no production endpoint or credential may be present.

The detailed plan is `development/execution_promotion_plan.md`. An offline
success, Web GPT recommendation or available credential is not by itself an
execution authorization.

## Controlled Micro-Live Promotion

The active product plan is
`development/funding_carry_fast_track_plan.md`.

A019 Testnet success does not authorize a production endpoint. Before any
real-money order:

1. T050 Operations Lite and production Shadow evidence must be complete;
2. A020 must record an exact account/instrument/quantity/notional/loss
   envelope, healthy clock/account/market state, kill-switch exercise,
   restart/recovery exercise and reconciled Ledger backup;
3. the project owner must explicitly approve A021, including the exact
   real-money amount, operator, operating window and abort criteria;
4. production credentials must enter only through the approved credential
   provider and must never reach source, logs, recorder or documentation;
5. the first cycle must remain manually started, bounded and independently
   stoppable;
6. unexplained position, balance, Ledger or reconciliation differences are an
   immediate no-go/halt.

A020 is readiness evidence only. A021 is the controlled micro-live acceptance.
Neither grants unattended automation or scaled production operation.

## Target-Host Performance

The 100,000-event offline baseline checks determinism, bounded retained memory
and thread cleanup. It does not establish a production latency service level.

A002B must measure representative normal, peak and burst loads on the selected
host and storage configuration. It must report p50, p95 and p99 latency,
backpressure behavior, recorder durability costs, retained-memory slopes and
thread/process health over a sustained soak.

## Recovery and Operations

The offline OMS recovery kernel now provides checksummed journaling,
deterministic restart reconstruction, non-terminal candidate discovery and
venue-neutral reconciliation. Binance REST query, private order-event
normalization, renewal/reconnect supervision and startup query orchestration
are also complete. Concrete bounded REST transport, private WebSocket resource
ownership, public server-time probing, aggregate health queries, an operator
kill switch, strict reduce-only enforcement, explicit environment credential
delivery, durable operator command recovery, signed operator authentication,
per-action authorization and mandatory deployment composition are complete
offline. The bounded mTLS identity adapter, strict request decoder, rate and
concurrency limits, external-audit port and durable endpoint-failure halt are
also complete offline.
Production acceptance still requires:

- authenticated Testnet evidence for Spot signature subscription and Futures
  listen-key renewal/reconnect;
- authenticated restart reconciliation evidence on the selected host;
- concrete TLS/mTLS termination, protected identity forwarding and external
  audit service retention around the completed bounded adapter;
- supervised process restart and health reporting;
- deployment secret injection, storage and rotation procedures;
- target-host exercise and approval of the deployment, rollback, recovery and
  incident runbooks;
- fault tests for slow or full storage, network loss and process termination.
