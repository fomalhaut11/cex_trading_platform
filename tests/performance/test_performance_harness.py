import tempfile
import unittest
from pathlib import Path

from tools.performance.harness import (
    report_json,
    run_order_book_benchmark,
    run_recorder_benchmark,
)


class PerformanceHarnessTests(unittest.TestCase):
    """Small smoke tests; production-sized loads remain explicit opt-in runs."""

    def test_order_book_harness_is_deterministic_and_bounded(self) -> None:
        first = run_order_book_benchmark(200, seed=7)
        second = run_order_book_benchmark(200, seed=7)

        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.event_count, 200)
        self.assertFalse(first.thread_leaks)
        self.assertLess(first.retained_traced_bytes, 2_000_000)
        self.assertGreater(first.events_per_second, 0)

    def test_recorder_harness_round_trips_without_thread_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            result = run_recorder_benchmark(
                50,
                directory=Path(name),
                seed=11,
            )

        self.assertEqual(result.event_count, 50)
        self.assertFalse(result.thread_leaks)
        self.assertGreater(result.artifact_bytes, 0)
        self.assertLess(result.retained_traced_bytes, 2_000_000)
        self.assertEqual(len(result.digest), 64)

    def test_report_is_stable_json_shape(self) -> None:
        rendered = report_json({"seed": 1, "results": []})
        self.assertIn('"seed": 1', rendered)
        self.assertIn('"results": []', rendered)


if __name__ == "__main__":
    unittest.main()

