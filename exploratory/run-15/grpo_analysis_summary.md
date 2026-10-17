# GRPO Reinforcement Learning Analysis

## Verdict

The reinforcement learning is working **selectively**. The LoRA learned to produce shorter, Ruff-cleaner code, and the improvement generalises to holdout tasks. There is no convincing correctness improvement because the baseline is already near the ceiling.

## Main evaluation changes

| Metric | Train: Base → LoRA | Holdout: Base → LoRA |
|---|---:|---:|
| Pass rate | 97.0% → 96.0% | 96.0% → 94.0% |
| Style clean | 47.0% → 71.0% | 69.0% → 90.0% |
| Pass + style clean | 47.0% → 70.0% | 66.0% → 84.0% |
| Mean completion tokens | 143.0 → 67.9 | 113.0 → 72.3 |
| Mean style violations | 1.27 → 0.38 | 0.86 → 0.19 |
| Mean total reward | 7.501 → 7.514 | 7.318 → 7.285 |

## Metric influence

The exact reward equation is:

```text
reward_total = 0.1·format + 0.1·syntax + 1.0·style + 0.3·compile + 4.5·tests + 1.0·performance + 1.0·AI_judge
```

- **Tests dominate total reward**: 57.6% of mean reward and 65.5% of observed reward variance.
- **AI judge most often differentiates completions**: it changes in 93 of the 158 informative GRPO groups and is the largest weighted difference in about 83.5 groups.
- **Performance is secondary**: 14.7% of reward variance and 15.0% of active-pair absolute differences.
- **Ruff style is the clearest learned outcome**, but only 3.6% of total reward variance because its score range is narrow.

## Important relationships

- Completion length vs AI-judge score: **r = −0.625**.
- Completion length vs style violations: **r = +0.552**.
- AI judge vs Ruff style reward: **r = +0.386**, indicating partial complementarity.
- Test reward vs performance reward: **r = +0.925**, largely because performance is gated by correctness.
- Total reward vs pass status: **r = +0.980**; total reward vs style-clean status: **r = +0.312**.

## Training-signal limitation

Only 158 of 500 groups (31.6%) had non-zero total reward variance. With two generations per prompt, 68.4% of GRPO groups supplied no relative preference signal. Increasing group size is the clearest optimisation for the next run.
