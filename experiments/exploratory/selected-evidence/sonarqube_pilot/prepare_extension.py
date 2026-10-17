"""Prepare a separate exploratory SonarQube dataset without executing code."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
UNSLOTH_ROOT = ROOT.parents[1]
CODEQUAL_DIR = ROOT.parent / "codequal_analyzer_pilot"
EXTENSION_DIR = ROOT / "extension"


def main() -> int:
    sys.path.insert(0, str(CODEQUAL_DIR))
    from run_pilot import SYNTHETIC_PAIRS  # pylint: disable=import-error

    if EXTENSION_DIR.exists():
        shutil.rmtree(EXTENSION_DIR)
    pairs_dir = EXTENSION_DIR / "pairs"
    script_dir = EXTENSION_DIR / "script_under_test"
    pairs_dir.mkdir(parents=True)
    script_dir.mkdir(parents=True)

    manifest: dict[str, object] = {"pairs": [], "script": {}}
    pair_rows = manifest["pairs"]
    assert isinstance(pair_rows, list)
    for pair in SYNTHETIC_PAIRS:
        for condition in ("clean", "degraded"):
            relative = Path("extension") / "pairs" / f"{pair['pair_id']}__{condition}.py"
            (ROOT / relative).write_text(pair[condition], encoding="utf-8")
            pair_rows.append(
                {
                    "path": relative.as_posix(),
                    "pair_id": pair["pair_id"],
                    "target": pair["target"],
                    "condition": condition,
                }
            )

    source_script = UNSLOTH_ROOT / "train.py"
    target_script = script_dir / "train.py"
    shutil.copyfile(source_script, target_script)
    manifest["script"] = {
        "path": target_script.relative_to(ROOT).as_posix(),
        "source": "train.py",
        "sha256": hashlib.sha256(source_script.read_bytes()).hexdigest(),
    }
    (ROOT / "extension_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pair_program_count": len(pair_rows),
                "script_sha256": manifest["script"]["sha256"],
                "candidate_code_executed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
