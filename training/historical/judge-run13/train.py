"""
train.py

GRPO training for Qwen3.6 with Unsloth.

Main modes:
- train
- eval_base
- eval_base_holdout
- eval_lora
- eval_lora_holdout
- sanity_reward
- tiny_overfit_train
- eval_lora_tiny

Example usage:

1. Check reward/evaluation code:
   TEST_MODE=sanity_reward python train.py

2. Evaluate base model on training tasks 0-49:
   TEST_MODE=eval_base python train.py

3. Train normally:
   TEST_MODE=train python train.py

4. Evaluate trained LoRA on training tasks 0-49:
   TEST_MODE=eval_lora LORA_PATH=grpo_mvp_lora python train.py

5. Evaluate trained LoRA on unseen holdout tasks 50-99:
   TEST_MODE=eval_lora_holdout LORA_PATH=grpo_mvp_lora python train.py

6. Tiny overfit test:
   TEST_MODE=tiny_overfit_train python train.py

7. Evaluate tiny overfit LoRA:
   TEST_MODE=eval_lora_tiny LORA_PATH=grpo_mvp_lora python train.py
"""

import unsloth


import ast
import hashlib
import re
import shlex
import statistics
import subprocess
import urllib.error
import urllib.request

try:
    import resource
except ImportError:
    resource = None

import sys
import os
import shutil
import csv
import json
import tempfile
from datetime import datetime

try:
    import transformers.utils.hub as transformers_hub
    from huggingface_hub.constants import HF_HUB_CACHE

    if not hasattr(transformers_hub, "TRANSFORMERS_CACHE"):
        transformers_hub.TRANSFORMERS_CACHE = str(HF_HUB_CACHE)
except Exception:
    pass

from unsloth import FastModel
from trl import GRPOConfig, GRPOTrainer
from datasets import load_dataset


# ── 0. Config ──────────────────────────────────────────────────────────────────

MODEL_NAME = os.getenv("MODEL_NAME", "unsloth/Qwen3.6-27B")

MAX_SEQ_LENGTH = int(os.getenv("MAX_SEQ_LENGTH", "2048"))
LOAD_IN_4BIT = os.getenv("LOAD_IN_4BIT", "1") == "1"
LOAD_IN_8BIT = os.getenv("LOAD_IN_8BIT", "0") == "1"
LOAD_IN_16BIT = os.getenv("LOAD_IN_16BIT", "0") == "1"
FULL_FINETUNING = False

if LOAD_IN_4BIT or LOAD_IN_8BIT:
    LOAD_IN_16BIT = False

LORA_RANK = int(os.getenv("LORA_RANK", "16"))
LORA_ALPHA = int(os.getenv("LORA_ALPHA", str(LORA_RANK)))
LORA_TARGET_MODULES = os.getenv("LORA_TARGET_MODULES", "all-linear")
USE_CHAT_TEMPLATE = os.getenv("USE_CHAT_TEMPLATE", "1") == "1"
QWEN_ENABLE_THINKING = os.getenv("QWEN_ENABLE_THINKING", "0") == "1"

TEST_MODE = os.getenv("TEST_MODE", "train")
# Valid modes:
# train
# eval_base
# eval_base_holdout
# eval_lora
# eval_lora_holdout
# sanity_reward
# tiny_overfit_train
# eval_lora_tiny

LORA_PATH = os.getenv("LORA_PATH", "grpo_mvp_lora")
TRAINING_MODES = {"train", "tiny_overfit_train"}

NUM_GENERATIONS = int(os.getenv("NUM_GENERATIONS", "2"))
EVAL_NUM_GENERATIONS = int(os.getenv("EVAL_NUM_GENERATIONS", "2"))

PER_DEVICE_TRAIN_BATCH_SIZE = int(
    os.getenv("PER_DEVICE_TRAIN_BATCH_SIZE", str(NUM_GENERATIONS))
)
GRADIENT_ACCUMULATION_STEPS = int(os.getenv("GRADIENT_ACCUMULATION_STEPS", "1"))

MAX_STEPS = int(os.getenv("MAX_STEPS", "500"))
TINY_MAX_STEPS = int(os.getenv("TINY_MAX_STEPS", "200"))

MAX_PROMPT_LENGTH = int(os.getenv("MAX_PROMPT_LENGTH", "1024"))
MAX_COMPLETION_LENGTH = int(os.getenv("MAX_COMPLETION_LENGTH", "384"))

LEARNING_RATE = float(os.getenv("LEARNING_RATE", "5e-6"))

RUN_TIMEOUT_SECONDS = int(os.getenv("CODE_RUN_TIMEOUT_SECONDS", "8"))
RUN_CPU_SECONDS = int(os.getenv("CODE_RUN_CPU_SECONDS", "8"))
RUN_MEMORY_MB = int(os.getenv("CODE_RUN_MEMORY_MB", "0"))
USE_RESOURCE_LIMITS = os.getenv("CODE_RUN_USE_RESOURCE_LIMITS", "0") == "1"

RUFF_COMMAND = os.getenv("RUFF_COMMAND", "ruff")
RUFF_SELECT = os.getenv("RUFF_SELECT", "E,W")
STYLE_PENALTY_BUDGET = float(os.getenv("STYLE_PENALTY_BUDGET", "10.0"))
LIGHT_PENALTY_CODES = {
    code.strip()
    for code in os.getenv("LIGHT_PENALTY_CODES", "E501,W291,W293").split(",")
    if code.strip()
}

REWARD_FORMAT_WEIGHT = float(os.getenv("REWARD_FORMAT_WEIGHT", "0.1"))
REWARD_SYNTAX_WEIGHT = float(os.getenv("REWARD_SYNTAX_WEIGHT", "0.1"))
REWARD_COMPILE_WEIGHT = float(os.getenv("REWARD_COMPILE_WEIGHT", "0.3"))
REWARD_STYLE_WEIGHT = float(os.getenv("REWARD_STYLE_WEIGHT", "1.0"))
REWARD_TESTS_WEIGHT = float(os.getenv("REWARD_TESTS_WEIGHT", "4.5"))
REWARD_PERFORMANCE_WEIGHT = float(os.getenv("REWARD_PERFORMANCE_WEIGHT", "1.0"))
REWARD_AI_JUDGE_WEIGHT = float(os.getenv("REWARD_AI_JUDGE_WEIGHT", "1.0"))
REWARD_PROFILE = os.getenv("REWARD_PROFILE", "baseline").strip().lower()
AI_JUDGE_REWARD_PROFILES = {
    "judge_only",
    "judge_combined",
    "judge_separate",
    "all_combined",
    "all_separate",
}
VALID_REWARD_PROFILES = {
    "baseline",
    "performance_only",
    "combined",
    "separate",
    *AI_JUDGE_REWARD_PROFILES,
}
if REWARD_PROFILE not in VALID_REWARD_PROFILES:
    raise ValueError(
        f"Unknown REWARD_PROFILE={REWARD_PROFILE}. "
        f"Valid profiles: {sorted(VALID_REWARD_PROFILES)}"
    )

PERFORMANCE_REPEATS = int(os.getenv("PERFORMANCE_REPEATS", "3"))
PERFORMANCE_TIMEOUT_SECONDS = float(os.getenv("PERFORMANCE_TIMEOUT_SECONDS", "2.0"))
PERFORMANCE_RUNTIME_WEIGHT = float(os.getenv("PERFORMANCE_RUNTIME_WEIGHT", "0.8"))
PERFORMANCE_MEMORY_WEIGHT = float(os.getenv("PERFORMANCE_MEMORY_WEIGHT", "0.2"))
PERFORMANCE_NOISE_TOLERANCE = float(
    os.getenv("PERFORMANCE_NOISE_TOLERANCE", "1.10")
)
PERFORMANCE_ENABLED = os.getenv(
    "PERFORMANCE_ENABLED",
    "1" if REWARD_PROFILE in {"performance_only", "combined", "separate", "all_combined", "all_separate"} else "0",
) == "1"

AI_JUDGE_ENABLED = os.getenv(
    "AI_JUDGE_ENABLED",
    "1" if REWARD_PROFILE in AI_JUDGE_REWARD_PROFILES else "0",
) == "1"
AI_JUDGE_BASE_URL = os.getenv("AI_JUDGE_BASE_URL", "http://localhost:11434")
AI_JUDGE_API_KEY = os.getenv("AI_JUDGE_API_KEY", "ollama")
AI_JUDGE_MODEL = os.getenv("AI_JUDGE_MODEL", "qwen3-coder:30b")
AI_JUDGE_TEMPERATURE = float(os.getenv("AI_JUDGE_TEMPERATURE", "0.0"))
AI_JUDGE_TOP_P = float(os.getenv("AI_JUDGE_TOP_P", "1.0"))
AI_JUDGE_MAX_TOKENS = int(os.getenv("AI_JUDGE_MAX_TOKENS", "900"))
AI_JUDGE_TIMEOUT_SECONDS = float(os.getenv("AI_JUDGE_TIMEOUT_SECONDS", "30.0"))
AI_JUDGE_SEED = int(os.getenv("AI_JUDGE_SEED", "3407"))
AI_JUDGE_REQUIRE_TEST_PASS = os.getenv("AI_JUDGE_REQUIRE_TEST_PASS", "1") == "1"
AI_JUDGE_MOCK = os.getenv("AI_JUDGE_MOCK", "0") == "1"
AI_JUDGE_MAX_FINDINGS = int(os.getenv("AI_JUDGE_MAX_FINDINGS", "8"))
AI_JUDGE_LOW_PENALTY = float(os.getenv("AI_JUDGE_LOW_PENALTY", "0.15"))
AI_JUDGE_MEDIUM_PENALTY = float(os.getenv("AI_JUDGE_MEDIUM_PENALTY", "0.35"))
AI_JUDGE_HIGH_PENALTY = float(os.getenv("AI_JUDGE_HIGH_PENALTY", "0.65"))
AI_JUDGE_CRITICAL_PENALTY = float(os.getenv("AI_JUDGE_CRITICAL_PENALTY", "1.0"))
AI_JUDGE_PROMPT_VERSION = "taxonomy_readability_maintainability_v3"
AI_JUDGE_SYSTEM_PROMPT = """You are an expert Python code quality reviewer.
Judge only taxonomy-defined readability and maintainability inefficiencies.
Do not judge functional correctness, runtime performance, imports, syntax, security, or ordinary formatter/linter style unless they directly create one of the listed taxonomy inefficiencies.
Assume the candidate has already been checked by tests when the prompt says so.
Return strict JSON only. Every finding must cite concrete code evidence and one allowed subcategory."""

AI_JUDGE_USER_TEMPLATE = """Evaluate the candidate Python code for this task.

Allowed taxonomy:
- Readability / Confusing Variable Naming: names that actively mislead the reader, shadow common built-ins, reuse the same identifier for different meanings, or create real ambiguity. Do not flag conventional short local loop names such as i, j, idx, idx2, elem, elem2, x, or y when their scope is small and usage is obvious.
- Readability / Sub-readable Code Exists: unnecessarily hard-to-follow code structure, such as avoidable nesting, dense lambdas/maps, or expression chains that reduce comprehension.
- Maintainability / Code Duplication: identical or near-identical code blocks that should be shared or factored because future changes must be repeated.
- Maintainability / Comment Duplication: repeated comments that add no new insight.
- Maintainability / Unnecessary Else: an else branch after a return, break, continue, or raise where removing the else would preserve behavior.
- Maintainability / Unnecessary Conditional Block: a conditional structure that can be simplified without changing behavior, such as returning True/False from an if/else around the same condition.

Rules:
- Report only significant findings that would matter during code review or future maintenance.
- Use the reference solution as calibration: do not flag candidate structure that is similar to the reference unless the candidate introduces additional readability or maintainability debt.
- Do not penalize a different valid algorithm just because it differs from the reference.
- Do not penalize ordinary clear algorithmic structure, such as simple loops, nested loops, pairwise comparisons, or straightforward conditionals.
- Do not mark code as sub-readable merely because a shorter or faster algorithm exists; algorithmic efficiency belongs to the performance reward, not this judge.
- Report "Sub-readable Code Exists" only when a local expression or control-flow choice is unnecessarily hard to understand compared with a simple equivalent in the same algorithm, such as avoidable dense lambdas, chained map/filter/reduce expressions, excessive nesting, or mixed responsibilities.
- Report "Confusing Variable Naming" only for concrete ambiguity, misleading names, built-in shadowing, or confusing identifier reuse. Do not report it merely because a variable name could be more descriptive.
- Do not penalize missing tests, imports, syntax, performance, or task correctness.
- If there are no significant findings in the allowed taxonomy, return an empty findings list.
- Use severity low, medium, high, or critical.
- Use 1-based line numbers from the numbered candidate code.

Return exactly this JSON shape:
{{
  "status": "ok",
  "findings": [
    {{
      "category": "Readability or Maintainability",
      "subcategory": "one allowed subcategory",
      "severity": "low|medium|high|critical",
      "line_start": 1,
      "line_end": 1,
      "evidence": "short quoted or paraphrased evidence",
      "reason": "why this matches the taxonomy"
    }}
  ]
}}

Task:
{task_prompt}

Candidate code with line numbers:
{numbered_code}

Reference solution for context only:
{reference_code}
"""
AI_JUDGE_PROMPT_HASH = hashlib.sha256(
    (
        AI_JUDGE_PROMPT_VERSION
        + "\n"
        + AI_JUDGE_SYSTEM_PROMPT
        + "\n"
        + AI_JUDGE_USER_TEMPLATE
    ).encode("utf-8")
).hexdigest()[:16]

TRAIN_TASK_START = int(os.getenv("TRAIN_TASK_START", "0"))
TRAIN_TASK_END = int(os.getenv("TRAIN_TASK_END", "50"))

HOLDOUT_TASK_START = int(os.getenv("HOLDOUT_TASK_START", "50"))
HOLDOUT_TASK_END = int(os.getenv("HOLDOUT_TASK_END", "100"))

TINY_TASK_START = int(os.getenv("TINY_TASK_START", "0"))
TINY_TASK_END = int(os.getenv("TINY_TASK_END", "5"))

SAFE_EXEC_PREAMBLE = """from typing import *
import functools
from functools import reduce
import math
import re
import itertools
import collections
"""


# ── 1. Output/log setup ────────────────────────────────────────────────────────

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = os.path.join("grpo_mvp_logs", RUN_ID)
os.makedirs(LOG_DIR, exist_ok=True)

JSONL_LOG_PATH = os.path.join(LOG_DIR, "samples.jsonl")
CSV_LOG_PATH = os.path.join(LOG_DIR, "samples.csv")

LOG_FIELDS = [
    "run_id",
    "step",
    "completion_index",
    "task_id",
    "model_name",
    "prompt",
    "raw_completion",
    "extracted_code",
    "format_status",
    "compile_status",
    "runtime_status",
    "failure_reason",
    "error_message",
    "stderr_preview",
    "test_status",
    "test_error_message",
    "test_stderr_preview",
    "syntax_status",
    "style_status",
    "style_score",
    "style_penalty",
    "style_violation_count",
    "style_codes",
    "style_messages",
    "performance_status",
    "performance_score",
    "performance_runtime_score",
    "performance_memory_score",
    "performance_elapsed_ms",
    "performance_reference_ms",
    "performance_peak_kb",
    "performance_reference_peak_kb",
    "performance_error",
    "ai_judge_status",
    "ai_judge_score",
    "ai_judge_findings_count",
    "ai_judge_findings_json",
    "ai_judge_error",
    "ai_judge_model",
    "ai_judge_prompt_version",
    "ai_judge_prompt_hash",
    "reward_format",
    "reward_syntax",
    "reward_style",
    "reward_compile",
    "reward_tests",
    "reward_performance",
    "reward_ai_judge",
    "reward_total",
    "prompt_token_length",
    "completion_token_length",
]

LOG_STATE = {"rows_written": 0}
DIAGNOSTIC_CACHE = {}
PERFORMANCE_REFERENCE_CACHE = {}

with open(CSV_LOG_PATH, "w", newline="", encoding="utf-8") as csv_file:
    csv.DictWriter(csv_file, fieldnames=LOG_FIELDS).writeheader()

print(f"TEST_MODE={TEST_MODE}")
print(f"MODEL_NAME={MODEL_NAME}")
print(f"Create fresh LoRA adapter for training: {TEST_MODE in TRAINING_MODES}")
print(
    "Model loading: "
    f"max_seq_length={MAX_SEQ_LENGTH}, "
    f"load_in_4bit={LOAD_IN_4BIT}, "
    f"load_in_8bit={LOAD_IN_8BIT}, "
    f"load_in_16bit={LOAD_IN_16BIT}, "
    f"full_finetuning={FULL_FINETUNING}, "
    "fast_inference=False"
)
print(
    "LoRA: "
    f"rank={LORA_RANK}, "
    f"alpha={LORA_ALPHA}, "
    f"target_modules={LORA_TARGET_MODULES}"
)
print(
    "Prompting: "
    f"use_chat_template={USE_CHAT_TEMPLATE}, "
    f"qwen_enable_thinking={QWEN_ENABLE_THINKING}"
)
print(
    "Run sizing: "
    f"num_generations={NUM_GENERATIONS}, "
    f"eval_num_generations={EVAL_NUM_GENERATIONS}, "
    f"per_device_train_batch_size={PER_DEVICE_TRAIN_BATCH_SIZE}, "
    f"gradient_accumulation_steps={GRADIENT_ACCUMULATION_STEPS}, "
    f"max_prompt_length={MAX_PROMPT_LENGTH}, "
    f"max_completion_length={MAX_COMPLETION_LENGTH}, "
    f"max_steps={MAX_STEPS}, "
    f"tiny_max_steps={TINY_MAX_STEPS}"
)
print(
    "Reward weights: "
    f"format={REWARD_FORMAT_WEIGHT}, "
    f"syntax={REWARD_SYNTAX_WEIGHT}, "
    f"compile={REWARD_COMPILE_WEIGHT}, "
    f"style={REWARD_STYLE_WEIGHT}, "
    f"tests={REWARD_TESTS_WEIGHT}, "
    f"performance={REWARD_PERFORMANCE_WEIGHT}, "
    f"ai_judge={REWARD_AI_JUDGE_WEIGHT}, "
    f"profile={REWARD_PROFILE}"
)
print(
    "AI judge: "
    f"enabled={AI_JUDGE_ENABLED}, "
    f"mock={AI_JUDGE_MOCK}, "
    f"model={AI_JUDGE_MODEL}, "
    f"require_test_pass={AI_JUDGE_REQUIRE_TEST_PASS}, "
    f"prompt_version={AI_JUDGE_PROMPT_VERSION}, "
    f"prompt_hash={AI_JUDGE_PROMPT_HASH}"
)
print(f"Logging completions to {JSONL_LOG_PATH} and {CSV_LOG_PATH}")


# ── 2. Clean outputs only when training ────────────────────────────────────────
# Important: do NOT delete grpo_mvp_lora when evaluating LoRA.

if TEST_MODE in TRAINING_MODES:
    for d in ["grpo_mvp_output", "grpo_mvp_lora"]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"Cleaned {d}/")


# ── 3. Model loading ───────────────────────────────────────────────────────────

def parse_lora_target_modules(value: str):
    if value in {"all-linear", "all_linear", "all"}:
        return "all-linear"
    return [module.strip() for module in value.split(",") if module.strip()]


def ensure_warnings_issued_attr(loaded_model, max_depth: int = 5):
    seen = set()
    queue = [(loaded_model, 0)]

    while queue:
        candidate, depth = queue.pop(0)
        if candidate is None:
            continue

        candidate_id = id(candidate)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)

        try:
            if not hasattr(candidate, "warnings_issued"):
                candidate.warnings_issued = {}
        except Exception:
            pass

        if depth >= max_depth:
            continue

        for attr_name in ["base_model", "model", "module"]:
            try:
                child = getattr(candidate, attr_name, None)
            except Exception:
                child = None
            if child is not None:
                queue.append((child, depth + 1))


model = None
tokenizer = None

if TEST_MODE != "sanity_reward":
    model, tokenizer = FastModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=LOAD_IN_4BIT,
        load_in_8bit=LOAD_IN_8BIT,
        load_in_16bit=LOAD_IN_16BIT,
        full_finetuning=FULL_FINETUNING,
        fast_inference=False,
    )

    if (
        getattr(tokenizer, "pad_token", None) is None
        and getattr(tokenizer, "eos_token", None) is not None
    ):
        tokenizer.pad_token = tokenizer.eos_token

    if TEST_MODE in TRAINING_MODES:
        model = FastModel.get_peft_model(
            model,
            r=LORA_RANK,
            target_modules=parse_lora_target_modules(LORA_TARGET_MODULES),
            lora_alpha=LORA_ALPHA,
            lora_dropout=0,
            bias="none",
            finetune_vision_layers=False,
            finetune_language_layers=True,
            finetune_attention_modules=True,
            finetune_mlp_modules=True,
            use_gradient_checkpointing="unsloth",
            random_state=3407,
        )
    ensure_warnings_issued_attr(model)


# ── 4. Prompt format ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Python coding assistant.
Return only a complete valid Python solution, then immediately close with </code>.
Do not explain.
Do not include markdown.
Do not include text after </code>.
Do not include examples after the solution."""


def apply_qwen_chat_template(user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        prompt_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=QWEN_ENABLE_THINKING,
        )
    except TypeError:
        prompt_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    return f"{prompt_text}<code>\n"


def format_prompt(example):
    reference_code = example["prompt"] + example["canonical_solution"]
    task_prompt = example["prompt"]
    user_prompt = f"### Instruction:\n{example['prompt']}\n\n### Response:"

    if USE_CHAT_TEMPLATE:
        prompt_text = apply_qwen_chat_template(user_prompt)
    else:
        prompt_text = f"{SYSTEM_PROMPT}\n\n{user_prompt}\n<code>\n"

    return {
        "prompt": prompt_text,
        "task_prompt": task_prompt,
        "reference_code": reference_code,
    }


# ── 5. Dataset splits ──────────────────────────────────────────────────────────

if TEST_MODE == "sanity_reward":
    raw_dataset = None
    train_dataset = None
    holdout_dataset = None
    tiny_dataset = None
    dataset = None
else:
    raw_dataset = load_dataset("openai/openai_humaneval", split="test")

    train_raw = raw_dataset.select(range(TRAIN_TASK_START, TRAIN_TASK_END))
    holdout_raw = raw_dataset.select(range(HOLDOUT_TASK_START, HOLDOUT_TASK_END))
    tiny_raw = raw_dataset.select(range(TINY_TASK_START, TINY_TASK_END))

    train_dataset = train_raw.map(format_prompt)
    holdout_dataset = holdout_raw.map(format_prompt)
    tiny_dataset = tiny_raw.map(format_prompt)

    if TEST_MODE in ["tiny_overfit_train", "eval_lora_tiny"]:
        dataset = tiny_dataset
    elif TEST_MODE in ["eval_base_holdout", "eval_lora_holdout"]:
        dataset = holdout_dataset
    else:
        dataset = train_dataset

    print("\n" + "=" * 60)
    print("DEBUG - raw prompt the model will receive:")
    print("=" * 60)
    print(dataset[0]["prompt"])
    print("=" * 60 + "\n")


# ── 6. Code extraction ─────────────────────────────────────────────────────────

def extract_code(text: str) -> str | None:
    if isinstance(text, list):
        text = " ".join(m["content"] if isinstance(m, dict) else str(m) for m in text)

    if "</code>" in text:
        code = text.split("</code>")[0].strip()
    else:
        code = text.strip()

    if "<code>" in code:
        code = code.split("<code>")[-1].strip()

    return code if len(code.strip()) >= 5 else None


# ── 7. Safety/blocklist ────────────────────────────────────────────────────────

BLOCKED_PATTERNS = [
    r"\bos\s*\.\s*system\b",
    r"\bsubprocess\b",
    r"\bshutil\s*\.\s*rmtree\b",
    r"\bos\s*\.\s*remove\b",
    r"\bos\s*\.\s*unlink\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bopen\s*\(.*['\"]w['\"]",
]


def matched_blocked_pattern(code: str) -> str | None:
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return pattern
    return None


def set_subprocess_limits():
    if resource is None or not USE_RESOURCE_LIMITS:
        return

    resource.setrlimit(resource.RLIMIT_CPU, (RUN_CPU_SECONDS, RUN_CPU_SECONDS))

    if RUN_MEMORY_MB > 0:
        memory_bytes = RUN_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))


def run_python_script(
    script: str,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess:
    preexec_fn = set_subprocess_limits if resource is not None and USE_RESOURCE_LIMITS else None

    with tempfile.TemporaryDirectory(prefix="code_reward_") as tmpdir:
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmpdir,
            timeout=RUN_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds,
            capture_output=True,
            text=True,
            preexec_fn=preexec_fn,
        )


# ── 8. Helpers ─────────────────────────────────────────────────────────────────

PERFORMANCE_RESULT_MARKER = "__CODE_PERFORMANCE_RESULT__="


def performance_benchmark_script(
    code: str,
    test: str,
    entry_point: str,
) -> str:
    """Build a script that times only the generated solution's test execution."""
    return f"""\
{SAFE_EXEC_PREAMBLE}
{code}

{test}

import json as __perf_json
import sys as __perf_sys
import time as __perf_time
import tracemalloc as __perf_tracemalloc

__perf_tracemalloc.start()
__perf_start_ns = __perf_time.perf_counter_ns()
check({entry_point})
__perf_elapsed_ns = __perf_time.perf_counter_ns() - __perf_start_ns
_, __perf_peak_bytes = __perf_tracemalloc.get_traced_memory()
__perf_tracemalloc.stop()
__perf_payload = {{
    "elapsed_ns": __perf_elapsed_ns,
    "peak_bytes": __perf_peak_bytes,
}}
__perf_sys.__stdout__.write(
    "\\n{PERFORMANCE_RESULT_MARKER}" + __perf_json.dumps(__perf_payload) + "\\n"
)
"""


def parse_performance_measurement(stdout: str) -> tuple[int, int]:
    for line in reversed(stdout.splitlines()):
        if line.startswith(PERFORMANCE_RESULT_MARKER):
            payload = json.loads(line[len(PERFORMANCE_RESULT_MARKER) :])
            return int(payload["elapsed_ns"]), int(payload["peak_bytes"])
    raise ValueError("performance result marker was not produced")


def benchmark_code_performance(code: str, test: str, entry_point: str) -> dict:
    """Measure a correct solution repeatedly in isolated subprocesses."""
    elapsed_samples = []
    peak_samples = []
    script = performance_benchmark_script(code, test, entry_point)

    for _ in range(max(1, PERFORMANCE_REPEATS)):
        try:
            result = run_python_script(script, PERFORMANCE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "elapsed_ms": PERFORMANCE_TIMEOUT_SECONDS * 1000.0,
                "peak_kb": 0.0,
                "error": "timeout",
            }
        except Exception as exc:
            return {
                "status": "exception",
                "elapsed_ms": 0.0,
                "peak_kb": 0.0,
                "error": str(exc),
            }

        if result.returncode != 0:
            return {
                "status": "error",
                "elapsed_ms": 0.0,
                "peak_kb": 0.0,
                "error": result.stderr[:500] or f"returncode={result.returncode}",
            }

        try:
            elapsed_ns, peak_bytes = parse_performance_measurement(result.stdout)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "status": "invalid_result",
                "elapsed_ms": 0.0,
                "peak_kb": 0.0,
                "error": str(exc),
            }

        elapsed_samples.append(elapsed_ns)
        peak_samples.append(peak_bytes)

    return {
        "status": "ok",
        "elapsed_ms": statistics.median(elapsed_samples) / 1_000_000.0,
        "peak_kb": statistics.median(peak_samples) / 1024.0,
        "error": "",
    }


def score_code_performance(candidate: dict, reference: dict | None) -> dict:
    """Score runtime and traced Python allocation relative to canonical code."""
    result = {
        "performance_status": candidate.get("status", "not_run"),
        "performance_score": 0.0,
        "performance_runtime_score": 0.0,
        "performance_memory_score": 0.0,
        "performance_elapsed_ms": float(candidate.get("elapsed_ms", 0.0)),
        "performance_reference_ms": 0.0,
        "performance_peak_kb": float(candidate.get("peak_kb", 0.0)),
        "performance_reference_peak_kb": 0.0,
        "performance_error": str(candidate.get("error", "")),
    }

    if candidate.get("status") != "ok":
        return result

    if not reference or reference.get("status") != "ok":
        result["performance_status"] = "reference_unavailable"
        result["performance_error"] = str((reference or {}).get("error", ""))
        return result

    candidate_ms = max(float(candidate["elapsed_ms"]), 1e-9)
    reference_ms = max(float(reference["elapsed_ms"]), 1e-9)
    candidate_kb = max(float(candidate["peak_kb"]), 1e-9)
    reference_kb = max(float(reference["peak_kb"]), 1e-9)

    runtime_score = min(
        1.0,
        PERFORMANCE_NOISE_TOLERANCE * reference_ms / candidate_ms,
    )
    memory_score = min(
        1.0,
        PERFORMANCE_NOISE_TOLERANCE * reference_kb / candidate_kb,
    )
    weight_total = max(
        PERFORMANCE_RUNTIME_WEIGHT + PERFORMANCE_MEMORY_WEIGHT,
        1e-9,
    )
    performance_score = (
        PERFORMANCE_RUNTIME_WEIGHT * runtime_score
        + PERFORMANCE_MEMORY_WEIGHT * memory_score
    ) / weight_total

    result.update(
        {
            "performance_status": "ok",
            "performance_score": performance_score,
            "performance_runtime_score": runtime_score,
            "performance_memory_score": memory_score,
            "performance_reference_ms": reference_ms,
            "performance_reference_peak_kb": reference_kb,
        }
    )
    return result


def normalize_completion(completion) -> str:
    if isinstance(completion, list):
        return " ".join(
            m["content"] if isinstance(m, dict) and "content" in m else str(m)
            for m in completion
        )
    return str(completion)


def token_count(text: str) -> int:
    try:
        encoder = tokenizer if hasattr(tokenizer, "encode") else tokenizer.tokenizer
        return len(encoder.encode(text, add_special_tokens=False))
    except Exception:
        return 0


def value_at(kwargs: dict, key: str, index: int, default: str = ""):
    value = kwargs.get(key, default)

    if isinstance(value, (list, tuple)):
        if not value:
            return default
        if index < len(value):
            return value[index]
        return value[index % len(value)]

    return value


# ── 9. Completion analysis / reward diagnostics ───────────────────────────────

def ruff_penalty(code: str) -> tuple[float, list[str], list[str], str, str]:
    with tempfile.TemporaryDirectory(prefix="style_reward_") as tmpdir:
        code_path = os.path.join(tmpdir, "solution.py")
        with open(code_path, "w", encoding="utf-8") as code_file:
            code_file.write(code.rstrip() + "\n")

        command = [
            *shlex.split(RUFF_COMMAND),
            "check",
            "--select",
            RUFF_SELECT,
            "--output-format",
            "json",
            "--isolated",
            code_path,
        ]

        try:
            result = subprocess.run(
                command,
                cwd=tmpdir,
                timeout=RUN_TIMEOUT_SECONDS,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return STYLE_PENALTY_BUDGET, [], [], "ruff_missing", f"Could not find Ruff command: {RUFF_COMMAND}"
        except subprocess.TimeoutExpired:
            return STYLE_PENALTY_BUDGET, [], [], "ruff_timeout", "Ruff timed out"

    try:
        violations = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return STYLE_PENALTY_BUDGET, [], [], "ruff_json_error", result.stdout[:500]

    if result.returncode not in {0, 1}:
        message = result.stderr[:500] or result.stdout[:500]
        return STYLE_PENALTY_BUDGET, [], [], "ruff_error", message

    codes = []
    messages = []
    penalty = 0.0
    for violation in violations:
        code_id = str(violation.get("code") or "unknown")
        message = str(violation.get("message") or "")
        codes.append(code_id)
        messages.append(f"{code_id}: {message}")
        penalty += 0.5 if code_id in LIGHT_PENALTY_CODES else 1.0

    return penalty, codes, messages, "ok", ""


AI_JUDGE_ALLOWED_SUBCATEGORIES = {
    "Readability": {
        "Confusing Variable Naming",
        "Sub-readable Code Exists",
    },
    "Maintainability": {
        "Code Duplication",
        "Comment Duplication",
        "Unnecessary Else",
        "Unnecessary Conditional Block",
    },
}

AI_JUDGE_SEVERITY_WEIGHTS = {
    "low": AI_JUDGE_LOW_PENALTY,
    "medium": AI_JUDGE_MEDIUM_PENALTY,
    "high": AI_JUDGE_HIGH_PENALTY,
    "critical": AI_JUDGE_CRITICAL_PENALTY,
}

def numbered_python_code(code: str) -> str:
    return "\n".join(
        f"{line_number:>4}: {line}"
        for line_number, line in enumerate(code.splitlines(), start=1)
    )


def build_ai_judge_user_prompt(
    task_prompt: str,
    code: str,
    reference_code: str = "",
) -> str:
    return AI_JUDGE_USER_TEMPLATE.format(
        task_prompt=task_prompt.strip() or "(task prompt unavailable)",
        numbered_code=numbered_python_code(code),
        reference_code=(reference_code.strip() or "(reference solution unavailable)"),
    )


def ai_judge_chat_completions_url() -> str:
    base_url = AI_JUDGE_BASE_URL.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def parse_json_object(text: str) -> dict:
    if isinstance(text, dict):
        return text

    stripped = str(text).strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def call_ollama_ai_judge(
    task_prompt: str,
    code: str,
    reference_code: str = "",
) -> dict:
    payload = {
        "model": AI_JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": AI_JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_ai_judge_user_prompt(
                    task_prompt=task_prompt,
                    code=code,
                    reference_code=reference_code,
                ),
            },
        ],
        "temperature": AI_JUDGE_TEMPERATURE,
        "top_p": AI_JUDGE_TOP_P,
        "max_tokens": AI_JUDGE_MAX_TOKENS,
        "stream": False,
        "seed": AI_JUDGE_SEED,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if AI_JUDGE_API_KEY:
        headers["Authorization"] = f"Bearer {AI_JUDGE_API_KEY}"

    request = urllib.request.Request(
        ai_judge_chat_completions_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=AI_JUDGE_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")

    response_json = json.loads(body)
    content = response_json["choices"][0]["message"]["content"]
    return parse_json_object(content)


def add_mock_finding(
    findings: list[dict],
    category: str,
    subcategory: str,
    severity: str,
    line_start: int,
    line_end: int,
    evidence: str,
    reason: str,
) -> None:
    findings.append(
        {
            "category": category,
            "subcategory": subcategory,
            "severity": severity,
            "line_start": line_start,
            "line_end": line_end,
            "evidence": evidence,
            "reason": reason,
        }
    )


def mock_ai_judge_response(code: str) -> dict:
    findings: list[dict] = []
    lines = code.splitlines()

    for line_number, line in enumerate(lines[:-1], start=1):
        if re.search(r"\breturn\b|\bbreak\b|\bcontinue\b|\braise\b", line):
            next_line = lines[line_number] if line_number < len(lines) else ""
            if re.match(r"\s*else\s*:", next_line):
                add_mock_finding(
                    findings,
                    "Maintainability",
                    "Unnecessary Else",
                    "low",
                    line_number + 1,
                    line_number + 1,
                    next_line.strip(),
                    "The else follows an early exit and can usually be removed without changing behavior.",
                )

    normalized_lines: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if len(stripped) < 18 or stripped.startswith("#"):
            continue
        previous = normalized_lines.get(stripped)
        if previous is not None:
            add_mock_finding(
                findings,
                "Maintainability",
                "Code Duplication",
                "medium",
                previous,
                line_number,
                stripped[:120],
                "The same non-trivial code appears more than once.",
            )
            break
        normalized_lines[stripped] = line_number

    comments = [
        (line_number, line.strip())
        for line_number, line in enumerate(lines, start=1)
        if line.strip().startswith("#")
    ]
    seen_comments: dict[str, int] = {}
    for line_number, comment in comments:
        previous = seen_comments.get(comment)
        if previous is not None:
            add_mock_finding(
                findings,
                "Maintainability",
                "Comment Duplication",
                "low",
                previous,
                line_number,
                comment,
                "The same comment is repeated without adding new information.",
            )
            break
        seen_comments[comment] = line_number

    if "map(" in code and "lambda" in code:
        line_number = next(
            (idx for idx, line in enumerate(lines, start=1) if "map(" in line and "lambda" in line),
            1,
        )
        add_mock_finding(
            findings,
            "Readability",
            "Sub-readable Code Exists",
            "medium",
            line_number,
            line_number,
            lines[line_number - 1].strip()[:120],
            "Dense map/lambda expressions can make short generated solutions harder to review.",
        )

    confusing_names = {"list", "dict", "str", "set", "sum", "max", "min", "input", "id"}
    for line_number, line in enumerate(lines, start=1):
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and match.group(1) in confusing_names:
            add_mock_finding(
                findings,
                "Readability",
                "Confusing Variable Naming",
                "low",
                line_number,
                line_number,
                line.strip(),
                "The variable name shadows a common Python built-in.",
            )
            break

    return {"status": "ok", "findings": findings[:AI_JUDGE_MAX_FINDINGS]}


def code_lines_for_span(code: str, line_start: int, line_end: int) -> str:
    lines = code.splitlines()
    if line_start <= 0 or line_end <= 0:
        return ""
    start_index = max(0, line_start - 1)
    end_index = min(len(lines), max(line_start, line_end))
    return "\n".join(lines[start_index:end_index])


def sanitize_ai_judge_findings(raw_response: dict, code: str = "") -> list[dict]:
    findings = raw_response.get("findings", [])
    if not isinstance(findings, list):
        return []

    sanitized = []
    for finding in findings[:AI_JUDGE_MAX_FINDINGS]:
        if not isinstance(finding, dict):
            continue

        category = str(finding.get("category", "")).strip()
        subcategory = str(finding.get("subcategory", "")).strip()
        severity = str(finding.get("severity", "")).strip().lower()
        if category not in AI_JUDGE_ALLOWED_SUBCATEGORIES:
            continue
        if subcategory not in AI_JUDGE_ALLOWED_SUBCATEGORIES[category]:
            continue
        if severity not in AI_JUDGE_SEVERITY_WEIGHTS:
            continue

        evidence = str(finding.get("evidence", "")).strip()[:300]
        reason = str(finding.get("reason", "")).strip()[:500]
        weak_naming_reason = re.search(
            r"\bnot descriptive\b|\bmore descriptive\b|\bdescriptive enough\b",
            reason,
            re.IGNORECASE,
        )
        conventional_names = re.search(
            r"\b(i|j|idx|idx2|elem|elem2|x|y)\b",
            evidence,
        )
        stronger_naming_issue = re.search(
            r"\bshadow|built-?in|reuse|reused|ambiguous|ambiguity|misleading|"
            r"different meanings|same identifier\b",
            reason,
            re.IGNORECASE,
        )
        if (
            subcategory == "Confusing Variable Naming"
            and weak_naming_reason
            and conventional_names
            and not stronger_naming_issue
        ):
            continue

        try:
            line_start = int(finding.get("line_start", 0))
            line_end = int(finding.get("line_end", line_start))
        except (TypeError, ValueError):
            line_start = 0
            line_end = 0

        span_text = code_lines_for_span(code, line_start, line_end)
        evidence_and_span = f"{evidence}\n{span_text}"
        if subcategory == "Unnecessary Else" and not re.search(
            r"\belse\s*:", evidence_and_span
        ):
            continue

        sanitized.append(
            {
                "category": category,
                "subcategory": subcategory,
                "severity": severity,
                "line_start": max(0, line_start),
                "line_end": max(0, line_end),
                "evidence": evidence,
                "reason": reason,
            }
        )

    return sanitized


def score_ai_judge_findings(findings: list[dict]) -> float:
    penalty = sum(
        AI_JUDGE_SEVERITY_WEIGHTS.get(finding.get("severity", ""), 0.0)
        for finding in findings
    )
    return max(0.0, min(1.0, 1.0 - penalty))


def apply_ai_judge_reward(
    diagnostic: dict,
    task_prompt: str,
    code: str,
    reference_code: str = "",
) -> None:
    diagnostic["ai_judge_model"] = AI_JUDGE_MODEL if AI_JUDGE_ENABLED else ""
    diagnostic["ai_judge_prompt_version"] = AI_JUDGE_PROMPT_VERSION
    diagnostic["ai_judge_prompt_hash"] = AI_JUDGE_PROMPT_HASH

    if not AI_JUDGE_ENABLED:
        diagnostic["ai_judge_status"] = "disabled"
        return

    if AI_JUDGE_REQUIRE_TEST_PASS and diagnostic["test_status"] != "passed":
        diagnostic["ai_judge_status"] = "not_eligible"
        return

    try:
        raw_response = (
            mock_ai_judge_response(code)
            if AI_JUDGE_MOCK
            else call_ollama_ai_judge(task_prompt, code, reference_code)
        )
        findings = sanitize_ai_judge_findings(raw_response, code=code)
        score = score_ai_judge_findings(findings)
        diagnostic["ai_judge_status"] = str(raw_response.get("status", "ok")) or "ok"
        diagnostic["ai_judge_score"] = score
        diagnostic["ai_judge_findings_count"] = len(findings)
        diagnostic["ai_judge_findings_json"] = json.dumps(findings, ensure_ascii=False)
        diagnostic["reward_ai_judge"] = score
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as exc:
        diagnostic["ai_judge_status"] = "error"
        diagnostic["ai_judge_error"] = str(exc)[:500]
    except Exception as exc:
        diagnostic["ai_judge_status"] = "error"
        diagnostic["ai_judge_error"] = f"{type(exc).__name__}: {exc}"[:500]


def analyze_completion(
    completion,
    task_prompt: str = "",
    test: str = "",
    entry_point: str = "",
    reference_code: str = "",
) -> dict:
    text = normalize_completion(completion)
    format_ok = "</code>" in text
    code = extract_code(text)

    diagnostic = {
        "raw_completion": text,
        "extracted_code": code or "",
        "format_status": "ok" if format_ok else "missing_closing_tag",
        "compile_status": "not_checked",
        "runtime_status": "not_run",
        "failure_reason": "",
        "error_message": "",
        "stderr_preview": "",
        "test_status": "not_run",
        "test_error_message": "",
        "test_stderr_preview": "",
        "syntax_status": "not_checked",
        "style_status": "not_checked",
        "style_score": 0.0,
        "style_penalty": 0.0,
        "style_violation_count": 0,
        "style_codes": "",
        "style_messages": "",
        "performance_status": "not_run",
        "performance_score": 0.0,
        "performance_runtime_score": 0.0,
        "performance_memory_score": 0.0,
        "performance_elapsed_ms": 0.0,
        "performance_reference_ms": 0.0,
        "performance_peak_kb": 0.0,
        "performance_reference_peak_kb": 0.0,
        "performance_error": "",
        "ai_judge_status": "not_checked" if AI_JUDGE_ENABLED else "disabled",
        "ai_judge_score": 0.0,
        "ai_judge_findings_count": 0,
        "ai_judge_findings_json": "[]",
        "ai_judge_error": "",
        "ai_judge_model": AI_JUDGE_MODEL if AI_JUDGE_ENABLED else "",
        "ai_judge_prompt_version": AI_JUDGE_PROMPT_VERSION,
        "ai_judge_prompt_hash": AI_JUDGE_PROMPT_HASH,
        "reward_format": 1.0 if format_ok else 0.0,
        "reward_syntax": 0.0,
        "reward_style": 0.0,
        "reward_compile": 0.0,
        "reward_tests": 0.0,
        "reward_performance": 0.0,
        "reward_ai_judge": 0.0,
    }

    if code is None:
        diagnostic["failure_reason"] = "no_code_extracted"
        if AI_JUDGE_ENABLED:
            diagnostic["ai_judge_status"] = "not_eligible"
        return diagnostic

    blocked_pattern = matched_blocked_pattern(code)
    if blocked_pattern:
        diagnostic["compile_status"] = "blocked"
        diagnostic["failure_reason"] = "blocked_pattern"
        diagnostic["error_message"] = blocked_pattern
        if AI_JUDGE_ENABLED:
            diagnostic["ai_judge_status"] = "not_eligible"
        return diagnostic

    try:
        ast.parse(code)
        diagnostic["syntax_status"] = "ok"
        diagnostic["compile_status"] = "ok"
        diagnostic["reward_syntax"] = 1.0
    except SyntaxError as e:
        diagnostic["syntax_status"] = "syntax_error"
        diagnostic["compile_status"] = "syntax_error"
        diagnostic["failure_reason"] = "syntax_error"
        diagnostic["error_message"] = str(e)
        if AI_JUDGE_ENABLED:
            diagnostic["ai_judge_status"] = "not_eligible"
        return diagnostic

    penalty, codes, messages, style_status, error_message = ruff_penalty(code)
    diagnostic["style_status"] = style_status if style_status != "ok" else ("ok" if not codes else "violations")
    diagnostic["style_penalty"] = penalty
    diagnostic["style_violation_count"] = len(codes)
    diagnostic["style_codes"] = ",".join(codes)
    diagnostic["style_messages"] = " | ".join(messages[:20])
    diagnostic["error_message"] = error_message

    if style_status != "ok":
        diagnostic["failure_reason"] = style_status

    style_score = max(0.0, 1.0 - penalty / max(STYLE_PENALTY_BUDGET, 1e-6))
    diagnostic["style_score"] = style_score
    diagnostic["reward_style"] = style_score

    try:
        result = run_python_script(f"{SAFE_EXEC_PREAMBLE}\n{code}")

        if result.returncode == 0:
            diagnostic["runtime_status"] = "ok"
            diagnostic["reward_compile"] = 1.0
        else:
            diagnostic["runtime_status"] = "runtime_error"
            diagnostic["failure_reason"] = diagnostic["failure_reason"] or "runtime_error"
            diagnostic["error_message"] = diagnostic["error_message"] or f"returncode={result.returncode}"
            diagnostic["stderr_preview"] = result.stderr[:500]
            diagnostic["reward_compile"] = 0.5

    except subprocess.TimeoutExpired:
        diagnostic["runtime_status"] = "timeout"
        diagnostic["failure_reason"] = diagnostic["failure_reason"] or "timeout"
        if AI_JUDGE_ENABLED:
            diagnostic["ai_judge_status"] = "not_eligible"
        return diagnostic

    except Exception as exc:
        diagnostic["runtime_status"] = "exception"
        diagnostic["failure_reason"] = diagnostic["failure_reason"] or "exception"
        diagnostic["error_message"] = diagnostic["error_message"] or str(exc)
        if AI_JUDGE_ENABLED:
            diagnostic["ai_judge_status"] = "not_eligible"
        return diagnostic

    if diagnostic["runtime_status"] != "ok" or not test or not entry_point:
        if AI_JUDGE_ENABLED:
            diagnostic["ai_judge_status"] = "not_eligible"
        return diagnostic

    test_script = f"{SAFE_EXEC_PREAMBLE}\n{code}\n\n{test}\n\ncheck({entry_point})"

    try:
        result = run_python_script(test_script)

        if result.returncode == 0:
            diagnostic["test_status"] = "passed"
            diagnostic["reward_tests"] = 1.0
        else:
            diagnostic["test_status"] = "failed"
            diagnostic["test_error_message"] = f"returncode={result.returncode}"
            diagnostic["test_stderr_preview"] = result.stderr[:500]

    except subprocess.TimeoutExpired:
        diagnostic["test_status"] = "timeout"
        diagnostic["test_error_message"] = "timeout"

    except Exception as exc:
        diagnostic["test_status"] = "exception"
        diagnostic["test_error_message"] = str(exc)

    apply_ai_judge_reward(
        diagnostic=diagnostic,
        task_prompt=task_prompt,
        code=code,
        reference_code=reference_code,
    )

    if not PERFORMANCE_ENABLED:
        diagnostic["performance_status"] = "disabled"
        return diagnostic

    if diagnostic["test_status"] != "passed":
        diagnostic["performance_status"] = "not_eligible"
        return diagnostic

    if not reference_code:
        diagnostic["performance_status"] = "reference_unavailable"
        diagnostic["performance_error"] = "reference_code was not provided"
        return diagnostic

    performance_settings = (
        PERFORMANCE_REPEATS,
        PERFORMANCE_TIMEOUT_SECONDS,
        PERFORMANCE_RUNTIME_WEIGHT,
        PERFORMANCE_MEMORY_WEIGHT,
        PERFORMANCE_NOISE_TOLERANCE,
    )
    reference_key = (reference_code, test, entry_point, performance_settings)
    if reference_key not in PERFORMANCE_REFERENCE_CACHE:
        PERFORMANCE_REFERENCE_CACHE[reference_key] = benchmark_code_performance(
            reference_code,
            test,
            entry_point,
        )

    candidate_performance = benchmark_code_performance(
        code,
        test,
        entry_point,
    )
    performance = score_code_performance(
        candidate_performance,
        PERFORMANCE_REFERENCE_CACHE[reference_key],
    )
    diagnostic.update(performance)
    diagnostic["reward_performance"] = diagnostic["performance_score"]

    return diagnostic


def base_reward_from_diagnostic(diagnostic: dict) -> float:
    total = (
        REWARD_FORMAT_WEIGHT * diagnostic["reward_format"]
        + REWARD_SYNTAX_WEIGHT * diagnostic["reward_syntax"]
        + REWARD_COMPILE_WEIGHT * diagnostic["reward_compile"]
        + REWARD_STYLE_WEIGHT * diagnostic["reward_style"]
        + REWARD_TESTS_WEIGHT * diagnostic["reward_tests"]
    )
    return max(0.0, float(total))


def total_reward_from_diagnostic(
    diagnostic: dict,
    include_performance: bool | None = None,
    include_ai_judge: bool | None = None,
) -> float:
    if include_performance is None:
        if REWARD_PROFILE == "performance_only":
            return float(diagnostic["reward_performance"])
        include_performance = REWARD_PROFILE in {
            "combined",
            "separate",
            "all_combined",
            "all_separate",
        }
    if include_ai_judge is None:
        if REWARD_PROFILE == "judge_only":
            return float(diagnostic["reward_ai_judge"])
        include_ai_judge = REWARD_PROFILE in {
            "judge_combined",
            "judge_separate",
            "all_combined",
            "all_separate",
        }
    total = base_reward_from_diagnostic(diagnostic)
    if include_performance:
        total += REWARD_PERFORMANCE_WEIGHT * diagnostic["reward_performance"]
    if include_ai_judge:
        total += REWARD_AI_JUDGE_WEIGHT * diagnostic["reward_ai_judge"]
    return max(0.0, float(total))


def get_completion_diagnostic(index: int, completion, kwargs: dict) -> dict:
    text = normalize_completion(completion)
    task_prompt = value_at(kwargs, "task_prompt", index, "")
    test = value_at(kwargs, "test", index, "")
    entry_point = value_at(kwargs, "entry_point", index, "")
    reference_code = value_at(kwargs, "reference_code", index, "")

    cache_key = (text, task_prompt, test, entry_point, reference_code)

    if cache_key not in DIAGNOSTIC_CACHE:
        DIAGNOSTIC_CACHE[cache_key] = analyze_completion(
            completion,
            task_prompt=task_prompt,
            test=test,
            entry_point=entry_point,
            reference_code=reference_code,
        )

    return DIAGNOSTIC_CACHE[cache_key]


# ── 10. Logging ────────────────────────────────────────────────────────────────

def write_sample_log(row: dict) -> None:
    with open(JSONL_LOG_PATH, "a", encoding="utf-8") as jsonl_file:
        jsonl_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=LOG_FIELDS)
        writer.writerow({field: row.get(field, "") for field in LOG_FIELDS})


def log_completion(index: int, completion, diagnostic: dict, kwargs: dict) -> None:
    row_number = LOG_STATE["rows_written"]

    prompt = value_at(kwargs, "prompts", index, value_at(kwargs, "prompt", index, ""))
    reward_total = total_reward_from_diagnostic(diagnostic)

    row = {
        "run_id": RUN_ID,
        "step": row_number // NUM_GENERATIONS,
        "completion_index": row_number % NUM_GENERATIONS,
        "task_id": value_at(kwargs, "task_id", index, ""),
        "model_name": MODEL_NAME,
        "prompt": prompt,
        "raw_completion": diagnostic["raw_completion"],
        "extracted_code": diagnostic["extracted_code"],
        "format_status": diagnostic["format_status"],
        "compile_status": diagnostic["compile_status"],
        "runtime_status": diagnostic["runtime_status"],
        "failure_reason": diagnostic["failure_reason"],
        "error_message": diagnostic["error_message"],
        "stderr_preview": diagnostic["stderr_preview"],
        "test_status": diagnostic["test_status"],
        "test_error_message": diagnostic["test_error_message"],
        "test_stderr_preview": diagnostic["test_stderr_preview"],
        "syntax_status": diagnostic["syntax_status"],
        "style_status": diagnostic["style_status"],
        "style_score": diagnostic["style_score"],
        "style_penalty": diagnostic["style_penalty"],
        "style_violation_count": diagnostic["style_violation_count"],
        "style_codes": diagnostic["style_codes"],
        "style_messages": diagnostic["style_messages"],
        "performance_status": diagnostic["performance_status"],
        "performance_score": diagnostic["performance_score"],
        "performance_runtime_score": diagnostic["performance_runtime_score"],
        "performance_memory_score": diagnostic["performance_memory_score"],
        "performance_elapsed_ms": diagnostic["performance_elapsed_ms"],
        "performance_reference_ms": diagnostic["performance_reference_ms"],
        "performance_peak_kb": diagnostic["performance_peak_kb"],
        "performance_reference_peak_kb": diagnostic["performance_reference_peak_kb"],
        "performance_error": diagnostic["performance_error"],
        "ai_judge_status": diagnostic["ai_judge_status"],
        "ai_judge_score": diagnostic["ai_judge_score"],
        "ai_judge_findings_count": diagnostic["ai_judge_findings_count"],
        "ai_judge_findings_json": diagnostic["ai_judge_findings_json"],
        "ai_judge_error": diagnostic["ai_judge_error"],
        "ai_judge_model": diagnostic["ai_judge_model"],
        "ai_judge_prompt_version": diagnostic["ai_judge_prompt_version"],
        "ai_judge_prompt_hash": diagnostic["ai_judge_prompt_hash"],
        "reward_format": diagnostic["reward_format"],
        "reward_syntax": diagnostic["reward_syntax"],
        "reward_style": diagnostic["reward_style"],
        "reward_compile": diagnostic["reward_compile"],
        "reward_tests": diagnostic["reward_tests"],
        "reward_performance": diagnostic["reward_performance"],
        "reward_ai_judge": diagnostic["reward_ai_judge"],
        "reward_total": reward_total,
        "prompt_token_length": token_count(prompt),
        "completion_token_length": token_count(normalize_completion(completion)),
    }

    write_sample_log(row)
    LOG_STATE["rows_written"] += 1


# ── 11. Reward function for GRPO ───────────────────────────────────────────────

def _print_reward(diagnostic: dict, score: float, label: str) -> None:
    preview = diagnostic["raw_completion"][:200].replace("\n", "|")
    print(f"  [OUTPUT] {preview}")
    print(
        f"  [{label}] "
        f"score={score} "
        f"format={diagnostic['reward_format']} "
        f"syntax={diagnostic['reward_syntax']} "
        f"compile={diagnostic['reward_compile']} "
        f"tests={diagnostic['reward_tests']} "
        f"style={diagnostic['reward_style']} "
        f"performance={diagnostic['reward_performance']:.4f} "
        f"ai_judge={diagnostic['reward_ai_judge']:.4f} "
        f"ai_judge_status={diagnostic['ai_judge_status']} "
        f"ai_judge_findings={diagnostic['ai_judge_findings_count']} "
        f"elapsed_ms={diagnostic['performance_elapsed_ms']:.4f} "
        f"reference_ms={diagnostic['performance_reference_ms']:.4f} "
        f"peak_kb={diagnostic['performance_peak_kb']:.2f} "
        f"performance_status={diagnostic['performance_status']} "
        f"style_score={diagnostic['style_score']} "
        f"violations={diagnostic['style_violation_count']} "
        f"codes={diagnostic['style_codes'] or 'none'} "
        f"syntax_status={diagnostic['syntax_status']} "
        f"runtime_status={diagnostic['runtime_status']} "
        f"test_status={diagnostic['test_status']} "
        f"style_status={diagnostic['style_status']} "
        f"reason={diagnostic['failure_reason'] or 'none'}"
    )


def reward_combined(completions, **kwargs) -> list[float]:
    """
    Combined reward:
    - small shaping rewards for format, syntax, and runnable code
    - style reward from Ruff/PEP8 quality
    - correctness reward from HumanEval tests

    Default max reward = 6.0 in the baseline profile and 7.0 in combined.
    """
    scores = []

    for index, completion in enumerate(completions):
        diagnostic = get_completion_diagnostic(index, completion, kwargs)
        score = total_reward_from_diagnostic(diagnostic)
        _print_reward(diagnostic, score, "REWARD")

        log_completion(index, completion, diagnostic, kwargs)
        scores.append(score)

    return scores


def reward_correctness_style(completions, **kwargs) -> list[float]:
    scores = []
    for index, completion in enumerate(completions):
        diagnostic = get_completion_diagnostic(index, completion, kwargs)
        score = base_reward_from_diagnostic(diagnostic)
        _print_reward(diagnostic, score, "CORRECTNESS_STYLE")
        log_completion(index, completion, diagnostic, kwargs)
        scores.append(score)
    return scores


def reward_performance(completions, **kwargs) -> list[float]:
    return [
        get_completion_diagnostic(index, completion, kwargs)["reward_performance"]
        for index, completion in enumerate(completions)
    ]


def reward_performance_logged(completions, **kwargs) -> list[float]:
    scores = reward_performance(completions, **kwargs)
    for index, (completion, score) in enumerate(zip(completions, scores)):
        diagnostic = get_completion_diagnostic(index, completion, kwargs)
        _print_reward(diagnostic, score, "PERFORMANCE")
        log_completion(index, completion, diagnostic, kwargs)
    return scores


def reward_ai_judge(completions, **kwargs) -> list[float]:
    return [
        get_completion_diagnostic(index, completion, kwargs)["reward_ai_judge"]
        for index, completion in enumerate(completions)
    ]


def reward_ai_judge_logged(completions, **kwargs) -> list[float]:
    scores = reward_ai_judge(completions, **kwargs)
    for index, (completion, score) in enumerate(zip(completions, scores)):
        diagnostic = get_completion_diagnostic(index, completion, kwargs)
        _print_reward(diagnostic, score, "AI_JUDGE")
        log_completion(index, completion, diagnostic, kwargs)
    return scores


# ── 12. Training config ────────────────────────────────────────────────────────

def make_training_args(mode: str) -> GRPOConfig:
    if mode == "tiny_overfit_train":
        output_dir = "grpo_mvp_output"
        max_steps = TINY_MAX_STEPS
        save_steps = 50
    else:
        output_dir = "grpo_mvp_output"
        max_steps = MAX_STEPS
        save_steps = 100

    return GRPOConfig(
        output_dir=output_dir,
        per_device_train_batch_size=PER_DEVICE_TRAIN_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        max_steps=max_steps,
        learning_rate=LEARNING_RATE,
        save_steps=save_steps,
        logging_steps=1,
        optim="adamw_8bit",
        report_to="none",
        max_prompt_length=MAX_PROMPT_LENGTH,
        max_completion_length=MAX_COMPLETION_LENGTH,
        num_generations=NUM_GENERATIONS,
    )


training_args = make_training_args(TEST_MODE)


# ── 13. Evaluation generation ─────────────────────────────────────────────────

def generate_completion(prompt: str, max_new_tokens: int = MAX_COMPLETION_LENGTH) -> str:
    try:
        FastModel.for_inference(model)
    except Exception:
        pass

    try:
        inputs = tokenizer(
            text=prompt,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_PROMPT_LENGTH,
        ).to(model.device)
    except TypeError:
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_PROMPT_LENGTH,
        ).to(model.device)

    generation_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": True,
        "temperature": 0.8,
        "top_p": 0.95,
    }
    pad_token_id = getattr(tokenizer, "eos_token_id", None)
    if pad_token_id is not None:
        generation_kwargs["pad_token_id"] = pad_token_id

    outputs = model.generate(**inputs, **generation_kwargs)

    input_length = inputs["input_ids"].shape[-1]
    completion_ids = outputs[0][input_length:]
    return tokenizer.decode(completion_ids, skip_special_tokens=True)


def evaluate_model(eval_dataset, label: str, output_path: str):
    rows = []

    print("\n" + "=" * 60)
    print(f"Starting evaluation: {label}")
    print("=" * 60)

    for item_idx, example in enumerate(eval_dataset):
        prompt = example["prompt"]
        task_prompt = example.get("task_prompt", "")
        test = example["test"]
        entry_point = example["entry_point"]
        task_id = example.get("task_id", f"task_{item_idx}")

        for gen_idx in range(EVAL_NUM_GENERATIONS):
            completion = generate_completion(
                prompt,
                max_new_tokens=MAX_COMPLETION_LENGTH,
            )

            diagnostic = analyze_completion(
                completion,
                task_prompt=task_prompt,
                test=test,
                entry_point=entry_point,
                reference_code=example.get("reference_code", ""),
            )

            reward_total = total_reward_from_diagnostic(diagnostic)

            row = {
                "label": label,
                "task_id": task_id,
                "item_idx": item_idx,
                "generation_idx": gen_idx,
                "raw_completion": diagnostic["raw_completion"],
                "extracted_code": diagnostic["extracted_code"],
                "format_status": diagnostic["format_status"],
                "compile_status": diagnostic["compile_status"],
                "runtime_status": diagnostic["runtime_status"],
                "failure_reason": diagnostic["failure_reason"],
                "error_message": diagnostic["error_message"],
                "stderr_preview": diagnostic["stderr_preview"],
                "test_status": diagnostic["test_status"],
                "test_error_message": diagnostic["test_error_message"],
                "test_stderr_preview": diagnostic["test_stderr_preview"],
                "syntax_status": diagnostic["syntax_status"],
                "style_status": diagnostic["style_status"],
                "style_score": diagnostic["style_score"],
                "style_penalty": diagnostic["style_penalty"],
                "style_violation_count": diagnostic["style_violation_count"],
                "style_codes": diagnostic["style_codes"],
                "style_messages": diagnostic["style_messages"],
                "performance_status": diagnostic["performance_status"],
                "performance_score": diagnostic["performance_score"],
                "performance_runtime_score": diagnostic["performance_runtime_score"],
                "performance_memory_score": diagnostic["performance_memory_score"],
                "performance_elapsed_ms": diagnostic["performance_elapsed_ms"],
                "performance_reference_ms": diagnostic["performance_reference_ms"],
                "performance_peak_kb": diagnostic["performance_peak_kb"],
                "performance_reference_peak_kb": diagnostic["performance_reference_peak_kb"],
                "performance_error": diagnostic["performance_error"],
                "ai_judge_status": diagnostic["ai_judge_status"],
                "ai_judge_score": diagnostic["ai_judge_score"],
                "ai_judge_findings_count": diagnostic["ai_judge_findings_count"],
                "ai_judge_findings_json": diagnostic["ai_judge_findings_json"],
                "ai_judge_error": diagnostic["ai_judge_error"],
                "ai_judge_model": diagnostic["ai_judge_model"],
                "ai_judge_prompt_version": diagnostic["ai_judge_prompt_version"],
                "ai_judge_prompt_hash": diagnostic["ai_judge_prompt_hash"],
                "reward_format": diagnostic["reward_format"],
                "reward_syntax": diagnostic["reward_syntax"],
                "reward_style": diagnostic["reward_style"],
                "reward_compile": diagnostic["reward_compile"],
                "reward_tests": diagnostic["reward_tests"],
                "reward_performance": diagnostic["reward_performance"],
                "reward_ai_judge": diagnostic["reward_ai_judge"],
                "reward_total": reward_total,
                "completion_token_length": token_count(completion),
            }

            rows.append(row)

            print(
                f"[{label}] "
                f"task={task_id} "
                f"gen={gen_idx} "
                f"reward={reward_total} "
                f"format={diagnostic['format_status']} "
                f"syntax={diagnostic['syntax_status']} "
                f"style={diagnostic['style_status']} "
                f"violations={diagnostic['style_violation_count']} "
                f"ai_judge={diagnostic['ai_judge_status']} "
                f"ai_judge_score={diagnostic['ai_judge_score']:.3f} "
                f"reason={diagnostic['failure_reason'] or 'none'}"
            )

    if not rows:
        print("No rows generated.")
        return

    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    format_ok = sum(1 for r in rows if r["format_status"] == "ok")
    syntax_ok = sum(1 for r in rows if r["syntax_status"] == "ok")
    style_ok = sum(1 for r in rows if r["style_status"] == "ok")
    test_passed = sum(1 for r in rows if r["test_status"] == "passed")
    passed_and_style_clean = sum(
        1 for r in rows if r["test_status"] == "passed" and r["style_status"] == "ok"
    )
    avg_reward = sum(float(r["reward_total"]) for r in rows) / len(rows)
    avg_style = sum(float(r["style_score"]) for r in rows) / len(rows)
    judged_rows = [r for r in rows if r["ai_judge_status"] == "ok"]
    avg_ai_judge = (
        sum(float(r["ai_judge_score"]) for r in judged_rows) / len(judged_rows)
        if judged_rows
        else 0.0
    )
    performance_rows = [r for r in rows if r["performance_status"] == "ok"]
    avg_performance = (
        sum(float(r["performance_score"]) for r in performance_rows) / len(performance_rows)
        if performance_rows
        else 0.0
    )
    avg_len = sum(int(r["completion_token_length"]) for r in rows) / len(rows)

    print("\n" + "=" * 60)
    print(f"Evaluation summary: {label}")
    print("=" * 60)
    print(f"Rows: {len(rows)}")
    print(f"Avg reward: {avg_reward:.3f}")
    print(f"Avg style score: {avg_style:.3f}")
    print(f"Avg AI judge score (judged solutions): {avg_ai_judge:.3f}")
    print(f"Avg performance score (correct solutions): {avg_performance:.3f}")
    print(f"Format OK rate: {format_ok / len(rows):.2%}")
    print(f"Syntax OK rate: {syntax_ok / len(rows):.2%}")
    print(f"Style OK rate: {style_ok / len(rows):.2%}")
    print(f"Test pass rate: {test_passed / len(rows):.2%}")
    print(f"Pass + style clean rate: {passed_and_style_clean / len(rows):.2%}")
    print(f"Avg completion length: {avg_len:.1f}")
    print(f"Saved to: {output_path}")


# ── 14. Reward/evaluator sanity check ──────────────────────────────────────────

def sanity_check_reward_code():
    """
    Checks whether your style evaluator rewards known-good and known-bad completions correctly.
    """
    raw = load_dataset("openai/openai_humaneval", split="test")
    example = raw[0]

    # HumanEval canonical_solution is usually the solution body.
    # example["prompt"] + example["canonical_solution"] forms complete code.
    correct_code = example["prompt"] + example["canonical_solution"]

    correct_completion = correct_code + "\n</code>"
    syntax_error_completion = "def broken(:\n    pass\n</code>"
    missing_tag_completion = "def whatever():\n    return 1"
    duplicated_but_correct_completion = """def has_close_elements(numbers, threshold):
    for i in range(len(numbers)):
        for j in range(len(numbers)):
            if i != j:
                distance = abs(numbers[i] - numbers[j])
                if distance < threshold:
                    return True
    for i in range(len(numbers)):
        for j in range(len(numbers)):
            if i != j:
                distance = abs(numbers[i] - numbers[j])
                if distance < threshold:
                    return True
    return False
</code>"""

    cases = [
        ("correct_canonical_solution", correct_completion),
        ("syntax_error", syntax_error_completion),
        ("missing_closing_tag", missing_tag_completion),
    ]
    if AI_JUDGE_ENABLED and AI_JUDGE_MOCK:
        cases.append(("duplicated_but_correct_mock_judge", duplicated_but_correct_completion))

    for name, completion in cases:
        diagnostic = analyze_completion(
            completion,
            task_prompt=example["prompt"],
            test=example["test"],
            entry_point=example["entry_point"],
            reference_code=correct_code,
        )

        reward_total = total_reward_from_diagnostic(diagnostic)

        print("\n" + "-" * 60)
        print(name)
        print("-" * 60)
        print(f"format_status: {diagnostic['format_status']}")
        print(f"syntax_status: {diagnostic['syntax_status']}")
        print(f"style_status: {diagnostic['style_status']}")
        print(f"style_score: {diagnostic['style_score']}")
        print(f"style_penalty: {diagnostic['style_penalty']}")
        print(f"style_codes: {diagnostic['style_codes'] or 'none'}")
        print(f"compile_status: {diagnostic['compile_status']}")
        print(f"runtime_status: {diagnostic['runtime_status']}")
        print(f"test_status: {diagnostic['test_status']}")
        print(f"failure_reason: {diagnostic['failure_reason'] or 'none'}")
        print(f"reward_format: {diagnostic['reward_format']}")
        print(f"reward_syntax: {diagnostic['reward_syntax']}")
        print(f"reward_style: {diagnostic['reward_style']}")
        print(f"reward_compile: {diagnostic['reward_compile']}")
        print(f"reward_tests: {diagnostic['reward_tests']}")
        print(f"performance_status: {diagnostic['performance_status']}")
        print(f"performance_score: {diagnostic['performance_score']}")
        print(f"performance_elapsed_ms: {diagnostic['performance_elapsed_ms']}")
        print(f"performance_reference_ms: {diagnostic['performance_reference_ms']}")
        print(f"reward_performance: {diagnostic['reward_performance']}")
        print(f"ai_judge_status: {diagnostic['ai_judge_status']}")
        print(f"ai_judge_score: {diagnostic['ai_judge_score']}")
        print(f"ai_judge_findings_count: {diagnostic['ai_judge_findings_count']}")
        print(f"ai_judge_findings_json: {diagnostic['ai_judge_findings_json']}")
        print(f"reward_ai_judge: {diagnostic['reward_ai_judge']}")
        print(f"reward_total: {reward_total}")

    print("\nExpected:")
    print("correct_canonical_solution should pass tests and get reward_total close to max if Ruff finds no E/W issues")
    print("syntax_error should get no syntax/style/compile/test reward")
    print("missing_closing_tag should get no_code_extracted")


def preflight_ai_judge() -> None:
    if not AI_JUDGE_ENABLED:
        return
    if AI_JUDGE_MOCK:
        print("AI judge preflight skipped: AI_JUDGE_MOCK=1")
        return

    print(
        "Checking AI judge endpoint "
        f"model={AI_JUDGE_MODEL} "
        "url=<configured>"
    )
    response = call_ollama_ai_judge(
        task_prompt="Write a function add_one(x) that returns x + 1.",
        code="def add_one(x):\n    return x + 1",
        reference_code="def add_one(x):\n    return x + 1",
    )
    findings = sanitize_ai_judge_findings(
        response,
        code="def add_one(x):\n    return x + 1",
    )
    print(
        "AI judge preflight OK: "
        f"status={response.get('status', 'ok')} "
        f"valid_findings={len(findings)} "
        f"prompt_hash={AI_JUDGE_PROMPT_HASH}"
    )


# ── 15. LoRA loading for eval modes ────────────────────────────────────────────

def load_lora_for_eval():
    global model

    if not os.path.exists(LORA_PATH):
        raise FileNotFoundError(
            f"LoRA path not found: {LORA_PATH}. "
            f"Train first or pass LORA_PATH=/path/to/lora."
        )

    from peft import PeftModel

    print(f"Loading LoRA from: {LORA_PATH}")
    model = PeftModel.from_pretrained(model, LORA_PATH)
    ensure_warnings_issued_attr(model)
    model.eval()

    try:
        FastModel.for_inference(model)
    except Exception:
        pass


# ── 16. Main switch ────────────────────────────────────────────────────────────

if TEST_MODE == "sanity_reward":
    sanity_check_reward_code()
    sys.exit(0)


preflight_ai_judge()


if TEST_MODE == "eval_base":
    evaluate_model(
        train_dataset,
        label="base_train_tasks_0_49",
        output_path=os.path.join(LOG_DIR, "eval_base_train_tasks.csv"),
    )
    sys.exit(0)


if TEST_MODE == "eval_base_holdout":
    evaluate_model(
        holdout_dataset,
        label="base_holdout_tasks_50_99",
        output_path=os.path.join(LOG_DIR, "eval_base_holdout_tasks.csv"),
    )
    sys.exit(0)


if TEST_MODE == "eval_lora":
    load_lora_for_eval()

    evaluate_model(
        train_dataset,
        label="lora_train_tasks_0_49",
        output_path=os.path.join(LOG_DIR, "eval_lora_train_tasks.csv"),
    )
    sys.exit(0)


if TEST_MODE == "eval_lora_holdout":
    load_lora_for_eval()

    evaluate_model(
        holdout_dataset,
        label="lora_holdout_tasks_50_99",
        output_path=os.path.join(LOG_DIR, "eval_lora_holdout_tasks.csv"),
    )
    sys.exit(0)


if TEST_MODE == "eval_lora_tiny":
    load_lora_for_eval()

    evaluate_model(
        tiny_dataset,
        label="lora_tiny_tasks_0_4",
        output_path=os.path.join(LOG_DIR, "eval_lora_tiny_tasks.csv"),
    )
    sys.exit(0)


if TEST_MODE in ["train", "tiny_overfit_train"]:
    if TEST_MODE == "tiny_overfit_train":
        print("Running tiny overfit training on HumanEval tasks 0-4.")
        print(f"TINY_MAX_STEPS={TINY_MAX_STEPS}")
    else:
        print("Running normal training on HumanEval tasks 0-49.")

    if REWARD_PROFILE == "performance_only":
        selected_reward_funcs = [reward_performance_logged]
    elif REWARD_PROFILE == "judge_only":
        selected_reward_funcs = [reward_ai_judge_logged]
    elif REWARD_PROFILE == "separate":
        selected_reward_funcs = [reward_correctness_style, reward_performance]
    elif REWARD_PROFILE == "judge_separate":
        selected_reward_funcs = [reward_correctness_style, reward_ai_judge]
    elif REWARD_PROFILE == "all_separate":
        selected_reward_funcs = [
            reward_correctness_style,
            reward_performance,
            reward_ai_judge,
        ]
    else:
        selected_reward_funcs = [reward_combined]

    trainer = GRPOTrainer(
        model=model,
        args=training_args,
        processing_class=tokenizer,
        reward_funcs=selected_reward_funcs,
        train_dataset=dataset,
    )

    print("Starting - watch reward lines each step")
    print("Good sign: more test_status=passed, style_status=ok, and scores close to max over time")
    print(f"Full completion diagnostics: {JSONL_LOG_PATH}")

    trainer.train()

    model.save_pretrained("grpo_mvp_lora")
    tokenizer.save_pretrained("grpo_mvp_lora")

    print("Done.")
    print("Saved LoRA to grpo_mvp_lora")
    sys.exit(0)


raise ValueError(f"Unknown TEST_MODE: {TEST_MODE}")
