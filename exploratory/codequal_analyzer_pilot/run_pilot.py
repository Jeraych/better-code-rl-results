"""Run a small, reproducible pilot of Maxime Robeyns' codequal_analyzer.

The pilot has two parts:
1. Paired synthetic programs with deliberately inserted static-quality defects.
2. A deterministic sample of existing Run 13 model generations.

No generated program is executed by this script.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_DIR = Path(__file__).resolve().parent
UNSLOTH_ROOT = EXPERIMENT_DIR.parents[1]
WORKSPACE_ROOT = UNSLOTH_ROOT.parent
DEFAULT_ANALYZER_PYTHON = WORKSPACE_ROOT / "tmp" / "research_codequal_analyzer" / "python"
DEFAULT_RUN13_CSV = UNSLOTH_ROOT / "results" / "13" / "samples.csv"


SYNTHETIC_PAIRS = [
    {
        "pair_id": "string_concatenation",
        "target": "performance",
        "clean": '''def solution(words):
    """Return all values converted to one string."""
    return "".join(str(word) for word in words)
''',
        "degraded": '''def solution(words):
    """Return all values converted to one string."""
    result = ""
    for word in words:
        result += str(word)
    return result
''',
    },
    {
        "pair_id": "file_open_in_loop",
        "target": "performance",
        "clean": '''def solution(path, lines):
    """Append each line to a file."""
    with open(path, "a", encoding="utf-8") as output:
        for line in lines:
            output.write(f"{line}\\n")
''',
        "degraded": '''def solution(path, lines):
    """Append each line to a file."""
    for line in lines:
        with open(path, "a", encoding="utf-8") as output:
            output.write(f"{line}\\n")
''',
    },
    {
        "pair_id": "broad_silent_exception",
        "target": "reliability",
        "clean": '''def solution(value):
    """Convert a value to an integer when possible."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
''',
        "degraded": '''def solution(value):
    """Convert a value to an integer when possible."""
    try:
        return int(value)
    except:
        pass
    return None
''',
    },
    {
        "pair_id": "branch_complexity",
        "target": "maintainability",
        "clean": '''LABELS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
    5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
}


def solution(number):
    """Return the English label for a digit."""
    return LABELS.get(number, "other")
''',
        "degraded": '''def solution(number):
    """Return the English label for a digit."""
    if number == 0:
        return "zero"
    if number == 1:
        return "one"
    if number == 2:
        return "two"
    if number == 3:
        return "three"
    if number == 4:
        return "four"
    if number == 5:
        return "five"
    if number == 6:
        return "six"
    if number == 7:
        return "seven"
    if number == 8:
        return "eight"
    if number == 9:
        return "nine"
    return "other"
''',
    },
    {
        "pair_id": "shell_injection",
        "target": "security",
        "clean": '''import subprocess


def solution(user_text):
    """Print text without invoking a command shell."""
    return subprocess.run(["echo", user_text], check=False).returncode
''',
        "degraded": '''import subprocess


def solution(user_text):
    """Print text by constructing a shell command."""
    command = "echo " + user_text
    return subprocess.run(command, shell=True, check=False).returncode
''',
    },
    {
        "pair_id": "unused_dead_code",
        "target": "maintainability",
        "clean": '''def solution(values):
    """Return doubled values."""
    return [value * 2 for value in values]
''',
        "degraded": '''def legacy_transform(value):
    """Old transformation retained after a refactor."""
    return value + 100


def solution(values):
    """Return doubled values."""
    return [value * 2 for value in values]
''',
    },
    {
        "pair_id": "nested_allocation",
        "target": "performance",
        "clean": '''def solution(values, factors):
    """Scale all values by every factor."""
    return [[value * factor for value in values] for factor in factors]
''',
        "degraded": '''def solution(values, factors):
    """Scale all values by every factor."""
    result = []
    for factor in factors:
        row = [value * factor for value in values]
        result += [row]
    return result
''',
    },
    {
        "pair_id": "blocking_call_in_loop",
        "target": "performance",
        "clean": '''import time


def solution(items, delay):
    """Wait for the requested total duration, then return the items."""
    time.sleep(delay * len(items))
    return list(items)
''',
        "degraded": '''import time


def solution(items, delay):
    """Wait once per item, then return the items."""
    result = []
    for item in items:
        time.sleep(delay)
        result.append(item)
    return result
''',
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyzer-python", type=Path, default=DEFAULT_ANALYZER_PYTHON)
    parser.add_argument("--run13-csv", type=Path, default=DEFAULT_RUN13_CSV)
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--synthetic-repetitions", type=int, default=3)
    return parser.parse_args()


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def population_sd(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.pstdev(values) if len(values) > 1 else None


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        rank = (position + end + 2) / 2.0
        for index in order[position : end + 1]:
            ranks[index] = rank
        position = end + 1
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else None


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(average_ranks(left), average_ranks(right))


def analyzer_commit(analyzer_python: Path) -> str | None:
    repository = analyzer_python.parent
    command = [
        "git",
        "-c",
        f"safe.directory={repository.as_posix()}",
        "-C",
        str(repository),
        "rev-parse",
        "HEAD",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def portable_path(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return str(path)


def analyze_code(
    code: str,
    filename: str = "solution.py",
    entrypoint: str | None = None,
) -> dict[str, Any]:
    from pycq_analyzer.api import measure_kchars, run_selected_analyzers
    from pycq_analyzer.main import calculate_scores

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="codequal_pilot_") as temp:
        directory = Path(temp)
        (directory / filename).write_text(code, encoding="utf-8")
        findings = run_selected_analyzers(
            directory,
            verbose=False,
            max_jobs=4,
            complexity_threshold="C",
            ignore_solution_unused=True,
        )
        kchars = measure_kchars(directory)
        scores = calculate_scores(findings, kchars=kchars)
    elapsed_ms = (time.perf_counter() - started) * 1000

    flat_findings = [finding for group in findings.values() for finding in group]
    entrypoint_filtered_findings = {
        characteristic: [
            finding
            for finding in items
            if not (
                entrypoint
                and finding.get("analyzer") == "vulture"
                and finding.get("rule_id") == "unused-function"
                and finding.get("raw_data", {}).get("name") == entrypoint
            )
        ]
        for characteristic, items in findings.items()
    }
    entrypoint_filtered_flat = [
        finding
        for group in entrypoint_filtered_findings.values()
        for finding in group
    ]
    entrypoint_filtered_scores = calculate_scores(
        entrypoint_filtered_findings,
        kchars=kchars,
    )
    return {
        "scores": scores,
        "entrypoint_filtered_scores": entrypoint_filtered_scores,
        "elapsed_ms": elapsed_ms,
        "finding_count": len(flat_findings),
        "entrypoint_filtered_finding_count": len(entrypoint_filtered_flat),
        "findings_by_characteristic": {
            characteristic: len(items) for characteristic, items in findings.items()
        },
        "findings_by_analyzer": dict(
            sorted(Counter(item.get("analyzer", "unknown") for item in flat_findings).items())
        ),
        "rule_ids": sorted({item.get("rule_id", "unknown") for item in flat_findings}),
    }


def analyzer_availability() -> dict[str, bool]:
    from pycq_analyzer.analyzers.bandit_analyzer import BanditAnalyzer
    from pycq_analyzer.analyzers.data_structure_analyzer import DataStructureComplexityAnalyzer
    from pycq_analyzer.analyzers.exception_handling_analyzer import ExceptionHandlingAnalyzer
    from pycq_analyzer.analyzers.pylint_analyzer import PylintAnalyzer
    from pycq_analyzer.analyzers.radon_analyzer import RadonAnalyzer
    from pycq_analyzer.analyzers.resource_consumption_analyzer import ResourceConsumptionAnalyzer
    from pycq_analyzer.analyzers.string_concat_analyzer import StringConcatenationAnalyzer
    from pycq_analyzer.analyzers.vulture_analyzer import VultureAnalyzer

    analyzers = [
        PylintAnalyzer,
        BanditAnalyzer,
        RadonAnalyzer,
        VultureAnalyzer,
        ExceptionHandlingAnalyzer,
        DataStructureComplexityAnalyzer,
        ResourceConsumptionAnalyzer,
        StringConcatenationAnalyzer,
    ]
    return {
        analyzer.__name__: analyzer(Path("."), verbose=False).is_available
        for analyzer in analyzers
    }


def run_synthetic(repetitions: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in SYNTHETIC_PAIRS:
        condition_results: dict[str, list[dict[str, Any]]] = {"clean": [], "degraded": []}
        for condition in condition_results:
            for _ in range(repetitions):
                condition_results[condition].append(analyze_code(pair[condition]))

        for condition, results in condition_results.items():
            score_keys = results[0]["scores"].keys()
            row: dict[str, Any] = {
                "pair_id": pair["pair_id"],
                "target": pair["target"],
                "condition": condition,
                "finding_count": results[0]["finding_count"],
                "mean_elapsed_ms": round(mean(item["elapsed_ms"] for item in results) or 0, 3),
                "score_deterministic": len(
                    {json.dumps(item["scores"], sort_keys=True) for item in results}
                )
                == 1,
                "rule_ids": "|".join(results[0]["rule_ids"]),
                "findings_by_analyzer": json.dumps(
                    results[0]["findings_by_analyzer"], sort_keys=True
                ),
            }
            for score_key in score_keys:
                row[score_key] = results[0]["scores"][score_key]
            rows.append(row)

    by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_pair.setdefault(row["pair_id"], {})[row["condition"]] = row

    deltas = {
        pair_id: round(values["clean"]["overall"] - values["degraded"]["overall"], 3)
        for pair_id, values in by_pair.items()
    }
    wins = sum(delta > 0 for delta in deltas.values())
    ties = sum(delta == 0 for delta in deltas.values())
    summary = {
        "pair_count": len(deltas),
        "directional_wins": wins,
        "ties": ties,
        "reversals": len(deltas) - wins - ties,
        "directional_accuracy": round(wins / len(deltas), 4),
        "mean_clean_minus_degraded_overall": round(statistics.fmean(deltas.values()), 3),
        "pair_deltas": deltas,
        "all_scores_deterministic": all(row["score_deterministic"] for row in rows),
    }
    return rows, summary


def run_padding_probe() -> dict[str, Any]:
    base = next(pair["degraded"] for pair in SYNTHETIC_PAIRS if pair["pair_id"] == "string_concatenation")
    padded = base + "\n" + "\n".join(f"# explanatory note {index:02d}" for index in range(80)) + "\n"
    base_result = analyze_code(base)
    padded_result = analyze_code(padded)
    return {
        "base": base_result,
        "padded": padded_result,
        "raw_overall_delta": round(
            padded_result["scores"]["overall"] - base_result["scores"]["overall"], 3
        ),
        "per_kchar_overall_delta": round(
            padded_result["scores"]["overall_per_kchar"]
            - base_result["scores"]["overall_per_kchar"],
            3,
        ),
    }


def eligible_run13_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    return [
        row
        for row in rows
        if row.get("test_status") == "passed"
        and row.get("ai_judge_status") == "ok"
        and row.get("extracted_code", "").strip()
    ]


def prompt_entrypoint(prompt: str) -> str | None:
    matches = re.findall(r"\bdef\s+([A-Za-z_]\w*)\s*\(", prompt)
    return matches[0] if matches else None


def run_real_sample(path: Path, sample_size: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = eligible_run13_rows(path)
    rng = random.Random(seed)
    selected = rng.sample(eligible, min(sample_size, len(eligible)))
    rows: list[dict[str, Any]] = []
    for source in selected:
        entrypoint = prompt_entrypoint(source["prompt"])
        result = analyze_code(source["extracted_code"], entrypoint=entrypoint)
        rows.append(
            {
                "run_id": source["run_id"],
                "step": int(source["step"]),
                "completion_index": int(source["completion_index"]),
                "task_id": source["task_id"],
                "entrypoint": entrypoint or "",
                "ai_judge_score": float(source["ai_judge_score"]),
                "style_score": float(source["style_score"]),
                "codequal_overall": result["scores"]["overall"],
                "codequal_overall_per_kchar": result["scores"]["overall_per_kchar"],
                "codequal_entrypoint_filtered_overall": result["entrypoint_filtered_scores"]["overall"],
                "codequal_entrypoint_filtered_overall_per_kchar": result[
                    "entrypoint_filtered_scores"
                ]["overall_per_kchar"],
                "codequal_maintainability": result["scores"]["maintainability"],
                "codequal_performance": result["scores"]["performance"],
                "codequal_reliability": result["scores"]["reliability"],
                "codequal_security": result["scores"]["security"],
                "finding_count": result["finding_count"],
                "entrypoint_filtered_finding_count": result[
                    "entrypoint_filtered_finding_count"
                ],
                "elapsed_ms": round(result["elapsed_ms"], 3),
                "rule_ids": "|".join(result["rule_ids"]),
                "findings_by_analyzer": json.dumps(
                    result["findings_by_analyzer"], sort_keys=True
                ),
            }
        )

    ai = [row["ai_judge_score"] for row in rows]
    style = [row["style_score"] for row in rows]
    raw = [row["codequal_overall"] for row in rows]
    normalized = [row["codequal_overall_per_kchar"] for row in rows]
    filtered = [row["codequal_entrypoint_filtered_overall"] for row in rows]
    filtered_normalized = [
        row["codequal_entrypoint_filtered_overall_per_kchar"] for row in rows
    ]
    summary = {
        "eligible_population": len(eligible),
        "sample_size": len(rows),
        "seed": seed,
        "overall_mean": round(mean(raw) or 0, 3),
        "overall_sd": round(population_sd(raw) or 0, 3),
        "overall_min": min(raw),
        "overall_max": max(raw),
        "overall_per_kchar_mean": round(mean(normalized) or 0, 3),
        "entrypoint_filtered_overall_mean": round(mean(filtered) or 0, 3),
        "entrypoint_filtered_overall_sd": round(population_sd(filtered) or 0, 3),
        "entrypoint_filtered_overall_min": min(filtered),
        "entrypoint_filtered_overall_max": max(filtered),
        "mean_findings": round(mean(row["finding_count"] for row in rows) or 0, 3),
        "mean_entrypoint_filtered_findings": round(
            mean(row["entrypoint_filtered_finding_count"] for row in rows) or 0,
            3,
        ),
        "mean_elapsed_ms": round(mean(row["elapsed_ms"] for row in rows) or 0, 3),
        "spearman_with_ai_judge": None if (value := spearman(raw, ai)) is None else round(value, 4),
        "spearman_normalized_with_ai_judge": None
        if (value := spearman(normalized, ai)) is None
        else round(value, 4),
        "spearman_entrypoint_filtered_with_ai_judge": None
        if (value := spearman(filtered, ai)) is None
        else round(value, 4),
        "spearman_entrypoint_filtered_normalized_with_ai_judge": None
        if (value := spearman(filtered_normalized, ai)) is None
        else round(value, 4),
        "spearman_with_style": None
        if (value := spearman(raw, style)) is None
        else round(value, 4),
        "pearson_with_ai_judge": None
        if (value := pearson(raw, ai)) is None
        else round(value, 4),
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    analyzer_python = args.analyzer_python.resolve()
    if not analyzer_python.exists():
        raise SystemExit(f"Analyzer Python directory not found: {analyzer_python}")
    sys.path.insert(0, str(analyzer_python))

    results_dir = EXPERIMENT_DIR / "results"
    synthetic_rows, synthetic_summary = run_synthetic(args.synthetic_repetitions)
    padding_summary = run_padding_probe()
    real_rows, real_summary = run_real_sample(args.run13_csv, args.sample_size, args.seed)

    write_csv(results_dir / "synthetic_pairs.csv", synthetic_rows)
    write_csv(results_dir / "run13_sample.csv", real_rows)

    summary = {
        "experiment": "codequal_analyzer_pilot",
        "python": sys.version,
        "analyzer_python": portable_path(analyzer_python),
        "analyzer_commit": analyzer_commit(analyzer_python),
        "quick_analyzer_availability": analyzer_availability(),
        "configuration": {
            "quick_analyzers": True,
            "max_jobs": 4,
            "complexity_threshold": "C",
            "ignore_solution_unused": True,
            "synthetic_repetitions": args.synthetic_repetitions,
        },
        "synthetic": synthetic_summary,
        "padding_probe": padding_summary,
        "run13": real_summary,
        "limitations": [
            "Synthetic pairs test sensitivity to deliberately seeded rules, not real-world validity.",
            "Run 13 comparison has no human ground truth; correlations show agreement, not correctness.",
            "The entrypoint-filtered result is a harness adaptation reported alongside the unchanged library score.",
            "Only the quick analyser subset is evaluated in this pilot.",
            "The local compatibility patch changes execution portability, not scoring rules.",
        ],
    }
    (results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
