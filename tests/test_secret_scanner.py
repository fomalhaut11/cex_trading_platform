import tempfile
import unittest
from pathlib import Path

from tools.ci.scan_secrets import scan_text


class SecretScannerTests(unittest.TestCase):
    def test_clean_text_has_no_findings(self) -> None:
        findings = scan_text(
            Path("settings.py"),
            "api_key = load_from_environment()\n",
        )
        self.assertEqual(findings, ())

    def test_high_confidence_token_reports_exact_line(self) -> None:
        token = "gh" + "p_" + "a" * 36
        findings = scan_text(
            Path("leak.txt"),
            f"safe\ncredential={token}\n",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].path, Path("leak.txt"))
        self.assertEqual(findings[0].line, 2)
        self.assertEqual(findings[0].pattern_name, "GitHub token")

    def test_binary_or_file_handling_is_outside_text_scanner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.txt"
            path.write_text("", encoding="utf-8")
            self.assertEqual(scan_text(path, path.read_text()), ())


if __name__ == "__main__":
    unittest.main()
