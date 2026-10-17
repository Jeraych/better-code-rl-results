from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import REPO_ROOT, redact_text, resolve_run_dir  # noqa: E402
from run_sonarqube_remote import parse_sensor_ms  # noqa: E402
from validate_run_bundle import SECRET_PATTERNS, required_files  # noqa: E402


class BundleTests(unittest.TestCase):
    def test_run_directory_is_scoped(self) -> None:
        expected = (REPO_ROOT / "research_runs" / "valid-run-01").resolve()
        self.assertEqual(resolve_run_dir(expected), expected)
        with self.assertRaises(ValueError):
            resolve_run_dir(REPO_ROOT / "outside-run")
        with self.assertRaises(ValueError):
            resolve_run_dir(REPO_ROOT / "research_runs" / "x")

    def test_secret_patterns_detect_credentials(self) -> None:
        self.assertIsNotNone(
            SECRET_PATTERNS["authorization_bearer"].search("Authorization: Bearer secret123")
        )
        self.assertIsNotNone(
            SECRET_PATTERNS["sonar_token_field"].search('{"token": "synthetic-fixture-token"}')
        )

    def test_repository_path_is_redacted(self) -> None:
        redacted = redact_text(REPO_ROOT / "research_runs")
        self.assertIn("<REPO_ROOT>", redacted)
        self.assertNotIn(str(REPO_ROOT), redacted)

    def test_sonar_sensor_timing_parser(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.log"
            path.write_text(
                "INFO: Sensor Python Sensor [python] (done) | time=2237ms\n",
                encoding="utf-8",
            )
            self.assertEqual(parse_sensor_ms(path), 2237)

    def test_required_ai_judge_evidence(self) -> None:
        paths = required_files("ai_judge_calibration", Path("stage"))
        self.assertIn(Path("stage/calls.jsonl"), paths)
        self.assertIn(Path("stage/RESULTS.md"), paths)


if __name__ == "__main__":
    unittest.main()
