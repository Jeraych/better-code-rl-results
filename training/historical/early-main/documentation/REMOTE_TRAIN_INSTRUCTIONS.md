### 1. SSH into the remote machine

```bash
ssh your_username@remote_machine_address
```

Example:

```bash
ssh cang688@hasel-artemis
```

---

### 2. Go to your project folder

```bash
cd /path/to/your/project
```

Example:

```bash
cd ~/Unsloth-RL
```

---

### 3. Check that the files are there

```bash
ls
```

You should see something like:

```bash
train_conrad.py
plot_training.py
```

---

### 4. Activate your Python environment

If the environment does not exist yet, create it first:

```bash
conda create -n unsloth_qwen python=3.11 -y
conda activate unsloth_qwen
python -m pip install -U pip setuptools wheel
python -m pip install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
python -m pip install -U --no-cache-dir -r requirements-remote-qwen.txt
python -m pip install -U --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

If CUDA 12.8 wheels are not supported on the machine, use the CUDA 12.1 wheel index instead:

```bash
conda create -n unsloth_qwen121 python=3.11 -y
conda activate unsloth_qwen121
python -m pip install -U pip setuptools wheel
python -m pip install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python -m pip install -U --no-cache-dir -r requirements-remote-qwen.txt
python -m pip install -U --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

If using Conda:

```bash
conda activate your_env_name
```

Example:

```bash
conda activate unsloth_qwen
```

If using venv:

```bash
source .venv/bin/activate
```

Check that the correct Python environment is active:

```bash
which python
python --version
```

---

### 5. Check GPU is visible

```bash
nvidia-smi
```

You should see the GPU name, current usage, and available VRAM.

For a single RTX 3090, `train_conrad.py` now defaults to the safer 3090 profile:

```text
MODEL_NAME=unsloth/Qwen3.6-27B
LOAD_IN_4BIT=1
LOAD_IN_16BIT=0
NUM_GENERATIONS=2
EVAL_NUM_GENERATIONS=2
MAX_COMPLETION_LENGTH=384
```

---

### 6. Test that the required imports work

```bash
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.version.cuda); print('cuda available:', torch.cuda.is_available())"
```

```bash
python -c "from unsloth import FastModel; print('unsloth ok')"
```

```bash
python - <<'PY'
import transformers.utils.hub as transformers_hub
from huggingface_hub.constants import HF_HUB_CACHE

if not hasattr(transformers_hub, "TRANSFORMERS_CACHE"):
    transformers_hub.TRANSFORMERS_CACHE = str(HF_HUB_CACHE)

from trl import GRPOConfig, GRPOTrainer
print("trl grpo ok")
PY
```

If all of these pass, the environment is ready.

---

### 7. Run foreground checks first

First check the reward/evaluation code without loading the large model:

```bash
TEST_MODE=sanity_reward python "train_conrad.py" 2>&1 | tee terminal_sanity_reward.log
```

Then run a one-step tiny training smoke test. This loads the model and exercises the GRPO training path before you leave the full run unattended:

```bash
TEST_MODE=tiny_overfit_train TINY_MAX_STEPS=1 MAX_COMPLETION_LENGTH=128 python "train_conrad.py" 2>&1 | tee terminal_tiny_smoke.log
```

If both commands finish without an error or CUDA out-of-memory, start the full run.

If the tiny smoke test gets CUDA out-of-memory, retry with a shorter completion length:

```bash
TEST_MODE=tiny_overfit_train TINY_MAX_STEPS=1 MAX_COMPLETION_LENGTH=96 python "train_conrad.py" 2>&1 | tee terminal_tiny_smoke.log
```

To inspect a saved test log:

```bash
less terminal_tiny_smoke.log
```

Quit `less` with:

```text
q
```

---

### 8. Run training remotely without needing SSH to stay connected

Since `tmux` may not be installed and may require `sudo`, use `nohup`.

```bash
nohup env TEST_MODE=train \
  MODEL_NAME="unsloth/Qwen3.6-27B" \
  LOAD_IN_4BIT=1 \
  LOAD_IN_16BIT=0 \
  NUM_GENERATIONS=2 \
  EVAL_NUM_GENERATIONS=2 \
  MAX_COMPLETION_LENGTH=384 \
  python "train_conrad.py" > terminal_train.log 2>&1 &
```

This command:

```bash
nohup
```

keeps the process running after SSH disconnects.

```bash
> terminal_train.log 2>&1
```

saves both normal output and errors into `terminal_train.log`.

```bash
&
```

runs the process in the background.

After this, you can close SSH and turn off your laptop. The training keeps running on the remote machine.

---

### 9. Check that training is running

```bash
ps aux | grep "train_conrad.py"
```

You should see a line like:

```text
cang688  3095605  121  3.7 ... python train_conrad.py
```

The number after your username is the process ID. In this example, the process ID is:

```text
3095605
```

Ignore the line that says:

```text
grep --color=auto train_conrad.py
```

That is just the search command itself.

---

### 10. Watch the training log

```bash
tail -f terminal_train.log
```

Stop watching the log with:

```text
Ctrl + c
```

This does **not** stop training. It only stops showing the live log output.

To see only the latest lines:

```bash
tail -n 100 terminal_train.log
```

To scroll through the whole log:

```bash
less terminal_train.log
```

Quit `less` with:

```text
q
```

---

### 11. Check GPU usage

```bash
nvidia-smi
```

Or watch it update continuously:

```bash
watch -n 1 nvidia-smi
```

Stop watching with:

```text
Ctrl + c
```

---

### 12. Reconnect later and check progress

```bash
ssh your_username@remote_machine_address
```

Then:

```bash
cd ~/Unsloth-RL
ps aux | grep "train_conrad.py"
tail -f terminal_train.log
```

---

### 13. Stop training manually if needed

Find the process ID:

```bash
ps aux | grep "train_conrad.py"
```

Then stop it:

```bash
kill <PID>
```

Example:

```bash
kill 3095605
```

Only use this if it does not stop normally:

```bash
kill -9 <PID>
```

---

### 14. Generate the training dashboard after training finishes

Install Plotly if needed:

```bash
python -m pip install plotly
```

Then run:

```bash
python plot_training.py
```

This should create:

```bash
training_dashboard.html
```

Check that it exists:

```bash
ls -lh training_dashboard.html
```

---

### 15. Important output folders

Your script saves:

```text
terminal_train.log
```

Terminal output from the training run.

```text
grpo_mvp_logs/...
```

Structured completion logs such as `samples.csv` and `samples.jsonl`.

```text
grpo_mvp_output/
```

Trainer checkpoints and trainer state.

```text
grpo_mvp_lora/
```

Final saved LoRA adapter and tokenizer.
