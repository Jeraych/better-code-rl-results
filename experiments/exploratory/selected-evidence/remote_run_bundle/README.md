# Remote experiment bundle

These scripts reproduce or run the prepared experiments without modifying the
committed pilot evidence. They require Python 3.11 or newer and create all
working environments inside `research_runs/<run_id>/work/`, which is removed
after a successful stage.

Available stages:

- `run_ai_judge_remote.py`: two-call-pair smoke test or frozen 144-call prompt
  calibration; requires an OpenAI-compatible Ollama endpoint.
- `run_codequal_remote.py`: exact CodeQual rerun at upstream commit
  `518360297f59ad7b6569233eb4b934e6b00c083b` in a disposable clone and venv.
- `run_sonarqube_remote.py`: exact SonarQube rerun using the pinned Community
  Build image digest, bound only to remote localhost.

Read `REMOTE_RUNBOOK.md` for branch strategy and exact commands. Each run must
be initialized with `init_run.py`, completed by one experiment stage, validated
with `validate_run_bundle.py`, and committed on that experiment's result branch.

No script writes into `experiments/codequal_analyzer_pilot/results/` or
`experiments/sonarqube_pilot/results/` in the real checkout.
