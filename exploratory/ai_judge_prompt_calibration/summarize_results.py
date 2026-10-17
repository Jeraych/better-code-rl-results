"""Summarize a completed AI-judge calibration run without model calls."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from calibration_core import ALLOWED_SUBCATEGORIES


ALL_LABELS = sorted(
    subcategory
    for subcategories in ALLOWED_SUBCATEGORIES.values()
    for subcategory in subcategories
)


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return 0.0 if precision == 0 or recall == 0 else None
    return round(2 * precision * recall / (precision + recall), 4)


def mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * proportion)
    return round(ordered[index], 3)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prompt_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [record for record in records if record["status"] == "ok"]
    per_category: dict[str, dict[str, Any]] = {}
    total_tp = total_fp = total_fn = 0
    for label in ALL_LABELS:
        tp = fp = fn = 0
        for record in successful:
            expected = set(record["expected_subcategories"])
            predicted = set(record["predicted_subcategories"])
            tp += label in expected and label in predicted
            fp += label not in expected and label in predicted
            fn += label in expected and label not in predicted
        precision = ratio(tp, tp + fp)
        recall = ratio(tp, tp + fn)
        per_category[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1(precision, recall),
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    micro_precision = ratio(total_tp, total_tp + total_fp)
    micro_recall = ratio(total_tp, total_tp + total_fn)
    macro_values = [item["f1"] for item in per_category.values() if item["f1"] is not None]
    clean = [record for record in successful if record["condition"] == "clean"]
    degraded = [record for record in successful if record["condition"] == "degraded"]

    pair_groups: dict[tuple[int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in successful:
        pair_groups[(record["repetition"], record["pair_id"])][record["condition"]] = record
    pair_counts = {"correct": 0, "tie": 0, "reversed": 0, "incomplete": 0}
    for conditions in pair_groups.values():
        if set(conditions) != {"clean", "degraded"}:
            pair_counts["incomplete"] += 1
            continue
        clean_score = conditions["clean"]["score"]
        degraded_score = conditions["degraded"]["score"]
        direction = "correct" if clean_score > degraded_score else "reversed" if clean_score < degraded_score else "tie"
        pair_counts[direction] += 1

    repeat_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in successful:
        repeat_groups[record["case_id"]].append(record)
    exact_agreement = []
    jaccards = []
    score_differences = []
    for case_records in repeat_groups.values():
        if len(case_records) < 2:
            continue
        ordered = sorted(case_records, key=lambda item: item["repetition"])
        left = set(ordered[0]["predicted_subcategories"])
        right = set(ordered[1]["predicted_subcategories"])
        exact_agreement.append(left == right)
        union = left | right
        jaccards.append(len(left & right) / len(union) if union else 1.0)
        score_differences.append(abs(ordered[0]["score"] - ordered[1]["score"]))

    return {
        "planned_records": len(records),
        "successful_records": len(successful),
        "error_records": len(records) - len(successful),
        "success_rate": ratio(len(successful), len(records)),
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": f1(micro_precision, micro_recall),
        "macro_f1": mean(macro_values),
        "exact_label_set_accuracy": ratio(
            sum(set(record["expected_subcategories"]) == set(record["predicted_subcategories"]) for record in successful),
            len(successful),
        ),
        "target_detection_rate": ratio(
            sum(record["target_subcategory"] in record["predicted_subcategories"] for record in degraded),
            len(degraded),
        ),
        "clean_false_positive_rate": ratio(
            sum(bool(record["predicted_subcategories"]) for record in clean),
            len(clean),
        ),
        "pair_direction": {
            **pair_counts,
            "correct_rate": ratio(pair_counts["correct"], pair_counts["correct"] + pair_counts["tie"] + pair_counts["reversed"]),
        },
        "repeatability": {
            "paired_cases": len(exact_agreement),
            "exact_label_agreement": ratio(sum(exact_agreement), len(exact_agreement)),
            "mean_jaccard": mean(jaccards),
            "mean_absolute_score_difference": mean(score_differences),
        },
        "finding_retention_rate": ratio(
            sum(record.get("sanitized_finding_count", 0) for record in successful),
            sum(record.get("raw_finding_count", 0) for record in successful),
        ),
        "latency_ms": {
            "mean": mean([record["elapsed_ms"] for record in records]),
            "median": percentile([record["elapsed_ms"] for record in records], 0.5),
            "p95": percentile([record["elapsed_ms"] for record in records], 0.95),
        },
        "per_category": per_category,
    }


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    baseline = summary["profiles"].get("baseline_v3")
    candidate = summary["profiles"].get("calibrated_v4")
    if not summary["protocol_complete"] or baseline is None or candidate is None:
        return {"outcome": "NOT_APPLICABLE", "reason": "Run does not match the frozen full protocol"}
    gates = {
        "macro_f1_improvement_at_least_0_05": candidate["macro_f1"] is not None
        and baseline["macro_f1"] is not None
        and candidate["macro_f1"] - baseline["macro_f1"] >= 0.05,
        "clean_false_positive_not_worse_and_at_most_0_15": candidate["clean_false_positive_rate"] is not None
        and baseline["clean_false_positive_rate"] is not None
        and candidate["clean_false_positive_rate"] <= baseline["clean_false_positive_rate"]
        and candidate["clean_false_positive_rate"] <= 0.15,
        "pair_correct_rate_at_least_0_75": candidate["pair_direction"]["correct_rate"] is not None
        and candidate["pair_direction"]["correct_rate"] >= 0.75,
        "success_rate_at_least_0_98": candidate["success_rate"] is not None
        and candidate["success_rate"] >= 0.98,
        "repeat_exact_agreement_at_least_0_80": candidate["repeatability"]["exact_label_agreement"] is not None
        and candidate["repeatability"]["exact_label_agreement"] >= 0.80,
        "every_category_recall_at_least_0_50": all(
            item["recall"] is not None and item["recall"] >= 0.50
            for item in candidate["per_category"].values()
        ),
    }
    return {
        "outcome": "ADVANCE_TO_NATURAL_CODE_PILOT" if all(gates.values()) else "RETAIN_BASELINE_V3",
        "gates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    run_dir = args.run_directory.resolve()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    configuration = manifest["configuration"]
    expected_keys = configuration["planned_calls"]
    if manifest["state"] != "complete" or len(records) != expected_keys:
        raise SystemExit(
            f"Run is incomplete: state={manifest['state']} records={len(records)} expected={expected_keys}"
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["profile"]].append(record)
    summary: dict[str, Any] = {
        "run_type": "ai_judge_prompt_calibration",
        "protocol_complete": configuration["case_count"] == 36
        and configuration["repetitions"] == 2
        and set(configuration["profiles"]) == {"baseline_v3", "calibrated_v4"},
        "configuration": configuration,
        "profiles": {
            profile: prompt_metrics(profile_records)
            for profile, profile_records in sorted(grouped.items())
        },
        "candidate_code_executed": False,
        "label_scope": "controlled synthetic interventions; not human ground truth",
    }
    summary["decision"] = decision(summary)

    call_rows = []
    for record in records:
        call_rows.append(
            {
                "profile": record["profile"],
                "case_id": record["case_id"],
                "pair_id": record["pair_id"],
                "condition": record["condition"],
                "target_subcategory": record["target_subcategory"],
                "repetition": record["repetition"],
                "status": record["status"],
                "expected_subcategories": "|".join(record["expected_subcategories"]),
                "predicted_subcategories": "|".join(record.get("predicted_subcategories", [])),
                "score": record.get("score", ""),
                "raw_finding_count": record.get("raw_finding_count", ""),
                "sanitized_finding_count": record.get("sanitized_finding_count", ""),
                "attempts": record["attempts"],
                "elapsed_ms": record["elapsed_ms"],
                "error_type": record.get("error_type", ""),
            }
        )
    write_csv(run_dir / "per_call.csv", call_rows)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    profile_lines = []
    for profile, metrics in summary["profiles"].items():
        profile_lines.append(
            f"| {profile} | {metrics['success_rate']} | {metrics['macro_f1']} | "
            f"{metrics['micro_precision']} | {metrics['micro_recall']} | "
            f"{metrics['clean_false_positive_rate']} | "
            f"{metrics['pair_direction']['correct_rate']} | "
            f"{metrics['repeatability']['exact_label_agreement']} |"
        )
    results_md = f"""# AI-judge calibration result

## Decision

**{summary['decision']['outcome']}**

This is a controlled synthetic-intervention result, not human ground truth.

| Prompt | Success | Macro F1 | Micro precision | Micro recall | Clean FPR | Pair direction | Repeat agreement |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(profile_lines)}

## Frozen decision gates

```json
{json.dumps(summary['decision'], indent=2)}
```

See `summary.json`, `per_call.csv`, and `calls.jsonl` for compact metrics and
raw auditable evidence. Errors were excluded as missing observations rather
than converted into zero rewards.
"""
    (run_dir / "RESULTS.md").write_text(results_md, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
