#!/usr/bin/env bash
set -euo pipefail

# Assumptions used by this launcher:
# - `train.py` is the active entrypoint.
# - `plot_training_conrad_toggle.py` at the repo root can build a dashboard
#   from explicit trainer-state, samples, and eval CSV paths.
# - `build_run13_ai_judge_dashboard.py` can build an AI-judge dashboard from a
#   result folder that already contains copied training artifacts.
# - `configs/reward_experiments.sh` is the default reward-experiment config.
# - performance uses the dedicated performance reward and benchmark settings.
# - the AI judge uses the dedicated judge reward and loads secrets from `.env`.

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

note() {
  printf 'NOTE: %s\n' "$*" >&2
}

normalize_token() {
  local token="${1,,}"
  token="${token//_/-}"
  token="${token// /-}"
  printf '%s' "$token"
}

metric_display_name() {
  case "$1" in
    baseline) printf 'Baseline' ;;
    correctness) printf 'Correctness' ;;
    style) printf 'Style' ;;
    performance) printf 'Performance' ;;
    llm-as-judge) printf 'AI Judge' ;;
    *) printf '%s' "$1" ;;
  esac
}

job_spec_name() {
  case "$1" in
    baseline) printf 'JOB_WEIGHTS_BASELINE' ;;
    all-metrics) printf 'JOB_WEIGHTS_ALL_METRICS' ;;
    double-correctness) printf 'JOB_WEIGHTS_DOUBLE_CORRECTNESS' ;;
    double-style) printf 'JOB_WEIGHTS_DOUBLE_STYLE' ;;
    double-best) printf 'JOB_WEIGHTS_DOUBLE_BEST_BASE' ;;
    *) return 1 ;;
  esac
}

job_param_name() {
  case "$1" in
    baseline) printf 'JOB_PARAM_OVERRIDES_BASELINE' ;;
    all-metrics) printf 'JOB_PARAM_OVERRIDES_ALL_METRICS' ;;
    double-correctness) printf 'JOB_PARAM_OVERRIDES_DOUBLE_CORRECTNESS' ;;
    double-style) printf 'JOB_PARAM_OVERRIDES_DOUBLE_STYLE' ;;
    double-best) printf 'JOB_PARAM_OVERRIDES_DOUBLE_BEST_BASE' ;;
    *) return 1 ;;
  esac
}

job_repeat_count() {
  local job_key="$1"
  if declare -p JOB_REPEAT_COUNTS >/dev/null 2>&1; then
    local count="${JOB_REPEAT_COUNTS[$job_key]:-1}"
    if [[ "$count" =~ ^[0-9]+$ ]] && (( count > 0 )); then
      printf '%s' "$count"
      return 0
    fi
  fi
  printf '1'
}

load_optional_env_file() {
  local env_file="${1:-.env}"
  [[ -f "$env_file" ]] || return 0

  local ai_judge_api_key_set=0
  local ai_judge_api_key=""
  local ai_judge_model_set=0
  local ai_judge_model=""
  local ai_judge_base_url_set=0
  local ai_judge_base_url=""

  if [[ -n "${AI_JUDGE_API_KEY+x}" ]]; then
    ai_judge_api_key_set=1
    ai_judge_api_key="$AI_JUDGE_API_KEY"
  fi
  if [[ -n "${AI_JUDGE_MODEL+x}" ]]; then
    ai_judge_model_set=1
    ai_judge_model="$AI_JUDGE_MODEL"
  fi
  if [[ -n "${AI_JUDGE_BASE_URL+x}" ]]; then
    ai_judge_base_url_set=1
    ai_judge_base_url="$AI_JUDGE_BASE_URL"
  fi

  # shellcheck source=/dev/null
  source "$env_file"

  if (( ai_judge_api_key_set )); then
    AI_JUDGE_API_KEY="$ai_judge_api_key"
  fi
  if (( ai_judge_model_set )); then
    AI_JUDGE_MODEL="$ai_judge_model"
  fi
  if (( ai_judge_base_url_set )); then
    AI_JUDGE_BASE_URL="$ai_judge_base_url"
  fi
}

PARAMETER_ORDER=(
  MODEL_NAME
  MAX_SEQ_LENGTH
  LOAD_IN_4BIT
  LOAD_IN_8BIT
  LOAD_IN_16BIT
  FULL_FINETUNING
  LORA_RANK
  LORA_ALPHA
  LORA_DROPOUT
  LORA_TARGET_MODULES
  SEED
  REPEAT_SEED_STEP
  USE_CHAT_TEMPLATE
  QWEN_ENABLE_THINKING
  NUM_GENERATIONS
  EVAL_NUM_GENERATIONS
  PER_DEVICE_TRAIN_BATCH_SIZE
  GRADIENT_ACCUMULATION_STEPS
  MAX_STEPS
  TINY_MAX_STEPS
  SAVE_STEPS_TRAIN
  SAVE_STEPS_TINY
  LOGGING_STEPS
  AUTO_RESUME
  RESUME_FROM_CHECKPOINT
  SAVE_STRATEGY
  SAVE_TOTAL_LIMIT
  OPTIM
  REPORT_TO
  REWARD_PROFILE
  PERFORMANCE_REPEATS
  PERFORMANCE_TIMEOUT_SECONDS
  PERFORMANCE_RUNTIME_WEIGHT
  PERFORMANCE_MEMORY_WEIGHT
  PERFORMANCE_NOISE_TOLERANCE
  AI_JUDGE_BASE_URL
  AI_JUDGE_MODEL
  AI_JUDGE_TEMPERATURE
  AI_JUDGE_TOP_P
  AI_JUDGE_MAX_TOKENS
  AI_JUDGE_TIMEOUT_SECONDS
  AI_JUDGE_SEED
  AI_JUDGE_REQUIRE_TEST_PASS
  AI_JUDGE_MOCK
  AI_JUDGE_MAX_FINDINGS
  AI_JUDGE_LOW_PENALTY
  AI_JUDGE_MEDIUM_PENALTY
  AI_JUDGE_HIGH_PENALTY
  AI_JUDGE_CRITICAL_PENALTY
  MAX_PROMPT_LENGTH
  MAX_COMPLETION_LENGTH
  LEARNING_RATE
  CODE_RUN_TIMEOUT_SECONDS
  CODE_RUN_CPU_SECONDS
  CODE_RUN_MEMORY_MB
  CODE_RUN_USE_RESOURCE_LIMITS
  RUFF_COMMAND
  RUFF_SELECT
  STYLE_PENALTY_BUDGET
  LIGHT_PENALTY_CODES
  TRAIN_TASK_START
  TRAIN_TASK_END
  HOLDOUT_TASK_START
  HOLDOUT_TASK_END
  TINY_TASK_START
  TINY_TASK_END
  SAVE_BEFORE_AFTER_CSV
  BEFORE_AFTER_CSV_PATH
  BEFORE_AFTER_SPLIT
  BEFORE_AFTER_NUM_TASKS
  BEFORE_AFTER_NUM_GENERATIONS
  BEFORE_AFTER_DO_SAMPLE
  BEFORE_AFTER_TEMPERATURE
  BEFORE_AFTER_TOP_P
)

SECRET_ENV_KEYS=(
  AI_JUDGE_API_KEY
)

lookup_env_value() {
  local array_name="$1"
  local key="$2"
  declare -n pairs="$array_name"
  local pair
  for pair in "${pairs[@]}"; do
    if [[ "${pair%%=*}" == "$key" ]]; then
      printf '%s' "${pair#*=}"
      return 0
    fi
  done
  return 1
}

is_secret_env_key() {
  local key="$1"
  local secret_key
  for secret_key in "${SECRET_ENV_KEYS[@]}"; do
    if [[ "$secret_key" == "$key" ]]; then
      return 0
    fi
  done
  return 1
}

mask_env_arg() {
  local arg="$1"
  local key="${arg%%=*}"
  if is_secret_env_key "$key"; then
    printf '%s' "$key=<redacted>"
  else
    printf '%q' "$arg"
  fi
}

print_env_table() {
  local title="$1"
  local array_name="$2"
  shift 2
  local -a keys=("$@")
  printf '%s\n' "$title"
  local key value printed=0
  for key in "${keys[@]}"; do
    if value="$(lookup_env_value "$array_name" "$key" 2>/dev/null)"; then
      printf '  %-30s %s\n' "$key" "$value"
      printed=1
    fi
  done
  if [[ "$printed" -eq 0 ]]; then
    printf '  (none)\n'
  fi
}

load_default_run_env() {
  local defaults_name="$1"
  declare -n defaults="$defaults_name"

  local key
  for key in "${PARAMETER_ORDER[@]}"; do
    if [[ -n "${!key+x}" ]]; then
      continue
    fi

    if [[ -n "${defaults[$key]+x}" ]]; then
      printf -v "$key" '%s' "${defaults[$key]}"
    fi
  done
}

assoc_to_pairs() {
  local assoc_name="$1"
  local out_name="$2"
  declare -n assoc="$assoc_name"
  declare -n out="$out_name"

  out=()
  local key
  for key in "${!assoc[@]}"; do
    out+=("$key=${assoc[$key]}")
  done
}

print_weight_table() {
  local title="$1"
  local array_name="$2"
  local -n table="$array_name"

  printf '%s\n' "$title"
  local key printed=0
  for key in "${METRIC_ORDER[@]}"; do
    if [[ -n "${table[$key]:-}" ]]; then
      printf '  %-18s %s\n' "$(metric_display_name "$key")" "${table[$key]}"
      printed=1
    fi
  done

  if [[ "$printed" -eq 0 ]]; then
    printf '  (none)\n'
  fi
}

build_requested_weights() {
  local job_key="$1"
  local double_metric="$2"
  local out_name="$3"
  local spec_name
  if ! spec_name="$(job_spec_name "$job_key")"; then
    die "Unknown job '$job_key'"
  fi

  declare -n spec="$spec_name"
  declare -n weights="$out_name"
  weights=()

  local key
  for key in "${!spec[@]}"; do
    weights["$key"]="${spec[$key]}"
  done

  if [[ "$job_key" == "double-best" ]]; then
    case "$double_metric" in
      performance|llm-as-judge) ;;
      *)
        die "Unsupported --double-metric '$double_metric'. Use 'performance' or 'llm-as-judge'."
        ;;
    esac
    weights["$double_metric"]="2.0"
  fi
}

resolve_active_weights() {
  local job_label="$1"
  local requested_name="$2"
  local active_name="$3"
  declare -n requested="$requested_name"
  declare -n active="$active_name"

  active=()

  local metric weight implemented env_var note_text
  for metric in "${METRIC_ORDER[@]}"; do
    weight="${requested[$metric]:-}"
    if [[ -z "$weight" ]]; then
      continue
    fi

    if [[ "$metric" == "baseline" ]]; then
      active[$metric]="$weight"
      continue
    fi

    implemented="${METRIC_IMPLEMENTED[$metric]:-0}"
    env_var="${METRIC_ENV_VAR[$metric]:-}"
    note_text="${METRIC_NOTES[$metric]:-}"

    if [[ "$implemented" != "1" ]]; then
      warn "$job_label: $(metric_display_name "$metric") is not implemented yet, so it will be skipped."
      [[ -n "$note_text" ]] && note "$job_label: $note_text"
      continue
    fi

    if [[ -z "$env_var" ]]; then
      warn "$job_label: $(metric_display_name "$metric") does not have a command hook yet, so it will be skipped."
      [[ -n "$note_text" ]] && note "$job_label: $note_text"
      continue
    fi

    active[$metric]="$weight"
    [[ -n "$note_text" ]] && note "$job_label: $note_text"
  done
}

build_job_env() {
  local job_label="$1"
  local repeat_index="$2"
  local repeat_total="$3"
  local active_name="$4"
  local overrides_name="$5"
  local out_name="$6"

  declare -n active="$active_name"
  declare -n overrides="$overrides_name"
  declare -n out_env="$out_name"

  local -A env_map=()
  local -a env_order=()

  set_env() {
    local key="$1"
    local value="$2"
    if [[ -z "${env_map[$key]+x}" ]]; then
      env_order+=("$key")
    fi
    env_map["$key"]="$value"
  }

  local key
  for key in "${PARAMETER_ORDER[@]}"; do
    if [[ -n "${!key+x}" ]]; then
      set_env "$key" "${!key}"
    fi
  done

  for key in "${!overrides[@]}"; do
    set_env "$key" "${overrides[$key]}"
  done

  local base_seed="${env_map[SEED]:-}"
  local seed_step="${env_map[REPEAT_SEED_STEP]:-1}"
  if [[ "$base_seed" =~ ^-?[0-9]+$ && "$seed_step" =~ ^-?[0-9]+$ ]]; then
    set_env "SEED" "$((base_seed + (repeat_index - 1) * seed_step))"
  fi

  set_env "RUN_ROOT" "$RUN_ROOT"
  set_env "RUN_NAME" "$job_label"
  set_env "REPEAT_INDEX" "$repeat_index"
  set_env "REPEAT_TOTAL" "$repeat_total"

  for key in "${BASELINE_WEIGHT_ORDER[@]}"; do
    set_env "$key" "${BASELINE_REWARD_WEIGHTS[$key]}"
  done

  for key in "${METRIC_ORDER[@]}"; do
    if [[ "$key" == "baseline" ]]; then
      continue
    fi

    if [[ -n "${active[$key]:-}" ]]; then
      local env_var="${METRIC_ENV_VAR[$key]:-}"
      if [[ -n "$env_var" ]]; then
        set_env "$env_var" "${active[$key]}"
      fi
    fi
  done

  for key in "${SECRET_ENV_KEYS[@]}"; do
    if [[ -n "${!key+x}" ]]; then
      set_env "$key" "${!key}"
    fi
  done

  out_env=()
  for key in "${env_order[@]}"; do
    out_env+=("$key=${env_map[$key]}")
  done
}

build_step_env() {
  local job_label="$1"
  local step_name="$2"
  local test_mode="$3"
  local job_root="$4"
  local lora_path="$5"
  local job_env_name="$6"
  local out_name="$7"

  declare -n job_env_ref="$job_env_name"
  declare -n out_env="$out_name"

  local step_run_id="${job_label}_${step_name}"
  local log_dir="$job_root/grpo_mvp_logs/$step_run_id"
  local output_dir="$job_root/grpo_mvp_output/$step_run_id"
  local lora_output_dir="$job_root/grpo_mvp_lora/$step_run_id"

  out_env=("${job_env_ref[@]}")
  out_env+=(
    "TEST_MODE=$test_mode"
    "RUN_ID=$step_run_id"
    "LOG_DIR=$log_dir"
    "OUTPUT_DIR=$output_dir"
    "LORA_OUTPUT_DIR=$lora_output_dir"
    "LORA_PATH=$lora_path"
  )
}

print_step_command() {
  local job_root="$1"
  shift
  local -a env_args=("$@")

  printf 'cd %q && env ' "$REPO_ROOT"
  local arg
  for arg in "${env_args[@]}"; do
    mask_env_arg "$arg"
    printf ' '
  done
  printf '%q %q\n' "$PYTHON_BIN" "$TRAIN_SCRIPT"
  printf 'Logs will land under: %s\n' "$job_root"
}

run_step() {
  local job_label="$1"
  local step_name="$2"
  local test_mode="$3"
  local job_root="$4"
  local lora_path="$5"
  local job_env_name="$6"
  local step_log="$7"

  local -a env_args=()
  build_step_env \
    "$job_label" \
    "$step_name" \
    "$test_mode" \
    "$job_root" \
    "$lora_path" \
    "$job_env_name" \
    env_args

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '\n[%s] %s\n' "$job_label" "$step_name"
    print_step_command "$job_root" "${env_args[@]}"
    return 0
  fi

  printf '\n[%s] Starting %s\n' "$job_label" "$step_name"
  printf '[%s] Log: %s\n' "$job_label" "$step_log"
  set +e
  (
    cd "$REPO_ROOT"
    env "${env_args[@]}" "$PYTHON_BIN" "$TRAIN_SCRIPT"
  ) 2>&1 | tee -a "$step_log"
  local status=${PIPESTATUS[0]}
  set -e
  if [[ "$status" -ne 0 ]]; then
    die "Job '$job_label' failed during step '$step_name' with exit code $status. See $step_log"
  fi
}

copy_artifact() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" ]] || die "Expected artifact not found: $src"
  mkdir -p "$(dirname "$dst")"
  cp -f "$src" "$dst"
}

copy_artifact_if_exists() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" ]] || return 0
  mkdir -p "$(dirname "$dst")"
  cp -f "$src" "$dst"
}

find_trainer_state() {
  local output_dir="$1"
  local root_state="$output_dir/trainer_state.json"
  if [[ -f "$root_state" ]]; then
    printf '%s' "$root_state"
    return 0
  fi

  local latest_state=""
  local latest_step=-1
  local state checkpoint step
  shopt -s nullglob
  for state in "$output_dir"/checkpoint-*/trainer_state.json; do
    [[ -f "$state" ]] || continue
    checkpoint="$(basename "$(dirname "$state")")"
    if [[ "$checkpoint" =~ ^checkpoint-([0-9]+)$ ]]; then
      step="${BASH_REMATCH[1]}"
      if (( 10#$step > latest_step )); then
        latest_step=$((10#$step))
        latest_state="$state"
      fi
    elif [[ -z "$latest_state" ]]; then
      latest_state="$state"
    fi
  done
  shopt -u nullglob

  if [[ -n "$latest_state" ]]; then
    printf '%s' "$latest_state"
    return 0
  fi

  return 1
}

collect_job_artifacts() {
  local job_label="$1"
  local job_root="$2"

  local train_step_id="${job_label}_train"
  local train_logs="$job_root/grpo_mvp_logs/$train_step_id"
  local train_output="$job_root/grpo_mvp_output/$train_step_id"
  local base_train_id="${job_label}_base_train"
  local base_holdout_id="${job_label}_base_holdout"
  local lora_train_id="${job_label}_lora_train"
  local lora_holdout_id="${job_label}_lora_holdout"

  copy_artifact "$train_logs/samples.csv" "$job_root/samples.csv"
  copy_artifact_if_exists "$train_logs/samples.jsonl" "$job_root/samples.jsonl"
  copy_artifact_if_exists "$train_logs/before_after_code.csv" "$job_root/before_after_code.csv"
  local trainer_state
  trainer_state="$(find_trainer_state "$train_output")" || die "Expected trainer_state.json not found in $train_output or its checkpoint-* folders"
  copy_artifact "$trainer_state" "$job_root/trainer_state.json"
  copy_artifact "$job_root/grpo_mvp_logs/$base_train_id/eval_base_train_tasks.csv" "$job_root/eval_base_train_tasks.csv"
  copy_artifact "$job_root/grpo_mvp_logs/$base_holdout_id/eval_base_holdout_tasks.csv" "$job_root/eval_base_holdout_tasks.csv"
  copy_artifact "$job_root/grpo_mvp_logs/$lora_train_id/eval_lora_train_tasks.csv" "$job_root/eval_lora_train_tasks.csv"
  copy_artifact "$job_root/grpo_mvp_logs/$lora_holdout_id/eval_lora_holdout_tasks.csv" "$job_root/eval_lora_holdout_tasks.csv"
}

csv_has_column() {
  local csv_path="$1"
  local column_name="$2"

  [[ -f "$csv_path" ]] || return 1
  local header
  header="$(head -n 1 "$csv_path")"
  [[ "$header" == *"$column_name"* ]]
}

build_dashboard() {
  local job_label="$1"
  local job_root="$2"
  local dashboard_output="$job_root/combined_dashboard.html"

  local train_step_id="${job_label}_train"
  local train_logs="$job_root/grpo_mvp_logs/$train_step_id"
  local trainer_state="$job_root/trainer_state.json"
  local base_train_eval="$job_root/eval_base_train_tasks.csv"
  local base_holdout_eval="$job_root/eval_base_holdout_tasks.csv"
  local lora_train_eval="$job_root/eval_lora_train_tasks.csv"
  local lora_holdout_eval="$job_root/eval_lora_holdout_tasks.csv"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '\n[%s] Dashboard command:\n' "$job_label"
    printf 'cd %q && %q %q --run-dir %q --trainer-state %q --samples %q --eval-file %q --eval-file %q --eval-file %q --eval-file %q --output %q\n' \
      "$REPO_ROOT" \
      "$PYTHON_BIN" \
      "$DASHBOARD_SCRIPT" \
      "$job_root" \
      "$trainer_state" \
      "$train_logs/samples.csv" \
      "$base_train_eval" \
      "$base_holdout_eval" \
      "$lora_train_eval" \
      "$lora_holdout_eval" \
      "$dashboard_output"
    return 0
  fi

  printf '[%s] Building dashboard: %s\n' "$job_label" "$dashboard_output"
  "$PYTHON_BIN" "$DASHBOARD_SCRIPT" \
    --run-dir "$job_root" \
    --trainer-state "$trainer_state" \
    --samples "$train_logs/samples.csv" \
    --eval-file "$base_train_eval" \
    --eval-file "$base_holdout_eval" \
    --eval-file "$lora_train_eval" \
    --eval-file "$lora_holdout_eval" \
    --output "$dashboard_output"
}

build_ai_judge_dashboard() {
  local job_label="$1"
  local job_root="$2"
  local dashboard_output="$job_root/ai_judge_dashboard.html"
  local summary_output="$job_root/AI_JUDGE_SUMMARY.md"
  local samples_csv="$job_root/samples.csv"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '\n[%s] AI judge dashboard command (auto-skips when samples.csv lacks AI judge columns):\n' "$job_label"
    printf 'cd %q && %q %q --result-dir %q\n' \
      "$REPO_ROOT" \
      "$PYTHON_BIN" \
      "$AI_JUDGE_DASHBOARD_SCRIPT" \
      "$job_root"
    return 0
  fi

  if ! csv_has_column "$samples_csv" "ai_judge_status"; then
    note "$job_label: skipping AI judge dashboard (no AI judge columns in $samples_csv)"
    return 0
  fi

  printf '[%s] Building AI judge dashboard: %s\n' "$job_label" "$dashboard_output"
  "$PYTHON_BIN" "$AI_JUDGE_DASHBOARD_SCRIPT" \
    --result-dir "$job_root"
  note "$job_label: AI judge dashboard saved in $job_root as $(basename "$dashboard_output") and $(basename "$summary_output")"
}

print_job_summary() {
  local job_key="$1"
  local job_label="$2"
  local job_root="$3"
  local selected_double_metric="$4"
  local repeat_index="$5"
  local repeat_total="$6"
  local requested_name="$7"
  local active_name="$8"
  local job_params_name="$9"
  local job_env_name="${10}"

  printf '\n%s\n' "============================================================"
  printf 'Job: %s\n' "$job_label"
  printf 'Job key: %s\n' "$job_key"
  printf 'Job root: %s\n' "$job_root"
  printf 'Repeat: %s/%s\n' "$repeat_index" "$repeat_total"
  if [[ "$job_key" == "double-best" ]]; then
    printf 'Selected double metric: %s\n' "$selected_double_metric"
  fi
  print_weight_table "Requested metric weights:" "$requested_name"
  print_weight_table "Active metric weights:" "$active_name"
  local -a job_param_pairs=()
  assoc_to_pairs "$job_params_name" job_param_pairs
  print_env_table "Job parameter overrides:" job_param_pairs "${PARAMETER_ORDER[@]}"
  print_env_table "Effective run parameters:" "$job_env_name" "${PARAMETER_ORDER[@]}"
  printf 'Baseline reward profile:\n'
  local key
  for key in "${BASELINE_WEIGHT_ORDER[@]}"; do
    printf '  %-18s %s\n' "$key" "${BASELINE_REWARD_WEIGHTS[$key]}"
  done
  printf '%s\n' "============================================================"
}

build_job_label() {
  local job_key="$1"
  local double_metric="$2"
  local repeat_index="$3"
  local repeat_total="$4"
  local base_label
  if [[ "$job_key" == "double-best" ]]; then
    base_label="double-best-$double_metric"
  else
    base_label="$job_key"
  fi

  if (( repeat_total > 1 )); then
    printf '%s-run-%02d' "$base_label" "$repeat_index"
  else
    printf '%s' "$base_label"
  fi
}

run_job_instance() {
  local job_key="$1"
  local selected_double_metric="$2"
  local repeat_index="$3"
  local repeat_total="$4"
  local requested_name="$5"
  local active_name="$6"
  local job_params_name="$7"
  local job_label
  job_label="$(build_job_label "$job_key" "$selected_double_metric" "$repeat_index" "$repeat_total")"

  local job_root="$RUN_ROOT/$job_label"
  local -a job_env=()

  build_job_env \
    "$job_label" \
    "$repeat_index" \
    "$repeat_total" \
    "$active_name" \
    "$job_params_name" \
    job_env

  print_job_summary \
    "$job_key" \
    "$job_label" \
    "$job_root" \
    "$selected_double_metric" \
    "$repeat_index" \
    "$repeat_total" \
    "$requested_name" \
    "$active_name" \
    "$job_params_name" \
    job_env

  if [[ "$DRY_RUN" -eq 0 ]]; then
    mkdir -p "$job_root"
  fi

  local train_lora_path="$job_root/grpo_mvp_lora/${job_label}_train"
  local -a steps=(
    "base_train:eval_base:$job_root/base_train.log"
    "base_holdout:eval_base_holdout:$job_root/base_holdout.log"
    "train:train:$job_root/train.log"
    "lora_train:eval_lora:$job_root/lora_train.log"
    "lora_holdout:eval_lora_holdout:$job_root/lora_holdout.log"
  )

  local step_name test_mode step_log
  local step_specs step_lora_path
  for step_specs in "${steps[@]}"; do
    IFS=':' read -r step_name test_mode step_log <<< "$step_specs"
    step_lora_path="$train_lora_path"
    run_step \
      "$job_label" \
      "$step_name" \
      "$test_mode" \
      "$job_root" \
      "$step_lora_path" \
      job_env \
      "$step_log"
  done

  if [[ "$DRY_RUN" -eq 1 ]]; then
    build_dashboard "$job_label" "$job_root"
    build_ai_judge_dashboard "$job_label" "$job_root"
    note "$job_label: dashboards and artifacts would be saved in $job_root"
    return 0
  fi

  collect_job_artifacts "$job_label" "$job_root"
  build_dashboard "$job_label" "$job_root"
  build_ai_judge_dashboard "$job_label" "$job_root"
  note "$job_label: dashboards and artifacts saved in $job_root"
}

run_job() {
  local job_key="$1"
  local selected_double_metric="$2"
  local repeat_total

  repeat_total="$(job_repeat_count "$job_key")"
  if [[ -n "${REPEAT_OVERRIDE:-}" ]]; then
    repeat_total="$REPEAT_OVERRIDE"
  fi

  local job_params_name
  job_params_name="$(job_param_name "$job_key")" || die "Unknown job '$job_key'"
  local base_job_label
  base_job_label="$(build_job_label "$job_key" "$selected_double_metric" 1 1)"

  local -A requested_weights=()
  local -A active_weights=()

  build_requested_weights "$job_key" "$selected_double_metric" requested_weights
  resolve_active_weights "$base_job_label" requested_weights active_weights

  local repeat_index
  for ((repeat_index = 1; repeat_index <= repeat_total; repeat_index++)); do
    run_job_instance \
      "$job_key" \
      "$selected_double_metric" \
      "$repeat_index" \
      "$repeat_total" \
      requested_weights \
      active_weights \
      "$job_params_name"
  done
}

next_run_number() {
  local max=0
  local path name

  shopt -s nullglob
  for path in "$RESULTS_ROOT"/*; do
    [[ -d "$path" ]] || continue
    name="$(basename "$path")"
    [[ "$name" =~ ^[0-9]+$ ]] || continue
    if (( name > max )); then
      max="$name"
    fi
  done
  shopt -u nullglob

  printf '%d' "$((max + 1))"
}

usage() {
  cat <<EOF
Usage:
  $0 --all [--dry-run] [--repeat N] [--double-metric performance|llm-as-judge]
  $0 --job baseline|all-metrics|double-correctness|double-style|double-best [--dry-run] [--repeat N] [--double-metric performance|llm-as-judge]

Options:
  --all                  Run the full experiment matrix.
  --job NAME             Run one named job only.
  --repeat N             Run each selected job N times.
  --double-metric NAME   Pick which remaining metric to double for double-best.
  --dry-run              Print commands and resolved weights without executing them.
  -h, --help             Show this help.

Environment overrides:
  REWARD_EXPERIMENTS_CONFIG, TRAIN_SCRIPT, PYTHON_BIN, DASHBOARD_SCRIPT,
  AI_JUDGE_DASHBOARD_SCRIPT,
  RESULTS_ROOT, RUN_ROOT, MODEL_NAME, LOAD_IN_4BIT, LOAD_IN_8BIT, LOAD_IN_16BIT,
  FULL_FINETUNING, LORA_RANK, LORA_ALPHA, LORA_DROPOUT, LORA_TARGET_MODULES,
  SEED, REPEAT_SEED_STEP, USE_CHAT_TEMPLATE, QWEN_ENABLE_THINKING,
  NUM_GENERATIONS, EVAL_NUM_GENERATIONS, PER_DEVICE_TRAIN_BATCH_SIZE,
  GRADIENT_ACCUMULATION_STEPS, MAX_STEPS, TINY_MAX_STEPS, SAVE_STEPS_TRAIN,
  SAVE_STEPS_TINY, LOGGING_STEPS, AUTO_RESUME, RESUME_FROM_CHECKPOINT,
  SAVE_STRATEGY, SAVE_TOTAL_LIMIT, OPTIM, REPORT_TO, MAX_PROMPT_LENGTH,
  MAX_COMPLETION_LENGTH, LEARNING_RATE, CODE_RUN_TIMEOUT_SECONDS,
  CODE_RUN_CPU_SECONDS, CODE_RUN_MEMORY_MB, CODE_RUN_USE_RESOURCE_LIMITS,
  RUFF_COMMAND, RUFF_SELECT, STYLE_PENALTY_BUDGET, LIGHT_PENALTY_CODES,
  TRAIN_TASK_START, TRAIN_TASK_END, HOLDOUT_TASK_START, HOLDOUT_TASK_END,
  TINY_TASK_START, TINY_TASK_END, REWARD_PROFILE, PERFORMANCE_REPEATS,
  PERFORMANCE_TIMEOUT_SECONDS, PERFORMANCE_RUNTIME_WEIGHT,
  PERFORMANCE_MEMORY_WEIGHT, PERFORMANCE_NOISE_TOLERANCE, AI_JUDGE_BASE_URL,
  AI_JUDGE_MODEL, AI_JUDGE_TEMPERATURE, AI_JUDGE_TOP_P, AI_JUDGE_MAX_TOKENS,
  AI_JUDGE_TIMEOUT_SECONDS, AI_JUDGE_SEED, AI_JUDGE_REQUIRE_TEST_PASS,
  AI_JUDGE_MOCK, AI_JUDGE_MAX_FINDINGS, AI_JUDGE_LOW_PENALTY,
  AI_JUDGE_MEDIUM_PENALTY, AI_JUDGE_HIGH_PENALTY,
  AI_JUDGE_CRITICAL_PENALTY, DOUBLE_METRIC

AI_JUDGE_API_KEY is read from .env when present and is not echoed in dry-run
command output. AI_JUDGE_DASHBOARD_SCRIPT defaults to
build_run13_ai_judge_dashboard.py.

Config file:
  configs/reward_experiments.sh holds DEFAULT_RUN_ENV, JOB_PARAM_OVERRIDES_*,
  and JOB_REPEAT_COUNTS for the shared experiment setup.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

CONFIG_DIR="configs"
DEFAULT_CONFIG_FILE="$CONFIG_DIR/reward_experiments.sh"
CONFIG_FILE="${REWARD_EXPERIMENTS_CONFIG:-$DEFAULT_CONFIG_FILE}"

PYTHON_BIN="${PYTHON_BIN:-python}"
TRAIN_SCRIPT="${TRAIN_SCRIPT:-train.py}"
DASHBOARD_SCRIPT="${DASHBOARD_SCRIPT:-plot_training_conrad_toggle.py}"
AI_JUDGE_DASHBOARD_SCRIPT="${AI_JUDGE_DASHBOARD_SCRIPT:-build_run13_ai_judge_dashboard.py}"
RESULTS_ROOT="${RESULTS_ROOT:-results}"

if [[ ! -f "$DEFAULT_CONFIG_FILE" ]]; then
  die "Default config file not found: $DEFAULT_CONFIG_FILE"
fi

# shellcheck source=/dev/null
source "$DEFAULT_CONFIG_FILE"

if [[ "$CONFIG_FILE" != "$DEFAULT_CONFIG_FILE" ]]; then
  [[ -f "$CONFIG_FILE" ]] || die "Config file not found: $CONFIG_FILE"
  # shellcheck source=/dev/null
  source "$CONFIG_FILE"
fi

for required_var in \
  DEFAULT_RUN_ENV \
  BASELINE_REWARD_WEIGHTS \
  METRIC_ENV_VAR \
  METRIC_IMPLEMENTED \
  METRIC_NOTES \
  METRIC_ORDER \
  BASELINE_WEIGHT_ORDER \
  JOB_WEIGHTS_BASELINE \
  JOB_WEIGHTS_ALL_METRICS \
  JOB_WEIGHTS_DOUBLE_CORRECTNESS \
  JOB_WEIGHTS_DOUBLE_STYLE \
  JOB_WEIGHTS_DOUBLE_BEST_BASE \
  JOB_PARAM_OVERRIDES_BASELINE \
  JOB_PARAM_OVERRIDES_ALL_METRICS \
  JOB_PARAM_OVERRIDES_DOUBLE_CORRECTNESS \
  JOB_PARAM_OVERRIDES_DOUBLE_STYLE \
  JOB_PARAM_OVERRIDES_DOUBLE_BEST_BASE \
  JOB_REPEAT_COUNTS
do
  declare -p "$required_var" >/dev/null 2>&1 || die "Missing required config variable: $required_var"
done

load_optional_env_file ".env"

load_default_run_env DEFAULT_RUN_ENV

if [[ ! -f "$TRAIN_SCRIPT" ]]; then
  die "TRAIN_SCRIPT does not exist: $TRAIN_SCRIPT"
fi

if [[ ! -f "$DASHBOARD_SCRIPT" ]]; then
  die "DASHBOARD_SCRIPT does not exist: $DASHBOARD_SCRIPT"
fi

if [[ ! -f "$AI_JUDGE_DASHBOARD_SCRIPT" ]]; then
  die "AI_JUDGE_DASHBOARD_SCRIPT does not exist: $AI_JUDGE_DASHBOARD_SCRIPT"
fi

JOB_MODE=""
SELECTED_JOB=""
DOUBLE_METRIC="${DOUBLE_METRIC:-performance}"
REPEAT_OVERRIDE=""
DRY_RUN=0
ALL_REQUESTED=0
JOB_REQUESTED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      [[ "$JOB_REQUESTED" -eq 0 ]] || die "Use either --all or --job NAME, not both."
      JOB_MODE="all"
      ALL_REQUESTED=1
      shift
      ;;
    --job)
      [[ $# -ge 2 ]] || die "--job requires a value"
      [[ "$ALL_REQUESTED" -eq 0 ]] || die "Use either --all or --job NAME, not both."
      JOB_MODE="one"
      JOB_REQUESTED=1
      SELECTED_JOB="$(normalize_token "$2")"
      shift 2
      ;;
    --job=*)
      [[ "$ALL_REQUESTED" -eq 0 ]] || die "Use either --all or --job NAME, not both."
      JOB_MODE="one"
      JOB_REQUESTED=1
      SELECTED_JOB="$(normalize_token "${1#*=}")"
      shift
      ;;
    --double-metric)
      [[ $# -ge 2 ]] || die "--double-metric requires a value"
      DOUBLE_METRIC="$(normalize_token "$2")"
      shift 2
      ;;
    --double-metric=*)
      DOUBLE_METRIC="$(normalize_token "${1#*=}")"
      shift
      ;;
    --repeat)
      [[ $# -ge 2 ]] || die "--repeat requires a value"
      [[ "$2" =~ ^[0-9]+$ ]] || die "--repeat must be a positive integer"
      (( 10#$2 > 0 )) || die "--repeat must be a positive integer"
      REPEAT_OVERRIDE="$2"
      shift 2
      ;;
    --repeat=*)
      REPEAT_OVERRIDE="${1#*=}"
      [[ "$REPEAT_OVERRIDE" =~ ^[0-9]+$ ]] || die "--repeat must be a positive integer"
      (( 10#$REPEAT_OVERRIDE > 0 )) || die "--repeat must be a positive integer"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

if [[ -z "$JOB_MODE" ]]; then
  die "Specify either --all or --job NAME"
fi

if [[ -n "${RUN_ROOT:-}" ]]; then
  RUN_ROOT="${RUN_ROOT%/}"
else
  RUN_NUMBER="$(next_run_number)"
  RUN_ROOT="$RESULTS_ROOT/$RUN_NUMBER"
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$RUN_ROOT"
fi

printf 'Results root: %s\n' "$RESULTS_ROOT"
printf 'Run folder: %s\n' "$RUN_ROOT"
printf 'Default entrypoint: %s\n' "$TRAIN_SCRIPT"
printf 'Dashboard builder: %s\n' "$DASHBOARD_SCRIPT"

if [[ "$JOB_MODE" == "all" ]]; then
  JOB_SEQUENCE=(baseline all-metrics double-correctness double-style double-best)
  for job_key in "${JOB_SEQUENCE[@]}"; do
    run_job "$job_key" "$DOUBLE_METRIC"
  done
else
  case "$SELECTED_JOB" in
    baseline|all-metrics|double-correctness|double-style|double-best)
      run_job "$SELECTED_JOB" "$DOUBLE_METRIC"
      ;;
    *)
      die "Unknown job '$SELECTED_JOB'. Valid jobs: baseline, all-metrics, double-correctness, double-style, double-best"
      ;;
  esac
fi

printf '\nAll requested jobs finished successfully.\n'
printf 'Run root: %s\n' "$RUN_ROOT"
