# Offline analyzer screening: first loop

**Evidence status:** controlled offline screening of previously saved completions. This is a candidate-selection gate, not a training-effect result.

## Inputs

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `results/12/samples.csv` | 1000 | `acfaf87dc67b1e7e38ce29b9b7d8880427477ad1d61fe4558632d11f5f64521a` |
| `results/13/samples.csv` | 1000 | `f3a53e6505897e598571493fd71db19ab44c3791e85d99e7d3280acaf63f42a0` |
| `results/15/all-metrics/samples.csv` | 1000 | `d111b74189b3bad0005c56ca35b089308cebb6f8ffcb7fa99fb37cf83f02f468` |

## Screening outcomes

| Analyzer | Eligible | Available | Activation | Ceiling | Non-zero group variance | Mean latency | Decision | Remote role |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Ruff E,W / PEP8-style | 2878 | 100.0% | 28.4% | 71.6% | 8.1% | N/A ms | **hold** | offline_measure_only |
| AST string concatenation | 2878 | 100.0% | 0.0% | 100.0% | 0.1% | 0.070 ms | **hold** | offline_measure_only |
| Dynamic performance | 2878 | 66.7% | 19.1% | 80.9% | 12.2% | N/A ms | **redesign** | offline_measure_only |

## Decision record

- StringConcat fixture gate: **pass** on 12 handcrafted cases; precision 1.000, recall 1.000, false-positive rate 0.0%. This establishes implementation feasibility only.
- `pep8_style`: **hold** — Frozen screening criteria not met: group_variation.
- `string_concat`: **hold** — Frozen screening criteria not met: activation, group_variation.
- `dynamic_performance`: **redesign** — Frozen screening criteria not met: ceiling, group_variation.

## Source-level diagnostic

| Source | Ruff activation | Ruff group variation | StringConcat activation | Performance ceiling | Performance group variation |
|---|---:|---:|---:|---:|---:|
| `results/12/samples.csv` | 26.1% | 5.5% | 0.0% | 81.4% | 11.2% |
| `results/13/samples.csv` | 28.0% | 8.6% | 0.1% | 0.0% | 0.0% |
| `results/15/all-metrics/samples.csv` | 30.9% | 10.1% | 0.0% | 80.5% | 13.3% |

## Frozen interpretation

Only analyzers marked `promote` should enter the next remote-training plan unchanged. `Hold` means collect broader or more activating data before promotion. `Redesign` means the present reward formulation should not consume confirmatory remote compute.

The screen uses stored Ruff and performance columns, because importing the training module would load model dependencies. StringConcat is re-executed directly against each test-passing saved completion. Analyzer effects on trained models are not measured in this loop.
