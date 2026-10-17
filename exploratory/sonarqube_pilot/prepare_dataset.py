"""Materialize the frozen SonarQube pilot dataset without executing candidates."""

from __future__ import annotations

import csv
import json
import random
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
UNSLOTH_ROOT = ROOT.parents[1]
CODEQUAL_DIR = ROOT.parent / "codequal_analyzer_pilot"
RUN13_CSV = UNSLOTH_ROOT / "results" / "13" / "samples.csv"
DATASET_DIR = ROOT / "dataset"
SAMPLE_SIZE = 50
SEED = 42


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def eligible_run13_rows() -> list[dict[str, str]]:
    with RUN13_CSV.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    return [
        row
        for row in rows
        if row.get("test_status") == "passed"
        and row.get("ai_judge_status") == "ok"
        and row.get("extracted_code", "").strip()
    ]


def main() -> int:
    sys.path.insert(0, str(CODEQUAL_DIR))
    from decision_fixtures import FIXTURES  # pylint: disable=import-error

    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    fixtures_dir = DATASET_DIR / "fixtures"
    run13_dir = DATASET_DIR / "run13"
    fixtures_dir.mkdir(parents=True)
    run13_dir.mkdir(parents=True)

    manifest: dict[str, object] = {
        "configuration": {"sample_size": SAMPLE_SIZE, "seed": SEED},
        "fixtures": [],
        "run13": [],
    }
    fixture_rows = manifest["fixtures"]
    assert isinstance(fixture_rows, list)
    for fixture in FIXTURES:
        relative = Path("dataset") / "fixtures" / f"{fixture['id']}.py"
        (ROOT / relative).write_text(fixture["code"], encoding="utf-8")
        fixture_rows.append(
            {
                "path": relative.as_posix(),
                "fixture_id": fixture["id"],
                "family": fixture["family"],
                "codequal_rule": fixture["rule"],
                "expected": fixture["expected"],
                "entrypoint": fixture["entrypoint"],
            }
        )

    eligible = eligible_run13_rows()
    selected = random.Random(SEED).sample(eligible, min(SAMPLE_SIZE, len(eligible)))
    run13_rows = manifest["run13"]
    assert isinstance(run13_rows, list)
    for index, row in enumerate(selected):
        filename = (
            f"{index:02d}_{safe_name(row['task_id'])}_{row['step']}_"
            f"{row['completion_index']}.py"
        )
        relative = Path("dataset") / "run13" / filename
        (ROOT / relative).write_text(row["extracted_code"], encoding="utf-8")
        run13_rows.append(
            {
                "path": relative.as_posix(),
                "run_id": row["run_id"],
                "step": int(row["step"]),
                "completion_index": int(row["completion_index"]),
                "task_id": row["task_id"],
                "ai_judge_score": float(row["ai_judge_score"]),
                "style_score": float(row["style_score"]),
            }
        )

    (ROOT / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "fixture_count": len(fixture_rows),
                "eligible_run13_population": len(eligible),
                "run13_sample_count": len(run13_rows),
                "seed": SEED,
                "candidate_code_executed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
