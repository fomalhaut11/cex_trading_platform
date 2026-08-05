import json
import unittest
from pathlib import Path

from tools.knowledge_graph.project_graph import (
    build_project_graph,
    check_project_graph,
    collect_code_sources,
    sha256_file,
)


class ProjectKnowledgeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = Path(__file__).resolve().parents[1]
        cls.result = build_project_graph(cls.repository)
        cls.nodes = {
            str(node["id"]): node for node in cls.result.graph["nodes"]
        }
        cls.edges = cls.result.graph["edges"]

    def test_graphify_source_manifest_matches_supported_code(self) -> None:
        payload = json.loads(
            (
                self.repository / "graphify-out" / "SOURCES.json"
            ).read_text(encoding="utf-8")
        )
        recorded = tuple(
            sorted(str(item["path"]) for item in payload["sources"])
        )
        self.assertEqual(recorded, collect_code_sources(self.repository))

    def test_frozen_decisions_and_external_gates_are_explicit(self) -> None:
        expected = {
            "adr:ADR-011": "accepted",
            "adr:ADR-012": "accepted",
            "adr:ADR-013": "proposed",
            "adr:ADR-014": "accepted",
            "task:T045": "complete",
            "gate:grouped-external-execution": "blocked",
            "gate:testnet": "unauthorized",
            "gate:production": "unauthorized",
        }
        self.assertEqual(
            {
                identity: self.nodes[identity]["status"]
                for identity in expected
            },
            expected,
        )

    def test_required_execution_boundary_edges_are_present(self) -> None:
        actual = {
            (
                str(edge["source"]),
                str(edge["relation"]),
                str(edge["target"]),
            )
            for edge in self.edges
        }
        required = {
            (
                "application:carry",
                "PRODUCES",
                "contract:basket-target-intent",
            ),
            (
                "contract:basket-target-intent",
                "REQUIRES_AUTHORIZATION_FROM",
                "boundary:portfolio-risk",
            ),
            (
                "boundary:oms-order-group",
                "BLOCKED_BY",
                "gate:grouped-external-execution",
            ),
            ("gate:testnet", "DEPENDS_ON", "task:A018"),
            ("gate:production", "DEPENDS_ON", "task:A020"),
            ("gate:production", "DEPENDS_ON", "task:A021"),
        }
        self.assertTrue(required.issubset(actual))

    def test_graph_has_unique_identities_and_no_dangling_edges(self) -> None:
        node_ids = [str(node["id"]) for node in self.result.graph["nodes"]]
        edge_ids = [str(edge["id"]) for edge in self.edges]
        self.assertEqual(len(node_ids), len(set(node_ids)))
        self.assertEqual(len(edge_ids), len(set(edge_ids)))
        identities = set(node_ids)
        for edge in self.edges:
            self.assertIn(str(edge["source"]), identities)
            self.assertIn(str(edge["target"]), identities)

    def test_every_evidence_record_is_content_addressed(self) -> None:
        for item in [*self.result.graph["nodes"], *self.edges]:
            for evidence in item["evidence"]:
                source_path = self.repository / str(
                    evidence["source_path"]
                )
                self.assertTrue(source_path.is_file())
                self.assertEqual(
                    str(evidence["source_hash"]),
                    sha256_file(source_path),
                )

    def test_ai_collaboration_never_becomes_graph_authority(self) -> None:
        for item in [*self.result.graph["nodes"], *self.edges]:
            if item["authority"] != "authoritative":
                continue
            for evidence in item["evidence"]:
                self.assertFalse(
                    str(evidence["source_path"]).startswith(
                        "ai_collaboration/"
                    )
                )

    def test_generated_graph_is_portable_and_fresh(self) -> None:
        serialized = json.dumps(
            self.result.graph,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn(str(self.repository), serialized)
        fresh, messages = check_project_graph(self.repository)
        self.assertTrue(fresh, "\n".join(messages))


if __name__ == "__main__":
    unittest.main()
