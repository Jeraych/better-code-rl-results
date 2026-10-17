# Run double-style AI Judge Run Summary

## Verdict

Run double-style is a successful integration run for the AI judge reward. The run logged 2000 completions across 500 trainer steps and 50 HumanEval tasks. The judge completed on 1863/2000 rows (93.2%) and on 1863/1918 passed rows (97.1%).

The run should be treated as a strong pilot rather than the final publishable calibration. The judge is active and correctly gated, but low-severity readability findings dominate and need manual validation before making a strong research claim.

## Key Metrics

| Metric | Value |
|---|---:|
| Total completions | 2000 |
| Trainer steps | 500 |
| Test pass rate | 1918/2000 = 95.9% |
| AI judge completed | 1863/2000 = 93.2% |
| AI judge completed among passed code | 1863/1918 = 97.1% |
| AI judge timeout errors | 55/2000 = 2.8% |
| Not eligible for judge | 82/2000 = 4.1% |
| Findings on failed code | 0 |
| Mean AI judge score, judged rows | 0.852 |
| Median AI judge score, judged rows | 0.850 |
| Mean total reward, all rows | 8.462 |
| Mean total reward, judged rows | 8.760 |

## AI Judge Findings

The judge produced 1573 accepted findings across 1246 completions. Findings were concentrated in readability rather than maintainability.

| Category | Findings | Affected rows |
|---|---:|---:|
| Readability | 1170 | 1098 |
| Maintainability | 403 | 400 |

| Subcategory | Findings | Affected rows | Description |
|---|---:|---:|---|
| Sub-readable Code Exists | 1024 | 1007 | Code structure judged harder to read than a simple equivalent, such as avoidable indexing, dense expressions, or local control-flow clutter. |
| Code Duplication | 205 | 202 | Repeated or redundant logic that may make future edits harder, including repeated branch bodies and repeated transformations. |
| Confusing Variable Naming | 146 | 106 | Names judged ambiguous or misleading enough to slow code review, such as single-letter parameters outside tiny local scopes. |
| Unnecessary Conditional Block | 111 | 111 | A conditional branch the judge believes can be simplified without changing behavior, such as verbose boolean branches or redundant special cases. |
| Unnecessary Else | 87 | 87 | An else branch after control flow, or an empty else branch such as `else: pass`, that can be removed. |
| Comment Duplication | 0 | 0 | Repeated comments that add no new information. No accepted findings of this type appeared in this run. |

Severity was light: 1374 low findings and 199 medium findings, with no high or critical findings.

## Interpretation

The strongest evidence that the judge is working is the clean eligibility behavior: there were zero findings on failed code. The model/prompt configuration was also stable throughout the run: `qwen-32b`, `taxonomy_readability_maintainability_v3`, hash `50d083c5e7100d2e`.

The main weakness is calibration. `Sub-readable Code Exists` accounts for 1024 of 1573 findings, and some sampled examples look subjective rather than objectively harmful. This is still useful as a training signal, but the paper should describe it as taxonomy-guided judge feedback and validate a sample manually.

## Training Signal

| Window | Mean reward | Mean reward std | Zero reward-std rate | Mean completion length |
|---|---:|---:|---:|---:|
| All 500 steps | 8.462 | 0.203 | 57.2% | 87.3 |
| First 50 steps | 8.255 | 0.444 | 36.0% | 132.7 |
| Last 50 steps | 8.501 | 0.336 | 66.0% | 82.1 |

The mean zero reward-std rate was 57.2%. Because this run used two generations per step, many GRPO groups had no within-group preference signal. A future run should use more generations if GPU budget allows.

## Recommended Next Steps

1. Add retry/backoff for AI judge timeout rows.
2. Manually label a stratified sample of judge findings, especially low-severity `Sub-readable Code Exists` cases.
3. Consider reducing the low-severity penalty or filtering naming/style-like readability findings more aggressively.
4. Compare against baseline, deterministic-only, judge-only, and combined reward profiles with the same task split and seeds.
5. For final paper experiments, report judge coverage, timeout rate, finding distribution, and reward variance together with pass rate.

## How to Run the AI Judge Safely

Keep the actual server address, port, and access key outside committed files. Set them privately in the shell/session or an untracked environment file.

```bash
# 1. Set private connection values in your shell/session only.
export AI_JUDGE_BASE_URL="<PRIVATE_OPENAI_COMPATIBLE_BASE_URL>"
export AI_JUDGE_API_KEY="<PRIVATE_ACCESS_KEY>"
export AI_JUDGE_MODEL="<JUDGE_MODEL_NAME>"

# 2. Optional local plumbing check with no remote judge call.
env TEST_MODE=sanity_reward REWARD_PROFILE=judge_combined AI_JUDGE_MOCK=1 python train.py

# 3. Real judge sanity check. The training script will run its AI-judge preflight.
env TEST_MODE=sanity_reward REWARD_PROFILE=judge_combined AI_JUDGE_ENABLED=1 AI_JUDGE_MOCK=0 python train.py

# 4. Tiny training smoke test.
env TEST_MODE=tiny_overfit_train TINY_MAX_STEPS=1 REWARD_PROFILE=judge_combined AI_JUDGE_ENABLED=1 AI_JUDGE_MOCK=0 python train.py

# 5. Remote full run with nohup.
nohup env TEST_MODE=train REWARD_PROFILE=judge_combined AI_JUDGE_ENABLED=1 AI_JUDGE_MOCK=0 python train.py > ai_judge_train.log 2>&1 &
```

The safe checks to look for are `AI judge: enabled=True`, `mock=False`, the expected judge model name, the expected prompt hash, and `ai_judge_status: ok` on passing samples. Failed tests should remain `ai_judge_status: not_eligible`.
