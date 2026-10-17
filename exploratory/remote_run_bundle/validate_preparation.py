"""Freeze and validate the remote execution bundle without external calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import py_compile
from pathlib import Path

import run_codequal_remote
import run_sonarqube_remote
from common import REPO_ROOT


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PREPARATION_MANIFEST.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict[str, object]:
    if run_codequal_remote.UPSTREAM_COMMIT != "518360297f59ad7b6569233eb4b934e6b00c083b":
        raise ValueError("Unexpected CodeQual upstream commit")
    if run_sonarqube_remote.SONAR_IMAGE != "sonarqube@sha256:d4899d380ad9d7b63ebaa751e047f5a4f064f8902cdf7c1a3c3c96f7d71600ed":
        raise ValueError("Unexpected SonarQube image digest")
    required_sources = [
        REPO_ROOT / "experiments" / "codequal_analyzer_pilot" / "FINAL_TEST_PROTOCOL.md",
        REPO_ROOT / "experiments" / "codequal_analyzer_pilot" / "results" / "decision_test_summary.json",
        REPO_ROOT / "experiments" / "sonarqube_pilot" / "PROTOCOL.md",
        REPO_ROOT / "experiments" / "sonarqube_pilot" / "results" / "summary.json",
        REPO_ROOT / "experiments" / "ai_judge_prompt_calibration" / "PREPARATION_MANIFEST.json",
    ]
    for path in required_sources:
        if not path.exists():
            raise FileNotFoundError(path)
    python_assets = sorted(ROOT.glob("*.py")) + sorted((ROOT / "tests").glob("*.py"))
    for path in python_assets:
        py_compile.compile(str(path), doraise=True)
    assets = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != MANIFEST
        and "__pycache__" not in path.parts
    )
    return {
        "bundle": "remote_experiment_preparation",
        "status": "READY_NOT_RUN",
        "codequal_upstream_commit": run_codequal_remote.UPSTREAM_COMMIT,
        "sonarqube_image": run_sonarqube_remote.SONAR_IMAGE,
        "ai_judge_preparation_manifest_sha256": sha256(required_sources[-1]),
        "frozen_source_evidence": {
            path.relative_to(REPO_ROOT).as_posix(): sha256(path)
            for path in required_sources
        },
        "assets": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in assets
        },
        "external_experiment_calls_made": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.write_manifest:
        MANIFEST.write_text(rendered, encoding="utf-8")
    elif not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8") != rendered:
        raise SystemExit("PREPARATION_MANIFEST.json is missing or stale")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
