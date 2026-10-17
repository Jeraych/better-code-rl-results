"""Shared utilities for isolated, evidence-preserving remote experiments."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


BUNDLE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BUNDLE_ROOT.parents[1]
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def redact_text(value: object) -> str:
    text = str(value)
    replacements = [
        (str(REPO_ROOT.resolve()), "<REPO_ROOT>"),
        (str(Path.home().resolve()), "<HOME>"),
    ]
    for original, replacement in replacements:
        text = text.replace(original, replacement)
        text = text.replace(original.replace("\\", "/"), replacement)
    return text


def resolve_run_dir(value: Path) -> Path:
    resolved = value.resolve()
    expected_root = (REPO_ROOT / "research_runs").resolve()
    if resolved.parent != expected_root:
        raise ValueError(f"Run directory must be a direct child of {expected_root}")
    if not RUN_ID_PATTERN.fullmatch(resolved.name):
        raise ValueError("Run ID must be 3-80 letters, digits, dots, dashes, or underscores")
    return resolved


def initialize_run(run_id: str) -> Path:
    run_dir = resolve_run_dir(REPO_ROOT / "research_runs" / run_id)
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {run_dir}")
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "state": "prepared",
        "created_at_utc": utc_now(),
        "repository_commit": git_commit(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "stages": {},
        "privacy": {
            "endpoint_recording": "redacted as <configured>",
            "secrets_expected_in_results": False,
        },
    }
    write_json(run_dir / "run_manifest.json", manifest)
    return run_dir


def update_stage(run_dir: Path, stage: str, values: dict[str, Any]) -> None:
    manifest_path = run_dir / "run_manifest.json"
    manifest = load_json(manifest_path)
    manifest["stages"][stage] = values
    states = [item.get("state") for item in manifest["stages"].values()]
    if "failed" in states:
        manifest["state"] = "failed"
    elif states and all(state == "complete" for state in states):
        manifest["state"] = "complete"
    else:
        manifest["state"] = "running"
    write_json(manifest_path, manifest)


def run_command(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
    allowed_exit_codes: set[int] | None = None,
) -> dict[str, Any]:
    started = utc_now()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    display_command = [redact_text(item) for item in command]
    log_path.write_text(
        f"COMMAND: {' '.join(display_command)}\nSTARTED_UTC: {started}\n"
        f"EXIT_CODE: {completed.returncode}\n\nSTDOUT\n{redact_text(completed.stdout)}"
        f"\n\nSTDERR\n{redact_text(completed.stderr)}",
        encoding="utf-8",
    )
    allowed = allowed_exit_codes if allowed_exit_codes is not None else {0}
    if completed.returncode not in allowed:
        raise RuntimeError(
            f"Command failed with {completed.returncode}; see {log_path}"
        )
    return {
        "command": display_command,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "exit_code": completed.returncode,
        "log": log_path.name,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_executable(venv: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    directory = "Scripts" if os.name == "nt" else "bin"
    return venv / directory / f"{name}{suffix}"
