"""Summarize repeated CodeQual factorial runs and estimate interactions."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


ARM_FACTORS = {
    "cq-core": (0, 0, 0),
    "cq-pep8": (1, 0, 0),
    "cq-concat": (0, 1, 0),
    "cq-performance": (0, 0, 1),
    "cq-pep8-concat": (1, 1, 0),
    "cq-pep8-performance": (1, 0, 1),
    "cq-concat-performance": (0, 1, 1),
    "cq-all": (1, 1, 1),
}
FACTOR_NAMES = ("pep8_style", "string_concat", "performance")


def arm_name(folder_name: str) -> str | None:
    for arm in sorted(ARM_FACTORS, key=len, reverse=True):
        if folder_name == arm or folder_name.startswith(f"{arm}-run-"):
            return arm
    return None


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def floats(rows: list[dict[str, str]], key: str) -> list[float]:
    values = []
    for row in rows:
        try:
            values.append(float(row.get(key, "")))
        except (TypeError, ValueError):
            pass
    return values


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def rate(rows: list[dict[str, str]], key: str, expected: str) -> float | None:
    return (
        sum(row.get(key) == expected for row in rows) / len(rows)
        if rows
        else None
    )


def concat_prevalence(rows: list[dict[str, str]]) -> float | None:
    counts = floats(rows, "codequal_finding_count")
    return sum(value > 0 for value in counts) / len(counts) if counts else None


def metrics(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
    perf_rows = [row for row in rows if row.get("performance_status") == "ok"]
    return {
        "rows": len(rows),
        "pass_rate": rate(rows, "test_status", "passed"),
        "style_score": mean(floats(rows, "style_score")),
        "concat_prevalence": concat_prevalence(rows),
        "performance_score": mean(floats(perf_rows, "performance_score")),
        "completion_tokens": mean(floats(rows, "completion_token_length")),
        "reward_total": mean(floats(rows, "reward_total")),
    }


def subtract(after: dict, before: dict) -> dict[str, float | None]:
    result = {}
    for key in ("pass_rate", "style_score", "concat_prevalence", "performance_score", "completion_tokens"):
        left, right = after.get(key), before.get(key)
        result[key] = left - right if left is not None and right is not None else None
    return result


def training_runtime(job_dir: Path) -> float | None:
    state_path = job_dir / "trainer_state.json"
    if not state_path.exists():
        return None
    try:
        history = json.loads(state_path.read_text(encoding="utf-8"))["log_history"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    values = [item.get("train_runtime") for item in history if item.get("train_runtime") is not None]
    return float(values[-1]) if values else None


def cell_means(records: list[dict], metric_path: tuple[str, str]) -> dict[tuple[int, int, int], float]:
    grouped: dict[tuple[int, int, int], list[float]] = defaultdict(list)
    outer, inner = metric_path
    for record in records:
        value = record[outer].get(inner)
        if value is not None:
            grouped[tuple(record["factors"])].append(float(value))
    return {cell: statistics.mean(values) for cell, values in grouped.items()}


def factorial_effects(cells: dict[tuple[int, int, int], float]) -> dict[str, float] | None:
    if set(cells) != set(ARM_FACTORS.values()):
        return None

    effects: dict[str, float] = {}
    for index, name in enumerate(FACTOR_NAMES):
        on = statistics.mean(value for cell, value in cells.items() if cell[index] == 1)
        off = statistics.mean(value for cell, value in cells.items() if cell[index] == 0)
        effects[name] = on - off

    for left, right in ((0, 1), (0, 2), (1, 2)):
        differences = []
        remaining = ({0, 1, 2} - {left, right}).pop()
        for fixed in (0, 1):
            def value(a: int, b: int) -> float:
                cell = [0, 0, 0]
                cell[left], cell[right], cell[remaining] = a, b, fixed
                return cells[tuple(cell)]
            differences.append(value(1, 1) - value(1, 0) - value(0, 1) + value(0, 0))
        effects[f"{FACTOR_NAMES[left]}:{FACTOR_NAMES[right]}"] = statistics.mean(differences)
    return effects


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    records = []
    for job_dir in sorted(path for path in args.run_root.iterdir() if path.is_dir()):
        arm = arm_name(job_dir.name)
        if arm is None:
            continue
        base = metrics(read_rows(job_dir / "eval_base_holdout_tasks.csv"))
        lora = metrics(read_rows(job_dir / "eval_lora_holdout_tasks.csv"))
        samples = read_rows(job_dir / "samples.csv")
        records.append(
            {
                "job": job_dir.name,
                "arm": arm,
                "factors": ARM_FACTORS[arm],
                "base_holdout": base,
                "lora_holdout": lora,
                "delta": subtract(lora, base),
                "training_runtime_seconds": training_runtime(job_dir),
                "mean_codequal_elapsed_ms": mean(floats(samples, "codequal_elapsed_ms")),
            }
        )

    metric_paths = [
        ("lora_holdout", "pass_rate"),
        ("delta", "pass_rate"),
        ("delta", "style_score"),
        ("delta", "concat_prevalence"),
        ("delta", "performance_score"),
        ("delta", "completion_tokens"),
    ]
    effects = {}
    for path in metric_paths:
        estimate = factorial_effects(cell_means(records, path))
        if estimate is not None:
            effects[f"{path[0]}.{path[1]}"] = estimate

    summary = {
        "run_root": str(args.run_root.resolve()),
        "run_count": len(records),
        "complete_factorial": all(
            sum(record["arm"] == arm for record in records) >= 1 for arm in ARM_FACTORS
        ),
        "records": records,
        "factorial_effects": effects,
        "interpretation_warning": (
            "Effects are differences of cell means. Use seed-level uncertainty and "
            "holdout correctness gates before making causal or publication claims."
        ),
    }

    output = args.output or args.run_root / "codequal_factorial_summary.json"
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Runs found: {len(records)}; complete factorial: {summary['complete_factorial']}")
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
