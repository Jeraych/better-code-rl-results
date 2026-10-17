# AI-judge prompt calibration protocol

## Question

Does a more operational, evidence-constrained prompt improve the reliability of
the existing taxonomy-grounded AI judge without increasing false alarms?

This is prompt calibration, not GRPO training. It compares the unchanged Run 13
production prompt (`baseline_v3`) with one frozen candidate (`calibrated_v4`)
through the same OpenAI-compatible Ollama request shape and the same local label,
line, and severity validation policy.

## Frozen inputs

- Six allowed subcategories only:
  - Confusing Variable Naming
  - Sub-readable Code Exists
  - Code Duplication
  - Comment Duplication
  - Unnecessary Else
  - Unnecessary Conditional Block
- Eighteen hand-authored behavioural pairs, three per subcategory.
- Each pair contains one clean control and one behaviourally equivalent program
  with a deliberately seeded target defect: 36 candidate programs total.
- The clean member is also supplied as reference context for both members.
- Two prompt profiles, two identical-seed repetitions, 144 planned calls.
- Default model and sampling match Run 13: `qwen3-coder:30b`, temperature 0,
  top-p 1, seed 3407, and 900 maximum response tokens.

The intervention labels are controlled synthetic labels, not human ground
truth. They test whether the judge recognizes seeded categories and avoids
flagging paired controls. They do not establish correctness on natural code.

## Metrics

Calculate separately for each prompt:

- micro and macro precision, recall, and F1 across the six subcategories;
- exact label-set accuracy;
- proportion of degraded cases where the seeded category is detected;
- clean-control false-positive rate;
- pairwise score direction: clean score greater than degraded, tie, or reverse;
- successful/schema-valid response rate;
- raw-to-sanitized finding retention;
- exact repeated-label agreement, Jaccard agreement, and score difference;
- latency, retry, timeout, and error distributions;
- per-category confusion counts and severity distribution.

Errors are missing observations, not zero-quality scores. Do not convert a
timeout or invalid response into a reward of zero for this comparison.

## Frozen decision rule

Advance `calibrated_v4` to a natural-code validation pilot only if all are true:

1. Macro F1 improves by at least 0.05 over `baseline_v3`.
2. Clean-control false-positive rate is no higher than baseline and no more than
   0.15.
3. At least 75% of pairs have a higher clean score than degraded score.
4. Successful/schema-valid response rate is at least 0.98.
5. Exact repeated-label agreement is at least 0.80.
6. Recall is at least 0.50 for every subcategory.

Otherwise retain `baseline_v3` and record which gate failed. Passing these gates
does not authorize changing `train.py`; it only justifies a separate validation
on stratified natural Run 13 outputs or an independent labelled dataset.

## Integrity and privacy

- The runner refuses to overwrite an output directory.
- Every run records repository commit, dataset hash, prompt hashes, model,
  sampling configuration, UTC timestamps, request hashes, raw response content,
  sanitized findings, and errors.
- Endpoint URLs and access keys are read from environment variables and never
  written to results.
- Candidate code is sent to the configured judge but never executed.
- Use a new result branch and `research_runs/<run_id>/ai_judge_calibration/` for
  every remote run.
