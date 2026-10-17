"""Validate and freeze calibration assets without contacting an AI judge."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

from calibration_core import build_user_prompt
from export_dataset import build_cases, render
from prompt_profiles import PROMPT_PROFILES


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
MANIFEST_PATH = ROOT / "PREPARATION_MANIFEST.json"
EXPECTED_BASELINE_HASH = "50d083c5e7100d2e"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_prompt_hash() -> str:
    tree = ast.parse((REPO_ROOT / "train.py").read_text(encoding="utf-8"))
    values: dict[str, str] = {}
    wanted = {
        "AI_JUDGE_PROMPT_VERSION",
        "AI_JUDGE_SYSTEM_PROMPT",
        "AI_JUDGE_USER_TEMPLATE",
    }
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in wanted:
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                values[target.id] = value
    if set(values) != wanted:
        raise ValueError("Could not extract the production AI-judge prompt")
    prompt_text = (
        values["AI_JUDGE_PROMPT_VERSION"]
        + "\n"
        + values["AI_JUDGE_SYSTEM_PROMPT"]
        + "\n"
        + values["AI_JUDGE_USER_TEMPLATE"]
    )
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]


def build_manifest() -> dict[str, object]:
    dataset_text, manifest_text = render()
    committed_dataset = (ROOT / "dataset" / "cases.jsonl").read_text(encoding="utf-8")
    committed_manifest = (ROOT / "dataset" / "manifest.json").read_text(encoding="utf-8")
    if committed_dataset != dataset_text or committed_manifest != manifest_text:
        raise ValueError("Committed dataset exports are stale")
    cases = build_cases()
    counts = Counter(
        case["target_subcategory"] for case in cases if case["condition"] == "degraded"
    )
    if len(cases) != 36 or set(counts.values()) != {3}:
        raise ValueError("Expected 36 cases and three seeded cases per subcategory")
    for case in cases:
        ast.parse(case["candidate_code"])
        prompt = build_user_prompt(PROMPT_PROFILES["calibrated_v4"], case)
        if case["candidate_code"].strip() not in prompt:
            # The rendered prompt contains numbered code, so verify distinctive content instead.
            first_code_line = case["candidate_code"].splitlines()[0]
            if first_code_line not in prompt:
                raise ValueError(f"Candidate missing from prompt: {case['case_id']}")

    baseline_hash = PROMPT_PROFILES["baseline_v3"].prompt_hash
    if baseline_hash != EXPECTED_BASELINE_HASH or production_prompt_hash() != baseline_hash:
        raise ValueError("baseline_v3 does not match the production Run 13 prompt")

    asset_paths = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != MANIFEST_PATH
        and "__pycache__" not in path.parts
        and "results" not in path.relative_to(ROOT).parts
    )
    return {
        "experiment": "ai_judge_prompt_calibration",
        "preparation_status": "READY_NOT_RUN",
        "production_prompt_source_commit": "efcfea624b59134bfe1c8f6c91c11d06cfc287bd",
        "dataset_sha256": hashlib.sha256(dataset_text.encode("utf-8")).hexdigest(),
        "prompt_hashes": {
            name: profile.prompt_hash for name, profile in PROMPT_PROFILES.items()
        },
        "pair_count": 18,
        "case_count": 36,
        "repetitions": 2,
        "planned_calls": 144,
        "candidate_code_executed": False,
        "assets": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in asset_paths
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.write_manifest:
        MANIFEST_PATH.write_text(rendered, encoding="utf-8")
    elif not MANIFEST_PATH.exists() or MANIFEST_PATH.read_text(encoding="utf-8") != rendered:
        raise SystemExit("PREPARATION_MANIFEST.json is missing or stale; run with --write-manifest")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
