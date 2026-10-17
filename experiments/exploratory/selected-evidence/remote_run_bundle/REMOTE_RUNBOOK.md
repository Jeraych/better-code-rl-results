# Remote experiment runbook

## What actually needs the remote machine

| Experiment | Remote required? | Resources | Expected purpose |
|---|---|---|---|
| AI-judge prompt calibration | Yes, unless the judge endpoint is reachable locally | Ollama and enough GPU/RAM for the unchanged Run 13 judge model | Main next experiment: 4-call smoke, then 144-call frozen comparison |
| CodeQual rerun | No; optional remote confirmation | CPU, Python, internet for clone/packages | Confirm portability/reproducibility of the frozen local result |
| SonarQube rerun | No; optional remote confirmation | Docker, roughly 4 GB free RAM, CPU | Confirm Docker/Linux reproducibility and script findings |
| GRPO training | Not prepared or authorized by this bundle | GPU and long runtime | Later, only after prompt calibration is interpreted |

The CodeQual and SonarQube pilots are already completed at commits `8afbb9e`
and `efcfea6`. Do not rerun them merely to replace those results. A remote rerun
is a new portability checkpoint and therefore uses a new branch and run ID.

## 1. Obtain the preparation revision

The remote checkout must contain branch `experiment/remote-experiment-prep`.
If it has not been published, push or transfer it first. On the remote machine:

```bash
cd /path/to/UnSloth-RL
git fetch --all --prune
git switch experiment/remote-experiment-prep
git status --short
git log -4 --oneline
```

`git status --short` must be empty before creating a result branch. Do not run
from a checkout containing uncommitted research outputs.

Validate the frozen judge resources without contacting Ollama:

```bash
python experiments/ai_judge_prompt_calibration/export_dataset.py --check
python experiments/ai_judge_prompt_calibration/run_calibration.py --validate-only
python experiments/ai_judge_prompt_calibration/validate_preparation.py
python -m unittest discover -s experiments/ai_judge_prompt_calibration/tests -v
```

Expected identifiers:

```text
dataset_sha256 = 6995ed389ac05e0d4ee58c74bc3514782422b3b9c4ad84f8d233c0de71739cb4
baseline_v3     = 50d083c5e7100d2e
calibrated_v4   = d00747192b661ec3
planned_calls   = 144
```

## 2. AI-judge calibration branch and Ollama setup

Create a result branch before making any call:

```bash
git switch -c results/ai-judge-calibration-<run_id>
```

Use the same judge model as Run 13. If Ollama runs on this machine, check it:

```bash
ollama --version
ollama list
nvidia-smi
```

If the model is missing, obtain the exact approved model tag before the run:

```bash
ollama pull qwen3-coder:30b
```

If Ollama is not already a service, start it in a separate session or with the
remote machine's service manager. Connection values stay in the shell only:

```bash
export AI_JUDGE_BASE_URL="<PRIVATE_OPENAI_COMPATIBLE_BASE_URL>"
export AI_JUDGE_API_KEY="<PRIVATE_ACCESS_KEY>"
export AI_JUDGE_MODEL="qwen3-coder:30b"
```

Run the read-only preflight. It reports `<configured>` instead of the endpoint:

```bash
python experiments/remote_run_bundle/preflight_remote.py --tools ai-judge
```

Initialize one unique run directory:

```bash
python experiments/remote_run_bundle/init_run.py <run_id>
```

Run the 4-call plumbing smoke first:

```bash
python experiments/remote_run_bundle/run_ai_judge_remote.py \
  research_runs/<run_id> --mode smoke
```

Inspect these before continuing:

```bash
cat research_runs/<run_id>/ai_judge_smoke/summary.json
sed -n '1,4p' research_runs/<run_id>/ai_judge_smoke/calls.jsonl
```

The smoke result must show four completed calls and no errors. It is not part of
the full metrics. Then run the frozen comparison into its separate stage:

```bash
python experiments/remote_run_bundle/run_ai_judge_remote.py \
  research_runs/<run_id> --mode full
```

If SSH disconnects, rerun exactly the same command with `--resume`. Completed
profile/case/repetition keys are skipped:

```bash
python experiments/remote_run_bundle/run_ai_judge_remote.py \
  research_runs/<run_id> --mode full --resume
```

Validate and commit only after the full stage completes:

```bash
python experiments/remote_run_bundle/validate_run_bundle.py \
  research_runs/<run_id>
git add -- research_runs/<run_id>
git diff --cached --check
git commit -m "Record AI judge calibration <run_id>"
```

Do not change `train.py` based on the result yet. First inspect
`ai_judge_calibration/RESULTS.md`, category metrics, raw responses, errors, and
the frozen decision gates.

## 3. Optional CodeQual Linux reproducibility run

Return to the preparation checkpoint and create a separate branch:

```bash
git switch experiment/remote-experiment-prep
git switch -c results/codequal-rerun-<run_id>
python experiments/remote_run_bundle/preflight_remote.py --tools codequal
python experiments/remote_run_bundle/init_run.py <run_id>
python experiments/remote_run_bundle/run_codequal_remote.py \
  research_runs/<run_id>
python experiments/remote_run_bundle/validate_run_bundle.py \
  research_runs/<run_id>
```

The runner clones the pinned upstream commit, applies the already-recorded
compatibility patch, creates a disposable venv, reruns the 23 fixtures and
50-output Run 13 sample, and preserves command logs plus dependency versions.
It does not execute generated candidate code. The upstream test command has
known failures documented by the original pilot, so its exit code is recorded
without being treated as the decision-test result.

Compare the new `decision_test_summary.json` with frozen commit `8afbb9e`, then:

```bash
git add -- research_runs/<run_id>
git diff --cached --check
git commit -m "Record CodeQual Linux rerun <run_id>"
```

## 4. Optional SonarQube Linux reproducibility run

Use another branch and run ID:

```bash
git switch experiment/remote-experiment-prep
git switch -c results/sonarqube-rerun-<run_id>
python experiments/remote_run_bundle/preflight_remote.py --tools sonarqube
python experiments/remote_run_bundle/init_run.py <run_id>
python experiments/remote_run_bundle/run_sonarqube_remote.py \
  research_runs/<run_id>
python experiments/remote_run_bundle/validate_run_bundle.py \
  research_runs/<run_id>
```

The container is pinned by digest and bound to `127.0.0.1` only. The runner
creates a temporary token, performs two unchanged 73-file scans and the separate
90-file extension scan, exports raw API evidence, revokes the token, and stops
the container. Generated candidates are scanned as text and never executed.

Compare `sonarqube/results/summary.json` with frozen commit `efcfea6`, then:

```bash
git add -- research_runs/<run_id>
git diff --cached --check
git commit -m "Record SonarQube Linux rerun <run_id>"
```

## 5. Copying evidence back instead of committing remotely

If the remote checkout cannot push, validate first, then archive only the run:

```bash
tar -czf <run_id>.tar.gz research_runs/<run_id>
```

Copy the archive through the approved university/private transfer route. After
extracting locally, verify the hashes in `evidence_manifest.json`, create the
appropriate `results/` branch, inspect the privacy scan, and commit the complete
run directory. Never copy Ollama model files, environment files, caches, venvs,
or the disposable `work/` directory.
