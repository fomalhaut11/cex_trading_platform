# CEX Quant

Production-oriented quantitative trading runtime for centralized exchanges.
The system is Python-first, Rust-ready and built around immutable domain
contracts, single-writer state and a deterministic hot path.

## Current Scope

- Canonical support for spot, perpetual, dated futures and option instruments.
- A modular `trading-core` process with independently deployable side services.
- Binance is the first venue adapter; venue-specific data cannot enter domains.
- IV, Greeks and volatility surfaces are versioned online features.

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
