# AI-judge prompt calibration

This experiment is fully prepared but has not made a real judge call. It compares
the exact Run 13 prompt with a candidate prompt on a frozen synthetic paired
dataset. See `PROTOCOL.md` before running it.

## Validate locally without Ollama

```bash
python experiments/ai_judge_prompt_calibration/export_dataset.py --check
python experiments/ai_judge_prompt_calibration/run_calibration.py --validate-only
python experiments/ai_judge_prompt_calibration/validate_preparation.py
```

## Small remote smoke test

Set connection values only in the remote shell. Do not put them in a committed
file or terminal log.

```bash
export AI_JUDGE_BASE_URL="<PRIVATE_OPENAI_COMPATIBLE_BASE_URL>"
export AI_JUDGE_API_KEY="<PRIVATE_ACCESS_KEY>"
export AI_JUDGE_MODEL="qwen3-coder:30b"

python experiments/ai_judge_prompt_calibration/run_calibration.py \
  --output-dir research_runs/<run_id>/ai_judge_smoke \
  --profiles baseline_v3 calibrated_v4 \
  --repetitions 1 \
  --case-limit 2
```

Inspect both calls before the full run. A smoke result is plumbing evidence only
and must not be mixed into the full calibration metrics.

## Frozen full calibration

```bash
python experiments/ai_judge_prompt_calibration/run_calibration.py \
  --output-dir research_runs/<run_id>/ai_judge_calibration \
  --profiles baseline_v3 calibrated_v4 \
  --repetitions 2

python experiments/ai_judge_prompt_calibration/summarize_results.py \
  research_runs/<run_id>/ai_judge_calibration
```

The full run makes 144 sequential requests. If interrupted, use `--resume` with
the exact same output directory; completed profile/case/repetition keys are not
called again. Never reuse an output directory for a different model or setup.

After the run, follow `experiments/remote_run_bundle/REMOTE_RUNBOOK.md` to
validate, copy back, privacy-check, and commit the result on a dedicated branch.
