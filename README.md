# CEX Quant

Production-oriented quantitative trading runtime for centralized exchanges.
The system is Python-first, Rust-ready and built around immutable domain
contracts, single-writer state and a deterministic hot path.

For the current Git/CI baseline, ADR status, implemented modules, hard blocks
and exact next task, start with [`START_HERE.md`](START_HERE.md).

## Current Scope

- Canonical support for spot, perpetual, dated futures and option instruments.
- A modular `trading-core` process with independently deployable side services.
- Binance is the first venue adapter; venue-specific data cannot enter domains.
- IV, Greeks and volatility surfaces are versioned online features.
- ADR-011's bounded offline N-leg Order Group foundation is implemented;
  accepted ADR-012 adds execution-consistent Portfolio inputs, generic N-leg
  Risk authorization, durable reservations/permits and recovery evidence.
  Web GPT accepted and closed all conditional implementation findings.
  ADR-013 is approved in principle and its project-owner-authorized offline
  Financial Ledger implementation is complete, pending final review.
  ADR-014 Carry Application Boundary is Accepted and T040-T044/A017 are
  implemented and accepted offline: authoritative Funding state, pure Carry
  policy, durable application lifecycle/recovery and blocked Runtime
  composition.
  Grouped external execution remains blocked pending a separate explicit
  Testnet authorization.

## Development

The package uses a `src` layout and supports Python 3.11 or newer.

```powershell
$python = "python"
& $python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
& $python -m unittest discover -s tests -v
```

Read `architecture/module_topology.md`, `architecture/state_ownership.md` and
the accepted ADRs before changing a public contract.

The optional local code graph is documented in
`development/graphify_code_graph.md`. Its committed snapshot supports
dependency navigation and impact analysis, but source, tests and accepted
architecture documents remain authoritative.

The active delivery sequence is the single-account BTC Funding Carry
Fast-Track MVP in `development/funding_carry_fast_track_plan.md`. The broader
`development/platform_delivery_plan.md` is retained but deferred until after
the MVP. Kernel compatibility and allowed change rules are defined by
`architecture/kernel_v1_freeze.md`.

The current Chinese AWS Lightsail provisioning and host-operations baseline
is `operations/aws_lightsail_server_guide_zh.md`. It prepares offline,
Testnet and Shadow infrastructure only and grants no trading authority.

For a self-contained Chinese overview of the current implementation, public
module boundaries, acceptance evidence and planned multi-leg extension, read
`architecture/project_architecture_overview_zh.md`.

Project status and quality gates are maintained in
`development/progress.md`, `development/roadmap.md` and
`development/continuous_integration.md`.

Deployment, rollback/recovery and incident procedures are maintained in the
`operations/` directory.

AI-assisted discussions, external review handoffs and their promotion history
are exchanged through `ai_collaboration/`. That directory is not an
architecture authority; accepted conclusions must be promoted to the
appropriate ADR, architecture, interface, development or operations document.
