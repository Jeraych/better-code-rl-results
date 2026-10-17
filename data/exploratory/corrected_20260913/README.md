# Recovered HumanEval+ scores — 2026-09-13

Original results/27–29 are preserved. This directory contains corrected copies
of 12 evaluation CSVs and 3 training-sample CSVs, plus a hashed summary.

Only 1,073 rows whose test execution failed with `Argument list too long` were
re-scored. All other rows were retained exactly, including genuine failures and
timeouts. Identical task/code pairs share one cached execution verdict. All 15
affected task reference solutions passed before candidate testing began.

## Corrected holdout scores

Each evaluation contains 50 tasks with 4 saved generations per task (200 outputs).
These percentages are sample pass rates, not pass@4 or independent-task counts.

| Run | Training arm / seed | Base correctness | LoRA correctness | LoRA correct AND Ruff-clean |
|---|---|---:|---:|---:|
| 27 | correctness / 3407 | 180/200 (90.0%) | 183/200 (91.5%) | 139/200 (69.5%) |
| 28 | correctness + Ruff / 3407 | 183/200 (91.5%) | 176/200 (88.0%) | 163/200 (81.5%) |
| 29 | correctness / 3409 | 182/200 (91.0%) | 181/200 (90.5%) | 111/200 (55.5%) |

Ruff-clean requires style_status=ok and zero violations. Ruff results were not
rerun or changed. Reward totals were adjusted by 4.5 times the change in the
binary correctness reward. Other reward components were retained.

## Execution and limitations

- Offline Linux Docker, Python 3.11.14, NumPy 2.2.6, 8-second candidate timeout.
  Candidate processes ran as UID/GID 65534; benchmark/results inputs were
  read-only. Container limits: 2 CPUs, 2 GiB RAM, 64 processes, no network.
- Image: sha256:726d5930111422aca0b3cfb58ecc1ec33930a46482e7a68e0c3baec815e93946.
- Tests came from the Hugging Face `evalplus/humanevalplus` test split via the
  datasets-server rows API. All 164 rows were downloaded without truncated cells.
  Dataset file hashes are in summary.json. The original runs did not supply a
  pinned dataset revision here, so exact historical dataset identity is not proven.
- This is targeted recovery, not a full re-evaluation under one new environment.
  Existing non-E2BIG outcomes still come from the original machine/environment.
- Training CSV corrections are retrospective audit scores only. The models were
  actually trained using the original faulty correctness rewards. Re-scoring
  does not repair the learning trajectory or establish a clean training ablation.
- The style run shows a preliminary correctness/style trade-off, not proof of
  superiority: there is only one recovered style seed in these three runs.
- Original JSONL and log summaries were not overwritten. Use these corrected
  CSVs and summary.json for recovered figures; retain original logs for provenance.

Verification command, from the repository root:

```text
python experiments/verify_heplus_recovery.py results results/corrected_20260913
```

Verified: 8,400 rows, original hashes intact, all unaffected rows unchanged,
corrected verdicts and reward arithmetic consistent, 200 unique task/generation
pairs in every evaluation CSV. No model training was run.
