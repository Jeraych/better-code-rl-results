# Remote candidate decision after offline loop 1

**Decision date:** 2026-08-19  
**Evidence status:** controlled offline screening and pre-remote decision  
**Machine-readable evidence:** `first_loop_summary.json`

## Decision

Do **not** launch the full PEP8 × StringConcat × dynamic-performance factorial
matrix unchanged on the remote machine. None of the three analyzers passed
every frozen aggregate screening gate.

The next remote comparison should be reduced to a matched, repeated two-arm
check:

1. `cq-core`: correctness and core rewards only;
2. `cq-pep8`: the same configuration plus the existing Ruff `E,W` reward.

Use identical task splits, model checkpoint, generation settings, step budget,
and at least three matched seeds. This is a conditional validation run, not a
claim that Ruff passed the aggregate offline gate.

## Analyzer dispositions

### Ruff E,W / PEP8-style: retain as the conditional candidate

- Availability among correct saved completions: 100%.
- Violation activation: 28.4%.
- Groups with non-zero score variation: 8.1%, below the frozen 10% aggregate
  threshold.
- Run 15 alone reached 10.1% group variation, and prior base/LoRA evaluation
  showed a measurable Ruff-clean change.

Ruff therefore remains the closest viable online candidate, but it should be
confirmed against `cq-core` before adding other factors.

### AST StringConcat: remove from the current HumanEval remote matrix

- The 12-case handcrafted fixture gate passed with precision and recall 1.00.
- Only 1 of 2,878 correct saved completions activated the rule (0.035%).
- Only 1 of 1,423 comparable groups varied (0.070%).
- Mean analysis latency was 0.068 ms.

The implementation is fast and passes its small feasibility fixture, but the
current HumanEval distribution provides essentially no learning signal. Keep
it as an offline measure. Reconsider it only with a targeted dataset containing
natural positive and negative string-building tasks.

### Dynamic performance: redesign before remote training

- Measurements were available for 1,920 correct completions.
- 80.9% of measured completions were at the maximum score.
- Only 12.2% of comparable groups had non-zero score variation, below the
  frozen 25% performance threshold.

Do not spend confirmatory remote compute on the current formulation. Candidate
redesigns include harder/scaled test inputs, operation-count proxies, or a
less-saturated relative score, followed by another offline screening loop.

### AI judge: deferred

The live judge was not part of this offline loop. Mock output must not be used
as research evidence. Judge-as-reward runs remain deferred until the endpoint
is available and the judge has been calibrated independently.

## Interpretation boundary

This loop evaluates analyzer feasibility and reward variation on saved outputs.
It does not estimate causal training effects. Any remote candidate still needs
matched repeated training and held-out evaluation before it can be described
as effective.
