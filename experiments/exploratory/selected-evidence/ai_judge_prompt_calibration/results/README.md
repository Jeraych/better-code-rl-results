# Result location policy

Do not write remote calibration results into this preparation directory.
Every execution uses a unique path under:

```text
research_runs/<run_id>/ai_judge_calibration/
```

The directory should contain `run_manifest.json`, `calls.jsonl`, `summary.json`,
CSV tables, `RESULTS.md`, and environment evidence. Commit that complete run on
a new `results/` branch after validation. This placeholder contains no result.
