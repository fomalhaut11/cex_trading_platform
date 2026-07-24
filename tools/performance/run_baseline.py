"""Run the opt-in offline baseline.

Example:
    python -m tools.performance.run_baseline --events 100000
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .harness import DEFAULT_SEED, report_json, run_suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON result path (parent must exist)",
    )
    args = parser.parse_args()
    if args.events <= 0:
        parser.error("--events must be positive")
    with tempfile.TemporaryDirectory(prefix="cex-quant-perf-") as name:
        report = run_suite(
            event_count=args.events,
            seed=args.seed,
            directory=Path(name),
        )
    rendered = report_json(report)
    print(rendered)
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

