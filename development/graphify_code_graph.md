# Graphify Code Graph

Status: implemented as a local, read-only development aid.

Graphify supplements repository navigation and impact analysis. It does not
change the frozen Kernel v1 architecture, authorize grouped execution, or
enter any runtime, Testnet or production dependency.

## Scope and Safety Boundary

The repository integration is deliberately narrow:

- Graphify is installed under the user's local application-data tool cache,
  outside the project virtual environment;
- `graphifyy` is pinned to `0.9.31`, and its wheel is accepted only after the
  recorded SHA-256 check passes;
- development-tool dependencies are version-pinned separately in
  `tools/knowledge_graph/requirements.lock`;
- extraction always uses `--code-only`, so parsing is local and no source is
  submitted to an LLM;
- community labels are disabled and visualization generation is disabled;
- documents, raw collaboration records, protocol fixtures, local state and
  credential files are excluded by `.graphifyignore`;
- no Graphify MCP server, graph database, Codex install, AGENTS rule or Git
  hook is installed.

The Graphify files therefore remain a non-blocking developer tool. They must
not be deployed to a trading host.

## Portable and Local Artifacts

Portable artifacts committed to Git:

- `graphify-out/graph.json` — queryable code graph;
- `graphify-out/GRAPH_REPORT.md` — broad generated graph report;
- `graphify-out/SNAPSHOT.md` — extraction mode, counts and source fingerprint.

Machine-specific caches, manifests, absolute root markers, generated HTML and
analysis scratch files are ignored by Git.

## Rebuild

From the repository root on the development workstation:

```powershell
& .\tools\knowledge_graph\update_code_graph.ps1
```

The script bootstraps the pinned tool only when necessary, verifies the
Graphify wheel, performs local AST extraction, clusters without LLM labels,
runs graph-integrity diagnostics and writes the portable snapshot.

Run it after a change to source, tests, code-oriented tooling or package
metadata. It is intentionally not a required CI or trading-runtime gate while
the Funding Carry Fast-Track remains the active priority.

## Query Examples

Use the isolated executable created by the rebuild script:

```powershell
$graphify = Join-Path $env:LOCALAPPDATA `
  "cex-quant-tools\graphify-0.9.31\venv\Scripts\graphify.exe"

& $graphify explain "CarryApplicationRuntime"
& $graphify explain "OrderGroupRuntime"
& $graphify path "BasketTargetIntent" "OrderGroupRuntime"
& $graphify query `
  "What connects BasketTargetIntent to PortfolioRiskCoordinator and OrderGroupRuntime?"
& $graphify query `
  "Where is grouped external execution blocked?"
```

Prefer `explain` and `path` for a bounded result. A broad natural-language
query may return hundreds of nodes and must be narrowed before treating it as
useful evidence.

## Initial T045-Oriented Validation

The initial graph was checked against current source:

1. `CarryApplicationRuntime` is correctly shown as the ADR-009 plus Carry
   composition that stops before Risk and OMS.
2. The shortest reported `BasketTargetIntent` to `OrderGroupRuntime` path
   passes through `group_for_approval()` in
   `tests/test_portfolio_risk_engine.py`. That is test composition, not a
   production runtime writer. The graph therefore helps expose, but does not
   close, the T045 production-composition audit.
3. `GroupedExecutionBlockedError` and
   `OrderGroupRuntime.submit_prepared_child()` are correctly surfaced at the
   current grouped external-execution boundary.
4. `ExecutionActionPermit`, `PortfolioRiskCoordinator`,
   `OrderGroupStateMachine` and `BasketTargetIntent` appear among the central
   connected abstractions, consistent with ADR-010 through ADR-012.
5. Graph diagnostics report no missing endpoints, dangling endpoints, exact
   duplicate edges or directed same-endpoint collapse in the committed graph.

These checks do not start or complete T045. T045 remains an evidence-backed
source audit and must identify the production single writer, identity
propagation, durable handoff and recovery ownership before implementation.

## Authority and Limitations

Authority order remains:

1. source code and passing tests;
2. accepted ADRs and authoritative architecture/interface documents;
3. task and progress records;
4. Graphify extracted edges;
5. Graphify inferred edges.

The graph intentionally excludes architecture and AI-collaboration documents,
so it cannot decide architecture status or trading authorization. Inferred
edges are navigation hints and require source verification. Numeric community
names are expected because remote/LLM labeling is disabled.

`GRAPH_REPORT.md` records the commit visible before generated artifacts are
committed, so its commit comparison is conservative. `SNAPSHOT.md` supplies a
content fingerprint over the exact indexed source set and is the preferred
freshness evidence.
