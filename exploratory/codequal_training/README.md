# CodeQual-inspired training experiment

## What is integrated

The online reward adds one deliberately narrow CodeQual-inspired rule:
repeated string construction inside a loop. It is AST-only, deterministic,
does not execute generated code, and contributes reward only after functional
tests pass by default.

PEP8 is represented by the existing Ruff `E,W` style reward. These rule
families are the pycodestyle/PEP8-compatible checks already used by the
pipeline. Running pycodestyle again online would duplicate the signal and add
a Python subprocess per completion, so exact pycodestyle parity is an offline
validation question rather than a second reward.

The released CodeQual aggregate score, resource-loop rules, and
data-structure rules are not integrated. The earlier controlled pilot found
known false positives, including numeric accumulation and ordinary lookup
dictionaries. Complexity, dead-code, and exception rules remain useful as
offline outcome measures but are not yet justified as online objectives.

## Local validation

```bash
python -m unittest tests.test_codequal_metrics -v
python experiments/codequal_training/validate_metric.py
```

The frozen gate requires precision >= 0.90, recall >= 0.80, false-positive
rate <= 0.10, and mean analysis time <= 5 ms on the small labelled fixture
set. Passing this gate establishes implementation feasibility only; it is not
external validity.

## Factorial training matrix

Preview the eight arms:

```bash
./run_reward_experiments.sh --codequal-factorial --dry-run --repeat 1
```

Run the confirmatory matrix with the configured three seeds per arm:

```bash
./run_reward_experiments.sh --codequal-factorial
```

After it finishes, calculate holdout deltas, main effects, and pairwise
interactions:

```bash
python experiments/codequal_training/analyze_factorial.py results/<run-number>
```

The 2^3 factors are:

| Factor | Off | On |
|---|---|---|
| PEP8-style | `REWARD_STYLE_WEIGHT=0` | Ruff `E,W`, weight 1.0 |
| String concat | disabled | AST metric, weight 1.0 |
| Dynamic performance | baseline profile | combined profile, weight 1.0 |

All arms retain format, syntax, compilation, and test rewards. The AI judge is
held out to avoid confounding the first efficiency comparison with network
latency and judge failures.

## Required outcome reporting

For each seed and arm report train and holdout correctness, style score,
string-concat prevalence, dynamic runtime/memory score, completion length,
reward variance, wall-clock training time, metric latency, and error/timeout
rates. Use paired base-versus-LoRA deltas and identical task splits.

Do not select the best arm from one seed. A candidate advances only if the
direction is consistent across at least three seeds, holdout correctness does
not materially regress, and the targeted metric improves without a worse
trade-off in another measured dimension.

## Publication decision

A workshop/student paper is plausible if the repeated factorial experiment
shows a reproducible trade-off or interaction, not merely a higher aggregate
reward. The minimum defensible contribution is: a validated low-cost static
reward, controlled multi-objective ablation, correctness-preserving decision
gate, and analysis of agreement between static flags and measured runtime.

If effects vanish across seeds, only training reward rises, or correctness
drops, the honest result is negative evidence about proxy rewards. That can
still support a thesis/report, but is unlikely to justify a standalone paper
without broader tasks, another model, and external validation labels.
