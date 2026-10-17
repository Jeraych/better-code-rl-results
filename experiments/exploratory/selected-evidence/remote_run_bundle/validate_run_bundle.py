"""Validate a completed run, scan for leaked credentials, and hash evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from common import load_json, resolve_run_dir, utc_now, write_json


SECRET_PATTERNS = {
    "authorization_bearer": re.compile(r"Authorization\s*[:=]\s*Bearer\s+\S+", re.IGNORECASE),
    "committed_api_key": re.compile(r"AI_JUDGE_API_KEY\s*=\s*[\"']?(?!<PRIVATE|<configured)[^\s\"']+", re.IGNORECASE),
    "sonar_token_field": re.compile(r"[\"']token[\"']\s*:\s*[\"'][A-Za-z0-9_-]{12,}"),
}


def required_files(stage: str, stage_dir: Path) -> list[Path]:
    if stage == "codequal_analyzer":
        return [
            stage_dir / "stage_manifest.json",
            stage_dir / "results" / "summary.json",
            stage_dir / "results" / "decision_test_summary.json",
            stage_dir / "results" / "decision_test_fixtures.csv",
        ]
    if stage == "sonarqube":
        return [
            stage_dir / "stage_manifest.json",
            stage_dir / "results" / "summary.json",
            stage_dir / "results" / "raw_issues_scan1.json",
            stage_dir / "results" / "raw_issues_scan2.json",
            stage_dir / "results" / "raw_issues_extension.json",
        ]
    if stage in {"ai_judge_smoke", "ai_judge_calibration"}:
        return [
            stage_dir / "stage_manifest.json",
            stage_dir / "run_manifest.json",
            stage_dir / "calls.jsonl",
            stage_dir / "summary.json",
            stage_dir / "per_call.csv",
            stage_dir / "RESULTS.md",
        ]
    return [stage_dir / "stage_manifest.json"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run_directory)
    run_manifest = load_json(run_dir / "run_manifest.json")
    errors = []
    if run_manifest.get("state") != "complete":
        errors.append(f"Top-level run state is {run_manifest.get('state')}, not complete")
    for stage, details in run_manifest.get("stages", {}).items():
        if details.get("state") != "complete":
            errors.append(f"Stage {stage} is {details.get('state')}")
        for path in required_files(stage, run_dir / stage):
            if not path.exists():
                errors.append(f"Missing required evidence: {path.relative_to(run_dir)}")

    leaks = []
    hashes = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.name == "evidence_manifest.json":
            continue
        relative = path.relative_to(run_dir).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.stat().st_size > 10_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                leaks.append({"file": relative, "pattern": name})
    if leaks:
        errors.append(f"Potential credential leaks: {len(leaks)}")
    evidence = {
        "run_id": run_manifest.get("run_id"),
        "validated_at_utc": utc_now(),
        "valid": not errors,
        "errors": errors,
        "potential_secret_leaks": leaks,
        "file_count": len(hashes),
        "sha256": hashes,
    }
    write_json(run_dir / "evidence_manifest.json", evidence)
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
