# Result 13 AI Judge Run Summary

## Verdict

Result 13 is a successful integration run for the AI judge reward. The run logged 1000 completions across 500 trainer steps and 50 HumanEval tasks. The judge completed on 934/1000 rows (93.4%) and on 934/958 passed rows (97.5%).

The run should be treated as a strong pilot rather than the final publishable calibration. The judge is active and correctly gated, but low-severity readability findings dominate and need manual validation before making a strong research claim.

## Key Metrics

| Metric | Value |
|---|---:|
| Total completions | 1000 |
| Trainer steps | 500 |
| Test pass rate | 958/1000 = 95.8% |
| AI judge completed | 934/1000 = 93.4% |
| AI judge completed among passed code | 934/958 = 97.5% |
| AI judge timeout errors | 24/1000 = 2.4% |
| Not eligible for judge | 42/1000 = 4.2% |
| Findings on failed code | 0 |
| Mean AI judge score, judged rows | 0.839 |
| Median AI judge score, judged rows | 0.850 |
| Mean total reward, all rows | 6.551 |
| Mean total reward, judged rows | 6.808 |

## AI Judge Findings

The judge produced 858 accepted findings across 639 completions. Findings were concentrated in readability rather than maintainability.

| Category | Findings | Affected rows |
|---|---:|---:|
| Readability | 637 | 590 |
| Maintainability | 221 | 221 |

| Subcategory | Findings | Affected rows | Description |
|---|---:|---:|---|
| Sub-readable Code Exists | 556 | 547 | Code structure judged harder to read than a simple equivalent, such as avoidable indexing, dense expressions, or local control-flow clutter. |
| Code Duplication | 138 | 138 | Repeated or redundant logic that may make future edits harder, including repeated branch bodies and repeated transformations. |
| Confusing Variable Naming | 81 | 61 | Names judged ambiguous or misleading enough to slow code review, such as single-letter parameters outside tiny local scopes. |
| Unnecessary Conditional Block | 48 | 48 | A conditional branch the judge believes can be simplified without changing behavior, such as verbose boolean branches or redundant special cases. |
| Unnecessary Else | 35 | 35 | An else branch after control flow, or an empty else branch such as `else: pass`, that can be removed. |
| Comment Duplication | 0 | 0 | Repeated comments that add no new information. No accepted findings of this type appeared in run 13. |

Severity was light: 750 low findings and 108 medium findings, with no high or critical findings.

## Interpretation

The strongest evidence that the judge is working is the clean eligibility behavior: there were zero findings on failed code. The model/prompt configuration was also stable throughout the run: `qwen-32b`, `taxonomy_readability_maintainability_v3`, hash `50d083c5e7100d2e`.

The main weakness is calibration. `Sub-readable Code Exists` accounts for 556 of 858 findings, and some sampled examples look subjective rather than objectively harmful. This is still useful as a training signal, but the paper should describe it as taxonomy-guided judge feedback and validate a sample manually.

## Training Signal

| Window | Mean reward | Mean reward std | Zero reward-std rate | Mean completion length |
|---|---:|---:|---:|---:|
| All 500 steps | 6.551 | 0.118 | 70.8% | 89.7 |
| First 50 steps | 6.565 | 0.126 | 58.0% | 130.6 |
| Last 50 steps | 6.589 | 0.031 | 70.0% | 78.6 |

The mean zero reward-std rate was 70.8%. Because this run used two generations per step, many GRPO groups had no within-group preference signal. A future run should use more generations if GPU budget allows.

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
