"""Run the prepared AI-judge smoke or full calibration as a recorded stage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from common import REPO_ROOT, load_json, redact_text, resolve_run_dir, run_command, update_stage, utc_now, write_json


EXPERIMENT = REPO_ROOT / "experiments" / "ai_judge_prompt_calibration"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--mode", choices=["smoke", "full"], default="full")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--request-delay-seconds", type=float, default=0.0)
    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run_directory)
    if not (run_dir / "run_manifest.json").exists():
        raise SystemExit("Initialize the run directory first")
    stage_name = "ai_judge_smoke" if args.mode == "smoke" else "ai_judge_calibration"
    stage_dir = run_dir / stage_name
    if stage_dir.exists() and not args.resume:
        raise SystemExit(f"Refusing to overwrite existing stage: {stage_dir}")
    if not os.getenv("AI_JUDGE_BASE_URL", "").strip():
        raise SystemExit("AI_JUDGE_BASE_URL must be configured in the shell")
    stage = {
        "state": "running",
        "mode": args.mode,
        "started_at_utc": utc_now(),
        "endpoint": "<configured>",
        "model": os.getenv("AI_JUDGE_MODEL", "qwen3-coder:30b"),
        "candidate_code_executed": False,
    }
    update_stage(run_dir, stage_name, stage)
    command = [
        sys.executable,
        str(EXPERIMENT / "run_calibration.py"),
        "--output-dir", str(stage_dir),
        "--profiles", "baseline_v3", "calibrated_v4",
        "--repetitions", "1" if args.mode == "smoke" else "2",
        "--request-delay-seconds", str(args.request_delay_seconds),
    ]
    if args.mode == "smoke":
        command.extend(["--case-limit", "2"])
    if args.resume:
        command.append("--resume")
    try:
        result = run_command(
            command,
            cwd=REPO_ROOT,
            log_path=run_dir / "logs" / f"{stage_name}.log",
            env=os.environ.copy(),
            allowed_exit_codes={0, 2},
        )
        if result["exit_code"] == 2:
            raise RuntimeError("Calibration completed with one or more recorded call errors")
        run_command(
            [sys.executable, str(EXPERIMENT / "summarize_results.py"), str(stage_dir)],
            cwd=REPO_ROOT,
            log_path=run_dir / "logs" / f"{stage_name}_summary.log",
        )
        stage.update(
            {
                "state": "complete",
                "finished_at_utc": utc_now(),
                "prompt_hashes": load_json(stage_dir / "run_manifest.json")["configuration"]["prompt_hashes"],
                "summary": load_json(stage_dir / "summary.json"),
            }
        )
        return_code = 0
    except Exception as exc:
        stage.update(
            {
                "state": "failed",
                "finished_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error_message": redact_text(exc)[:500].replace(os.getenv("AI_JUDGE_BASE_URL", ""), "<configured>"),
            }
        )
        return_code = 1
    write_json(stage_dir / "stage_manifest.json", stage)
    update_stage(run_dir, stage_name, stage)
    print(json.dumps(stage, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
