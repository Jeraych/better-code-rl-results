import unittest

from experiments.analyzer_screening.screen_candidates import (
    DEFAULT_THRESHOLDS,
    decide_candidates,
    group_variation,
)
from experiments.analyzer_screening.screen_extended_candidates import (
    decide,
    infer_entrypoint,
)


class AnalyzerScreeningTests(unittest.TestCase):
    def test_group_variation_counts_only_comparable_groups(self):
        rows = [
            {"_source": "a", "run_id": "r", "step": "1", "task_id": "t", "score": "1"},
            {"_source": "a", "run_id": "r", "step": "1", "task_id": "t", "score": "0"},
            {"_source": "a", "run_id": "r", "step": "2", "task_id": "u", "score": "1"},
            {"_source": "a", "run_id": "r", "step": "2", "task_id": "u", "score": "1"},
            {"_source": "a", "run_id": "r", "step": "3", "task_id": "v", "score": "0"},
        ]
        summary = group_variation(rows, lambda row: float(row["score"]))
        self.assertEqual(summary["comparable_group_count"], 2)
        self.assertEqual(summary["nonzero_variance_group_count"], 1)
        self.assertEqual(summary["nonzero_variance_group_rate"], 0.5)

    def test_decision_gate_keeps_saturated_performance_out(self):
        good_static = {
            "available_count": 100,
            "availability_rate": 1.0,
            "activation_rate": 0.25,
            "nonzero_variance_group_rate": 0.5,
        }
        analyzers = {
            "pep8_style": dict(good_static),
            "string_concat": dict(good_static),
            "dynamic_performance": {
                "available_count": 100,
                "ceiling_rate": 0.90,
                "nonzero_variance_group_rate": 0.10,
            },
        }
        decisions = decide_candidates(
            analyzers,
            {"online_gate_passed": True},
            DEFAULT_THRESHOLDS,
        )
        self.assertEqual(decisions["pep8_style"]["decision"], "promote")
        self.assertEqual(decisions["string_concat"]["decision"], "promote")
        self.assertEqual(decisions["dynamic_performance"]["decision"], "redesign")

    def test_infer_entrypoint_uses_first_top_level_function(self):
        code = "class Helper:\n    pass\n\ndef solve(value):\n    return value\n"
        self.assertEqual(infer_entrypoint(code), "solve")

    def test_infer_entrypoint_prefers_target_from_prompt(self):
        code = "def helper(value):\n    return value\n\ndef solve(value):\n    return helper(value)\n"
        prompt = "Complete this function:\n\ndef solve(value: int) -> int:\n    pass\n"
        self.assertEqual(infer_entrypoint(code, prompt), "solve")

    def test_extended_gate_keeps_batch_tool_offline(self):
        fixture = {
            "precision": 1.0,
            "recall": 1.0,
            "false_positive_rate": 0.0,
            "deterministic": True,
        }
        saved = {
            "availability_rate": 1.0,
            "activation_rate": 0.25,
            "activation_count": 25,
            "nonzero_variance_group_rate": 0.5,
            "mean_elapsed_ms": 1.0,
        }
        decision = decide("bandit_security", fixture, saved)
        self.assertEqual(decision["decision"], "offline_evaluator_only")
        self.assertFalse(decision["criteria"]["in_process"])

    def test_extended_gate_records_missing_measurements_as_rejection(self):
        fixture = {
            "precision": 1.0,
            "recall": 1.0,
            "false_positive_rate": 0.0,
            "deterministic": True,
        }
        saved = {
            "availability_rate": 0.0,
            "activation_rate": 0.0,
            "activation_count": 0,
            "nonzero_variance_group_rate": 0.0,
            "mean_elapsed_ms": None,
        }
        decision = decide("mypy_type_safety", fixture, saved)
        self.assertEqual(decision["decision"], "reject_current_configuration")
        self.assertFalse(decision["criteria"]["online_latency"])


if __name__ == "__main__":
    unittest.main()
