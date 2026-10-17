# AI Judge Reward Design

## Purpose

The AI judge reward adds a non-functional quality signal to GRPO training. It
targets qualities that are difficult to measure with deterministic checks:
readability and maintainability. Correctness, syntax, runnable status, Ruff
style, and measured runtime performance remain separate objective rewards.

This keeps the research claim narrow: execution rewards teach the model to pass
tests and run efficiently; the AI judge teaches the model to avoid
taxonomy-defined code-quality inefficiencies that tests and performance counters
do not capture well.

## What The Judge Scores

The judge is limited to these taxonomy categories from "A Taxonomy of
Inefficiencies in LLM-Generated Python Code":

- Readability
  - Confusing Variable Naming
  - Sub-readable Code Exists
- Maintainability
  - Code Duplication
  - Comment Duplication
  - Unnecessary Else
  - Unnecessary Conditional Block

The judge must not score:

- functional correctness, because HumanEval tests already provide that signal;
- syntax/import/runtime errors, because parsing and subprocess execution cover
  them;
- measured performance, because the performance branch benchmarks runtime and
  traced memory;
- ordinary formatter/linter style, because Ruff already provides a deterministic
  style reward.

The reference solution is used as calibration context. The judge should not
penalize ordinary clear algorithmic structure, such as simple loops or pairwise
comparisons, especially when that structure is similar to the reference. It
should report readability findings only when the candidate introduces local
complexity that is unnecessarily hard to understand compared with a simple
equivalent in the same algorithm.

Variable naming findings are intentionally conservative. The judge should not
penalize conventional short local loop names, such as `i`, `j`, `idx`, or
`elem`, merely because longer names are possible. The implementation also
filters weak naming findings when the reason is only "not descriptive enough"
and there is no concrete ambiguity, built-in shadowing, misleading name, or
confusing identifier reuse.

Some taxonomy findings are validated against the candidate code before scoring.
For example, an `Unnecessary Else` finding is discarded if neither the cited
evidence nor the cited line span contains an actual `else:` block. This prevents
obvious judge hallucinations from affecting the reward.

## How It Works

`train.py` sends the original HumanEval task, the generated candidate code with
line numbers, and the canonical solution as context to an Ollama
OpenAI-compatible `/v1/chat/completions` endpoint. The server address is supplied
with `AI_JUDGE_BASE_URL`; private server details should not be committed.

The judge returns strict JSON findings. Each finding must include a taxonomy
category, taxonomy subcategory, severity, line span, evidence, and reason. The
code then validates the labels and computes the reward locally:

```text
score = max(0.0, 1.0 - sum(severity_penalties))
```

Default penalties:

```text
low = 0.15
medium = 0.35
high = 0.65
critical = 1.0
```

The model is never trusted to provide its own scalar score. It only provides
structured evidence, which makes the reward auditable in `samples.csv` and
`samples.jsonl`.

By default, the AI judge runs only when `test_status=passed`. Incorrect code
receives no AI-judge reward.

## Research Rationale

The taxonomy paper motivates the selected categories by showing that
LLM-generated Python code has inefficiencies beyond correctness, including
readability and maintainability. Its practitioner survey validates these
categories as relevant to real-world code adoption.

The project proposal calls for a dual reward system combining execution-based
feedback with an LLM-as-judge mechanism. This implementation follows that plan
while keeping deterministic rewards responsible for objective properties.

The GRPO code-quality literature motivates moving beyond binary pass/fail
signals and evaluating whether richer quality rewards change generated-code
tradeoffs. This implementation supports that by adding `judge_combined`,
`judge_only`, `all_combined`, and separate-reward ablation profiles.

## Suggested Experiments

Keep model, task split, generation count, max steps, prompt length, completion
length, and seed settings fixed across runs:

```text
baseline
combined
judge_combined
all_combined
```

Report:

- pass rate;
- style-clean rate;
- performance score among correct solutions;
- AI-judge score among correct solutions;
- frequency of judge findings by taxonomy subcategory;
- reward variance and `frac_reward_zero_std`;
- completion length.

For publishable validation, sample heldout outputs and run a blind human
comparison against the judge labels. Report agreement and inspect whether the
judge reward causes reward hacking, such as overly short code, excessive
comments, or degraded correctness/performance.

When the judge-enabled experiment launcher runs, it also preserves the paired
`before_after_code.csv` comparison and writes `ai_judge_dashboard.html` plus
`AI_JUDGE_SUMMARY.md` inside the job folder for later inspection.
