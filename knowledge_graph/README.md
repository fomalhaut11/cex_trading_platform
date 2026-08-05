# Project Knowledge Graph

Status: active repository authority and synchronization infrastructure.

The project knowledge graph is federated:

1. `graphify-out/graph.json` provides the complete supported static code graph;
2. `knowledge_graph/generated/project_graph.json` provides deterministic
   project authority, delivery, operations, state ownership and traceability;
3. `knowledge_graph/sources/authoritative_facts.json` contains the small set of
   explicit cross-domain facts that cannot safely be inferred from syntax.

Source code, passing tests, accepted ADRs and authoritative repository
documents remain the source of truth. The graph is an evidence-backed index,
not an independent decision-maker.

## Authority Levels

- `authoritative`: explicitly curated or extracted from an authoritative
  project record such as the task table or state-ownership table;
- `extracted`: deterministic syntax, heading, reference or code-graph fact;
- `inferred`: model-derived candidate that cannot override authority;
- `proposal`: unaccepted candidate awaiting review.

Historical files under `ai_collaboration/` are intentionally excluded from
the authoritative graph. Accepted conclusions must first be promoted to an
ADR, architecture, interface, delivery or operations document.

## Synchronize

Run the one repository command:

```powershell
& .\tools\knowledge_graph\update_code_graph.ps1
```

It:

1. verifies and updates the isolated Graphify code graph;
2. writes a portable code-source manifest and fingerprint;
3. extracts project authority and evidence;
4. validates required nodes, edges and external gates;
5. atomically replaces generated artifacts only after validation.

## Check Without Writing

```powershell
& .\.venv\Scripts\python.exe -m tools.knowledge_graph check
```

Run this command as part of local acceptance. Any source, task, ADR,
architecture, operations or code change that is not reflected in the locally
committed graph fails the check.

## Query

```powershell
& .\.venv\Scripts\python.exe -m tools.knowledge_graph stats
& .\.venv\Scripts\python.exe -m tools.knowledge_graph query T045
& .\.venv\Scripts\python.exe -m tools.knowledge_graph query `
  "grouped external execution"
& .\.venv\Scripts\python.exe -m tools.knowledge_graph explain `
  gate:grouped-external-execution
```

Queries load the project graph and Graphify code graph as one read-only
federated view.

## Generated Artifacts

- `generated/project_graph.json`: canonical project nodes and edges;
- `generated/manifest.json`: exact source lists, hashes and fingerprints;
- `generated/validation_report.json`: constraint result;
- `generated/GRAPH_REPORT.md`: human-readable summary.

Generated files are portable. Machine caches and absolute repository paths
remain excluded.

## Modification Safety

Knowledge-graph synchronization is automatic through the local rebuild command
and versioned by local Git. It is not a GitHub Actions or remote-repository
requirement. Graph-driven source modification remains gated:

- a stale graph cannot authorize an automated change;
- inferred/proposal facts cannot be promoted automatically;
- architecture, Risk, OMS, Accounting and external-execution authority
  changes require explicit review;
- no graph tool is allowed to write credentials or trading-host state.
