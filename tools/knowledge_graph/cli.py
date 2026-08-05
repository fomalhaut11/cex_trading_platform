"""Command-line interface for the CEX Quant project knowledge graph."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from .project_graph import (
    GENERATED_DIRECTORY,
    KnowledgeGraphError,
    check_project_graph,
    load_federated_graph,
    sync_project_graph,
)


def _repository(value: str) -> Path:
    return Path(value).resolve()


def _sync(repository: Path) -> int:
    result = sync_project_graph(repository)
    print(
        "project knowledge graph synchronized: "
        f"{result['node_count']} nodes, {result['edge_count']} edges, "
        f"+{result['nodes_added']}/-{result['nodes_removed']} nodes, "
        f"+{result['edges_added']}/-{result['edges_removed']} edges"
    )
    changed = result["changed_files"]
    if changed:
        print("changed artifacts:")
        for path in changed:
            print(f"  {path}")
    else:
        print("portable artifacts already matched")
    return 0


def _check(repository: Path) -> int:
    fresh, messages = check_project_graph(repository)
    if fresh:
        print("project knowledge graph is fresh and valid")
        return 0
    print("project knowledge graph check failed:", file=sys.stderr)
    for message in messages:
        print(f"  {message}", file=sys.stderr)
    print(
        "run tools/knowledge_graph/update_code_graph.ps1 and commit the "
        "portable graph artifacts",
        file=sys.stderr,
    )
    return 1


def _stats(repository: Path) -> int:
    graph_path = repository / GENERATED_DIRECTORY / "project_graph.json"
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = payload["nodes"]
    edges = payload["edges"]
    type_counts = Counter(str(node["type"]) for node in nodes)
    authority_counts = Counter(str(edge["authority"]) for edge in edges)
    print(f"project nodes: {len(nodes)}")
    print(f"project edges: {len(edges)}")
    print("node types:")
    for name, count in sorted(type_counts.items()):
        print(f"  {name}: {count}")
    print("edge authority:")
    for name, count in sorted(authority_counts.items()):
        print(f"  {name}: {count}")
    return 0


def _query(repository: Path, term: str, limit: int) -> int:
    nodes, edges = load_federated_graph(repository)
    lowered = term.casefold()
    matches = [
        node
        for node in nodes
        if lowered
        in " ".join(
            (
                str(node.get("id", "")),
                str(node.get("label", "")),
                str(node.get("type", "")),
                str(node.get("status", "")),
            )
        ).casefold()
    ][:limit]
    if not matches:
        print(f"no knowledge-graph nodes matched: {term}")
        return 1
    edge_index: dict[str, list[dict[str, object]]] = {}
    for edge in edges:
        edge_index.setdefault(str(edge.get("source")), []).append(edge)
        edge_index.setdefault(str(edge.get("target")), []).append(edge)
    for node in matches:
        node_id = str(node["id"])
        print(
            f"{node_id} | {node.get('type')} | {node.get('label')}"
            + (
                f" | status={node.get('status')}"
                if node.get("status") is not None
                else ""
            )
        )
        for edge in edge_index.get(node_id, [])[:8]:
            direction = "->" if edge.get("source") == node_id else "<-"
            other = (
                edge.get("target")
                if direction == "->"
                else edge.get("source")
            )
            print(
                f"  {direction} {edge.get('relation')} {other} "
                f"[{edge.get('authority')}]"
            )
    return 0


def _explain(repository: Path, identity: str) -> int:
    nodes, edges = load_federated_graph(repository)
    lowered = identity.casefold()
    candidates = [
        node
        for node in nodes
        if str(node.get("id", "")).casefold() == lowered
        or str(node.get("label", "")).casefold() == lowered
    ]
    if not candidates:
        print(f"node not found: {identity}", file=sys.stderr)
        return 1
    node = candidates[0]
    node_id = str(node["id"])
    print(json.dumps(node, ensure_ascii=False, indent=2, sort_keys=True))
    print("relationships:")
    for edge in edges:
        if edge.get("source") == node_id or edge.get("target") == node_id:
            print(
                f"  {edge.get('source')} -[{edge.get('relation')}]-> "
                f"{edge.get('target')} [{edge.get('authority')}]"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(
        description="CEX Quant project knowledge graph",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repository root (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="rebuild portable project graph")
    subparsers.add_parser("check", help="fail if the graph is stale or invalid")
    subparsers.add_parser("stats", help="show project graph statistics")
    query = subparsers.add_parser("query", help="query the federated graph")
    query.add_argument("term")
    query.add_argument("--limit", type=int, default=20)
    explain = subparsers.add_parser("explain", help="explain one node")
    explain.add_argument("identity")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the knowledge-graph CLI."""

    parser = build_parser()
    namespace = parser.parse_args(arguments)
    repository = _repository(namespace.root)
    try:
        if namespace.command == "sync":
            return _sync(repository)
        if namespace.command == "check":
            return _check(repository)
        if namespace.command == "stats":
            return _stats(repository)
        if namespace.command == "query":
            return _query(repository, namespace.term, namespace.limit)
        if namespace.command == "explain":
            return _explain(repository, namespace.identity)
    except (KnowledgeGraphError, OSError, json.JSONDecodeError) as error:
        print(f"knowledge graph error: {error}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {namespace.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
