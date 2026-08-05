"""Build and validate the repository-native project knowledge graph.

Graphify remains the code-structure provider. This module deterministically
extracts project authority, delivery and operations facts, then links selected
canonical concepts to Graphify nodes without copying the whole code graph.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "1.0"

PROJECT_DOCUMENT_ROOTS = (
    "adr",
    "architecture",
    "interfaces",
    "development",
    "operations",
)
PROJECT_ROOT_DOCUMENTS = (
    "README.md",
    "START_HERE.md",
    "knowledge_graph/README.md",
    "tools/knowledge_graph/update_code_graph.ps1",
)
CODE_ROOTS = ("src", "tests", "tools")
CODE_SUFFIXES = frozenset({".py", ".ps1"})
GENERATED_DIRECTORY = "knowledge_graph/generated"
GRAPHIFY_GRAPH_PATH = "graphify-out/graph.json"
GRAPHIFY_SOURCES_PATH = "graphify-out/SOURCES.json"

ADR_PATTERN = re.compile(r"\bADR-\d{3}\b")
TASK_PATTERN = re.compile(r"\b[TA]\d{3}[A-Z]?\b")
COMMIT_PATTERN = re.compile(r"(?<![0-9a-f])(?:[0-9a-f]{7,40})(?![0-9a-f])")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*]\(([^)]+)\)")
NUMBERED_RULE_PATTERN = re.compile(r"^(\d+)\.\s+(.+)")

AUTHORITIES = frozenset({"authoritative", "extracted", "inferred", "proposal"})


class KnowledgeGraphError(RuntimeError):
    """Raised when graph extraction, validation or freshness checks fail."""


def sha256_bytes(value: bytes) -> str:
    """Return a lowercase SHA-256 digest."""

    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    """Return a lowercase SHA-256 digest for UTF-8 text."""

    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """Hash one file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: object) -> str:
    """Serialize generated artifacts deterministically."""

    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def slug(value: str) -> str:
    """Build a stable, readable identifier component."""

    lowered = value.strip().lower()
    lowered = re.sub(r"[`*_()\[\]{}<>]", "", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered)
    return lowered.strip("-") or "unnamed"


def normalize_status(value: str) -> str:
    """Map repository status prose to a bounded machine status."""

    lowered = value.strip().lower()
    if "unauthorized" in lowered or "not authorized" in lowered:
        return "unauthorized"
    if "accepted" in lowered:
        return "accepted"
    if "complete" in lowered or "closed" in lowered:
        return "complete"
    if "deferred" in lowered:
        return "deferred"
    if "planned" in lowered:
        return "planned"
    if "proposed" in lowered:
        return "proposed"
    if "active" in lowered:
        return "active"
    if "blocked" in lowered:
        return "blocked"
    if "external" in lowered:
        return "external"
    if not lowered:
        return "unspecified"
    return slug(lowered)


@dataclass(frozen=True)
class Evidence:
    """Repository evidence for a node or edge."""

    source_path: str
    source_hash: str
    line: int
    method: str

    def as_dict(self) -> dict[str, object]:
        """Return a stable JSON representation."""

        return {
            "line": self.line,
            "method": self.method,
            "source_hash": self.source_hash,
            "source_path": self.source_path,
        }


@dataclass
class Node:
    """One canonical project-graph node."""

    node_id: str
    label: str
    node_type: str
    authority: str
    status: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a stable JSON representation."""

        result: dict[str, object] = {
            "attributes": dict(sorted(self.attributes.items())),
            "authority": self.authority,
            "evidence": [
                item.as_dict()
                for item in sorted(
                    self.evidence,
                    key=lambda item: (
                        item.source_path,
                        item.line,
                        item.method,
                        item.source_hash,
                    ),
                )
            ],
            "id": self.node_id,
            "label": self.label,
            "type": self.node_type,
        }
        if self.status is not None:
            result["status"] = self.status
        return result


@dataclass
class Edge:
    """One typed, evidence-backed relationship."""

    source: str
    relation: str
    target: str
    authority: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def edge_id(self) -> str:
        """Return a deterministic relationship identity."""

        material = "\t".join(
            (self.source, self.relation, self.target, self.authority)
        )
        return f"edge:{sha256_text(material)[:24]}"

    def as_dict(self) -> dict[str, object]:
        """Return a stable JSON representation."""

        return {
            "authority": self.authority,
            "confidence": self.confidence,
            "evidence": [
                item.as_dict()
                for item in sorted(
                    self.evidence,
                    key=lambda item: (
                        item.source_path,
                        item.line,
                        item.method,
                        item.source_hash,
                    ),
                )
            ],
            "id": self.edge_id,
            "relation": self.relation,
            "source": self.source,
            "target": self.target,
        }


class GraphAccumulator:
    """Merge deterministic facts while rejecting identity conflicts."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[tuple[str, str, str, str], Edge] = {}

    def add_node(self, node: Node) -> None:
        """Add or evidence-merge a node."""

        if node.authority not in AUTHORITIES:
            raise KnowledgeGraphError(
                f"unknown node authority {node.authority!r}: {node.node_id}"
            )
        current = self.nodes.get(node.node_id)
        if current is None:
            self.nodes[node.node_id] = node
            return
        labels_conflict = current.label.casefold() != node.label.casefold()
        if labels_conflict or current.node_type != node.node_type:
            raise KnowledgeGraphError(
                f"node identity conflict for {node.node_id}: "
                f"{current.label}/{current.node_type} versus "
                f"{node.label}/{node.node_type}"
            )
        if current.status is None:
            current.status = node.status
        elif node.status is not None and current.status != node.status:
            raise KnowledgeGraphError(
                f"status conflict for {node.node_id}: "
                f"{current.status!r} versus {node.status!r}"
            )
        for key, value in node.attributes.items():
            previous = current.attributes.get(key)
            if previous is not None and previous != value:
                raise KnowledgeGraphError(
                    f"attribute conflict for {node.node_id}.{key}: "
                    f"{previous!r} versus {value!r}"
                )
            current.attributes[key] = value
        _extend_unique_evidence(current.evidence, node.evidence)

    def add_edge(self, edge: Edge) -> None:
        """Add or evidence-merge a typed edge."""

        if edge.authority not in AUTHORITIES:
            raise KnowledgeGraphError(
                f"unknown edge authority {edge.authority!r}: "
                f"{edge.source} {edge.relation} {edge.target}"
            )
        key = (edge.source, edge.relation, edge.target, edge.authority)
        current = self.edges.get(key)
        if current is None:
            self.edges[key] = edge
            return
        if current.confidence != edge.confidence:
            raise KnowledgeGraphError(
                f"edge confidence conflict for {key}: "
                f"{current.confidence} versus {edge.confidence}"
            )
        _extend_unique_evidence(current.evidence, edge.evidence)

    def as_graph(
        self,
        *,
        project_fingerprint: str,
        code_fingerprint: str,
        graphify_version: str,
        graphify_graph_hash: str,
    ) -> dict[str, object]:
        """Return the canonical federated project-graph descriptor."""

        nodes = [
            node.as_dict()
            for node in sorted(self.nodes.values(), key=lambda item: item.node_id)
        ]
        edges = [
            edge.as_dict()
            for edge in sorted(self.edges.values(), key=lambda item: item.edge_id)
        ]
        return {
            "edges": edges,
            "federated_sources": [
                {
                    "authority": "extracted",
                    "graph_path": GRAPHIFY_GRAPH_PATH,
                    "graph_sha256": graphify_graph_hash,
                    "kind": "code_graph",
                    "source_fingerprint": code_fingerprint,
                    "tool": graphify_version,
                }
            ],
            "graph_kind": "cex_quant_project_knowledge_graph",
            "metadata": {
                "code_source_fingerprint": code_fingerprint,
                "edge_count": len(edges),
                "generator_version": GENERATOR_VERSION,
                "node_count": len(nodes),
                "project_source_fingerprint": project_fingerprint,
            },
            "nodes": nodes,
            "schema_version": SCHEMA_VERSION,
        }


def _extend_unique_evidence(
    target: list[Evidence],
    additions: Iterable[Evidence],
) -> None:
    existing = {
        (item.source_path, item.source_hash, item.line, item.method)
        for item in target
    }
    for item in additions:
        key = (item.source_path, item.source_hash, item.line, item.method)
        if key not in existing:
            target.append(item)
            existing.add(key)


@dataclass(frozen=True)
class ParsedDocument:
    """Cached Markdown structure used by the second extraction pass."""

    path: str
    text: str
    lines: tuple[str, ...]
    source_hash: str
    document_id: str
    title: str
    line_sections: tuple[str, ...]


@dataclass(frozen=True)
class BuildResult:
    """All deterministic outputs from one in-memory build."""

    graph: dict[str, object]
    manifest: dict[str, object]
    validation: dict[str, object]
    report: str


def collect_code_sources(repository: Path) -> tuple[str, ...]:
    """Return the exact local code-graph input set."""

    paths: list[str] = []
    pyproject = repository / "pyproject.toml"
    if pyproject.is_file():
        paths.append("pyproject.toml")
    for root_name in CODE_ROOTS:
        root = repository / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in CODE_SUFFIXES:
                paths.append(path.relative_to(repository).as_posix())
    return tuple(sorted(set(paths)))


def collect_project_sources(repository: Path) -> tuple[str, ...]:
    """Return authoritative project-graph inputs, excluding historical AI."""

    paths: list[str] = []
    for relative in PROJECT_ROOT_DOCUMENTS:
        if (repository / relative).is_file():
            paths.append(relative)
    for root_name in PROJECT_DOCUMENT_ROOTS:
        root = repository / root_name
        if root.is_dir():
            paths.extend(
                path.relative_to(repository).as_posix()
                for path in root.rglob("*.md")
                if path.is_file()
            )
    for root_name in ("knowledge_graph/schema", "knowledge_graph/sources"):
        root = repository / root_name
        if root.is_dir():
            paths.extend(
                path.relative_to(repository).as_posix()
                for path in root.rglob("*.json")
                if path.is_file()
            )
    workflow_root = repository / ".github" / "workflows"
    if workflow_root.is_dir():
        paths.extend(
            path.relative_to(repository).as_posix()
            for path in workflow_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
        )
    return tuple(sorted(set(paths)))


def source_records(
    repository: Path,
    relative_paths: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Hash a stable source list."""

    records = []
    for relative_path in relative_paths:
        absolute_path = repository / relative_path
        if not absolute_path.is_file():
            raise KnowledgeGraphError(f"source file is missing: {relative_path}")
        records.append(
            {
                "path": relative_path,
                "sha256": sha256_file(absolute_path),
            }
        )
    return tuple(records)


def records_fingerprint(records: Sequence[Mapping[str, str]]) -> str:
    """Hash ordered path/file-hash records using the Graphify convention."""

    material = "\n".join(
        f"{record['path']}\t{record['sha256']}"
        for record in sorted(records, key=lambda item: item["path"])
    )
    return sha256_text(material)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise KnowledgeGraphError(f"cannot read JSON {path}: {error}") from error


def _load_graphify_sources(
    repository: Path,
) -> tuple[dict[str, object], tuple[dict[str, str], ...]]:
    path = repository / GRAPHIFY_SOURCES_PATH
    if not path.is_file():
        raise KnowledgeGraphError(
            "Graphify source manifest is missing; run "
            "tools/knowledge_graph/update_code_graph.ps1"
        )
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise KnowledgeGraphError("Graphify source manifest must be an object")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise KnowledgeGraphError("Graphify source manifest has no source list")
    records: list[dict[str, str]] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            raise KnowledgeGraphError("invalid Graphify source record")
        path_value = item.get("path")
        hash_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(hash_value, str):
            raise KnowledgeGraphError("invalid Graphify path/hash record")
        records.append({"path": path_value, "sha256": hash_value})
    return payload, tuple(records)


def validate_code_freshness(
    repository: Path,
) -> tuple[dict[str, object], tuple[dict[str, str], ...]]:
    """Reject a missing, changed or incomplete Graphify code snapshot."""

    payload, recorded = _load_graphify_sources(repository)
    expected_paths = collect_code_sources(repository)
    recorded_paths = tuple(sorted(item["path"] for item in recorded))
    if recorded_paths != expected_paths:
        missing = sorted(set(expected_paths) - set(recorded_paths))
        obsolete = sorted(set(recorded_paths) - set(expected_paths))
        raise KnowledgeGraphError(
            "Graphify source set is stale; "
            f"missing={missing[:10]}, obsolete={obsolete[:10]}"
        )
    current = source_records(repository, expected_paths)
    if current != tuple(sorted(recorded, key=lambda item: item["path"])):
        changed = [
            item["path"]
            for item, old in zip(
                current,
                sorted(recorded, key=lambda value: value["path"]),
                strict=True,
            )
            if item["sha256"] != old["sha256"]
        ]
        raise KnowledgeGraphError(
            f"Graphify source hashes are stale: {changed[:20]}"
        )
    fingerprint = records_fingerprint(current)
    recorded_fingerprint = payload.get("source_fingerprint")
    if fingerprint != recorded_fingerprint:
        raise KnowledgeGraphError(
            "Graphify aggregate source fingerprint does not match its records"
        )
    graph_path = repository / GRAPHIFY_GRAPH_PATH
    if not graph_path.is_file():
        raise KnowledgeGraphError("Graphify graph.json is missing")
    graph_hash = sha256_file(graph_path)
    if payload.get("graph_sha256") != graph_hash:
        raise KnowledgeGraphError(
            "Graphify graph hash does not match its source manifest"
        )
    return payload, current


def _document_kind(path: str) -> str:
    if path.startswith("adr/"):
        return "ArchitectureDecisionDocument"
    if path.startswith("architecture/"):
        return "ArchitectureDocument"
    if path.startswith("interfaces/"):
        return "InterfaceDocument"
    if path.startswith("development/"):
        return "DeliveryDocument"
    if path.startswith("operations/"):
        return "OperationsDocument"
    if path.startswith(".github/workflows/"):
        return "ContinuousIntegrationDefinition"
    if path.startswith("knowledge_graph/"):
        return "KnowledgeGraphDefinition"
    return "ProjectDocument"


def _evidence(
    path: str,
    source_hashes: Mapping[str, str],
    line: int,
    method: str,
) -> Evidence:
    source_hash = source_hashes.get(path)
    if source_hash is None:
        raise KnowledgeGraphError(f"evidence source was not indexed: {path}")
    return Evidence(
        source_path=path,
        source_hash=source_hash,
        line=line,
        method=method,
    )


def _parse_markdown_structure(
    repository: Path,
    path: str,
    source_hashes: Mapping[str, str],
    accumulator: GraphAccumulator,
) -> ParsedDocument:
    text = (repository / path).read_text(encoding="utf-8")
    lines = tuple(text.splitlines())
    title = Path(path).stem
    for line in lines:
        heading = HEADING_PATTERN.match(line)
        if heading and len(heading.group(1)) == 1:
            title = heading.group(2).strip()
            break
    document_id = f"doc:{path}"
    root_evidence = _evidence(path, source_hashes, 1, "document-path")
    accumulator.add_node(
        Node(
            node_id=document_id,
            label=title,
            node_type=_document_kind(path),
            authority="authoritative",
            attributes={"path": path},
            evidence=[root_evidence],
        )
    )

    current_section = document_id
    section_for_line: list[str] = []
    heading_counts: Counter[str] = Counter()
    for line_number, line in enumerate(lines, start=1):
        heading = HEADING_PATTERN.match(line)
        if heading:
            heading_title = heading.group(2).strip()
            anchor = slug(heading_title)
            heading_counts[anchor] += 1
            suffix = (
                ""
                if heading_counts[anchor] == 1
                else f"-{heading_counts[anchor]}"
            )
            current_section = f"section:{path}#{anchor}{suffix}"
            section_evidence = _evidence(
                path,
                source_hashes,
                line_number,
                "markdown-heading",
            )
            accumulator.add_node(
                Node(
                    node_id=current_section,
                    label=heading_title,
                    node_type="DocumentSection",
                    authority="extracted",
                    attributes={
                        "heading_level": len(heading.group(1)),
                        "path": path,
                    },
                    evidence=[section_evidence],
                )
            )
            accumulator.add_edge(
                Edge(
                    source=document_id,
                    relation="CONTAINS",
                    target=current_section,
                    authority="extracted",
                    confidence=1.0,
                    evidence=[section_evidence],
                )
            )
        section_for_line.append(current_section)
    return ParsedDocument(
        path=path,
        text=text,
        lines=lines,
        source_hash=source_hashes[path],
        document_id=document_id,
        title=title,
        line_sections=tuple(section_for_line),
    )


def _status_after_heading(document: ParsedDocument, heading_name: str) -> str:
    target = f"## {heading_name}".lower()
    for index, line in enumerate(document.lines):
        if line.strip().lower() != target:
            continue
        for candidate in document.lines[index + 1 :]:
            stripped = candidate.strip()
            if stripped.startswith("#"):
                return ""
            if stripped:
                return stripped.strip("`*_. ")
    return ""


def _extract_adr(
    document: ParsedDocument,
    source_hashes: Mapping[str, str],
    accumulator: GraphAccumulator,
) -> None:
    match = ADR_PATTERN.search(document.path)
    if match is None:
        return
    adr_id = match.group(0)
    raw_status = _status_after_heading(document, "Status")
    status = normalize_status(raw_status) if raw_status else "unspecified_legacy"
    evidence = _evidence(document.path, source_hashes, 1, "adr-filename")
    accumulator.add_node(
        Node(
            node_id=f"adr:{adr_id}",
            label=document.title,
            node_type="ArchitectureDecision",
            authority="authoritative",
            status=status,
            attributes={
                "decision_id": adr_id,
                "raw_status": raw_status or "status heading absent",
            },
            evidence=[evidence],
        )
    )
    accumulator.add_edge(
        Edge(
            source=f"adr:{adr_id}",
            relation="DEFINED_IN",
            target=document.document_id,
            authority="extracted",
            confidence=1.0,
            evidence=[evidence],
        )
    )


def _extract_task_table(
    document: ParsedDocument,
    source_hashes: Mapping[str, str],
    accumulator: GraphAccumulator,
) -> None:
    if document.path != "development/tasks.md":
        return
    parsed_rows: list[tuple[str, str, str, str, int]] = []
    for line_number, line in enumerate(document.lines, start=1):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4 or TASK_PATTERN.fullmatch(cells[0]) is None:
            continue
        parsed_rows.append((cells[0], cells[1], cells[2], cells[3], line_number))
    for item_id, title, raw_status, dependencies, line_number in parsed_rows:
        evidence = _evidence(
            document.path,
            source_hashes,
            line_number,
            "task-table-row",
        )
        node_type = (
            "AcceptanceCriterion" if item_id.startswith("A") else "DeliveryTask"
        )
        accumulator.add_node(
            Node(
                node_id=f"task:{item_id}",
                label=title,
                node_type=node_type,
                authority="authoritative",
                status=normalize_status(raw_status),
                attributes={
                    "item_id": item_id,
                    "raw_dependencies": dependencies,
                    "raw_status": raw_status,
                },
                evidence=[evidence],
            )
        )
        accumulator.add_edge(
            Edge(
                source=f"task:{item_id}",
                relation="DEFINED_IN",
                target=document.document_id,
                authority="extracted",
                confidence=1.0,
                evidence=[evidence],
            )
        )
    for item_id, _title, _status, dependencies, line_number in parsed_rows:
        evidence = _evidence(
            document.path,
            source_hashes,
            line_number,
            "task-dependency-cell",
        )
        for dependency in TASK_PATTERN.findall(dependencies):
            accumulator.add_edge(
                Edge(
                    source=f"task:{item_id}",
                    relation="DEPENDS_ON",
                    target=f"task:{dependency}",
                    authority="authoritative",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )
        for dependency in ADR_PATTERN.findall(dependencies):
            accumulator.add_edge(
                Edge(
                    source=f"task:{item_id}",
                    relation="DEPENDS_ON",
                    target=f"adr:{dependency}",
                    authority="authoritative",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )


def _clean_table_value(value: str) -> str:
    return re.sub(r"[`*_]", "", value).strip()


def _extract_state_ownership(
    document: ParsedDocument,
    source_hashes: Mapping[str, str],
    accumulator: GraphAccumulator,
) -> None:
    if document.path != "architecture/state_ownership.md":
        return
    for line_number, line in enumerate(document.lines, start=1):
        if not line.startswith("|"):
            continue
        cells = [_clean_table_value(cell) for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0].lower() == "state" or set(cells[0]) <= {"-", ":"}:
            continue
        state_label, writer_label, readers = cells[:3]
        evidence = _evidence(
            document.path,
            source_hashes,
            line_number,
            "state-ownership-table",
        )
        state_id = f"state:{slug(state_label)}"
        writer_id = f"component:{slug(writer_label)}"
        accumulator.add_node(
            Node(
                node_id=state_id,
                label=state_label,
                node_type="OwnedState",
                authority="authoritative",
                attributes={"writer": writer_label},
                evidence=[evidence],
            )
        )
        accumulator.add_node(
            Node(
                node_id=writer_id,
                label=writer_label,
                node_type="StateOwner",
                authority="authoritative",
                evidence=[evidence],
            )
        )
        accumulator.add_edge(
            Edge(
                source=state_id,
                relation="OWNED_BY",
                target=writer_id,
                authority="authoritative",
                confidence=1.0,
                evidence=[evidence],
            )
        )
        accumulator.add_edge(
            Edge(
                source=document.document_id,
                relation="DECLARES_STATE",
                target=state_id,
                authority="extracted",
                confidence=1.0,
                evidence=[evidence],
            )
        )
        for reader_label in (
            value.strip() for value in readers.split(",") if value.strip()
        ):
            reader_id = f"component:{slug(reader_label)}"
            accumulator.add_node(
                Node(
                    node_id=reader_id,
                    label=reader_label,
                    node_type="StateReader",
                    authority="extracted",
                    evidence=[evidence],
                )
            )
            accumulator.add_edge(
                Edge(
                    source=state_id,
                    relation="READ_BY",
                    target=reader_id,
                    authority="extracted",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )


def _extract_architecture_constraints(
    document: ParsedDocument,
    source_hashes: Mapping[str, str],
    accumulator: GraphAccumulator,
) -> None:
    specifications = {
        "architecture/module_topology.md": ("Dependency Rules", "dependency"),
        "architecture/kernel_v1_freeze.md": (
            "Prohibited Changes",
            "prohibition",
        ),
    }
    specification = specifications.get(document.path)
    if specification is None:
        return
    heading_name, polarity = specification
    active = False
    ordinal = 0
    for line_number, line in enumerate(document.lines, start=1):
        if line.strip() == f"## {heading_name}":
            active = True
            continue
        if active and line.startswith("## "):
            break
        text = ""
        if active and polarity == "dependency":
            numbered = NUMBERED_RULE_PATTERN.match(line)
            if numbered:
                ordinal = int(numbered.group(1))
                text = numbered.group(2).strip()
        elif active and line.startswith("- "):
            ordinal += 1
            text = line[2:].strip()
        if not text:
            continue
        evidence = _evidence(
            document.path,
            source_hashes,
            line_number,
            f"architecture-{polarity}",
        )
        constraint_id = (
            f"constraint:{slug(Path(document.path).stem)}:{polarity}:{ordinal}"
        )
        accumulator.add_node(
            Node(
                node_id=constraint_id,
                label=text,
                node_type="ArchitectureConstraint",
                authority="authoritative",
                status="active",
                attributes={"polarity": polarity},
                evidence=[evidence],
            )
        )
        accumulator.add_edge(
            Edge(
                source=document.document_id,
                relation="DECLARES_CONSTRAINT",
                target=constraint_id,
                authority="authoritative",
                confidence=1.0,
                evidence=[evidence],
            )
        )


def _extract_workflow(
    repository: Path,
    path: str,
    source_hashes: Mapping[str, str],
    accumulator: GraphAccumulator,
) -> None:
    lines = (repository / path).read_text(encoding="utf-8").splitlines()
    name = Path(path).stem
    for line in lines:
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
            break
    workflow_id = f"ci-workflow:{slug(name)}"
    evidence = _evidence(path, source_hashes, 1, "workflow-definition")
    accumulator.add_node(
        Node(
            node_id=workflow_id,
            label=name,
            node_type="ContinuousIntegrationWorkflow",
            authority="authoritative",
            status="active",
            attributes={"path": path},
            evidence=[evidence],
        )
    )
    inside_jobs = False
    for line_number, line in enumerate(lines, start=1):
        if line == "jobs:":
            inside_jobs = True
            continue
        if inside_jobs and line and not line.startswith(" "):
            break
        job_match = re.match(r"^  ([a-zA-Z0-9_-]+):\s*$", line)
        if not inside_jobs or job_match is None:
            continue
        job_name = job_match.group(1)
        job_id = f"ci-job:{slug(name)}:{slug(job_name)}"
        job_evidence = _evidence(
            path,
            source_hashes,
            line_number,
            "workflow-job",
        )
        accumulator.add_node(
            Node(
                node_id=job_id,
                label=job_name,
                node_type="ContinuousIntegrationJob",
                authority="authoritative",
                status="active",
                evidence=[job_evidence],
            )
        )
        accumulator.add_edge(
            Edge(
                source=workflow_id,
                relation="CONTAINS_JOB",
                target=job_id,
                authority="authoritative",
                confidence=1.0,
                evidence=[job_evidence],
            )
        )


def _resolve_repository_path(
    repository: Path,
    source_path: str,
    raw_target: str,
) -> str | None:
    target = raw_target.strip().strip("<>").replace("\\", "/")
    if not target or "://" in target or target.startswith("#"):
        return None
    target = target.split("#", 1)[0]
    target = re.sub(r":\d+$", "", target)
    candidates = [
        repository / target,
        repository / Path(source_path).parent / target,
    ]
    root = repository.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return resolved.relative_to(root).as_posix()
    return None


def _ensure_reference_node(
    reference: str,
    evidence: Evidence,
    accumulator: GraphAccumulator,
) -> str:
    if reference.startswith("ADR-"):
        node_id = f"adr:{reference}"
        if node_id not in accumulator.nodes:
            accumulator.add_node(
                Node(
                    node_id=node_id,
                    label=reference,
                    node_type="ArchitectureDecision",
                    authority="extracted",
                    status="unresolved",
                    evidence=[evidence],
                )
            )
        return node_id
    node_id = f"task:{reference}"
    if node_id not in accumulator.nodes:
        accumulator.add_node(
            Node(
                node_id=node_id,
                label=reference,
                node_type=(
                    "AcceptanceCriterion"
                    if reference.startswith("A")
                    else "DeliveryTask"
                ),
                authority="extracted",
                status="unresolved",
                evidence=[evidence],
            )
        )
    return node_id


def _graphify_code_index(
    graphify_graph: Mapping[str, object],
) -> tuple[dict[str, list[dict[str, object]]], dict[str, dict[str, object]]]:
    raw_nodes = graphify_graph.get("nodes")
    if not isinstance(raw_nodes, list):
        raise KnowledgeGraphError("Graphify graph has no node list")
    by_label: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_id: dict[str, dict[str, object]] = {}
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue
        node_id = raw_node.get("id")
        label = raw_node.get("label")
        if isinstance(node_id, str):
            by_id[node_id] = raw_node
        if isinstance(label, str):
            by_label[label].append(raw_node)
    return dict(by_label), by_id


def _add_code_stub(
    raw_node: Mapping[str, object],
    repository: Path,
    accumulator: GraphAccumulator,
) -> str:
    raw_id = raw_node.get("id")
    label = raw_node.get("label")
    if not isinstance(raw_id, str) or not isinstance(label, str):
        raise KnowledgeGraphError("invalid Graphify code node")
    source_path = raw_node.get("source_file")
    source_location = raw_node.get("source_location")
    source_path_text = source_path if isinstance(source_path, str) else ""
    line = 1
    if isinstance(source_location, str):
        match = re.search(r"L(\d+)", source_location)
        if match:
            line = int(match.group(1))
    source_hash = (
        sha256_file(repository / source_path_text)
        if source_path_text and (repository / source_path_text).is_file()
        else sha256_text(raw_id)
    )
    evidence = Evidence(
        source_path=source_path_text,
        source_hash=source_hash,
        line=line,
        method="graphify-code-node",
    )
    canonical_id = f"code:{raw_id}"
    accumulator.add_node(
        Node(
            node_id=canonical_id,
            label=label,
            node_type="CodeSymbol",
            authority="extracted",
            attributes={
                "graphify_id": raw_id,
                "source_file": source_path_text,
                "source_location": (
                    source_location if isinstance(source_location, str) else ""
                ),
            },
            evidence=[evidence],
        )
    )
    return canonical_id


def _code_label_candidates(token: str) -> tuple[str, ...]:
    clean = token.strip()
    candidates = [clean]
    if "." in clean and "/" not in clean:
        tail = clean.rsplit(".", 1)[1]
        candidates.extend((tail, f".{tail}"))
    if clean.endswith("()") and not clean.startswith("."):
        candidates.append(f".{clean}")
    return tuple(dict.fromkeys(candidates))


def _extract_document_references(
    repository: Path,
    document: ParsedDocument,
    source_hashes: Mapping[str, str],
    documents: Mapping[str, ParsedDocument],
    code_by_label: Mapping[str, list[dict[str, object]]],
    accumulator: GraphAccumulator,
) -> None:
    for line_number, line in enumerate(document.lines, start=1):
        section_id = document.line_sections[line_number - 1]
        evidence = _evidence(
            document.path,
            source_hashes,
            line_number,
            "deterministic-reference",
        )
        for reference in sorted(
            set(ADR_PATTERN.findall(line) + TASK_PATTERN.findall(line))
        ):
            target = _ensure_reference_node(reference, evidence, accumulator)
            if target == section_id:
                continue
            accumulator.add_edge(
                Edge(
                    source=section_id,
                    relation="MENTIONS",
                    target=target,
                    authority="extracted",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )
        for raw_commit in COMMIT_PATTERN.findall(line):
            commit_id = f"commit:{raw_commit.lower()}"
            accumulator.add_node(
                Node(
                    node_id=commit_id,
                    label=raw_commit,
                    node_type="CommitReference",
                    authority="extracted",
                    evidence=[evidence],
                )
            )
            accumulator.add_edge(
                Edge(
                    source=section_id,
                    relation="MENTIONS_COMMIT",
                    target=commit_id,
                    authority="extracted",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )
        raw_paths = [
            *MARKDOWN_LINK_PATTERN.findall(line),
            *INLINE_CODE_PATTERN.findall(line),
        ]
        for raw_path in raw_paths:
            resolved_path = _resolve_repository_path(
                repository,
                document.path,
                raw_path,
            )
            if resolved_path is None or resolved_path == document.path:
                continue
            if resolved_path.startswith(f"{GENERATED_DIRECTORY}/"):
                continue
            if resolved_path in documents:
                target_id = documents[resolved_path].document_id
            else:
                target_id = f"artifact:{resolved_path}"
                accumulator.add_node(
                    Node(
                        node_id=target_id,
                        label=resolved_path,
                        node_type="RepositoryArtifact",
                        authority="extracted",
                        attributes={"path": resolved_path},
                        evidence=[evidence],
                    )
                )
            accumulator.add_edge(
                Edge(
                    source=section_id,
                    relation="REFERENCES_FILE",
                    target=target_id,
                    authority="extracted",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )
        for token in INLINE_CODE_PATTERN.findall(line):
            matches: list[dict[str, object]] = []
            for candidate in _code_label_candidates(token):
                matches.extend(code_by_label.get(candidate, []))
            source_matches = [
                item
                for item in matches
                if isinstance(item.get("source_file"), str)
                and str(item["source_file"]).startswith("src/")
            ]
            unique_matches = {
                str(item["id"]): item
                for item in source_matches
                if isinstance(item.get("id"), str)
            }
            if len(unique_matches) != 1:
                continue
            raw_node = next(iter(unique_matches.values()))
            code_id = _add_code_stub(raw_node, repository, accumulator)
            accumulator.add_edge(
                Edge(
                    source=section_id,
                    relation="MENTIONS_CODE",
                    target=code_id,
                    authority="extracted",
                    confidence=1.0,
                    evidence=[evidence],
                )
            )


def _find_locator_line(repository: Path, path: str, locator: str) -> int:
    lines = (repository / path).read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if locator in line:
            return line_number
    raise KnowledgeGraphError(
        f"curated evidence locator not found in {path}: {locator!r}"
    )


def _curated_evidence(
    repository: Path,
    raw: Mapping[str, object],
    source_hashes: Mapping[str, str],
) -> Evidence:
    path = raw.get("source_path")
    if not isinstance(path, str):
        raise KnowledgeGraphError("curated evidence requires source_path")
    locator = raw.get("locator")
    line_value = raw.get("line", 1)
    if isinstance(locator, str):
        line_value = _find_locator_line(repository, path, locator)
    if not isinstance(line_value, int):
        raise KnowledgeGraphError("curated evidence line must be an integer")
    return _evidence(path, source_hashes, line_value, "curated-project-fact")


def _load_curated_facts(
    repository: Path,
    source_hashes: Mapping[str, str],
    code_by_label: Mapping[str, list[dict[str, object]]],
    accumulator: GraphAccumulator,
) -> None:
    facts_path = repository / "knowledge_graph/sources/authoritative_facts.json"
    payload = _load_json(facts_path)
    if not isinstance(payload, dict):
        raise KnowledgeGraphError("authoritative facts must be an object")
    raw_nodes = payload.get("nodes")
    raw_edges = payload.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise KnowledgeGraphError("authoritative facts need nodes and edges")
    code_links: list[tuple[str, list[str], Evidence]] = []
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            raise KnowledgeGraphError("invalid curated node")
        evidence_raw = raw_node.get("evidence")
        if not isinstance(evidence_raw, dict):
            raise KnowledgeGraphError("curated node requires evidence")
        evidence = _curated_evidence(repository, evidence_raw, source_hashes)
        node_id = raw_node.get("id")
        label = raw_node.get("label")
        node_type = raw_node.get("type")
        authority = raw_node.get("authority", "authoritative")
        if not all(
            isinstance(value, str)
            for value in (node_id, label, node_type, authority)
        ):
            raise KnowledgeGraphError("invalid curated node identity")
        attributes = raw_node.get("attributes", {})
        if not isinstance(attributes, dict):
            raise KnowledgeGraphError("curated node attributes must be an object")
        status = raw_node.get("status")
        if status is not None and not isinstance(status, str):
            raise KnowledgeGraphError("curated node status must be a string")
        accumulator.add_node(
            Node(
                node_id=node_id,
                label=label,
                node_type=node_type,
                authority=authority,
                status=status,
                attributes=dict(attributes),
                evidence=[evidence],
            )
        )
        raw_labels = raw_node.get("code_labels", [])
        if not isinstance(raw_labels, list) or not all(
            isinstance(value, str) for value in raw_labels
        ):
            raise KnowledgeGraphError("code_labels must be a string list")
        code_links.append((node_id, list(raw_labels), evidence))
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            raise KnowledgeGraphError("invalid curated edge")
        evidence_raw = raw_edge.get("evidence")
        if not isinstance(evidence_raw, dict):
            raise KnowledgeGraphError("curated edge requires evidence")
        evidence = _curated_evidence(repository, evidence_raw, source_hashes)
        source = raw_edge.get("source")
        relation = raw_edge.get("relation")
        target = raw_edge.get("target")
        authority = raw_edge.get("authority", "authoritative")
        confidence = raw_edge.get("confidence", 1.0)
        if not all(
            isinstance(value, str)
            for value in (source, relation, target, authority)
        ) or not isinstance(confidence, (float, int)):
            raise KnowledgeGraphError("invalid curated edge")
        accumulator.add_edge(
            Edge(
                source=source,
                relation=relation,
                target=target,
                authority=authority,
                confidence=float(confidence),
                evidence=[evidence],
            )
        )
    for canonical_id, labels, evidence in code_links:
        for label in labels:
            matches = [
                item
                for item in code_by_label.get(label, [])
                if isinstance(item.get("source_file"), str)
                and str(item["source_file"]).startswith("src/")
            ]
            if not matches:
                raise KnowledgeGraphError(
                    f"curated code label does not resolve: {label}"
                )
            for raw_node in matches:
                code_id = _add_code_stub(raw_node, repository, accumulator)
                accumulator.add_edge(
                    Edge(
                        source=canonical_id,
                        relation="IMPLEMENTED_BY",
                        target=code_id,
                        authority="extracted",
                        confidence=1.0,
                        evidence=[evidence],
                    )
                )


def _ensure_edge_endpoints(accumulator: GraphAccumulator) -> None:
    missing: list[str] = []
    for edge in accumulator.edges.values():
        if edge.source not in accumulator.nodes:
            missing.append(edge.source)
        if edge.target not in accumulator.nodes:
            missing.append(edge.target)
    if missing:
        raise KnowledgeGraphError(
            f"graph edges have missing endpoints: {sorted(set(missing))[:20]}"
        )


def _validate_constraints(
    repository: Path,
    graph: Mapping[str, object],
) -> dict[str, object]:
    constraints = _load_json(
        repository / "knowledge_graph/schema/constraints.json"
    )
    if not isinstance(constraints, dict):
        raise KnowledgeGraphError("constraints file must be an object")
    raw_nodes = graph.get("nodes")
    raw_edges = graph.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise KnowledgeGraphError("generated graph has invalid node/edge lists")
    node_map = {
        str(node["id"]): node
        for node in raw_nodes
        if isinstance(node, dict) and "id" in node
    }
    edge_keys = {
        (
            str(edge.get("source")),
            str(edge.get("relation")),
            str(edge.get("target")),
        )
        for edge in raw_edges
        if isinstance(edge, dict)
    }
    errors: list[str] = []
    warnings: list[str] = []
    required_nodes = constraints.get("required_nodes", [])
    if not isinstance(required_nodes, list):
        raise KnowledgeGraphError("required_nodes must be a list")
    for requirement in required_nodes:
        if not isinstance(requirement, dict):
            raise KnowledgeGraphError("invalid required node constraint")
        node_id = requirement.get("id")
        expected_status = requirement.get("status")
        node = node_map.get(str(node_id))
        if node is None:
            errors.append(f"required node missing: {node_id}")
        elif expected_status is not None and node.get("status") != expected_status:
            errors.append(
                f"required status mismatch for {node_id}: "
                f"{node.get('status')} != {expected_status}"
            )
    required_edges = constraints.get("required_edges", [])
    if not isinstance(required_edges, list):
        raise KnowledgeGraphError("required_edges must be a list")
    for requirement in required_edges:
        if not isinstance(requirement, dict):
            raise KnowledgeGraphError("invalid required edge constraint")
        key = (
            str(requirement.get("source")),
            str(requirement.get("relation")),
            str(requirement.get("target")),
        )
        if key not in edge_keys:
            errors.append(f"required edge missing: {' '.join(key)}")
    forbidden_prefixes = constraints.get(
        "forbidden_authoritative_source_prefixes",
        [],
    )
    if not isinstance(forbidden_prefixes, list):
        raise KnowledgeGraphError("forbidden prefixes must be a list")
    for collection_name in ("nodes", "edges"):
        for item in graph.get(collection_name, []):
            if not isinstance(item, dict) or item.get("authority") != "authoritative":
                continue
            for evidence in item.get("evidence", []):
                if not isinstance(evidence, dict):
                    continue
                source_path = str(evidence.get("source_path", ""))
                if any(
                    source_path.startswith(str(prefix))
                    for prefix in forbidden_prefixes
                ):
                    errors.append(
                        "authoritative fact uses forbidden source: "
                        f"{source_path}"
                    )
    for node in raw_nodes:
        if (
            isinstance(node, dict)
            and node.get("type") == "ArchitectureDecision"
            and node.get("status") == "unspecified_legacy"
        ):
            warnings.append(
                f"legacy ADR has no explicit status heading: {node.get('id')}"
            )
    return {
        "errors": sorted(set(errors)),
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "edge_count": len(raw_edges),
            "error_count": len(set(errors)),
            "node_count": len(raw_nodes),
            "valid": not errors,
            "warning_count": len(set(warnings)),
        },
        "warnings": sorted(set(warnings)),
    }


def _render_report(
    graph: Mapping[str, object],
    validation: Mapping[str, object],
) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise KnowledgeGraphError("cannot report malformed graph")
    type_counts = Counter(
        str(node.get("type"))
        for node in nodes
        if isinstance(node, dict)
    )
    authority_counts = Counter(
        str(edge.get("authority"))
        for edge in edges
        if isinstance(edge, dict)
    )
    status_counts = Counter(
        str(node.get("status"))
        for node in nodes
        if isinstance(node, dict) and node.get("status") is not None
    )
    metadata = graph.get("metadata", {})
    lines = [
        "# Project Knowledge Graph Report",
        "",
        "This report describes the deterministic project graph. The federated",
        "Graphify code graph remains in `graphify-out/graph.json`.",
        "",
        "## Summary",
        "",
        f"- Project nodes: {len(nodes)}",
        f"- Project edges: {len(edges)}",
        f"- Project source fingerprint: `{metadata.get('project_source_fingerprint')}`",
        f"- Code source fingerprint: `{metadata.get('code_source_fingerprint')}`",
        f"- Validation: {'PASS' if validation['summary']['valid'] else 'FAIL'}",
        "",
        "## Node Types",
        "",
    ]
    lines.extend(
        f"- `{name}`: {count}"
        for name, count in sorted(type_counts.items())
    )
    lines.extend(["", "## Edge Authority", ""])
    lines.extend(
        f"- `{name}`: {count}"
        for name, count in sorted(authority_counts.items())
    )
    lines.extend(["", "## Status Distribution", ""])
    lines.extend(
        f"- `{name}`: {count}"
        for name, count in sorted(status_counts.items())
    )
    lines.extend(
        [
            "",
            "## Critical Current Facts",
            "",
            "- T045-T046 and A018 are complete offline.",
            "- Runtime owns registered execution planning and exact gateway routing.",
            "- A019 is the next external promotion gate and remains unauthorized.",
            "- Grouped external execution is blocked.",
            "- Binance grouped Testnet execution is unauthorized.",
            "- Production and real-money execution are unauthorized.",
            "- Carry produces a generic Basket target and owns no venue I/O.",
            "",
            "## Validation Warnings",
            "",
        ]
    )
    warnings = validation.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Graph-derived facts never override source code, passing tests or",
            "accepted repository authority. Inferred/proposal facts cannot be",
            "promoted without explicit review.",
            "",
        ]
    )
    return "\n".join(lines)


def build_project_graph(repository: Path) -> BuildResult:
    """Build the complete deterministic project layer in memory."""

    repository = repository.resolve()
    graphify_sources, code_records = validate_code_freshness(repository)
    graphify_graph = _load_json(repository / GRAPHIFY_GRAPH_PATH)
    if not isinstance(graphify_graph, dict):
        raise KnowledgeGraphError("Graphify graph must be an object")
    code_by_label, _code_by_id = _graphify_code_index(graphify_graph)

    project_paths = collect_project_sources(repository)
    project_records = source_records(repository, project_paths)
    source_hashes = {
        record["path"]: record["sha256"] for record in project_records
    }
    project_fingerprint = records_fingerprint(project_records)
    code_fingerprint = records_fingerprint(code_records)

    accumulator = GraphAccumulator()
    documents: dict[str, ParsedDocument] = {}
    for path in project_paths:
        if path.endswith(".md"):
            document = _parse_markdown_structure(
                repository,
                path,
                source_hashes,
                accumulator,
            )
            documents[path] = document
    for document in documents.values():
        _extract_adr(document, source_hashes, accumulator)
        _extract_task_table(document, source_hashes, accumulator)
        _extract_state_ownership(document, source_hashes, accumulator)
        _extract_architecture_constraints(document, source_hashes, accumulator)
    for path in project_paths:
        if path.startswith(".github/workflows/"):
            _extract_workflow(
                repository,
                path,
                source_hashes,
                accumulator,
            )
    _load_curated_facts(
        repository,
        source_hashes,
        code_by_label,
        accumulator,
    )
    for document in documents.values():
        _extract_document_references(
            repository,
            document,
            source_hashes,
            documents,
            code_by_label,
            accumulator,
        )
    _ensure_edge_endpoints(accumulator)

    graphify_graph_hash = sha256_file(repository / GRAPHIFY_GRAPH_PATH)
    graph = accumulator.as_graph(
        project_fingerprint=project_fingerprint,
        code_fingerprint=code_fingerprint,
        graphify_version=str(graphify_sources.get("graphify_version", "")),
        graphify_graph_hash=graphify_graph_hash,
    )
    validation = _validate_constraints(repository, graph)
    manifest = {
        "code_graph": {
            "graph_path": GRAPHIFY_GRAPH_PATH,
            "graph_sha256": graphify_graph_hash,
            "source_count": len(code_records),
            "source_fingerprint": code_fingerprint,
            "sources_path": GRAPHIFY_SOURCES_PATH,
            "tool": graphify_sources.get("graphify_version", ""),
        },
        "generator_version": GENERATOR_VERSION,
        "project_sources": {
            "source_count": len(project_records),
            "source_fingerprint": project_fingerprint,
            "sources": list(project_records),
        },
        "schema_version": SCHEMA_VERSION,
    }
    report = _render_report(graph, validation)
    return BuildResult(
        graph=graph,
        manifest=manifest,
        validation=validation,
        report=report,
    )


def _generated_artifacts(result: BuildResult) -> dict[str, str]:
    return {
        "GRAPH_REPORT.md": result.report,
        "manifest.json": canonical_json(result.manifest),
        "project_graph.json": canonical_json(result.graph),
        "validation_report.json": canonical_json(result.validation),
    }


def _graph_identity_set(
    payload: Mapping[str, object] | None,
    key: str,
) -> set[str]:
    if payload is None:
        return set()
    raw_items = payload.get(key, [])
    if not isinstance(raw_items, list):
        return set()
    return {
        str(item["id"])
        for item in raw_items
        if isinstance(item, dict) and "id" in item
    }


def sync_project_graph(repository: Path) -> dict[str, object]:
    """Atomically replace portable graph artifacts after validation."""

    repository = repository.resolve()
    result = build_project_graph(repository)
    summary = result.validation.get("summary", {})
    if not isinstance(summary, dict) or not summary.get("valid"):
        raise KnowledgeGraphError(
            f"project graph validation failed: {result.validation['errors']}"
        )
    generated_root = repository / GENERATED_DIRECTORY
    previous_graph_path = generated_root / "project_graph.json"
    previous_graph: Mapping[str, object] | None = None
    if previous_graph_path.is_file():
        loaded = _load_json(previous_graph_path)
        if isinstance(loaded, dict):
            previous_graph = loaded
    current_nodes = _graph_identity_set(result.graph, "nodes")
    current_edges = _graph_identity_set(result.graph, "edges")
    previous_nodes = _graph_identity_set(previous_graph, "nodes")
    previous_edges = _graph_identity_set(previous_graph, "edges")

    generated_root.mkdir(parents=True, exist_ok=True)
    changed_files: list[str] = []
    for name, content in _generated_artifacts(result).items():
        target = generated_root / name
        previous = (
            target.read_text(encoding="utf-8") if target.is_file() else None
        )
        if previous != content:
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            temporary.replace(target)
            changed_files.append(
                target.relative_to(repository).as_posix()
            )
    return {
        "changed_files": changed_files,
        "edge_count": len(current_edges),
        "edges_added": len(current_edges - previous_edges),
        "edges_removed": len(previous_edges - current_edges),
        "node_count": len(current_nodes),
        "nodes_added": len(current_nodes - previous_nodes),
        "nodes_removed": len(previous_nodes - current_nodes),
        "project_source_fingerprint": result.manifest["project_sources"][
            "source_fingerprint"
        ],
    }


def check_project_graph(repository: Path) -> tuple[bool, tuple[str, ...]]:
    """Check freshness without changing any repository file."""

    repository = repository.resolve()
    try:
        result = build_project_graph(repository)
    except KnowledgeGraphError as error:
        return False, (str(error),)
    generated_root = repository / GENERATED_DIRECTORY
    differences: list[str] = []
    for name, expected in _generated_artifacts(result).items():
        target = generated_root / name
        if not target.is_file():
            differences.append(f"generated artifact missing: {target}")
            continue
        actual = target.read_text(encoding="utf-8")
        if actual != expected:
            differences.append(
                f"generated artifact is stale: "
                f"{target.relative_to(repository).as_posix()}"
            )
    return not differences, tuple(differences)


def load_federated_graph(
    repository: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Load project nodes plus the complete Graphify code graph for queries."""

    project_payload = _load_json(
        repository / GENERATED_DIRECTORY / "project_graph.json"
    )
    graphify_payload = _load_json(repository / GRAPHIFY_GRAPH_PATH)
    if not isinstance(project_payload, dict) or not isinstance(
        graphify_payload,
        dict,
    ):
        raise KnowledgeGraphError("federated graph sources must be objects")
    project_nodes = project_payload.get("nodes", [])
    project_edges = project_payload.get("edges", [])
    graphify_nodes = graphify_payload.get("nodes", [])
    graphify_edges = graphify_payload.get("links", [])
    if not all(
        isinstance(value, list)
        for value in (
            project_nodes,
            project_edges,
            graphify_nodes,
            graphify_edges,
        )
    ):
        raise KnowledgeGraphError("federated graph has malformed collections")
    nodes = [dict(item) for item in project_nodes if isinstance(item, dict)]
    known_ids = {str(item.get("id")) for item in nodes}
    for raw in graphify_nodes:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            continue
        code_id = f"code:{raw['id']}"
        if code_id in known_ids:
            continue
        nodes.append(
            {
                "attributes": {
                    "graphify_id": raw["id"],
                    "source_file": raw.get("source_file", ""),
                    "source_location": raw.get("source_location", ""),
                },
                "authority": "extracted",
                "evidence": [],
                "id": code_id,
                "label": raw.get("label", raw["id"]),
                "type": "CodeSymbol",
            }
        )
    edges = [dict(item) for item in project_edges if isinstance(item, dict)]
    for raw in graphify_edges:
        if not isinstance(raw, dict):
            continue
        source = raw.get("source")
        target = raw.get("target")
        relation = raw.get("relation")
        if not all(isinstance(value, str) for value in (source, target, relation)):
            continue
        authority = str(raw.get("confidence_type", "EXTRACTED")).lower()
        if authority not in AUTHORITIES:
            authority = "extracted"
        edge_id = "code-edge:" + sha256_text(
            f"{source}\t{relation}\t{target}\t{raw.get('source_file', '')}"
        )[:24]
        edges.append(
            {
                "authority": authority,
                "confidence": raw.get("confidence", 1.0),
                "evidence": [],
                "id": edge_id,
                "relation": relation.upper(),
                "source": f"code:{source}",
                "target": f"code:{target}",
            }
        )
    return nodes, edges
