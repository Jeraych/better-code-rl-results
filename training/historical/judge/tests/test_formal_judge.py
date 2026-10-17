"""Stdlib-only regressions. No trainer imports, model loads, or live API calls."""
import ast
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import judge_reliability as reliability
import formal_judge_run as launcher


def envelope(value):
    return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(value)}}]}).encode())


def finding(**changes):
    return {"category": "Maintainability", "subcategory": "Unnecessary Conditional Block",
            "severity": "medium", "line_start": 1, "line_end": 2,
            "evidence": "if x", "reason": "Returning boolean condition simplifies the block", **changes}


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.request = urllib.request.Request("http://invalid.example/v1/chat/completions")

    def call(self, opener, sleep=lambda seconds: None):
        return reliability.request_judge(self.request, 60, json.loads, opener=opener, sleep=sleep)

    def test_valid_response_is_returned_unchanged(self):
        value = {"status": "ok", "findings": [finding()]}
        self.assertEqual(self.call(lambda *a, **k: envelope(value)), value)

    def test_transient_retries_have_bounded_backoff(self):
        calls, delays = [], []
        def opener(*args, **kwargs):
            calls.append(kwargs["timeout"])
            if len(calls) < 3:
                raise TimeoutError("SECRET endpoint text")
            return envelope({"status": "ok", "findings": []})
        self.assertEqual(self.call(opener, delays.append)["findings"], [])
        self.assertEqual(calls, [60, 60, 60])
        self.assertEqual(delays, [1.0, 2.0])

    def test_exhaustion_aborts_and_redacts(self):
        with patch.object(reliability, "record_event") as event:
            with self.assertRaises(reliability.JudgeFailure) as caught:
                self.call(lambda *a, **k: (_ for _ in ()).throw(TimeoutError("SECRET")))
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(sum(c.args[0] == "attempt" for c in event.call_args_list), 3)
        self.assertEqual(event.call_args_list[-1].args[0], "fatal")

    def test_http_auth_is_not_retried(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError("SECRET", 401, "SECRET", {}, None)
        with self.assertRaises(reliability.JudgeFailure):
            self.call(opener)
        self.assertEqual(len(calls), 1)

    def test_http_429_retried(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise urllib.error.HTTPError("SECRET", 429, "SECRET", {}, None)
            return envelope({"status": "ok", "findings": []})
        self.call(opener)
        self.assertEqual(len(calls), 2)

    def test_malformed_schema_never_clean(self):
        values = [{}, [], {"status": "error", "findings": []},
                  {"status": "ok"}, {"status": "ok", "findings": {}},
                  {"status": "ok", "findings": [None]},
                  {"status": "ok", "findings": [finding(line_start="1")]},
                  {"status": "ok", "findings": [finding(reason=None)]}]
        for value in values:
            with self.subTest(value=value), self.assertRaises(reliability.JudgeFailure):
                self.call(lambda *a, **k: envelope(value))

    def test_invalid_json_and_envelope_abort_without_retry(self):
        for body in [b"not json", b"{}", b'{"choices":[]}', b'\xff']:
            calls = []
            def opener(*args, **kwargs):
                calls.append(1)
                return io.BytesIO(body)
            with self.subTest(body=body), self.assertRaises(reliability.JudgeFailure):
                self.call(opener)
            self.assertEqual(len(calls), 1)

    def test_safe_statistics_are_persisted(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "events.jsonl"
            with patch.dict(os.environ, {"AI_JUDGE_STATUS_PATH": str(path)}):
                self.call(lambda *a, **k: envelope({"status": "ok", "findings": []}))
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([e["status"] for e in events], ["attempt", "ok"])


class HistoricalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = subprocess.check_output(["git", "show", launcher.BASELINE + ":train.py"],
                                              cwd=ROOT).decode("utf-8")
        cls.current = (ROOT / "train.py").read_text(encoding="utf-8")
        cls.old = launcher.historical_namespace(source=cls.baseline)
        cls.new = launcher.historical_namespace()

    def test_historical_semantic_functions_identical(self):
        names = {"numbered_python_code", "build_ai_judge_user_prompt", "parse_json_object",
                 "code_lines_for_span", "sanitize_ai_judge_findings", "score_ai_judge_findings",
                 "total_reward_from_diagnostic", "reward_combined", "make_training_args"}
        def nodes(source):
            return {n.name: ast.dump(n) for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name in names}
        self.assertEqual(nodes(self.baseline), nodes(self.current))
        self.assertEqual(len(nodes(self.current)), len(names))

    def test_prompt_and_taxonomy_constants_identical(self):
        for key in ("AI_JUDGE_SYSTEM_PROMPT", "AI_JUDGE_USER_TEMPLATE", "AI_JUDGE_PROMPT_VERSION",
                    "AI_JUDGE_PROMPT_HASH", "AI_JUDGE_ALLOWED_SUBCATEGORIES", "AI_JUDGE_SEVERITY_WEIGHTS"):
            self.assertEqual(self.old[key], self.new[key])
        self.assertEqual(self.new["AI_JUDGE_PROMPT_HASH"], "50d083c5e7100d2e")

    def test_valid_sanitized_scores_match_baseline(self):
        values = [[], [finding()], [finding(severity="low")], [finding(severity="HIGH")],
                  [finding(severity="critical")], [finding(category="Unknown")],
                  [finding(subcategory="Unnecessary Else", evidence="if x")],
                  [finding(subcategory="Unnecessary Else", evidence="else:")],
                  [finding(category="Readability", subcategory="Confusing Variable Naming",
                           evidence="i", reason="could be more descriptive")],
                  [finding()] * 12]
        for findings in values:
            response = {"status": "ok", "findings": findings}
            reliability.validate_response(response)
            a = self.old["sanitize_ai_judge_findings"](response, "if x:\n    return True")
            b = self.new["sanitize_ai_judge_findings"](response, "if x:\n    return True")
            self.assertEqual(a, b)
            self.assertEqual(self.old["score_ai_judge_findings"](a), self.new["score_ai_judge_findings"](b))

    def test_failure_cannot_return_reward(self):
        namespace = self.new.copy()
        namespace["call_ollama_ai_judge"] = lambda *a: (_ for _ in ()).throw(reliability.JudgeFailure("http"))
        fn = self.new["apply_ai_judge_reward"]
        with patch.dict(fn.__globals__, namespace):
            diagnostic = {"test_status": "passed", "reward_ai_judge": 0}
            with self.assertRaises(reliability.JudgeFailure):
                fn(diagnostic, "task", "code")

    def test_correctness_gate_unchanged(self):
        diagnostic = {"test_status": "failed", "reward_ai_judge": 0}
        with patch.dict(self.new, {"call_ollama_ai_judge": lambda *a: self.fail("must be gated")}):
            self.new["apply_ai_judge_reward"](diagnostic, "task", "code")
        self.assertEqual(diagnostic["ai_judge_status"], "not_eligible")
        self.assertEqual(diagnostic["reward_ai_judge"], 0)

    def test_valid_reward_diagnostics_match_baseline(self):
        for response in ({"status": "ok", "findings": []},
                         {"status": "ok", "findings": [finding()]},
                         {"status": "ok", "findings": [finding(severity="HIGH")]}):
            old, new = {"test_status": "passed"}, {"test_status": "passed"}
            for namespace, diagnostic in ((self.old, old), (self.new, new)):
                with patch.dict(namespace, {"call_ollama_ai_judge": lambda *a: response}):
                    namespace["apply_ai_judge_reward"](diagnostic, "task", "if x:\n    return True")
            self.assertEqual(old, new)

    def test_invalid_response_raises_before_clean_reward(self):
        for response in ({}, {"status": "ok", "findings": [None]}):
            with patch.dict(self.new, {"call_ollama_ai_judge": lambda *a: response}):
                diagnostic = {"test_status": "passed", "reward_ai_judge": 0}
                with self.assertRaises(reliability.JudgeFailure):
                    self.new["apply_ai_judge_reward"](diagnostic, "task", "code")
                self.assertNotIn("ai_judge_score", diagnostic)

    def test_formal_has_no_standalone_dependency(self):
        for name in launcher.FILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("individual_judge", text)
            self.assertNotIn("ai_judge_standalone", text)


class ConfigurationTests(unittest.TestCase):
    def test_smoke_diff_is_only_steps(self):
        full, smoke = launcher.config(), launcher.config(True)
        self.assertEqual({k: (full[k], smoke[k]) for k in full if full[k] != smoke[k]},
                         {"MAX_STEPS": ("500", "20")})
        self.assertEqual(full["REWARD_FORMAT_WEIGHT"], "0.1")
        self.assertEqual(full["REWARD_SYNTAX_WEIGHT"], "0.1")
        self.assertEqual(full["REWARD_COMPILE_WEIGHT"], "0.3")

    def test_ambient_trainer_knobs_removed_and_paths_fresh(self):
        with patch.dict(os.environ, {"AUTO_RESUME": "1", "SAVE_BEFORE_AFTER_CSV": "0",
                                    "LORA_PATH": "smoke-checkpoint", "MAX_STEPS": "999"}):
            values = launcher.stage_config(launcher.config(), ROOT / "results/new", "train")
            env = launcher.child_env(values, {"AI_JUDGE_MODEL": "qwen-32b"})
        self.assertEqual(env["AUTO_RESUME"], "0")
        self.assertEqual(env["SAVE_BEFORE_AFTER_CSV"], "1")
        self.assertEqual(env["MAX_STEPS"], "500")
        self.assertNotIn("smoke-checkpoint", env["LORA_PATH"])

    def test_dry_run_never_loads_secrets_or_starts_process(self):
        args = type("Args", (), {"smoke": True, "seed": 3407, "dry_run": True})()
        with patch.object(launcher, "credentials", side_effect=AssertionError("secrets")), \
                patch.object(launcher.subprocess, "run", side_effect=AssertionError("process")), \
                patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(launcher.run(args), 0)

    def test_pure_mode_rejected(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/formal_judge_run.py"),
                                 "--pure", "--dry-run"], capture_output=True)
        self.assertEqual(result.returncode, 2)


class HealthTests(unittest.TestCase):
    def fixture(self, root):
        values = launcher.config(True)
        meta = {"mode": "smoke", "seed": 3407, "status": "completed", "end": "synthetic-test",
                "start": "synthetic-test", "git_commit": launcher.BASELINE,
                "git_branch": "synthetic-test", "dirty": False, "dataset": {},
                "requested_alias": "qwen-32b", "recorded_backend": launcher.BACKEND,
                "stage_results": [{"stage": stage, "start": "synthetic-test",
                                   "end": "synthetic-test", "exit_code": 0}
                                  for stage in launcher.STAGES],
                "configuration": values, "prompt": launcher.prompt_metadata(),
                "source_hashes": launcher.source_hashes(),
                "stages": {stage: launcher.stage_config(values, root, stage) for stage in launcher.STAGES}}
        launcher.write_json(root / "metadata.json", meta)
        (root / "judge-status.jsonl").write_text(
            '\n'.join(json.dumps({"status": status}) for status in ("attempt", "ok", "evaluation")),
            encoding="utf-8")
        for name in ("packages.txt", "gpu.txt", "source.diff", "baseline.diff", "git-status.txt", "judge-prompt.txt",
                     "judge-summary.json", "adapters/train/adapter_config.json",
                     "adapters/train/adapter_model.safetensors"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("synthetic test fixture", encoding="utf-8")
        for name in launcher.FILES:
            target = root / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        target = root / "output/train/trainer_state.json"
        target.parent.mkdir(parents=True)
        launcher.write_json(target, {"global_step": 20})
        fields = ["step", "reward_ai_judge", "reward_total", "ai_judge_status", "test_status",
                  "ai_judge_error", "ai_judge_findings_json", "ai_judge_model",
                  "ai_judge_prompt_hash", "ai_judge_prompt_version"]
        rows = [{"step": step, "reward_ai_judge": score, "reward_total": 5 + score,
                 "ai_judge_status": "ok", "test_status": "passed", "ai_judge_error": "",
                 "ai_judge_findings_json": "[]", "ai_judge_model": "qwen-32b",
                 "ai_judge_prompt_hash": meta["prompt"]["historical_hash"],
                 "ai_judge_prompt_version": meta["prompt"]["version"]}
                for step in range(20) for score in (0.65, 0.85, 0.65, 0.85)]
        target = root / "logs/train/samples.csv"
        target.parent.mkdir(parents=True)
        def write_rows():
            with target.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        write_rows()
        return meta, rows, write_rows

    def test_health_and_gate_pass_then_reject_failed_infrastructure(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory) / "correctness-judge-smoke" / "fixture"
            root.mkdir(parents=True)
            meta, rows, write_rows = self.fixture(root)
            self.assertTrue(launcher.health(root)["pass"])
            launcher.approval_gate(root, "formal", 3407)
            rows[0]["ai_judge_status"] = "error"
            write_rows()
            report = launcher.health(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["checks"]["no_failure_quality_rewards"])
            with self.assertRaises(ValueError):
                launcher.approval_gate(root, "formal", 3407)

    def test_health_rejects_equal_rewards_and_missing_step(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory) / "correctness-judge-smoke" / "fixture"
            root.mkdir(parents=True)
            meta, rows, write_rows = self.fixture(root)
            for row in rows:
                row["reward_ai_judge"] = 1
            rows.pop()
            write_rows()
            report = launcher.health(root)
            self.assertFalse(report["checks"]["useful_within_group_judge_variation"])
            self.assertFalse(report["checks"]["complete_steps_and_groups"])


if __name__ == "__main__":
    unittest.main()
