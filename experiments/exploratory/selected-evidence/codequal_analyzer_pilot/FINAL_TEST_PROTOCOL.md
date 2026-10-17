# Final decision test protocol

## Decision being made

Determine whether `codequal_analyzer` should be used in this research as:

1. A rule-level offline reporting metric.
2. A fast static supplement in `train.py`.
3. Neither.

The released `overall_per_kchar` score is already excluded because the padding
probe showed that comments can improve it without changing findings.

## Label source

The test uses manually specified expectations attached to small synthetic
fixtures. No human reviewers or model-generated labels are required. Each
fixture targets one published rule family and is labelled before execution as
either a positive example or a clean/legitimate control.

Rule families:

- Inefficient string concatenation.
- Excessive resource consumption in loops.
- Improper exception handling.
- Excessive data-structure complexity.
- Cyclomatic complexity.
- Dead code.

## Additional integration checks

- Arbitrary HumanEval entry-point names must not be reported as dead code.
- Invalid syntax must be rejected before analysis.
- Adding comments must not change selected rule findings.
- Renaming an entry point while supplying the new name must not change results.
- Repeated analysis must be deterministic.
- Generated code must never be executed.

## Predefined decision gates

### Offline research metric: GO

All of the following must hold:

- Precision >= 0.80.
- Recall >= 0.70.
- False-positive rate <= 0.20.
- Entry-point, syntax, padding, rename, and determinism checks pass.
- Mean full quick-analysis time <= 2 seconds per solution locally.

If the aggregate gate fails but individual rule families satisfy the accuracy
requirements, the decision becomes **LIMITED GO** for only those rule families.

### Online `train.py` supplement: GO

All of the following must hold for the AST-only subset:

- Precision >= 0.80.
- Recall >= 0.80.
- False-positive rate <= 0.10.
- Mean analysis time <= 100 ms per solution locally.
- Syntax, entry-point, padding, rename, and determinism checks pass.

Failure means the analyser is not added to the GRPO reward path. A later
purpose-built in-process rule implementation may still be considered.

## Interpretation boundary

Passing this test establishes controlled rule sensitivity and integration
feasibility. It does not establish agreement with human code-quality judgement
or semantic correctness.
