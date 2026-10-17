from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calibration_core import sanitize_findings  # noqa: E402
from export_dataset import build_cases  # noqa: E402
from prompt_profiles import PROMPT_PROFILES  # noqa: E402
from summarize_results import prompt_metrics  # noqa: E402


class PreparationTests(unittest.TestCase):
    def test_baseline_prompt_matches_run13_hash(self) -> None:
        self.assertEqual(PROMPT_PROFILES["baseline_v3"].prompt_hash, "50d083c5e7100d2e")

    def test_dataset_is_balanced(self) -> None:
        cases = build_cases()
        self.assertEqual(len(cases), 36)
        self.assertEqual(sum(case["condition"] == "clean" for case in cases), 18)
        self.assertEqual(sum(case["condition"] == "degraded" for case in cases), 18)

    def test_unnecessary_else_requires_else_evidence(self) -> None:
        response = {
            "status": "ok",
            "findings": [
                {
                    "category": "Maintainability",
                    "subcategory": "Unnecessary Else",
                    "severity": "low",
                    "line_start": 1,
                    "line_end": 1,
                    "evidence": "return value",
                    "reason": "remove the branch",
                }
            ],
        }
        self.assertEqual(sanitize_findings(response, "def f():\n    return 1\n"), [])

    def test_perfect_predictions_have_perfect_metrics(self) -> None:
        records = []
        for case in build_cases():
            predicted = case["expected_subcategories"]
            records.append(
                {
                    **case,
                    "profile": "test",
                    "repetition": 1,
                    "status": "ok",
                    "predicted_subcategories": predicted,
                    "score": 1.0 if case["condition"] == "clean" else 0.85,
                    "raw_finding_count": len(predicted),
                    "sanitized_finding_count": len(predicted),
                    "elapsed_ms": 1.0,
                }
            )
        metrics = prompt_metrics(records)
        self.assertEqual(metrics["micro_f1"], 1.0)
        self.assertEqual(metrics["macro_f1"], 1.0)
        self.assertEqual(metrics["clean_false_positive_rate"], 0.0)
        self.assertEqual(metrics["pair_direction"]["correct_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
