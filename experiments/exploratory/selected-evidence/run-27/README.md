# Run 27 — PARTIALLY BROKEN PILOT

Correctness baseline, seed 3407. Training completed 500 steps, but HumanEval+
test execution hit `Argument list too long` during both training and evaluation.
236 of 2,000 training outputs received no correctness reward because of this
infrastructure error. This is not a clean final ablation.

Original logs and scores are retained unchanged. See
[recovered scores and limitations](../corrected_20260913/README.md).
Offline re-scoring repairs reported verdicts, not the model's training history.
