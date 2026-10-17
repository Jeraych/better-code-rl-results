"""Reproduce CodeQual in a disposable layout without touching frozen results."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from common import (
    REPO_ROOT,
    load_json,
    redact_text,
    resolve_run_dir,
    run_command,
    sha256_file,
    update_stage,
    utc_now,
    venv_python,
    write_json,
)


UPSTREAM_URL = "https://github.com/MaximeRobeyns/codequal_analyzer.git"
UPSTREAM_COMMIT = "518360297f59ad7b6569233eb4b934e6b00c083b"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run_directory)
    if not (run_dir / "run_manifest.json").exists():
        raise SystemExit("Initialize the run directory first")
    stage_dir = run_dir / "codequal_analyzer"
    if stage_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing stage: {stage_dir}")
    stage_dir.mkdir()
    logs = stage_dir / "logs"
    work = run_dir / "work" / "codequal_workspace"
    fake_repo = work / "UnSloth-RL"
    experiment = fake_repo / "experiments" / "codequal_analyzer_pilot"
    analyzer = work / "tmp" / "research_codequal_analyzer"
    venv = work / "codequal_venv"
    stage = {
        "state": "running",
        "started_at_utc": utc_now(),
        "upstream_url": UPSTREAM_URL,
        "upstream_commit": UPSTREAM_COMMIT,
        "candidate_code_executed": False,
    }
    update_stage(run_dir, "codequal_analyzer", stage)
    try:
        experiment.parent.mkdir(parents=True, exist_ok=True)
        analyzer.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO_ROOT / "experiments" / "codequal_analyzer_pilot", experiment)
        shutil.rmtree(experiment / "results")
        (experiment / "results").mkdir()
        source_samples = REPO_ROOT / "results" / "13" / "samples.csv"
        target_samples = fake_repo / "results" / "13" / "samples.csv"
        target_samples.parent.mkdir(parents=True)
        shutil.copy2(source_samples, target_samples)

        commands = []
        commands.append(
            run_command(
                ["git", "clone", UPSTREAM_URL, str(analyzer)],
                cwd=work,
                log_path=logs / "01_clone.log",
            )
        )
        commands.append(
            run_command(
                ["git", "checkout", "--detach", UPSTREAM_COMMIT],
                cwd=analyzer,
                log_path=logs / "02_checkout.log",
            )
        )
        commands.append(
            run_command(
                ["git", "apply", str(experiment / "patches" / "windows-compat.patch")],
                cwd=analyzer,
                log_path=logs / "03_patch.log",
            )
        )
        commands.append(
            run_command(
                [sys.executable, "-m", "venv", str(venv)],
                cwd=work,
                log_path=logs / "04_venv.log",
            )
        )
        python = venv_python(venv)
        commands.append(
            run_command(
                [str(python), "-m", "pip", "install", "--requirement", str(experiment / "requirements-pilot.txt")],
                cwd=work,
                log_path=logs / "05_install.log",
            )
        )
        upstream_test = run_command(
            [str(python), "-m", "pytest", "-q"],
            cwd=analyzer,
            log_path=logs / "06_upstream_tests.log",
            allowed_exit_codes=set(range(0, 256)),
        )
        commands.append(
            run_command(
                [str(python), "run_pilot.py", "--sample-size", "50", "--seed", "42", "--synthetic-repetitions", "3"],
                cwd=experiment,
                log_path=logs / "07_pilot.log",
            )
        )
        commands.append(
            run_command(
                [str(python), "summarize_results.py"],
                cwd=experiment,
                log_path=logs / "08_statistics.log",
            )
        )
        commands.append(
            run_command(
                [str(python), "run_decision_test.py", "--repetitions", "2"],
                cwd=experiment,
                log_path=logs / "09_decision.log",
            )
        )
        commands.append(
            run_command(
                [str(python), "run_script_smoke.py"],
                cwd=experiment,
                log_path=logs / "10_script_smoke.log",
            )
        )
        freeze = run_command(
            [str(python), "-m", "pip", "freeze"],
            cwd=work,
            log_path=logs / "11_pip_freeze.log",
        )
        (stage_dir / "environment_freeze.txt").write_text(freeze["stdout"], encoding="utf-8")
        shutil.copytree(experiment / "results", stage_dir / "results")
        source_hashes = {
            path.name: sha256_file(path)
            for path in [
                experiment / "FINAL_TEST_PROTOCOL.md",
                experiment / "decision_fixtures.py",
                experiment / "codequal_adapter.py",
                experiment / "requirements-pilot.txt",
                experiment / "patches" / "windows-compat.patch",
                source_samples,
            ]
        }
        stage.update(
            {
                "state": "complete",
                "finished_at_utc": utc_now(),
                "upstream_test_exit_code": upstream_test["exit_code"],
                "commands": [
                    {key: value for key, value in command.items() if key not in {"stdout", "stderr"}}
                    for command in commands
                ],
                "source_hashes": source_hashes,
                "result_summary": load_json(stage_dir / "results" / "decision_test_summary.json"),
            }
        )
        write_json(stage_dir / "stage_manifest.json", stage)
        update_stage(run_dir, "codequal_analyzer", stage)
        if not args.keep_work:
            shutil.rmtree(work)
        print(json.dumps(stage, indent=2))
        return 0
    except Exception as exc:
        stage.update(
            {
                "state": "failed",
                "finished_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error_message": redact_text(exc)[:500],
                "work_preserved": True,
            }
        )
        write_json(stage_dir / "stage_manifest.json", stage)
        update_stage(run_dir, "codequal_analyzer", stage)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
