# Execution commands

Working directory: <PRIVATE_PATH>

Python: <PRIVATE_PATH>

```powershell
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/evaluate.py prepare --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/check_contracts.py
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/evaluate.py phase-a --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/evaluate.py phase-a-retry --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/evaluate.py phase-b --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/analyze_results.py --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/write_report.py --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/evaluate.py verify --out experiments/ai_judge_prompt_ab_run30/run-20261010
& '<PRIVATE_PATH>' -B experiments/ai_judge_prompt_ab_run30/verify_artifacts.py --out experiments/ai_judge_prompt_ab_run30/run-20261010
```

prepare was attempted twice: the first detected shell export prefixes unsupported by the existing literal reader, before creating outputs. The second succeeded after calibration-only in-memory normalization.

phase-a produced ten immediate sandbox transport failures, no responses. The first phase-a-retry escalation was rejected by automatic approval review before execution. The user then explicitly confirmed ownership of the endpoint and approved the request bundle and bearer authentication. The second, approved phase-a-retry invocation completed with ten valid responses. phase-b was subsequently approved and completed automatically, reusing the preflight responses and obtaining the remaining 150 valid reviews. All 160 successful responses returned qwen-32b and finish_reason stop.

analyze_results is offline and checks incidental repeated exact payloads and token/finish metadata. evaluate verify checks preservation and unavailable failure scores. verify_artifacts checks the full paired dataset, approved previews, prompt/source hashes, CSV/review coverage, and scans only the new calibration directory for the private credential, reporting booleans/counts without printing its value.

Additional read-only inspection: git status --porcelain=v1 --untracked-files=all; git show 8cc4accd0c687a040543a791e472e3f5b236e2e2:train.py; git check-ignore -v .env; Python stdin inspection of CSV groups, cached dataset rows, prompt hashes and credential-presence booleans. A socket probe returned PermissionError/10013; no key was transmitted by that probe.

An initial mocked check using the sandbox temporary directory failed on temporary-file permissions before contract execution. The dedicated project-local check_contracts.py then passed all checks. Its synthetic diagnostics are outside study results.

No model imports, candidate execution, training, package installation, remote GPU operations, commits or changes to pre-existing files occurred.
