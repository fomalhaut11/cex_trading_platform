from __future__ import annotations

import ast
import unittest
from pathlib import Path

from cex_quant.core import ClientOrderId, UnixNanos
from cex_quant.runtime import GroupedExecutionBlockedError, OrderGroupRuntime

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "src" / "cex_quant"


def imports_under(*roots: Path) -> tuple[tuple[Path, str], ...]:
    found: list[tuple[Path, str]] = []
    for root in roots:
        paths = (root,) if root.is_file() else tuple(root.rglob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.extend((path, alias.name) for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    found.append((path, node.module))
    return tuple(found)


class A018FrozenBoundaryAcceptanceTests(unittest.TestCase):
    def test_frozen_oms_and_risk_have_no_carry_dependency(self) -> None:
        forbidden = tuple(
            (path, module)
            for path, module in imports_under(SOURCE / "oms", SOURCE / "risk")
            if module.startswith("cex_quant.applications.carry")
        )
        self.assertEqual(forbidden, ())

    def test_t046_runtime_adapters_have_no_binance_or_network_import(self) -> None:
        files = tuple(
            SOURCE / "runtime" / name
            for name in (
                "carry_projection.py",
                "grouped_execution.py",
                "offline_execution.py",
                "portfolio_projection.py",
            )
        )
        forbidden_roots = (
            "aiohttp",
            "asyncio",
            "http",
            "requests",
            "socket",
            "urllib",
            "websockets",
        )
        forbidden = tuple(
            (path, module)
            for path, module in imports_under(*files)
            if "binance" in module.lower()
            or module.split(".", maxsplit=1)[0] in forbidden_roots
        )
        self.assertEqual(forbidden, ())

    def test_grouped_runtime_has_no_production_composition_root(self) -> None:
        constructors = tuple(
            path.relative_to(ROOT)
            for path in (ROOT / "src").rglob("*.py")
            if path.name != "grouped_execution.py"
            and "GroupedExecutionRuntime(" in path.read_text(encoding="utf-8")
        )
        self.assertEqual(constructors, ())

    def test_original_group_submit_route_remains_hard_blocked(self) -> None:
        groups = OrderGroupRuntime(now_ns=lambda: UnixNanos(1_000))
        with self.assertRaises(GroupedExecutionBlockedError):
            groups.submit_prepared_child(ClientOrderId("a018-blocked"))


if __name__ == "__main__":
    unittest.main()
