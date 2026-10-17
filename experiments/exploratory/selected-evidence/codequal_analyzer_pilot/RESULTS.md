# codequal_analyzer pilot results

## Research question

Can `codequal_analyzer` provide a quick, deterministic static-quality signal
that distinguishes deliberately degraded Python solutions and complements the
existing AI judge on real generated code?

## Method

The quick analyser configuration was tested at upstream commit
`518360297f59ad7b6569233eb4b934e6b00c083b`. Eight clean/degraded synthetic
pairs targeted maintainability, performance, reliability, or security. Each
condition was scored three times. The primary synthetic endpoint was the raw
overall score difference, `clean - degraded`.

For a label-free real-output check, 50 examples were sampled with seed 42 from
934 Run 13 completions that passed their tests, had a successful AI judgement,
and contained extracted code. Spearman correlations compare the static score
with the existing AI-judge and style scores. These correlations measure
agreement only; neither automated score is human ground truth.

## Results

### Synthetic sensitivity

- The clean version scored higher in all 8/8 pairs.
- Mean clean-minus-degraded overall score: **5.603 points**.
- Pair differences ranged from **2.26 to 12.53 points**.
- Directional accuracy: **100%**, Wilson 95% CI **67.6%-100%**.
- Two-sided sign test: **p = 0.007812**.
- All scores were identical across the three repetitions.

This confirms deterministic sensitivity to deliberately seeded rules. It does
not establish coverage of unexpected or semantic quality defects, because the
fixtures were designed from the analyser's documented rule families.

### Run 13 sample

- Released/raw overall score: mean **94.018**, SD **1.738**, range
  **90.32-94.94**.
- Only **three distinct raw overall scores** occurred among 50 solutions.
- All 50 solutions received an `unused-function` finding because HumanEval
  entry points are task-specific rather than literally named `solution`.
- After removing only that known entry-point warning, mean score was **98.964**
  and only **12 non-entry-point findings across 11/50 solutions** remained.
- Before entry-point filtering, findings came from Vulture (51), the resource
  consumption analyser (10), and Pylint (1). The quick configuration produced
  no findings from the other five enabled analysers on this sample.
- Raw score versus AI judge: Spearman **rho = 0.299**, bootstrap 95% CI
  **0.069-0.517**.
- Raw score versus style score: Spearman **rho = -0.013**.
- Entry-point-adjusted length-normalized score versus AI judge: Spearman
  **rho = -0.112**, bootstrap 95% CI **-0.414-0.225**.
- Mean local analysis time was **922 ms per solution**.

The modest positive raw-score/AI-judge association suggests limited convergent
signal, but the score resolution is very low and dominated by a small number
of static rules. It should not be interpreted as validation of either metric.

### Length-normalization probe

Adding 80 comment lines to the same inefficient program:

- Left the findings unchanged.
- Left the raw overall score unchanged at **92.80**.
- Increased `overall_per_kchar` from **72.66 to 82.82**, a gain of
  **10.16 points**.

The current per-kcharacter score can therefore be improved by non-functional
padding. It should not be used as a reward or primary comparison metric without
redesign and adversarial validation.

## Reproducibility audit

With the Windows compatibility patch and the deliberately minimal quick-path
environment, the upstream test suite produced **29 passed, 16 failed, and 2
skipped** tests. The remaining failures include:

- Tests pointing to `python/sample_project`, while the repository stores the
  fixtures under `python/examples/sample_project`.
- A score test that expects the older linear formula rather than the current
  nonlinear formula.
- Tests for Mypy, Safety, and Xenon, which were not installed for this
  quick-path pilot.

Consequently, this pilot validates the specific quick experiment path, not the
entire released package.

## Current decision

`codequal_analyzer` is useful as an **offline, per-rule supplementary
evaluator**, particularly for targeted static performance and reliability
smells. The released scalar score is not yet suitable as a GRPO reward because
of entry-point false positives, compressed score resolution, exploitable
length normalization, incomplete test reproducibility, and approximately
one-second per-solution process overhead.

For subsequent experiments, retain raw findings and selected rule severities,
report individual quality dimensions, and avoid `overall_per_kchar`. Keep this
metric separate from runtime performance and from the AI judge.

## Final decision test

A subsequent pre-specified test added 23 positive/control fixtures, robustness
checks, and an AST-only dry run on 50 Run 13 outputs. The full quick analyser
passed the aggregate offline gate, while the AST-only path failed the online
reward gate because its false-positive rate was 0.222. See
`FINAL_DECISION.md` for the rule-family results and final recommendation.
