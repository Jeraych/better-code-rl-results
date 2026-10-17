"""Export and verify the committed frozen calibration dataset."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

from cases import PAIRS


ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "dataset" / "cases.jsonl"
MANIFEST_PATH = ROOT / "dataset" / "manifest.json"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_cases() -> list[dict[str, object]]:
    cases = []
    seen_pairs = set()
    for pair in PAIRS:
        if pair["pair_id"] in seen_pairs:
            raise ValueError(f"Duplicate pair: {pair['pair_id']}")
        seen_pairs.add(pair["pair_id"])
        ast.parse(pair["clean"])
        ast.parse(pair["degraded"])
        for condition in ("clean", "degraded"):
            expected = [] if condition == "clean" else [pair["subcategory"]]
            cases.append(
                {
                    "case_id": f"{pair['pair_id']}__{condition}",
                    "pair_id": pair["pair_id"],
                    "condition": condition,
                    "target_category": pair["category"],
                    "target_subcategory": pair["subcategory"],
                    "expected_subcategories": expected,
                    "task_prompt": pair["task_prompt"],
                    "candidate_code": pair[condition],
                    "reference_code": pair["clean"],
                    "seeded_evidence": pair["seeded_evidence"] if condition == "degraded" else "",
                    "candidate_code_executed": False,
                }
            )
    return cases


def render() -> tuple[str, str]:
    cases = build_cases()
    dataset_text = "".join(canonical_json(case) + "\n" for case in cases)
    dataset_sha256 = hashlib.sha256(dataset_text.encode("utf-8")).hexdigest()
    categories = Counter(case["target_subcategory"] for case in cases if case["condition"] == "degraded")
    manifest = {
        "dataset_version": "synthetic_pairs_v1",
        "dataset_sha256": dataset_sha256,
        "pair_count": len(cases) // 2,
        "case_count": len(cases),
        "clean_controls": sum(case["condition"] == "clean" for case in cases),
        "seeded_cases": sum(case["condition"] == "degraded" for case in cases),
        "seeded_cases_by_subcategory": dict(sorted(categories.items())),
        "candidate_code_executed": False,
        "label_scope": "controlled synthetic interventions; not human ground truth",
    }
    return dataset_text, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    dataset_text, manifest_text = render()
    if args.check:
        if not DATASET_PATH.exists() or DATASET_PATH.read_text(encoding="utf-8") != dataset_text:
            raise SystemExit("Committed cases.jsonl is not the deterministic export")
        if not MANIFEST_PATH.exists() or MANIFEST_PATH.read_text(encoding="utf-8") != manifest_text:
            raise SystemExit("Committed manifest.json is not the deterministic export")
        print("Calibration dataset is current and deterministic")
        return 0
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATASET_PATH.write_text(dataset_text, encoding="utf-8")
    MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    print(manifest_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
