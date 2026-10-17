# Paper Comparison Notes

This file tracks differences between the taxonomy paper/replication package and the current GRPO experiment so they can be aligned later for comparison.

## Paper / Replication Baseline

- Models:
  - `meta-llama/CodeLlama-7b-hf`
  - `google/codegemma-7b`
  - `deepseek-ai/deepseek-coder-6.7b-base`
- Dataset:
  - HumanEval+ according to the paper.
  - Local replication CSVs contain 164 rows per model.
- Prompt style:
  - Continuation-style HumanEval prompt.
  - The saved CSV prompts are raw function prefixes/docstrings.
  - No `<code>` tags, no chat template, and no explicit system prompt are visible in the saved outputs.
- Generation style:
  - `transformers.pipeline("text-generation")`.
  - The stored `result` includes the original prompt plus the model continuation.
  - Temperature is reported as `0` in the paper.
  - The paper says it followed the default Hugging Face configuration for each model.
- Extraction/evaluation:
  - Extracts the generated Python method from the full generated text.
  - Records `compiled` and `passed` in the CSVs.
  - Uses GPT-4o-mini as a judge for inefficiency labels/regressions.

## Current GRPO Experiment

- Model:
  - Default: `unsloth/Qwen3.6-35B-A3B`
  - Override with `MODEL_NAME`, for example `unsloth/Qwen3.6-27B`.
  - This differs from the paper's `CodeLlama-7b-hf`.
- Dataset:
  - `openai/openai_humaneval`, split `test`.
  - Training defaults to examples 0-49, with 50-99 reserved for holdout evaluation.
- Prompt style:
  - Qwen chat template with thinking disabled by default.
  - Instruction/system prompt plus `### Instruction` / `### Response`.
  - Response is primed with `<code>`.
  - Extraction currently requires a closing `</code>` tag.
- Training:
  - Uses Unsloth `FastModel` + LoRA + TRL `GRPOTrainer`.
  - Qwen3.6 GRPO uses `fast_inference=False`.
  - `num_generations = 4`.
  - `max_completion_length = 512`.
- Rewards:
  - `reward_has_format`: `1.0` when `</code>` appears, else `0.0`.
  - `reward_code_compiles`: `0.0` for extraction/blocklist/syntax failure, `0.5` for runtime error, `1.0` for successful subprocess execution.
  - `reward_humaneval_tests`: `1.0` when the generated function passes the HumanEval tests, else `0.0`.
  - Execution runs in a temporary empty directory with a subprocess timeout.
  - `resource.setrlimit` CPU/memory caps are opt-in because they caused `returncode=-9` false negatives on the HPC.
  - Default execution settings are `CODE_RUN_TIMEOUT_SECONDS=8`, `CODE_RUN_USE_RESOURCE_LIMITS=0`, and `CODE_RUN_MEMORY_MB=0`.
  - To re-enable CPU/memory limits later, set `CODE_RUN_USE_RESOURCE_LIMITS=1`, optionally with `CODE_RUN_CPU_SECONDS` and `CODE_RUN_MEMORY_MB`.
- Diagnostics:
  - Logs full completions to `grpo_mvp_logs/<run_id>/samples.jsonl`.
  - Logs spreadsheet-friendly summaries to `grpo_mvp_logs/<run_id>/samples.csv`.

## Alignment Steps For Fair Comparison

- Add model/config switches for the remaining paper models if they need to be rerun without editing code.
- Add a HumanEval continuation prompt mode with no tags.
- Add extraction compatible with the paper output shape: prompt plus continuation, then extracted method.
- Add HumanEval/HumanEval+ unit-test reward or at least post-training evaluation.
- Keep RL rewards separate from final evaluation metrics:
  - Training reward measures what GRPO optimized.
  - Evaluation should report compile rate, pass rate, and inefficiency labels in the paper's format.
- Run a no-RL baseline with the same local script/config before comparing LoRA-adapted checkpoints.

## Current Interpretation Cautions

- `trainer_state.json` is a training log, not the final research result.
- `reward` in `trainer_state.json` is the mean reward observed during sampled training generations.
- If `completions/clipped_ratio` is high, generations are hitting `max_completion_length` before an EOS/stop condition.
- If `frac_reward_zero_std` is `1.0`, every generation in a GRPO group received the same reward, so the trainer has little or no preference signal for that step.
- If old logs show `reward_has_code_block` or `reward_has_reasoning`, they came from an earlier reward setup, not the current `train_conrad.py`.
