# Qwen3.6 GRPO Adaptation

This project now uses `train_conrad.py` for the Qwen3.6 GRPO path.

## Why this differs from the basic Unsloth guide

- Qwen3.6 is a Qwen3.5-style hybrid reasoning model, so the prompt should use the model chat template instead of the old DeepSeek/CodeLlama Alpaca-style plain prompt.
- Qwen3.6 runs in thinking mode by default. This script disables thinking by default with `enable_thinking=False` when the tokenizer supports it, then primes the assistant turn with `<code>\n` so the reward extractor still expects the model to finish with `</code>`.
- For GRPO, keep `fast_inference=False`. The Unsloth Qwen3.5 RL note says to use Unsloth inference for this family when vLLM is not the supported path.
- For Qwen3.6-35B-A3B, use `FastModel`, not `FastLanguageModel`. The script also disables vision-layer LoRA because the HumanEval task is text-only.

## Default RTX 3090 run

```powershell
$env:TEST_MODE="train"
python train_conrad.py
```

Default model:

```text
unsloth/Qwen3.6-27B
```

This is configured as 4-bit LoRA by default:

```text
LOAD_IN_16BIT=0
LOAD_IN_4BIT=1
LOAD_IN_8BIT=0
NUM_GENERATIONS=2
EVAL_NUM_GENERATIONS=2
MAX_COMPLETION_LENGTH=384
```

## Larger MoE option

```powershell
$env:MODEL_NAME="unsloth/Qwen3.6-35B-A3B"
$env:LOAD_IN_16BIT="1"
$env:LOAD_IN_4BIT="0"
$env:TEST_MODE="train"
python train_conrad.py
```

Only use this on a machine with substantially more VRAM than a single RTX 3090.

## More conservative memory escape hatch

If the default 3090 run still runs out of memory:

```powershell
$env:NUM_GENERATIONS="2"
$env:MAX_COMPLETION_LENGTH="256"
python train_conrad.py
```

Treat this as a stability run and compare against the default 384-token completion length if the machine can fit it.
