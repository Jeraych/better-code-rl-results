"""Add compact statistical summaries to an existing pilot run."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter
from pathlib import Path

from run_pilot import spearman


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    spread = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    return (centre - spread) / denominator, (centre + spread) / denominator


def two_sided_sign_test(successes: int, total: int) -> float:
    extreme = max(successes, total - successes)
    one_tail = sum(math.comb(total, value) for value in range(extreme, total + 1)) / (2**total)
    return min(1.0, 2 * one_tail)


def bootstrap_spearman(
    left: list[float],
    right: list[float],
    repetitions: int = 5000,
    seed: int = 20260805,
) -> tuple[float, float]:
    rng = random.Random(seed)
    estimates = []
    for _ in range(repetitions):
        indices = [rng.randrange(len(left)) for _ in left]
        estimate = spearman([left[index] for index in indices], [right[index] for index in indices])
        if estimate is not None:
            estimates.append(estimate)
    estimates.sort()
    lower = estimates[int(0.025 * (len(estimates) - 1))]
    upper = estimates[int(0.975 * (len(estimates) - 1))]
    return lower, upper


def main() -> None:
    base = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    with (RESULTS / "run13_sample.csv").open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))

    wins = base["synthetic"]["directional_wins"]
    pair_count = base["synthetic"]["pair_count"]
    wilson = wilson_interval(wins, pair_count)

    ai = [float(row["ai_judge_score"]) for row in rows]
    metric_columns = [
        "codequal_overall",
        "codequal_entrypoint_filtered_overall",
        "codequal_overall_per_kchar",
        "codequal_entrypoint_filtered_overall_per_kchar",
    ]
    correlations = {}
    for column in metric_columns:
        values = [float(row[column]) for row in rows]
        estimate = spearman(values, ai)
        interval = bootstrap_spearman(values, ai)
        correlations[column] = {
            "spearman": round(estimate, 4) if estimate is not None else None,
            "bootstrap_95pct_ci": [round(interval[0], 4), round(interval[1], 4)],
        }

    analyzer_counts = Counter()
    rule_presence = Counter()
    for row in rows:
        analyzer_counts.update(json.loads(row["findings_by_analyzer"]))
        rule_presence.update(rule for rule in row["rule_ids"].split("|") if rule)

    result = {
        "synthetic_directional_accuracy": {
            "wins": wins,
            "pairs": pair_count,
            "wilson_95pct_ci": [round(wilson[0], 4), round(wilson[1], 4)],
            "two_sided_sign_test_p": round(two_sided_sign_test(wins, pair_count), 6),
        },
        "run13_score_resolution": {
            column: dict(sorted(Counter(row[column] for row in rows).items()))
            for column in metric_columns
        },
        "run13_findings": {
            "raw_total": sum(int(row["finding_count"]) for row in rows),
            "entrypoint_filtered_total": sum(
                int(row["entrypoint_filtered_finding_count"]) for row in rows
            ),
            "samples_with_non_entrypoint_findings": sum(
                int(row["entrypoint_filtered_finding_count"]) > 0 for row in rows
            ),
            "analyzer_counts_before_entrypoint_filter": dict(analyzer_counts.most_common()),
            "rule_presence_by_sample_before_entrypoint_filter": dict(rule_presence.most_common()),
        },
        "run13_correlations_with_ai_judge": correlations,
        "bootstrap": {"repetitions": 5000, "seed": 20260805},
    }
    (RESULTS / "statistical_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
