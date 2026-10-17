"""Run the pre-specified final decision test for codequal_analyzer."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from codequal_adapter import analyze_candidate
from decision_fixtures import AST_ONLY_FAMILIES, FIXTURES


ROOT = Path(__file__).resolve().parent
UNSLOTH_ROOT = ROOT.parents[1]
WORKSPACE_ROOT = UNSLOTH_ROOT.parent
DEFAULT_ANALYZER_PYTHON = WORKSPACE_ROOT / "tmp" / "research_codequal_analyzer" / "python"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyzer-python", type=Path, default=DEFAULT_ANALYZER_PYTHON)
    parser.add_argument("--repetitions", type=int, default=2)
    return parser.parse_args()


def rule_detected(rule: str, rule_ids: list[str]) -> bool:
    if rule.endswith("-"):
        return any(item.startswith(rule) for item in rule_ids)
    return rule in rule_ids


def classification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(row["expected"] and row["detected"] for row in rows)
    tn = sum(not row["expected"] and not row["detected"] for row in rows)
    fp = sum(not row["expected"] and row["detected"] for row in rows)
    fn = sum(row["expected"] and not row["detected"] for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "false_positive_rate": round(1 - specificity, 4),
    }


def run_mode(mode: str, repetitions: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixtures = [
        fixture
        for fixture in FIXTURES
        if mode == "quick" or fixture["family"] in AST_ONLY_FAMILIES
    ]
    rows = []
    for fixture in fixtures:
        results = [
            analyze_candidate(fixture["code"], fixture["entrypoint"], mode=mode)
            for _ in range(repetitions)
        ]
        first = results[0]
        detected = rule_detected(fixture["rule"], first["rule_ids"])
        deterministic = all(result["rule_ids"] == first["rule_ids"] for result in results)
        rows.append(
            {
                "mode": mode,
                "fixture_id": fixture["id"],
                "family": fixture["family"],
                "target_rule": fixture["rule"],
                "expected": fixture["expected"],
                "detected": detected,
                "correct": detected == fixture["expected"],
                "deterministic": deterministic,
                "mean_elapsed_ms": round(
                    statistics.fmean(result["elapsed_ms"] for result in results), 3
                ),
                "detected_rule_ids": "|".join(first["rule_ids"]),
            }
        )

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)
    summary = classification(rows)
    summary.update(
        {
            "fixture_count": len(rows),
            "mean_elapsed_ms": round(statistics.fmean(row["mean_elapsed_ms"] for row in rows), 3),
            "all_deterministic": all(row["deterministic"] for row in rows),
            "by_family": {
                family: classification(family_rows)
                for family, family_rows in sorted(by_family.items())
            },
        }
    )
    return rows, summary


def robustness_checks() -> dict[str, Any]:
    base = next(item for item in FIXTURES if item["id"] == "concat_str_conversion_positive")
    padded_code = base["code"] + "\n" + "\n".join(
        f"# non-functional comment {index}" for index in range(80)
    )
    base_result = analyze_candidate(base["code"], base["entrypoint"], mode="quick")
    padded_result = analyze_candidate(padded_code, base["entrypoint"], mode="quick")

    renamed_code = '''def renamed_entrypoint(numbers):
    result = []
    current = None
    for number in numbers:
        current = number if current is None else max(current, number)
        result.append(current)
    return result
'''
    original = next(item for item in FIXTURES if item["id"] == "entrypoint_control")
    original_result = analyze_candidate(original["code"], original["entrypoint"], mode="quick")
    renamed_result = analyze_candidate(renamed_code, "renamed_entrypoint", mode="quick")

    invalid = analyze_candidate("def broken(:\n    pass\n", "broken", mode="quick")
    return {
        "padding_invariant": base_result["rule_ids"] == padded_result["rule_ids"],
        "padding_base_rules": base_result["rule_ids"],
        "padding_padded_rules": padded_result["rule_ids"],
        "entrypoint_rename_invariant": original_result["rule_ids"] == renamed_result["rule_ids"],
        "entrypoint_original_rules": original_result["rule_ids"],
        "entrypoint_renamed_rules": renamed_result["rule_ids"],
        "invalid_syntax_gated": invalid["status"] == "invalid_syntax" and not invalid["findings"],
        "invalid_syntax_status": invalid["status"],
        "candidate_code_executed": False,
    }


def decision(summary: dict[str, Any], robustness: dict[str, Any]) -> dict[str, Any]:
    robustness_pass = all(
        robustness[key]
        for key in [
            "padding_invariant",
            "entrypoint_rename_invariant",
            "invalid_syntax_gated",
        ]
    ) and not robustness["candidate_code_executed"]
    quick = summary["quick"]
    ast_only = summary["ast_only"]

    quick_go = (
        quick["precision"] >= 0.80
        and quick["recall"] >= 0.70
        and quick["false_positive_rate"] <= 0.20
        and quick["mean_elapsed_ms"] <= 2000
        and quick["all_deterministic"]
        and robustness_pass
    )
    ast_go = (
        ast_only["precision"] >= 0.80
        and ast_only["recall"] >= 0.80
        and ast_only["false_positive_rate"] <= 0.10
        and ast_only["mean_elapsed_ms"] <= 100
        and ast_only["all_deterministic"]
        and robustness_pass
    )
    passing_families = [
        family
        for family, metrics in quick["by_family"].items()
        if metrics["precision"] >= 0.80
        and metrics["recall"] >= 0.70
        and metrics["false_positive_rate"] <= 0.20
    ]
    return {
        "offline_research": "GO" if quick_go else ("LIMITED_GO" if passing_families else "NO_GO"),
        "online_train_script": "GO" if ast_go else "NO_GO",
        "passing_rule_families": passing_families,
        "robustness_pass": robustness_pass,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    analyzer_python = args.analyzer_python.resolve()
    if not analyzer_python.exists():
        raise SystemExit(f"Analyzer not found: {analyzer_python}")
    sys.path.insert(0, str(analyzer_python))

    quick_rows, quick_summary = run_mode("quick", args.repetitions)
    ast_rows, ast_summary = run_mode("ast_only", args.repetitions)
    robustness = robustness_checks()
    summaries = {"quick": quick_summary, "ast_only": ast_summary}
    final_decision = decision(summaries, robustness)
    output = {
        "protocol": "FINAL_TEST_PROTOCOL.md",
        "configuration": {"repetitions": args.repetitions},
        "summary": summaries,
        "robustness": robustness,
        "decision": final_decision,
    }

    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    write_csv(results_dir / "decision_test_fixtures.csv", quick_rows + ast_rows)
    (results_dir / "decision_test_summary.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
