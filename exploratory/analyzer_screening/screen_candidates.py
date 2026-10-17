"""Screen reward analyzers against saved completions before remote training.

The script deliberately avoids importing ``train.py`` because doing so loads the
training stack and model dependencies.  It re-runs the lightweight AST string
concatenation analyzer and uses the Ruff and dynamic-performance diagnostics
already recorded in training CSV artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codequal_metrics import analyze_string_concatenation  # noqa: E402


SCREEN_VERSION = "1.0"
DEFAULT_FIXTURE_SUMMARY = (
    REPO_ROOT
    / "experiments"
    / "codequal_training"
    / "results"
    / "validation_summary.json"
)
DEFAULT_THRESHOLDS = {
    "minimum_rows": 100,
    "minimum_availability_rate": 0.90,
    "minimum_activation_rate": 0.05,
    "maximum_activation_rate": 0.95,
    "minimum_nonzero_group_variance_rate": 0.10,
    "maximum_performance_ceiling_rate": 0.75,
    "minimum_performance_nonzero_group_variance_rate": 0.25,
}


def safe_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(paths: Iterable[Path]) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    rows: list[dict[str, str]] = []
    sources: list[dict[str, object]] = []
    for path in paths:
        resolved = path.resolve()
        with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
            source_rows = list(csv.DictReader(handle))
        source_id = (
            resolved.relative_to(REPO_ROOT).as_posix()
            if resolved.is_relative_to(REPO_ROOT)
            else resolved.as_posix()
        )
        for row_number, row in enumerate(source_rows, start=2):
            row["_source"] = source_id
            row["_row_number"] = str(row_number)
        rows.extend(source_rows)
        sources.append(
            {
                "path": source_id,
                "sha256": sha256_file(resolved),
                "row_count": len(source_rows),
            }
        )
    return rows, sources


def eligible_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("test_status", "").strip().lower() == "passed"]


def group_variation(
    rows: Iterable[dict[str, str]],
    value: Callable[[dict[str, str]], float | None],
) -> dict[str, object]:
    groups: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        measured = value(row)
        if measured is None:
            continue
        key = (
            row.get("_source", ""),
            row.get("run_id", ""),
            row.get("step", ""),
            row.get("task_id", ""),
        )
        groups[key].append(measured)

    comparable = [values for values in groups.values() if len(values) >= 2]
    varying = [values for values in comparable if max(values) - min(values) > 1e-12]
    return {
        "comparable_group_count": len(comparable),
        "nonzero_variance_group_count": len(varying),
        "nonzero_variance_group_rate": safe_ratio(len(varying), len(comparable)),
    }


def summarize_recorded_analyzer(
    rows: list[dict[str, str]],
    *,
    score_field: str,
    available: Callable[[dict[str, str]], bool],
    activated: Callable[[dict[str, str], float], bool],
) -> dict[str, object]:
    eligible = eligible_rows(rows)
    measured: list[tuple[dict[str, str], float]] = []
    for row in eligible:
        score = safe_float(row.get(score_field))
        if available(row) and score is not None:
            measured.append((row, score))

    scores = [score for _, score in measured]
    activated_count = sum(activated(row, score) for row, score in measured)
    variation = group_variation(
        [row for row, _ in measured], lambda row: safe_float(row.get(score_field))
    )
    return {
        "eligible_count": len(eligible),
        "available_count": len(measured),
        "availability_rate": safe_ratio(len(measured), len(eligible)),
        "activation_count": activated_count,
        "activation_rate": safe_ratio(activated_count, len(measured)),
        "mean_score": statistics.mean(scores) if scores else None,
        "ceiling_count": sum(score >= 0.999 for score in scores),
        "ceiling_rate": safe_ratio(sum(score >= 0.999 for score in scores), len(scores)),
        **variation,
    }


def summarize_string_concat(rows: list[dict[str, str]]) -> dict[str, object]:
    eligible = eligible_rows(rows)
    analyzed: list[tuple[dict[str, str], dict[str, object]]] = []
    for row in eligible:
        code = row.get("extracted_code", "")
        if not code.strip():
            continue
        analyzed.append((row, analyze_string_concatenation(code)))

    valid = [(row, result) for row, result in analyzed if result["status"] == "ok"]
    scores_by_row = {id(row): float(result["score"]) for row, result in valid}
    latencies = [float(result["elapsed_ms"]) for _, result in valid]
    activated_count = sum(int(result["finding_count"]) > 0 for _, result in valid)
    variation = group_variation(
        [row for row, _ in valid], lambda row: scores_by_row[id(row)]
    )
    return {
        "eligible_count": len(eligible),
        "available_count": len(valid),
        "availability_rate": safe_ratio(len(valid), len(eligible)),
        "activation_count": activated_count,
        "activation_rate": safe_ratio(activated_count, len(valid)),
        "mean_score": statistics.mean(scores_by_row.values()) if scores_by_row else None,
        "ceiling_count": len(valid) - activated_count,
        "ceiling_rate": safe_ratio(len(valid) - activated_count, len(valid)),
        "mean_elapsed_ms": statistics.mean(latencies) if latencies else None,
        "max_elapsed_ms": max(latencies) if latencies else None,
        "analysis_error_count": len(analyzed) - len(valid),
        **variation,
    }


def load_fixture_gate(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"available": False, "online_gate_passed": False, "path": path.as_posix()}
    result = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": (
            path.resolve().relative_to(REPO_ROOT).as_posix()
            if path.resolve().is_relative_to(REPO_ROOT)
            else path.resolve().as_posix()
        ),
        "fixture_count": result.get("fixture_count"),
        "precision": result.get("precision"),
        "recall": result.get("recall"),
        "false_positive_rate": result.get("false_positive_rate"),
        "mean_elapsed_ms": result.get("mean_elapsed_ms"),
        "online_gate_passed": bool(result.get("online_gate_passed", False)),
    }


def decide_candidates(
    analyzers: dict[str, dict[str, object]],
    fixture_gate: dict[str, object],
    thresholds: dict[str, float],
) -> dict[str, dict[str, object]]:
    style = analyzers["pep8_style"]
    style_criteria = {
        "minimum_rows": style["available_count"] >= thresholds["minimum_rows"],
        "availability": style["availability_rate"]
        >= thresholds["minimum_availability_rate"],
        "activation_range": thresholds["minimum_activation_rate"]
        <= style["activation_rate"]
        <= thresholds["maximum_activation_rate"],
        "group_variation": style["nonzero_variance_group_rate"]
        >= thresholds["minimum_nonzero_group_variance_rate"],
    }
    style_pass = all(style_criteria.values())

    concat = analyzers["string_concat"]
    concat_criteria = {
        "fixture_gate": fixture_gate.get("online_gate_passed") is True,
        "minimum_rows": concat["available_count"] >= thresholds["minimum_rows"],
        "availability": concat["availability_rate"]
        >= thresholds["minimum_availability_rate"],
        "activation": concat["activation_rate"]
        >= thresholds["minimum_activation_rate"],
        "group_variation": concat["nonzero_variance_group_rate"]
        >= thresholds["minimum_nonzero_group_variance_rate"],
    }
    concat_pass = all(concat_criteria.values())

    performance = analyzers["dynamic_performance"]
    performance_criteria = {
        "minimum_rows": performance["available_count"] >= thresholds["minimum_rows"],
        "ceiling": performance["ceiling_rate"]
        <= thresholds["maximum_performance_ceiling_rate"],
        "group_variation": performance["nonzero_variance_group_rate"]
        >= thresholds["minimum_performance_nonzero_group_variance_rate"],
    }
    performance_pass = all(performance_criteria.values())

    def failed(criteria: dict[str, bool]) -> str:
        return ", ".join(name for name, passed in criteria.items() if not passed)

    return {
        "pep8_style": {
            "decision": "promote" if style_pass else "hold",
            "remote_role": "online_reward" if style_pass else "offline_measure_only",
            "criteria": style_criteria,
            "reason": (
                "Recorded Ruff E,W outcomes have adequate coverage, activation, and within-group variation."
                if style_pass
                else f"Frozen screening criteria not met: {failed(style_criteria)}."
            ),
        },
        "string_concat": {
            "decision": "promote" if concat_pass else "hold",
            "remote_role": "online_reward" if concat_pass else "offline_measure_only",
            "criteria": concat_criteria,
            "reason": (
                "The fixture gate passed and saved completions provide adequate activation and variation."
                if concat_pass
                else f"Frozen screening criteria not met: {failed(concat_criteria)}."
            ),
        },
        "dynamic_performance": {
            "decision": "promote" if performance_pass else "redesign",
            "remote_role": "online_reward" if performance_pass else "offline_measure_only",
            "criteria": performance_criteria,
            "reason": (
                "Recorded performance scores avoid excessive ceiling saturation and vary within groups."
                if performance_pass
                else f"Frozen screening criteria not met: {failed(performance_criteria)}."
            ),
        },
    }


def format_percent(value: object) -> str:
    return "N/A" if value is None else f"{float(value):.1%}"


def format_number(value: object, digits: int = 3) -> str:
    return "N/A" if value is None else f"{float(value):.{digits}f}"


def render_markdown(result: dict[str, object]) -> str:
    analyzers = result["analyzers"]
    decisions = result["decisions"]
    lines = [
        "# Offline analyzer screening: first loop",
        "",
        "**Evidence status:** controlled offline screening of previously saved completions. This is a candidate-selection gate, not a training-effect result.",
        "",
        "## Inputs",
        "",
        "| Artifact | Rows | SHA-256 |",
        "|---|---:|---|",
    ]
    for source in result["sources"]:
        lines.append(f"| `{source['path']}` | {source['row_count']} | `{source['sha256']}` |")

    lines.extend(
        [
            "",
            "## Screening outcomes",
            "",
            "| Analyzer | Eligible | Available | Activation | Ceiling | Non-zero group variance | Mean latency | Decision | Remote role |",
            "|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for analyzer_id, label in (
        ("pep8_style", "Ruff E,W / PEP8-style"),
        ("string_concat", "AST string concatenation"),
        ("dynamic_performance", "Dynamic performance"),
    ):
        summary = analyzers[analyzer_id]
        decision = decisions[analyzer_id]
        lines.append(
            f"| {label} | {summary['eligible_count']} | "
            f"{format_percent(summary['availability_rate'])} | "
            f"{format_percent(summary['activation_rate'])} | "
            f"{format_percent(summary['ceiling_rate'])} | "
            f"{format_percent(summary['nonzero_variance_group_rate'])} | "
            f"{format_number(summary.get('mean_elapsed_ms'))} ms | "
            f"**{decision['decision']}** | {decision['remote_role']} |"
        )

    fixture = result["string_concat_fixture_gate"]
    lines.extend(
        [
            "",
            "## Decision record",
            "",
            f"- StringConcat fixture gate: **{'pass' if fixture['online_gate_passed'] else 'fail'}** on {fixture.get('fixture_count', 'N/A')} handcrafted cases; precision {format_number(fixture.get('precision'))}, recall {format_number(fixture.get('recall'))}, false-positive rate {format_percent(fixture.get('false_positive_rate'))}. This establishes implementation feasibility only.",
        ]
    )
    for analyzer_id in ("pep8_style", "string_concat", "dynamic_performance"):
        decision = decisions[analyzer_id]
        lines.append(f"- `{analyzer_id}`: **{decision['decision']}** — {decision['reason']}")

    lines.extend(
        [
            "",
            "## Source-level diagnostic",
            "",
            "| Source | Ruff activation | Ruff group variation | StringConcat activation | Performance ceiling | Performance group variation |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for source in result["source_diagnostics"]:
        source_analyzers = source["analyzers"]
        lines.append(
            f"| `{source['path']}` | "
            f"{format_percent(source_analyzers['pep8_style']['activation_rate'])} | "
            f"{format_percent(source_analyzers['pep8_style']['nonzero_variance_group_rate'])} | "
            f"{format_percent(source_analyzers['string_concat']['activation_rate'])} | "
            f"{format_percent(source_analyzers['dynamic_performance']['ceiling_rate'])} | "
            f"{format_percent(source_analyzers['dynamic_performance']['nonzero_variance_group_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## Frozen interpretation",
            "",
            "Only analyzers marked `promote` should enter the next remote-training plan unchanged. `Hold` means collect broader or more activating data before promotion. `Redesign` means the present reward formulation should not consume confirmatory remote compute.",
            "",
            "The screen uses stored Ruff and performance columns, because importing the training module would load model dependencies. StringConcat is re-executed directly against each test-passing saved completion. Analyzer effects on trained models are not measured in this loop.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, type=Path, help="Saved samples CSV; repeat for multiple inputs")
    parser.add_argument("--fixture-summary", type=Path, default=DEFAULT_FIXTURE_SUMMARY)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, sources = read_rows(args.input)
    analyzers = {
        "pep8_style": summarize_recorded_analyzer(
            rows,
            score_field="style_score",
            available=lambda row: row.get("style_status") in {"ok", "violations"},
            activated=lambda row, score: (safe_float(row.get("style_violation_count")) or 0.0) > 0.0,
        ),
        "string_concat": summarize_string_concat(rows),
        "dynamic_performance": summarize_recorded_analyzer(
            rows,
            score_field="performance_score",
            available=lambda row: row.get("performance_status") == "ok",
            activated=lambda row, score: score < 0.999,
        ),
    }
    fixture_gate = load_fixture_gate(args.fixture_summary)
    source_diagnostics = []
    for source in sources:
        source_rows = [row for row in rows if row["_source"] == source["path"]]
        source_diagnostics.append(
            {
                "path": source["path"],
                "analyzers": {
                    "pep8_style": summarize_recorded_analyzer(
                        source_rows,
                        score_field="style_score",
                        available=lambda row: row.get("style_status")
                        in {"ok", "violations"},
                        activated=lambda row, score: (
                            safe_float(row.get("style_violation_count")) or 0.0
                        )
                        > 0.0,
                    ),
                    "string_concat": summarize_string_concat(source_rows),
                    "dynamic_performance": summarize_recorded_analyzer(
                        source_rows,
                        score_field="performance_score",
                        available=lambda row: row.get("performance_status") == "ok",
                        activated=lambda row, score: score < 0.999,
                    ),
                },
            }
        )
    result = {
        "screen_version": SCREEN_VERSION,
        "evidence_status": "controlled_offline_screening",
        "sources": sources,
        "thresholds": DEFAULT_THRESHOLDS,
        "string_concat_fixture_gate": fixture_gate,
        "analyzers": analyzers,
        "source_diagnostics": source_diagnostics,
        "decisions": decide_candidates(analyzers, fixture_gate, DEFAULT_THRESHOLDS),
        "limitations": [
            "Saved completions were generated by prior runs and do not estimate a new training effect.",
            "The StringConcat fixture set is small and handcrafted, not independently labelled.",
            "Stored Ruff results are used because Ruff is not re-executed by this dependency-light script.",
            "Performance measurements inherit the hardware and benchmark policy of their source runs.",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "first_loop_summary.json"
    markdown_path = args.output_dir / "FIRST_LOOP_RESULTS.md"
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["decisions"], indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
