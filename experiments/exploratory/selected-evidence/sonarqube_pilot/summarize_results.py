"""Create compact, research-ready tables from exported SonarQube API data."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_component(component: str) -> str:
    return component.split(":", 1)[1] if ":" in component else component


def issue_signature(issue: dict[str, Any]) -> tuple[object, ...]:
    return (
        issue["rule"],
        relative_component(issue["component"]),
        issue.get("line"),
        issue["message"],
    )


def classification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(row["expected"] and row["detected"] for row in rows)
    tn = sum(not row["expected"] and not row["detected"] for row in rows)
    fp = sum(not row["expected"] and row["detected"] for row in rows)
    fn = sum(row["expected"] and not row["detected"] for row in rows)
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "specificity": round(tn / (tn + fp), 4) if tn + fp else None,
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else None,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    manifest = load_json(ROOT / "dataset_manifest.json")
    extension_manifest = load_json(ROOT / "extension_manifest.json")
    mapping = load_json(ROOT / "rule_mapping.json")["families"]
    scan1 = load_json(RESULTS / "raw_issues_scan1.json")["issues"]
    scan2 = load_json(RESULTS / "raw_issues_scan2.json")["issues"]
    extension = load_json(RESULTS / "raw_issues_extension.json")["issues"]
    timings = load_json(RESULTS / "timings.json")

    scan1_by_path: dict[str, list[dict[str, Any]]] = {}
    for issue in scan1:
        scan1_by_path.setdefault(relative_component(issue["component"]), []).append(issue)

    fixture_rows = []
    applicable_rows = []
    for fixture in manifest["fixtures"]:
        family_mapping = mapping[fixture["family"]]
        rules = set(family_mapping["rule_keys"])
        found_rules = sorted(
            {issue["rule"] for issue in scan1_by_path.get(fixture["path"], [])}
        )
        detected = any(rule in rules for rule in found_rules)
        row = {
            "fixture_id": fixture["fixture_id"],
            "family": fixture["family"],
            "mapping_status": family_mapping["status"],
            "expected": fixture["expected"],
            "detected": detected,
            "correct": fixture["expected"] == detected,
            "sonar_rules": "|".join(found_rules),
        }
        fixture_rows.append(row)
        if rules:
            applicable_rows.append(row)

    extension_by_path: dict[str, list[dict[str, Any]]] = {}
    for issue in extension:
        extension_by_path.setdefault(relative_component(issue["component"]), []).append(issue)

    pairs: dict[str, dict[str, Any]] = {}
    for program in extension_manifest["pairs"]:
        pair = pairs.setdefault(
            program["pair_id"],
            {"pair_id": program["pair_id"], "target": program["target"]},
        )
        issues = extension_by_path.get(program["path"], [])
        pair[f"{program['condition']}_issues"] = len(issues)
        pair[f"{program['condition']}_rules"] = "|".join(
            sorted({issue["rule"] for issue in issues})
        )
    pair_rows = []
    for pair in pairs.values():
        clean = pair.get("clean_issues", 0)
        degraded = pair.get("degraded_issues", 0)
        pair["direction"] = (
            "correct" if degraded > clean else "reversed" if degraded < clean else "tie"
        )
        pair_rows.append(pair)

    train_path = extension_manifest["script"]["path"]
    train_rows = [
        {
            "rule": issue["rule"],
            "line": issue.get("line"),
            "message": issue["message"],
            "clean_code_attribute": issue.get("cleanCodeAttribute", ""),
            "impact_severity": issue.get("impactSeverity", ""),
        }
        for issue in extension_by_path.get(train_path, [])
    ]

    run13_rows = []
    for sample in manifest["run13"]:
        issues = scan1_by_path.get(sample["path"], [])
        run13_rows.append(
            {
                "task_id": sample["task_id"],
                "step": sample["step"],
                "completion_index": sample["completion_index"],
                "issue_count": len(issues),
                "rule_keys": "|".join(sorted({issue["rule"] for issue in issues})),
            }
        )

    relevant_keys = {
        rule
        for family in mapping.values()
        for rule in family["rule_keys"]
    } | {issue["rule"] for issue in extension}
    active_rules_path = RESULTS / "active_python_rules.json"
    if active_rules_path.exists():
        active_rules = load_json(active_rules_path)["rules"]
        relevant_rules = [
            {
                "key": rule["key"],
                "name": rule["name"],
                "type": rule.get("type"),
                "status": rule.get("status"),
            }
            for rule in active_rules
            if rule["key"] in relevant_keys
        ]
        (RESULTS / "relevant_rules.json").write_text(
            json.dumps(relevant_rules, indent=2), encoding="utf-8"
        )

    scan1_signatures = sorted(issue_signature(issue) for issue in scan1)
    scan2_signatures = sorted(issue_signature(issue) for issue in scan2)
    summary = {
        "environment": {
            "sonarqube_version": "26.7.0.124771",
            "docker_image_digest": "sha256:d4899d380ad9d7b63ebaa751e047f5a4f064f8902cdf7c1a3c3c96f7d71600ed",
            "scanner": "pysonar 1.3.0.4086",
            "quality_profile": "Sonar way",
            "active_python_rules": 362,
        },
        "frozen_dataset": {
            "fixture_count": len(fixture_rows),
            "run13_sample_count": len(run13_rows),
            "total_issues": len(scan1),
            "run13_issues": sum(row["issue_count"] for row in run13_rows),
            "mapped_fixture_metrics": classification(applicable_rows),
            "mapped_fixture_count": len(applicable_rows),
            "direct_or_partial_family_count": sum(
                bool(family["rule_keys"]) for family in mapping.values()
            ),
            "repeatable": scan1_signatures == scan2_signatures,
            "scan_1_signatures": [list(item) for item in scan1_signatures],
            "scan_2_signatures": [list(item) for item in scan2_signatures],
        },
        "exploratory_extension": {
            "pair_count": len(pair_rows),
            "directionally_correct_pairs": sum(
                row["direction"] == "correct" for row in pair_rows
            ),
            "tied_pairs": sum(row["direction"] == "tie" for row in pair_rows),
            "reversed_pairs": sum(row["direction"] == "reversed" for row in pair_rows),
            "train_py_sha256": extension_manifest["script"]["sha256"],
            "train_py_issue_count": len(train_rows),
            "train_py_rules": dict(Counter(row["rule"] for row in train_rows)),
            "total_issues": len(extension),
        },
        "timings": timings,
        "candidate_code_executed": False,
    }

    write_csv(RESULTS / "fixture_results.csv", fixture_rows)
    write_csv(RESULTS / "pair_results.csv", pair_rows)
    write_csv(RESULTS / "run13_results.csv", run13_rows)
    write_csv(RESULTS / "train_py_issues.csv", train_rows)
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
