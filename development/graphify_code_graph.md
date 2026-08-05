# Graphify Code Graph

Status: implemented as the code-structure provider of the federated project
knowledge graph.

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
- `graphify-out/SNAPSHOT.md` — extraction mode, counts and source fingerprint;
- `graphify-out/SOURCES.json` — exact portable code-source hashes used by the
  project-graph freshness check.

Machine-specific caches, manifests, absolute root markers, generated HTML and
analysis scratch files are ignored by Git.

## Rebuild

From the repository root on the development workstation:

```powershell
& .\tools\knowledge_graph\update_code_graph.ps1
```

The script bootstraps the pinned tool only when necessary, verifies the
Graphify wheel, performs local AST extraction, clusters without LLM labels,
runs graph-integrity diagnostics and writes the portable snapshot. It then
builds and validates the deterministic project-authority layer under
`knowledge_graph/generated/`.

Run it after a change to source, tests, code-oriented tooling, package
metadata, ADRs, architecture, interfaces, delivery plans or operations
authority. The local acceptance command
`python -m tools.knowledge_graph check` rejects stale committed artifacts.
Neither Graphify nor the project graph is a trading-host runtime dependency or
a remote GitHub Actions requirement.

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

## Current Architecture Validation

The graph must show the completed T045-T046/A018 composition and the additive
execution extension points:

1. `GroupedExecutionRuntime` resolves an immutable `ExecutionPlanRef` through
   `ObjectiveExecutionPlanResolver` and obtains the algorithm from
   `ExecutionPlannerRegistry`.
2. `SequentialResidualExecutionPlanner` owns only deterministic action
   proposal. Portfolio Risk still issues permits, OMS owns group/child facts
   and Runtime orders the calls.
3. `ExactExecutionGatewayRouter` lives under Runtime adapters and dispatches
   submit, cancel and query through exact account/instrument scopes. It has no
   strategy, leg-count, product or venue-selection policy.
4. Synthetic two-, three-, four- and 16-leg plus Binance/OKX multi-account
   tests connect to the same planner/router boundaries without changing
   Basket, Risk, OMS or Accounting contracts.
5. Graph diagnostics must report no missing endpoints, dangling endpoints,
   exact duplicate edges or directed same-endpoint collapse.

These graph relationships are offline structural evidence only. They do not
implement an OKX gateway, authorize cross-venue execution, open Testnet or
grant real-money authority.

## Authority and Limitations

Authority order remains:

1. source code and passing tests;
2. accepted ADRs and authoritative architecture/interface documents;
3. task and progress records;
4. Graphify extracted edges;
5. Graphify inferred edges.

The Graphify layer intentionally excludes architecture and AI-collaboration
documents. The separate project layer indexes authoritative repository
documents and explicit execution gates, while historical files under
`ai_collaboration/` remain non-authoritative. Inferred edges are navigation
hints and require source verification. Numeric community names are expected
because remote/LLM labeling is disabled.

`GRAPH_REPORT.md` records the commit visible before generated artifacts are
committed, so its commit comparison is conservative. `SNAPSHOT.md` supplies a
content fingerprint over the exact indexed source set and is the preferred
freshness evidence.

For the complete source hierarchy, synchronization contract, query commands
and automatic-modification safety boundary, read `knowledge_graph/README.md`.
