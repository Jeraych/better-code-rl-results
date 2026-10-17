"""Validate the online string-concatenation metric on frozen labelled pairs."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codequal_metrics import analyze_string_concatenation  # noqa: E402


FIXTURES = [
    ("plain_value", True, "def f(xs):\n s = ''\n for x in xs:\n  s += x\n return s\n"),
    ("str_call", True, "def f(xs):\n s = ''\n for x in xs:\n  s += str(x)\n return s\n"),
    ("f_string", True, "def f(xs):\n s = ''\n for x in xs:\n  s += f'{x}'\n return s\n"),
    ("expanded_add", True, "def f(xs):\n s = ''\n for x in xs:\n  s = s + x\n return s\n"),
    ("while_loop", True, "def f(xs):\n s = ''\n i = 0\n while i < len(xs):\n  s += xs[i]\n  i += 1\n return s\n"),
    ("nested_loop", True, "def f(rows):\n s = ''\n for row in rows:\n  for x in row:\n   s += x\n return s\n"),
    ("numeric_sum", False, "def f(xs):\n total = 0\n for x in xs:\n  total += x\n return total\n"),
    ("float_sum", False, "def f(xs):\n total = 0.0\n for x in xs:\n  total += x\n return total\n"),
    ("list_append", False, "def f(xs):\n out = []\n for x in xs:\n  out.append(str(x))\n return ''.join(out)\n"),
    ("join_generator", False, "def f(xs):\n return ''.join(str(x) for x in xs)\n"),
    ("outside_loop", False, "def f(x):\n s = ''\n s += x\n return s\n"),
    ("bytes_growth", False, "def f(xs):\n out = b''\n for x in xs:\n  out += x\n return out\n"),
]


def safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> int:
    rows = []
    for fixture_id, expected, code in FIXTURES:
        result = analyze_string_concatenation(code)
        predicted = int(result["finding_count"]) > 0
        rows.append(
            {
                "fixture_id": fixture_id,
                "expected": expected,
                "predicted": predicted,
                "finding_count": result["finding_count"],
                "elapsed_ms": result["elapsed_ms"],
            }
        )

    tp = sum(row["expected"] and row["predicted"] for row in rows)
    tn = sum(not row["expected"] and not row["predicted"] for row in rows)
    fp = sum(not row["expected"] and row["predicted"] for row in rows)
    fn = sum(row["expected"] and not row["predicted"] for row in rows)
    summary = {
        "fixture_count": len(rows),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": safe_ratio(tp, tp + fp),
        "recall": safe_ratio(tp, tp + fn),
        "false_positive_rate": safe_ratio(fp, fp + tn),
        "mean_elapsed_ms": statistics.mean(row["elapsed_ms"] for row in rows),
        "max_elapsed_ms": max(row["elapsed_ms"] for row in rows),
        "rows": rows,
    }
    summary["online_gate_passed"] = (
        summary["precision"] >= 0.90
        and summary["recall"] >= 0.80
        and summary["false_positive_rate"] <= 0.10
        and summary["mean_elapsed_ms"] <= 5.0
    )

    output = Path(__file__).with_name("results") / "validation_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["online_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
