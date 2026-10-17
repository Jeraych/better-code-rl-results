# Reward Experiment Launcher

This repo uses `run_reward_experiments.sh` as the launcher and `configs/reward_experiments.sh` as the single source of truth for reward weights, training knobs, job-specific overrides, and repeat counts.

The launcher is intentionally self-contained at runtime:

- it uses `train.py` as the default entrypoint,
- it writes runs under `results/<run_number>/`,
- it builds the combined training dashboard with `plot_training_conrad_toggle.py`,
- it builds the AI-judge dashboard with `build_run13_ai_judge_dashboard.py` for jobs that include judge data,
- it does not depend on files in `documentation/` or `old_versions/`.

## Quick Start

Run the full matrix:

```bash
./run_reward_experiments.sh --all
```

Run one job:

```bash
./run_reward_experiments.sh --job baseline
./run_reward_experiments.sh --job double-correctness
./run_reward_experiments.sh --job double-style
./run_reward_experiments.sh --job double-best --double-metric performance
```

Run the same job multiple times:

```bash
./run_reward_experiments.sh --job baseline --repeat 3
./run_reward_experiments.sh --all --repeat 2
```

Preview the commands without running them:

```bash
./run_reward_experiments.sh --all --dry-run
```

## What Gets Created

Each top-level invocation creates the next numeric folder in `results/`.

If `results/11` already exists, the next run folder becomes `results/12`.

Example layout:

```text
results/
  9/
  10/
  11/
  12/
    baseline-run-01/
    baseline-run-02/
    all-metrics/
    double-correctness/
    double-style/
    double-best-performance/
```

If a job is repeated, the launcher appends `-run-01`, `-run-02`, and so on to keep each repeat separate.

## Job Folder Layout

Each job folder contains the job’s logs, copied CSV files, trainer state, and dashboard.

Example:

```text
results/12/baseline-run-01/
  base_train.log
  base_holdout.log
  train.log
  lora_train.log
  lora_holdout.log
  samples.csv
  samples.jsonl
  before_after_code.csv
  trainer_state.json
  eval_base_train_tasks.csv
  eval_base_holdout_tasks.csv
  eval_lora_train_tasks.csv
  eval_lora_holdout_tasks.csv
  combined_dashboard.html
  ai_judge_dashboard.html
  AI_JUDGE_SUMMARY.md
  grpo_mvp_logs/
  grpo_mvp_output/
  grpo_mvp_lora/
```

The root-level copies are the files you usually inspect first.
The AI-judge dashboard files are only created for judge-enabled jobs whose
`samples.csv` contains AI-judge columns.

## Config File

Edit `configs/reward_experiments.sh` when you want to change the experiment matrix or the training setup.

The file holds three kinds of settings:

- `DEFAULT_RUN_ENV`: shared training and evaluation defaults.
- `JOB_PARAM_OVERRIDES_*`: job-specific overrides for one experiment.
- `JOB_REPEAT_COUNTS`: how many times to repeat each job by default.

The launcher also accepts `--repeat N`, which overrides the config file for the current command.

## Important Knobs

These are the parameters and hyperparameters that are usually worth tuning first:

- Model and precision:
  - `MODEL_NAME`
  - `MAX_SEQ_LENGTH`
  - `LOAD_IN_4BIT`
  - `LOAD_IN_8BIT`
  - `LOAD_IN_16BIT`
- Adapter setup:
  - `FULL_FINETUNING`
  - `LORA_RANK`
  - `LORA_ALPHA`
  - `LORA_DROPOUT`
  - `LORA_TARGET_MODULES`
- Training dynamics:
  - `SEED`
  - `REPEAT_SEED_STEP`
  - `NUM_GENERATIONS`
  - `EVAL_NUM_GENERATIONS`
  - `PER_DEVICE_TRAIN_BATCH_SIZE`
  - `GRADIENT_ACCUMULATION_STEPS`
  - `MAX_STEPS`
  - `TINY_MAX_STEPS`
  - `SAVE_STEPS_TRAIN`
  - `SAVE_STEPS_TINY`
  - `LOGGING_STEPS`
  - `OPTIM`
  - `REPORT_TO`
  - `LEARNING_RATE`
- Reward mix:
  - `REWARD_PROFILE`
  - `REWARD_PERFORMANCE_WEIGHT`
  - `REWARD_AI_JUDGE_WEIGHT`
- Performance benchmark:
  - `PERFORMANCE_REPEATS`
  - `PERFORMANCE_TIMEOUT_SECONDS`
  - `PERFORMANCE_RUNTIME_WEIGHT`
  - `PERFORMANCE_MEMORY_WEIGHT`
  - `PERFORMANCE_NOISE_TOLERANCE`
- AI judge:
  - `AI_JUDGE_BASE_URL`
  - `AI_JUDGE_MODEL`
  - `AI_JUDGE_TEMPERATURE`
  - `AI_JUDGE_TOP_P`
  - `AI_JUDGE_MAX_TOKENS`
  - `AI_JUDGE_TIMEOUT_SECONDS`
  - `AI_JUDGE_SEED`
  - `AI_JUDGE_REQUIRE_TEST_PASS`
  - `AI_JUDGE_MOCK`
  - `AI_JUDGE_MAX_FINDINGS`
  - `AI_JUDGE_LOW_PENALTY`
  - `AI_JUDGE_MEDIUM_PENALTY`
  - `AI_JUDGE_HIGH_PENALTY`
  - `AI_JUDGE_CRITICAL_PENALTY`
  - `AI_JUDGE_API_KEY` (stored in the untracked `.env` file)
- Prompt and output sizes:
  - `MAX_PROMPT_LENGTH`
  - `MAX_COMPLETION_LENGTH`
- Runtime and safety:
  - `CODE_RUN_TIMEOUT_SECONDS`
  - `CODE_RUN_CPU_SECONDS`
  - `CODE_RUN_MEMORY_MB`
  - `CODE_RUN_USE_RESOURCE_LIMITS`
  - `RUFF_COMMAND`
  - `RUFF_SELECT`
  - `STYLE_PENALTY_BUDGET`
  - `LIGHT_PENALTY_CODES`
- Dataset splits:
  - `TRAIN_TASK_START`
  - `TRAIN_TASK_END`
  - `HOLDOUT_TASK_START`
  - `HOLDOUT_TASK_END`
  - `TINY_TASK_START`
  - `TINY_TASK_END`
- Before/after comparison CSV:
  - `SAVE_BEFORE_AFTER_CSV`
  - `BEFORE_AFTER_CSV_PATH`
  - `BEFORE_AFTER_SPLIT`
  - `BEFORE_AFTER_NUM_TASKS`
  - `BEFORE_AFTER_NUM_GENERATIONS`
  - `BEFORE_AFTER_DO_SAMPLE`
  - `BEFORE_AFTER_TEMPERATURE`
  - `BEFORE_AFTER_TOP_P`

These knobs matter because they control cost, variance, and how aggressively the reward signals are mixed into training.

## Changing One Job

If you want one job to use a different configuration, add or edit the matching override block in `configs/reward_experiments.sh`.

Example:

```bash
declare -A JOB_PARAM_OVERRIDES_DOUBLE_CORRECTNESS=(
  [MAX_STEPS]="700"
  [LEARNING_RATE]="3e-6"
  [SEED]="3500"
)
```

That keeps the job definition and the hyperparameters in the same place.

## Repeating A Job

To run the same job multiple times, set `JOB_REPEAT_COUNTS` in the config file or use `--repeat N` on the command line.

Example:

```bash
declare -A JOB_REPEAT_COUNTS=(
  [baseline]=3
  [double-best]=5
)
```

The launcher increments `SEED` by `REPEAT_SEED_STEP` on each repeat when the seed is numeric.

If you want identical repeats, set:

```bash
REPEAT_SEED_STEP=0
```

## Reward Metrics

The launcher maps the conceptual reward metrics to the environment variables that `train.py` already reads.

Current mapping:

- `Baseline` uses the default reward profile from `train.py`:
  - `REWARD_FORMAT_WEIGHT`
  - `REWARD_SYNTAX_WEIGHT`
  - `REWARD_COMPILE_WEIGHT`
  - `REWARD_STYLE_WEIGHT`
  - `REWARD_TESTS_WEIGHT`
- `Correctness` maps to `REWARD_TESTS_WEIGHT`.
- `Style` maps to `REWARD_STYLE_WEIGHT`.
- `Performance` maps to `REWARD_PERFORMANCE_WEIGHT` and uses the `PERFORMANCE_*` benchmark knobs.
- `AI Judge` maps to `REWARD_AI_JUDGE_WEIGHT` and uses the `AI_JUDGE_*` settings.

These weights are the final environment values passed to `train.py`, not
relative multipliers. For example, baseline-strength correctness uses
`REWARD_TESTS_WEIGHT=4.5`; a doubled-correctness job uses `9.0`.

The reward profile controls which signals contribute to the scalar reward:

- `baseline`
- `combined`
- `judge_combined`
- `all_combined`

The relevant config blocks are:

- `DEFAULT_RUN_ENV`
- `BASELINE_REWARD_WEIGHTS`
- `METRIC_ENV_VAR`
- `METRIC_IMPLEMENTED`
- `METRIC_NOTES`
- `JOB_WEIGHTS_*`
- `JOB_PARAM_OVERRIDES_*`

If you change the judge endpoint or model, update the untracked `.env` file
that the launcher sources before it starts the jobs.

## Dashboard And Artifacts

After the training and evaluation steps complete for a job, the launcher calls:

```bash
python plot_training_conrad_toggle.py \
  --run-dir <job-folder> \
  --trainer-state <training-step trainer_state.json> \
  --samples <training-step samples.csv> \
  --eval-file <eval csv 1> \
  --eval-file <eval csv 2> \
  --eval-file <eval csv 3> \
  --eval-file <eval csv 4> \
  --output <job-folder>/combined_dashboard.html
```

It also calls:

```bash
python build_run13_ai_judge_dashboard.py \
  --result-dir <job-folder>
```

That keeps the dashboards tied to the exact files produced by that job repeat.

The copied root-level files mean:

- `samples.csv`: the consolidated sample log used by the dashboard.
- `samples.jsonl`: the full raw sample log for row-level inspection.
- `before_after_code.csv`: paired base and trained-LoRA completions for side-by-side code contrast.
- `trainer_state.json`: the trainer history used by the dashboard.
- `eval_*.csv`: the evaluation summaries for base and LoRA runs.
- `combined_dashboard.html`: the rendered dashboard for the job.
- `ai_judge_dashboard.html`: the judge-focused dashboard for judge-enabled jobs.
- `AI_JUDGE_SUMMARY.md`: the judge-focused Markdown summary for judge-enabled jobs.
- `grpo_mvp_output/`: checkpoints and trainer state from training.
- `grpo_mvp_lora/`: the saved LoRA adapter from training.

## Assumptions

- `train.py` is the active training and evaluation entrypoint.
- `plot_training_conrad_toggle.py` can build a dashboard from explicit trainer-state, sample-log, and eval-CSV paths.
- `build_run13_ai_judge_dashboard.py` can build the judge-focused dashboard from a result folder containing `samples.csv` and `trainer_state.json`.
- `performance` uses the dedicated reward hook and benchmark settings.
- `AI Judge` uses the dedicated reward hook and the secrets stored in the local `.env` file.
