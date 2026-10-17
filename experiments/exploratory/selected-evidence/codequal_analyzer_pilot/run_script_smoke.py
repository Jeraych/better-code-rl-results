"""Dry-run the AST-only adapter on existing Run 13 completions."""

from __future__ import annotations

import csv
import json
import random
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from codequal_adapter import analyze_candidate


ROOT = Path(__file__).resolve().parent
UNSLOTH_ROOT = ROOT.parents[1]
WORKSPACE_ROOT = UNSLOTH_ROOT.parent
ANALYZER_PYTHON = WORKSPACE_ROOT / "tmp" / "research_codequal_analyzer" / "python"
RUN13_CSV = UNSLOTH_ROOT / "results" / "13" / "samples.csv"


def entrypoint_from_prompt(prompt: str) -> str | None:
    matches = re.findall(r"\bdef\s+([A-Za-z_]\w*)\s*\(", prompt)
    return matches[0] if matches else None


def main() -> int:
    sys.path.insert(0, str(ANALYZER_PYTHON))
    with RUN13_CSV.open(encoding="utf-8-sig", newline="") as source:
        rows = [
            row
            for row in csv.DictReader(source)
            if row.get("test_status") == "passed"
            and row.get("extracted_code", "").strip()
        ]

    selected = random.Random(42).sample(rows, min(50, len(rows)))
    records = []
    rule_counts = Counter()
    for row in selected:
        entrypoint = entrypoint_from_prompt(row.get("prompt", ""))
        result = analyze_candidate(
            row["extracted_code"],
            entrypoint,
            mode="ast_only",
        )
        rule_counts.update(result["rule_ids"])
        records.append(
            {
                "task_id": row.get("task_id", ""),
                "entrypoint_found": entrypoint is not None,
                "status": result["status"],
                "elapsed_ms": result["elapsed_ms"],
                "rule_ids": result["rule_ids"],
            }
        )

    output = {
        "population": len(rows),
        "sample_size": len(records),
        "seed": 42,
        "mode": "ast_only",
        "successful": sum(record["status"] == "ok" for record in records),
        "entrypoints_extracted": sum(record["entrypoint_found"] for record in records),
        "samples_with_findings": sum(bool(record["rule_ids"]) for record in records),
        "mean_elapsed_ms": round(statistics.fmean(record["elapsed_ms"] for record in records), 3),
        "max_elapsed_ms": round(max(record["elapsed_ms"] for record in records), 3),
        "rule_presence_by_sample": dict(rule_counts.most_common()),
        "candidate_code_executed": False,
    }
    (ROOT / "results" / "script_adapter_smoke.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
