"""Run the frozen loop-2 analyzer screen on fixtures and saved completions."""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.metadata
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from radon.complexity import cc_visit
from vulture import Vulture


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from experiments.analyzer_screening.loop2_fixtures import FIXTURES  # noqa: E402
from experiments.analyzer_screening.screen_candidates import (  # noqa: E402
    group_variation,
    safe_ratio,
    sha256_file,
)


ANALYZERS = (
    "radon_complexity",
    "vulture_dead_code",
    "pylint_exceptions",
    "pylint_structure",
    "bandit_security",
    "mypy_type_safety",
)
IN_PROCESS_ANALYZERS = {"radon_complexity", "vulture_dead_code"}
THRESHOLDS = {
    "fixture_precision": 0.80,
    "fixture_recall": 0.70,
    "fixture_false_positive_rate": 0.20,
    "availability_rate": 0.90,
    "minimum_activation_rate": 0.05,
    "maximum_activation_rate": 0.95,
    "nonzero_group_variance_rate": 0.10,
    "online_mean_elapsed_ms": 5.0,
}


def blank_result() -> dict[str, object]:
    return {"status": "ok", "finding_count": 0, "codes": [], "elapsed_ms": 0.0}


def infer_entrypoint(code: str, prompt: str = "") -> str:
    prompt_functions = re.findall(r"(?m)^\s*def\s+([A-Za-z_]\w*)\s*\(", prompt)
    if prompt_functions:
        return prompt_functions[-1]
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return ""


def run_radon(items: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    outputs = {}
    for item in items:
        started = time.perf_counter_ns()
        try:
            blocks = cc_visit(item["code"])
            findings = [block for block in blocks if int(block.complexity) > 10]
            outputs[item["id"]] = {
                "status": "ok",
                "finding_count": len(findings),
                "codes": [f"CC:{block.name}:{block.complexity}" for block in findings],
                "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000,
            }
        except Exception as exc:  # analyzer failures must remain data
            outputs[item["id"]] = {
                "status": "error",
                "finding_count": 0,
                "codes": [],
                "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000,
                "error": str(exc),
            }
    return outputs


def run_vulture(items: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    outputs = {}
    for item in items:
        started = time.perf_counter_ns()
        try:
            analyzer = Vulture(verbose=False)
            analyzer.scan(item["code"], filename=f"{item['id']}.py")
            entrypoint = item.get("entrypoint", "")
            unused = [
                finding
                for finding in analyzer.get_unused_code(min_confidence=60)
                if not (finding.typ == "function" and finding.name == entrypoint)
            ]
            outputs[item["id"]] = {
                "status": "ok",
                "finding_count": len(unused),
                "codes": [f"{finding.typ}:{finding.name}" for finding in unused],
                "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000,
            }
        except Exception as exc:
            outputs[item["id"]] = {
                "status": "error",
                "finding_count": 0,
                "codes": [],
                "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000,
                "error": str(exc),
            }
    return outputs


def materialize(items: list[dict[str, str]], directory: Path) -> dict[str, str]:
    mapping = {}
    for index, item in enumerate(items):
        stem = f"case_{index:05d}"
        path = directory / f"{stem}.py"
        path.write_text(item["code"], encoding="utf-8")
        mapping[stem] = item["id"]
    return mapping


def initialize_batch(items: list[dict[str, str]], elapsed_ms: float) -> dict[str, dict[str, object]]:
    per_item = elapsed_ms / len(items) if items else 0.0
    return {
        item["id"]: {
            "status": "ok",
            "finding_count": 0,
            "codes": [],
            "elapsed_ms": per_item,
        }
        for item in items
    }


def mark_batch_error(items: list[dict[str, str]], elapsed_ms: float, error: str) -> dict[str, dict[str, object]]:
    results = initialize_batch(items, elapsed_ms)
    for result in results.values():
        result["status"] = "error"
        result["error"] = error[:1000]
    return results


def run_pylint(items: list[dict[str, str]], python: Path) -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="analyzer_pylint_") as tmp:
        directory = Path(tmp)
        mapping = materialize(items, directory)
        command = [
            str(python),
            "-m",
            "pylint",
            str(directory),
            "--disable=all",
            "--enable=bare-except,broad-exception-caught,too-many-branches,too-many-statements,too-many-locals",
            "--output-format=json",
            "--reports=n",
            "--score=n",
            "--persistent=n",
            "--jobs=1",
        ]
        started = time.perf_counter_ns()
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        try:
            messages = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            return mark_batch_error(items, elapsed_ms, completed.stderr or completed.stdout)

        by_analyzer = {
            "pylint_exceptions": initialize_batch(items, elapsed_ms),
            "pylint_structure": initialize_batch(items, elapsed_ms),
        }
        exception_symbols = {"bare-except", "broad-exception-caught"}
        structure_symbols = {"too-many-branches", "too-many-statements", "too-many-locals"}
        for message in messages:
            stem = Path(message.get("path", "")).stem
            item_id = mapping.get(stem)
            symbol = message.get("symbol", "")
            analyzer_id = (
                "pylint_exceptions"
                if symbol in exception_symbols
                else "pylint_structure" if symbol in structure_symbols else None
            )
            if item_id and analyzer_id:
                result = by_analyzer[analyzer_id][item_id]
                result["finding_count"] = int(result["finding_count"]) + 1
                result["codes"].append(symbol)
        return by_analyzer


def run_bandit(items: list[dict[str, str]], python: Path) -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="analyzer_bandit_") as tmp:
        directory = Path(tmp)
        mapping = materialize(items, directory)
        command = [str(python), "-m", "bandit", "-r", str(directory), "-f", "json", "-q"]
        started = time.perf_counter_ns()
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            return mark_batch_error(items, elapsed_ms, completed.stderr or completed.stdout)
        outputs = initialize_batch(items, elapsed_ms)
        for finding in payload.get("results", []):
            item_id = mapping.get(Path(finding.get("filename", "")).stem)
            if item_id:
                outputs[item_id]["finding_count"] = int(outputs[item_id]["finding_count"]) + 1
                outputs[item_id]["codes"].append(finding.get("test_id", "unknown"))
        return outputs


MYPY_PATTERN = re.compile(r"^(.*?):(\d+): error: .*?\s+\[([^\]]+)\]$")


def run_mypy(items: list[dict[str, str]], python: Path) -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="analyzer_mypy_") as tmp:
        directory = Path(tmp)
        mapping = materialize(items, directory)
        command = [
            str(python),
            "-m",
            "mypy",
            str(directory),
            "--check-untyped-defs",
            "--ignore-missing-imports",
            "--follow-imports=skip",
            "--no-incremental",
            "--no-error-summary",
            "--no-pretty",
            "--show-error-codes",
        ]
        started = time.perf_counter_ns()
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        outputs = initialize_batch(items, elapsed_ms)
        unexpected = []
        for line in completed.stdout.splitlines():
            stripped = line.strip()
            if not stripped or ": note:" in stripped:
                continue
            match = MYPY_PATTERN.match(stripped)
            if not match:
                unexpected.append(line)
                continue
            item_id = mapping.get(Path(match.group(1)).stem)
            if item_id:
                outputs[item_id]["finding_count"] = int(outputs[item_id]["finding_count"]) + 1
                outputs[item_id]["codes"].append(match.group(3))
        if completed.returncode not in {0, 1} or unexpected:
            error = "\n".join(unexpected) or completed.stderr
            return mark_batch_error(items, elapsed_ms, error)
        return outputs


def run_all(items: list[dict[str, str]], python: Path) -> dict[str, dict[str, dict[str, object]]]:
    pylint = run_pylint(items, python)
    return {
        "radon_complexity": run_radon(items),
        "vulture_dead_code": run_vulture(items),
        "pylint_exceptions": pylint["pylint_exceptions"],
        "pylint_structure": pylint["pylint_structure"],
        "bandit_security": run_bandit(items, python),
        "mypy_type_safety": run_mypy(items, python),
    }


def confusion(
    items: list[dict[str, object]],
    outputs: dict[str, dict[str, object]],
    repeated_outputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    rows = []
    for item in items:
        result = outputs[item["id"]]
        predicted = result["status"] == "ok" and int(result["finding_count"]) > 0
        rows.append({"id": item["id"], "expected": item["expected"], "predicted": predicted, **result})
    valid = [row for row in rows if row["status"] == "ok"]
    tp = sum(bool(row["expected"]) and bool(row["predicted"]) for row in valid)
    tn = sum(not bool(row["expected"]) and not bool(row["predicted"]) for row in valid)
    fp = sum(not bool(row["expected"]) and bool(row["predicted"]) for row in valid)
    fn = sum(bool(row["expected"]) and not bool(row["predicted"]) for row in valid)
    return {
        "fixture_count": len(rows),
        "available_count": len(valid),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": safe_ratio(tp, tp + fp),
        "recall": safe_ratio(tp, tp + fn),
        "false_positive_rate": safe_ratio(fp, fp + tn),
        "deterministic": all(
            outputs[item["id"]]["status"] == repeated_outputs[item["id"]]["status"]
            and outputs[item["id"]]["finding_count"]
            == repeated_outputs[item["id"]]["finding_count"]
            and outputs[item["id"]]["codes"] == repeated_outputs[item["id"]]["codes"]
            for item in items
        ),
        "rows": rows,
    }


def summarize_saved(items: list[dict[str, str]], outputs: dict[str, dict[str, object]]) -> dict[str, object]:
    valid_items = [item for item in items if outputs[item["id"]]["status"] == "ok"]
    counts = [int(outputs[item["id"]]["finding_count"]) for item in valid_items]
    scores = {item["id"]: 1.0 / (1.0 + int(outputs[item["id"]]["finding_count"])) for item in valid_items}
    variation_rows = [
        {
            "_source": item["source"],
            "run_id": item["run_id"],
            "step": item["step"],
            "task_id": item["task_id"],
            "score": str(scores[item["id"]]),
        }
        for item in valid_items
    ]
    variation = group_variation(variation_rows, lambda row: float(row["score"]))
    latencies = [float(outputs[item["id"]]["elapsed_ms"]) for item in valid_items]
    code_counts = Counter(code for item in valid_items for code in outputs[item["id"]]["codes"])
    activated = sum(count > 0 for count in counts)
    return {
        "eligible_count": len(items),
        "available_count": len(valid_items),
        "availability_rate": safe_ratio(len(valid_items), len(items)),
        "activation_count": activated,
        "activation_rate": safe_ratio(activated, len(valid_items)),
        "mean_finding_count": statistics.mean(counts) if counts else None,
        "ceiling_rate": safe_ratio(len(valid_items) - activated, len(valid_items)),
        "mean_elapsed_ms": statistics.mean(latencies) if latencies else None,
        "top_codes": dict(code_counts.most_common(10)),
        "error_count": len(items) - len(valid_items),
        **variation,
    }


def decide(analyzer_id: str, fixture: dict[str, object], saved: dict[str, object]) -> dict[str, object]:
    criteria = {
        "fixture_precision": fixture["precision"] >= THRESHOLDS["fixture_precision"],
        "fixture_recall": fixture["recall"] >= THRESHOLDS["fixture_recall"],
        "fixture_false_positive_rate": fixture["false_positive_rate"] <= THRESHOLDS["fixture_false_positive_rate"],
        "deterministic": fixture["deterministic"] is True,
        "availability": saved["availability_rate"] >= THRESHOLDS["availability_rate"],
        "activation": THRESHOLDS["minimum_activation_rate"] <= saved["activation_rate"] <= THRESHOLDS["maximum_activation_rate"],
        "group_variation": saved["nonzero_variance_group_rate"] >= THRESHOLDS["nonzero_group_variance_rate"],
        "online_latency": saved["mean_elapsed_ms"] is not None
        and saved["mean_elapsed_ms"] <= THRESHOLDS["online_mean_elapsed_ms"],
        "in_process": analyzer_id in IN_PROCESS_ANALYZERS,
    }
    validity = all(
        criteria[key]
        for key in (
            "fixture_precision",
            "fixture_recall",
            "fixture_false_positive_rate",
            "deterministic",
            "availability",
        )
    )
    useful_signal = criteria["activation"] and criteria["group_variation"]
    online = validity and useful_signal and criteria["online_latency"] and criteria["in_process"]
    if online:
        decision = "conditional_online_candidate"
        role = "small_remote_ablation"
    elif validity and saved["activation_count"] > 0:
        decision = "offline_evaluator_only"
        role = "offline_outcome_measure"
    elif validity:
        decision = "reject_current_dataset"
        role = "targeted_dataset_only"
    else:
        decision = "reject_current_configuration"
        role = "none_until_revalidated"
    failed = [name for name, passed in criteria.items() if not passed]
    return {"decision": decision, "role": role, "criteria": criteria, "failed_criteria": failed}


def load_saved(path: Path) -> tuple[list[dict[str, str]], dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    items = []
    for index, row in enumerate(rows):
        if row.get("test_status") != "passed" or not row.get("extracted_code", "").strip():
            continue
        code = row["extracted_code"]
        items.append(
            {
                "id": f"saved_{index:05d}",
                "code": code,
                "entrypoint": infer_entrypoint(code, row.get("prompt", "")),
                "source": path.as_posix(),
                "run_id": row.get("run_id", ""),
                "step": row.get("step", ""),
                "task_id": row.get("task_id", ""),
            }
        )
    return items, {"path": path.as_posix(), "sha256": sha256_file(path), "row_count": len(rows), "eligible_count": len(items)}


def tool_versions() -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in ("radon", "vulture", "pylint", "bandit", "mypy", "ruff")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_items = [{**fixture} for fixture in FIXTURES]
    saved_items, source = load_saved(args.input)
    fixture_outputs = run_all(fixture_items, args.python)
    repeated_fixture_outputs = run_all(fixture_items, args.python)
    saved_outputs = run_all(saved_items, args.python)
    fixture_summaries = {}
    saved_summaries = {}
    decisions = {}
    for analyzer_id in ANALYZERS:
        relevant = [fixture for fixture in fixture_items if fixture["analyzer"] == analyzer_id]
        fixture_summaries[analyzer_id] = confusion(
            relevant,
            fixture_outputs[analyzer_id],
            repeated_fixture_outputs[analyzer_id],
        )
        saved_summaries[analyzer_id] = summarize_saved(saved_items, saved_outputs[analyzer_id])
        decisions[analyzer_id] = decide(analyzer_id, fixture_summaries[analyzer_id], saved_summaries[analyzer_id])

    result = {
        "screen_version": "2.0",
        "evidence_status": "controlled_offline_screening",
        "source": source,
        "tool_versions": tool_versions(),
        "thresholds": THRESHOLDS,
        "fixtures_are_independent_labels": False,
        "fixture_summaries": fixture_summaries,
        "saved_output_summaries": saved_summaries,
        "decisions": decisions,
        "limitations": [
            "Fixtures are small, purpose-built development cases rather than independent external labels.",
            "Saved outputs come from Run 15 and do not estimate analyzer-caused training effects.",
            "Pylint, Bandit, and Mypy latency is amortized over a batch and is not per-call online latency.",
            "The first top-level generated function is treated as the HumanEval entry point for Vulture filtering.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "loop2_summary.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decisions, indent=2))
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
