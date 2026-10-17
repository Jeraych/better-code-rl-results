#!/usr/bin/env bash

# Default configuration for run_reward_experiments.sh.
#
# Assumptions:
# - train.py is the current entrypoint.
# - train.py already reads the reward, performance, and AI-judge env vars below.
# - Baseline means the baseline reward profile in train.py.
# - The launcher loads AI_JUDGE_API_KEY from the local untracked `.env` file.

# Shared run defaults.
#
# These are the main knobs you are likely to tune:
# - model and precision: MODEL_NAME, MAX_SEQ_LENGTH, LOAD_IN_4BIT/8BIT/16BIT
# - LoRA setup: FULL_FINETUNING, LORA_RANK, LORA_ALPHA, LORA_DROPOUT,
#   LORA_TARGET_MODULES
# - repeatability: SEED, REPEAT_SEED_STEP
# - batch/compute budget: NUM_GENERATIONS, EVAL_NUM_GENERATIONS,
#   PER_DEVICE_TRAIN_BATCH_SIZE, GRADIENT_ACCUMULATION_STEPS, MAX_STEPS,
#   TINY_MAX_STEPS, SAVE_STEPS_TRAIN, SAVE_STEPS_TINY, LOGGING_STEPS,
#   AUTO_RESUME, RESUME_FROM_CHECKPOINT, SAVE_STRATEGY, SAVE_TOTAL_LIMIT
# - optimizer/training loop: OPTIM, REPORT_TO, LEARNING_RATE
# - reward mix: REWARD_PROFILE, REWARD_PERFORMANCE_WEIGHT, REWARD_AI_JUDGE_WEIGHT
#   and REWARD_CODEQUAL_WEIGHT
# - prompt sizes: MAX_PROMPT_LENGTH, MAX_COMPLETION_LENGTH
# - performance benchmark: PERFORMANCE_REPEATS, PERFORMANCE_TIMEOUT_SECONDS,
#   PERFORMANCE_RUNTIME_WEIGHT, PERFORMANCE_MEMORY_WEIGHT,
#   PERFORMANCE_NOISE_TOLERANCE
# - AI judge: AI_JUDGE_BASE_URL, AI_JUDGE_MODEL, AI_JUDGE_TEMPERATURE,
#   AI_JUDGE_TOP_P, AI_JUDGE_MAX_TOKENS, AI_JUDGE_TIMEOUT_SECONDS,
#   AI_JUDGE_SEED, AI_JUDGE_REQUIRE_TEST_PASS, AI_JUDGE_MOCK,
#   AI_JUDGE_MAX_FINDINGS, AI_JUDGE_LOW_PENALTY, AI_JUDGE_MEDIUM_PENALTY,
#   AI_JUDGE_HIGH_PENALTY, AI_JUDGE_CRITICAL_PENALTY
# - secret: AI_JUDGE_API_KEY is loaded from the untracked `.env` file.
# - code execution limits: CODE_RUN_TIMEOUT_SECONDS, CODE_RUN_CPU_SECONDS,
#   CODE_RUN_MEMORY_MB, CODE_RUN_USE_RESOURCE_LIMITS
# - style analysis: RUFF_COMMAND, RUFF_SELECT, STYLE_PENALTY_BUDGET,
#   LIGHT_PENALTY_CODES
# - dataset splits: TRAIN_TASK_START/END, HOLDOUT_TASK_START/END,
#   TINY_TASK_START/END

declare -A DEFAULT_RUN_ENV=(
  [MODEL_NAME]="unsloth/Qwen3.6-27B"
  [MAX_SEQ_LENGTH]="2048"
  [LOAD_IN_4BIT]="1"
  [LOAD_IN_8BIT]="0"
  [LOAD_IN_16BIT]="0"
  [FULL_FINETUNING]="0"
  [LORA_RANK]="16"
  [LORA_ALPHA]="16"
  [LORA_DROPOUT]="0"
  [LORA_TARGET_MODULES]="all-linear"
  [SEED]="3407"
  [REPEAT_SEED_STEP]="1"
  [USE_CHAT_TEMPLATE]="1"
  [QWEN_ENABLE_THINKING]="0"
  [NUM_GENERATIONS]="4"
  [EVAL_NUM_GENERATIONS]="4"
  [PER_DEVICE_TRAIN_BATCH_SIZE]="4"
  [GRADIENT_ACCUMULATION_STEPS]="1"
  [MAX_STEPS]="500"
  [TINY_MAX_STEPS]="200"
  [SAVE_STEPS_TRAIN]="100"
  [SAVE_STEPS_TINY]="50"
  [LOGGING_STEPS]="1"
  [AUTO_RESUME]="1"
  [SAVE_STRATEGY]="steps"
  [SAVE_TOTAL_LIMIT]="2"
  [OPTIM]="adamw_8bit"
  [REPORT_TO]="none"
  [REWARD_PROFILE]="all_combined"
  [PERFORMANCE_REPEATS]="3"
  [PERFORMANCE_TIMEOUT_SECONDS]="2.0"
  [PERFORMANCE_RUNTIME_WEIGHT]="0.8"
  [PERFORMANCE_MEMORY_WEIGHT]="0.2"
  [PERFORMANCE_NOISE_TOLERANCE]="1.10"
  [AI_JUDGE_BASE_URL]="http://localhost:11434"
  [AI_JUDGE_MODEL]="qwen3-coder:30b"
  [AI_JUDGE_TEMPERATURE]="0.0"
  [AI_JUDGE_TOP_P]="1.0"
  [AI_JUDGE_MAX_TOKENS]="900"
  [AI_JUDGE_TIMEOUT_SECONDS]="30.0"
  [AI_JUDGE_SEED]="3407"
  [AI_JUDGE_REQUIRE_TEST_PASS]="1"
  [AI_JUDGE_MOCK]="0"
  [AI_JUDGE_MAX_FINDINGS]="8"
  [AI_JUDGE_LOW_PENALTY]="0.15"
  [AI_JUDGE_MEDIUM_PENALTY]="0.35"
  [AI_JUDGE_HIGH_PENALTY]="0.65"
  [AI_JUDGE_CRITICAL_PENALTY]="1.0"
  [CODEQUAL_STRING_CONCAT_ENABLED]="0"
  [CODEQUAL_REQUIRE_TEST_PASS]="1"
  [REWARD_CODEQUAL_WEIGHT]="1.0"
  [MAX_PROMPT_LENGTH]="1024"
  [MAX_COMPLETION_LENGTH]="384"
  [LEARNING_RATE]="5e-6"
  [CODE_RUN_TIMEOUT_SECONDS]="8"
  [CODE_RUN_CPU_SECONDS]="8"
  [CODE_RUN_MEMORY_MB]="0"
  [CODE_RUN_USE_RESOURCE_LIMITS]="0"
  [RUFF_COMMAND]="ruff"
  [RUFF_SELECT]="E,W"
  [STYLE_PENALTY_BUDGET]="10.0"
  [LIGHT_PENALTY_CODES]="E501,W291,W293"
  [TRAIN_TASK_START]="0"
  [TRAIN_TASK_END]="50"
  [HOLDOUT_TASK_START]="50"
  [HOLDOUT_TASK_END]="100"
  [TINY_TASK_START]="0"
  [TINY_TASK_END]="5"
)

declare -A BASELINE_REWARD_WEIGHTS=(
  [REWARD_FORMAT_WEIGHT]="0.1"
  [REWARD_SYNTAX_WEIGHT]="0.1"
  [REWARD_COMPILE_WEIGHT]="0.3"
  [REWARD_STYLE_WEIGHT]="1.0"
  [REWARD_TESTS_WEIGHT]="4.5"
)

declare -A METRIC_ENV_VAR=(
  [baseline]=""
  [correctness]="REWARD_TESTS_WEIGHT"
  [style]="REWARD_STYLE_WEIGHT"
  [performance]="REWARD_PERFORMANCE_WEIGHT"
  [llm-as-judge]="REWARD_AI_JUDGE_WEIGHT"
  [codequal-stringconcat]="REWARD_CODEQUAL_WEIGHT"
)

declare -A METRIC_IMPLEMENTED=(
  [baseline]=1
  [correctness]=1
  [style]=1
  [performance]=1
  [llm-as-judge]=1
  [codequal-stringconcat]=1
)

declare -A METRIC_NOTES=(
  [baseline]="Baseline uses the default baseline reward profile from train.py."
  [performance]="Performance uses REWARD_PERFORMANCE_WEIGHT and the PERFORMANCE_* benchmark knobs."
  [llm-as-judge]="AI Judge uses REWARD_AI_JUDGE_WEIGHT and loads its secret/model settings from the local .env file."
  [codequal-stringconcat]="CodeQual-inspired string concatenation uses a deterministic AST rule and is correctness-gated."
)

METRIC_ORDER=(baseline correctness style performance llm-as-judge codequal-stringconcat)
BASELINE_WEIGHT_ORDER=(
  REWARD_FORMAT_WEIGHT
  REWARD_SYNTAX_WEIGHT
  REWARD_COMPILE_WEIGHT
  REWARD_STYLE_WEIGHT
  REWARD_TESTS_WEIGHT
)

declare -A JOB_WEIGHTS_BASELINE=(
  [baseline]=1.0
)

# These values map directly to train.py's REWARD_* env vars. Correctness uses
# the baseline tests weight of 4.5, not a relative multiplier.
declare -A JOB_WEIGHTS_ALL_METRICS=(
  [baseline]=1.0
  [correctness]=4.5
  [style]=1.0
  [performance]=1.0
  [llm-as-judge]=1.0
)

declare -A JOB_WEIGHTS_DOUBLE_CORRECTNESS=(
  [baseline]=1.0
  [correctness]=9.0
  [style]=1.0
  [performance]=1.0
  [llm-as-judge]=1.0
)

declare -A JOB_WEIGHTS_DOUBLE_STYLE=(
  [baseline]=1.0
  [correctness]=4.5
  [style]=2.0
  [performance]=1.0
  [llm-as-judge]=1.0
)

declare -A JOB_WEIGHTS_DOUBLE_BEST_BASE=(
  [baseline]=1.0
  [correctness]=4.5
  [style]=1.0
  [performance]=1.0
  [llm-as-judge]=1.0
)

# Per-job parameter overrides live in the same config file so you can tune
# hyperparameters alongside the reward matrix. Add/remove keys as needed.
#
# Examples:
# - set a different SEED for a specific job
# - shorten MAX_STEPS for a smoke test
# - widen MAX_PROMPT_LENGTH for a more expensive experiment
# - set REPEAT_SEED_STEP to 0 if you want identical repeats instead of
#   advancing the seed each time

declare -A JOB_PARAM_OVERRIDES_BASELINE=(
  [REWARD_PROFILE]="baseline"
)

declare -A JOB_PARAM_OVERRIDES_ALL_METRICS=(
)

declare -A JOB_PARAM_OVERRIDES_DOUBLE_CORRECTNESS=(
)

declare -A JOB_PARAM_OVERRIDES_DOUBLE_STYLE=(
)

declare -A JOB_PARAM_OVERRIDES_DOUBLE_BEST_BASE=(
)

# Focused 2^3 factorial: PEP8-style (Ruff E/W), dynamic performance, and the
# CodeQual-inspired string-concatenation rule.  AI judge is deliberately held
# out of this first matrix because its latency and stochastic availability
# would confound metric-cost comparisons.
declare -A JOB_WEIGHTS_CQ_CORE=(
  [baseline]=1.0 [correctness]=4.5 [style]=0.0 [performance]=0.0 [codequal-stringconcat]=0.0
)
declare -A JOB_WEIGHTS_CQ_PEP8=(
  [baseline]=1.0 [correctness]=4.5 [style]=1.0 [performance]=0.0 [codequal-stringconcat]=0.0
)
declare -A JOB_WEIGHTS_CQ_CONCAT=(
  [baseline]=1.0 [correctness]=4.5 [style]=0.0 [performance]=0.0 [codequal-stringconcat]=1.0
)
declare -A JOB_WEIGHTS_CQ_PERFORMANCE=(
  [baseline]=1.0 [correctness]=4.5 [style]=0.0 [performance]=1.0 [codequal-stringconcat]=0.0
)
declare -A JOB_WEIGHTS_CQ_PEP8_CONCAT=(
  [baseline]=1.0 [correctness]=4.5 [style]=1.0 [performance]=0.0 [codequal-stringconcat]=1.0
)
declare -A JOB_WEIGHTS_CQ_PEP8_PERFORMANCE=(
  [baseline]=1.0 [correctness]=4.5 [style]=1.0 [performance]=1.0 [codequal-stringconcat]=0.0
)
declare -A JOB_WEIGHTS_CQ_CONCAT_PERFORMANCE=(
  [baseline]=1.0 [correctness]=4.5 [style]=0.0 [performance]=1.0 [codequal-stringconcat]=1.0
)
declare -A JOB_WEIGHTS_CQ_ALL=(
  [baseline]=1.0 [correctness]=4.5 [style]=1.0 [performance]=1.0 [codequal-stringconcat]=1.0
)

declare -A JOB_PARAM_OVERRIDES_CQ_CORE=(
  [REWARD_PROFILE]="baseline" [CODEQUAL_STRING_CONCAT_ENABLED]="0"
)
declare -A JOB_PARAM_OVERRIDES_CQ_PEP8=(
  [REWARD_PROFILE]="baseline" [CODEQUAL_STRING_CONCAT_ENABLED]="0"
)
declare -A JOB_PARAM_OVERRIDES_CQ_CONCAT=(
  [REWARD_PROFILE]="baseline" [CODEQUAL_STRING_CONCAT_ENABLED]="1"
)
declare -A JOB_PARAM_OVERRIDES_CQ_PERFORMANCE=(
  [REWARD_PROFILE]="combined" [CODEQUAL_STRING_CONCAT_ENABLED]="0"
)
declare -A JOB_PARAM_OVERRIDES_CQ_PEP8_CONCAT=(
  [REWARD_PROFILE]="baseline" [CODEQUAL_STRING_CONCAT_ENABLED]="1"
)
declare -A JOB_PARAM_OVERRIDES_CQ_PEP8_PERFORMANCE=(
  [REWARD_PROFILE]="combined" [CODEQUAL_STRING_CONCAT_ENABLED]="0"
)
declare -A JOB_PARAM_OVERRIDES_CQ_CONCAT_PERFORMANCE=(
  [REWARD_PROFILE]="combined" [CODEQUAL_STRING_CONCAT_ENABLED]="1"
)
declare -A JOB_PARAM_OVERRIDES_CQ_ALL=(
  [REWARD_PROFILE]="combined" [CODEQUAL_STRING_CONCAT_ENABLED]="1"
)

CODEQUAL_FACTORIAL_JOB_SEQUENCE=(
  cq-core
  cq-pep8
  cq-concat
  cq-performance
  cq-pep8-concat
  cq-pep8-performance
  cq-concat-performance
  cq-all
)

# Default repeat counts. Use this to run the same job multiple times with the
# same configuration. The launcher will also expose a `--repeat` override.
declare -A JOB_REPEAT_COUNTS=(
  [baseline]=1
  [all-metrics]=1
  [double-correctness]=1
  [double-style]=1
  [double-best]=1
  [cq-core]=3
  [cq-pep8]=3
  [cq-concat]=3
  [cq-performance]=3
  [cq-pep8-concat]=3
  [cq-pep8-performance]=3
  [cq-concat-performance]=3
  [cq-all]=3
)
