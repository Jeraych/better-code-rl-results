from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        prompt = payload["messages"][1]["content"]
        findings = []
        if "list = []" in prompt:
            findings.append(
                {
                    "category": "Readability",
                    "subcategory": "Confusing Variable Naming",
                    "severity": "low",
                    "line_start": 2,
                    "line_end": 2,
                    "evidence": "list = []",
                    "reason": "The name shadows the built-in list type; renaming preserves behavior.",
                }
            )
        content = json.dumps({"status": "ok", "findings": findings})
        response = {
            "id": "mock",
            "model": "mock-judge",
            "choices": [{"message": {"content": content}}],
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class RunnerRoundTripTests(unittest.TestCase):
    def test_runner_and_summarizer_round_trip(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "mock_run"
                env = os.environ.copy()
                env["AI_JUDGE_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
                env["AI_JUDGE_API_KEY"] = "mock-key"
                env["AI_JUDGE_MODEL"] = "mock-judge"
                run = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "run_calibration.py"),
                        "--output-dir",
                        str(output),
                        "--profiles",
                        "baseline_v3",
                        "calibrated_v4",
                        "--repetitions",
                        "1",
                        "--case-limit",
                        "2",
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(run.returncode, 0, run.stderr)
                summarize = subprocess.run(
                    [sys.executable, str(ROOT / "summarize_results.py"), str(output)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(summarize.returncode, 0, summarize.stderr)
                calls = (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
                summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual(len(calls), 4)
                self.assertEqual(summary["decision"]["outcome"], "NOT_APPLICABLE")
                self.assertTrue(all(item["success_rate"] == 1.0 for item in summary["profiles"].values()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
