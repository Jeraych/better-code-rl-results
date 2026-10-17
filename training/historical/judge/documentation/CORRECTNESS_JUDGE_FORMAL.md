# Prepared historical correctness + judge experiment

Preparation only: no local judge calls, GPU training, remote connection or push.
Branch: `experiments/correctness-judge-formal`; source baseline:
`8cc4accd0c687a040543a791e472e3f5b236e2e2`.
The two pre-existing dirty checkouts were not edited or copied.

The user's completed local A/B calibration selected the historical instrument:
55% equal-reward groups and mean within-group population SD 0.0393, versus
90% and 0.0130 for the standalone conservative instrument. These are supplied
calibration results, not measurements repeated in this preparation.
The standalone instrument remains calibration-only and is absent from this
formal dependency chain. The private endpoint must request alias `qwen-32b`.
`Qwen2.5-32B-Instruct-AWQ` is recorded separately as the externally confirmed
current backend supplied by the user, not independently queried here.

## Exact source/config changes from 8cc4acc

- `train.py`: imports `judge_reliability`; routes the existing historical
  HTTP request through its retry/schema boundary; validates before sanitizing;
  records successful evaluation statistics; raises on failures instead of
  swallowing them; saves final trainer state after training for health checks.
- `judge_reliability.py`: a stdlib-only transport and structural-validation
  module. It does not implement prompt construction, sanitizer or scoring.
- `configs/correctness_judge_3seeds.sh`: reworked literal configuration based
  on the useful matched settings in the existing draft. One seed per command;
  no standalone mode, external prompt file, copied env, automatic three-seed
  queue or pure-reward option.
- `configs/correctness_judge_smoke.sh`: only `MAX_STEPS=20`. The same 50 training
  and 50 holdout tasks, evaluation stages, support rewards and save interval
  remain in smoke. In particular this is not the draft's five-step/two-task run.
- `run_correctness_judge.sh` and `scripts/formal_judge_run.py`: a small Bash
  entrypoint and stdlib orchestrator replace the draft's generic queue path.
  This avoids endpoint values in printed shell commands and records complete
  per-stage settings. The committed generic queue launcher is unchanged.
- `.gitignore`: ignores the two new run roots, connectivity outputs and lock;
  the existing `.env` ignore rule is retained.
- `tests/test_formal_judge.py`: offline transport, scoring-equivalence,
  isolation/configuration, dry-run, health and preceding-run gate regressions.
- This guide documents provenance, preparation boundaries and human commands.

The historical system/user prompts, task + numbered candidate + reference
context, JSON extraction, sanitizer, taxonomy/severity constants, score
calculation, correctness gate, aggregate reward and GRPO argument builder are
preserved. Historical prompt hash: `50d083c5e7100d2e`; the launcher records
its complete SHA-256 and exact prompt text too. AST comparisons and valid-response
regressions against `git show 8cc4acc:train.py` verify the unchanged functions.

Reliability is an explicit methodological difference: missing/non-ok status,
missing or non-list findings, non-object findings, missing/non-string textual
fields, and non-integer line fields are unavailable responses, not clean code.
The historical sanitizer still handles taxonomy values, severity normalization,
line-span adjustments and evidence heuristics exactly as before on structurally
valid responses. For example, a structurally valid finding filtered by the old
sanitizer remains filtered; this patch does not revise that judgment.

There are at most three HTTP attempts for timeout/network failures and HTTP
408/429/500/502/503/504, with 1s and 2s backoff. Each attempt has a 60s timeout.
Other HTTP errors, JSON/UTF-8 parse errors and schema errors fail immediately.
Exhaustion or unexpected errors abort the trainer and launcher, so there is
no quality reward returned from an infrastructure failure. A recovered retry
is counted separately and the eventual valid response uses historical scoring.
Error records retain categories/status codes, never raw provider exception
text, headers, response bodies, private URLs or credentials.

## Matched settings and output layout

Model `unsloth/Qwen3.6-27B`, 4-bit, fresh LoRA rank/alpha 16/16, LR 5e-6,
batch/accumulation 4/1, four generations, prompt/completion 1024/384,
500 steps, seed 3407 initially. Dataset `evalplus/humanevalplus`, split `test`,
train indices `[0,50)`, holdout `[50,100)`. Correctness/judge/style weights
4.5/1/0, format/syntax/execution 0.1/0.1/0.3; performance disabled.
Judge temperature/top-p/max tokens 0/1/900; judge seed stays 3407 for all
matched training seeds, consistent with the draft settings.

Each command runs these five stages in order, as the historical launcher did:
`eval_base`, `eval_base_holdout`, `train`, `eval_lora`, `eval_lora_holdout`.
The historical before/after CSV collection (10 tasks, one deterministic
generation, current training split) is retained. Smoke therefore includes the
same evaluations and can take noticeably longer than its 20 training updates.

Roots: `results/correctness-judge-smoke/seed-3407-<UTC timestamp>/` and
`results/correctness-judge-formal/seed-3407-<UTC timestamp>/`. Directories are
created exclusively. `AUTO_RESUME=0`, `RESUME_FROM_CHECKPOINT=none`, and each
run gets its own `output/train` and `adapters/train`. The full run cannot point
to a smoke adapter. Final `trainer_state.json` is saved even when smoke is
shorter than the unchanged 250-step checkpoint interval.

Metadata contains commit/branch, dirty status, source diff against HEAD and
baseline, exact source snapshots and hashes, seed, all explicit per-stage
configuration/path settings, prompt/version/hashes, alias/backend description,
dataset/splits, package freeze, GPU/driver dump, start/end and stage exit codes.
`judge-status.jsonl` records attempts, successes, errors, retries, fatalities
and successful scored evaluations; `judge-summary.json` aggregates them.
Only the three private judge settings are loaded from root `.env` or exported
environment values (exports take precedence). Ambient trainer config values
are cleared before applying the matched settings. `GPU_DEVICE` defaults to 1;
set it deliberately for the remote machine. No private env is copied here.

## Human execution instructions — not executed during preparation

First review the local diff. The branch is not available remotely until its
local preparation commit is pushed. After review, a human can publish it from
local PowerShell:

```powershell
git -C '<PRIVATE_PATH>' push -u origin experiments/correctness-judge-formal
```

Then, on the remote Linux machine, use a separate clone and activate the same
Python/CUDA environment used for runs 30–32. Do not replace files in an existing
dirty remote checkout. The model and dataset names match, but historical exact
Hub revisions were not pinned: verify cached snapshots/package compatibility
before interpreting results as a strict replication. No environment upgrade
or new training environment is prescribed here.

1. Checkout/pull the published formal branch into an isolated clone:

```bash
set -euo pipefail
FORMAL_REPO="$HOME/UnSloth-RL-judge-formal"
test ! -e "$FORMAL_REPO"
git clone --single-branch --branch experiments/correctness-judge-formal \
  https://github.com/Jeraych/UnSloth-RL.git "$FORMAL_REPO"
cd "$FORMAL_REPO"
git pull --ff-only
git merge-base --is-ancestor 8cc4accd0c687a040543a791e472e3f5b236e2e2 HEAD
git status --short
python -m unittest discover -s tests -p test_formal_judge.py -v
bash -n run_correctness_judge.sh configs/correctness_judge_3seeds.sh configs/correctness_judge_smoke.sh
```

If that destination already exists, stop and inspect it; do not delete or
reset it. Use a new explicitly chosen destination for a fresh clone instead.

2. Create the private `.env` directly on the remote machine:

```bash
umask 077
test ! -e .env
${EDITOR:-nano} .env
```

Enter only these three assignments, replacing the first two values privately.
Quote literal values if needed; do not use shell substitutions. Do not paste
the completed file into chat or print it in logs:

```dotenv
AI_JUDGE_BASE_URL='PRIVATE_OPENAI_COMPATIBLE_BASE_URL'
AI_JUDGE_API_KEY='PRIVATE_API_KEY'
AI_JUDGE_MODEL=qwen-32b
```

The historical URL builder accepts a base root (adds `/v1/chat/completions`),
a base ending `/v1`, or a full URL ending `/chat/completions`.

3. Verify ignored status and remote environment without exposing env values:

```bash
chmod 600 .env
git check-ignore --quiet .env
test -z "$(git ls-files -- .env)"
python -m pip check
nvidia-smi
export GPU_DEVICE=1  # use the intended available GPU on this remote machine
bash run_correctness_judge.sh --dry-run --smoke --seed 3407
```

4. Make exactly two connectivity requests from the remote machine:

```bash
bash run_correctness_judge.sh --connectivity 2
```

This command extracts the historical judge functions without importing
Unsloth or loading a model/dataset. It uses task/candidate/reference context,
validates JSON/schema, saves redacted results, makes one HTTP attempt per
probe, and exits nonzero on failure. `--connectivity 3`, `4` or `5` is also
supported; this is a connectivity check, not a calibration batch.

5. Run the seed-3407 20-step smoke in a persistent remote terminal session:

```bash
bash run_correctness_judge.sh --smoke --seed 3407
```

The launcher prints `RUN_DIRECTORY=...` before work starts; stage output goes
to that directory's five stage logs. In another terminal you can follow
`tail -f <RUN_DIRECTORY>/train.log` during the training stage.

6. Inspect smoke health; replace the placeholder with that printed directory:

```bash
SMOKE_DIR='/absolute/path/from/RUN_DIRECTORY'
bash run_correctness_judge.sh --health "$SMOKE_DIR"
python -m json.tool "$SMOKE_DIR/health.json"
python -m json.tool "$SMOKE_DIR/judge-summary.json"
```

Pass requires exit code 0, `health.json` `pass=true`, and all checks true:

- At least one successful validated judge HTTP response; zero fatal, parse
  or schema errors. Recovered transient retries are visible, not hidden.
- All test-passing training candidates have judge status `ok`, no judge error
  rows, and ineligible candidates retain zero gated judge reward. Any fatal
  judge error must have stopped the run, never become a quality score.
- At least one complete four-output training group has two distinct judge
  scores among correctness-eligible candidates, plus nonzero total reward
  variation. This avoids counting correctness gating alone as useful judge
  discrimination. If all eligible scores tie, stop and diagnose; do not tune
  the formal instrument or bypass the gate just to get a pass.
- Exactly 20 completed training steps, 80 sample rows and 20 groups of four;
  recorded historical prompt/model fields match; final adapter exists.
- Commit/diff/config, prompt, source snapshots/hashes, package/GPU information,
  judge events/summary, run start/end and all stage outcomes are present.
- Stage paths are inside that smoke root, resume is disabled, and the final
  trainer state/adapter belong to it. Missing/malformed artifacts fail health.

A smoke pass is operational evidence, not evidence of improved model quality.

7. Start a fresh seed-3407 500-step formal run only after smoke passes:

```bash
bash run_correctness_judge.sh --seed 3407 --after "$SMOKE_DIR"
```

The launcher rechecks smoke health, matching source hashes and configuration;
`--after` authorizes the prerequisite, never supplies a checkpoint or adapter.
It creates a new formal directory and starts a fresh adapter at step 0.

After the seed-3407 formal run passes health, subsequent seeds remain separate
explicit commands, requiring success of the preceding matched formal seed:

```bash
SEED3407_DIR='/absolute/path/of/successful/formal/seed-3407-run'
bash run_correctness_judge.sh --seed 3408 --after "$SEED3407_DIR"
SEED3408_DIR='/absolute/path/of/successful/formal/seed-3408-run'
bash run_correctness_judge.sh --seed 3409 --after "$SEED3408_DIR"
```

## Local validation and remaining remote gates

The offline suite compares historical source/valid scores, mocks network errors,
and verifies fail-closed behavior/config/health. Dry runs do not load `.env`,
contact endpoints, instantiate the trainer or create run outputs. The smoke
configuration differs from full only in `MAX_STEPS`; mode/path labels differ
by design. `--pure` is rejected. No standalone files are imported.

Remaining gates: publish the reviewed local branch; remote repository access;
private settings; compatible CUDA/training packages, GPU memory and model/dataset
snapshots; two successful connectivity probes; actual smoke health. These have
not been tested here. Local worktree creation bypassed Git LFS hydration after
a sandbox MSYS failure, leaving archived ZIPs as LFS pointers; formal source
does not depend on those ZIPs. The registered worktree and source baseline
were verified despite the post-checkout hook's nonzero exit.
