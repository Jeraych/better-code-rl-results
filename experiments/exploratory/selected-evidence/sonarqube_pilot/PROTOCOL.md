# SonarQube pilot protocol

## Research question

Can SonarQube Community Build provide useful, reproducible offline evidence for
the taxonomy-grounded evaluation pipeline, beyond the existing dynamic
runtime/memory reward and AI judge?

SonarQube is evaluated as an offline static-analysis baseline. Candidate code
is scanned but never executed. This pilot does not add SonarQube findings to
GRPO rewards.

## Frozen data

1. The same 23 pre-labelled fixtures used by the final `codequal_analyzer`
   decision test. They cover string concatenation, resource use in loops,
   exception handling, data-structure complexity, branch complexity, and dead
   code, including 11 negative controls.
2. The same deterministic sample of 50 functionally passing Run 13 generations
   (seed 42) used by the CodeQual pilot.

`prepare_dataset.py` materializes each program as a separate Python file and
writes a manifest linking every file to its label and provenance.

## Configuration

- SonarQube Community Build 26.7.0.124771.
- Docker image digest:
  `sonarqube@sha256:d4899d380ad9d7b63ebaa751e047f5a4f064f8902cdf7c1a3c3c96f7d71600ed`.
- Built-in default Python quality profile; no rule thresholds are tuned after
  viewing outcomes.
- Python source version is declared as 3.12 for rule compatibility.
- Scanner and server-processing time are recorded separately from one-time
  image download and server startup.

## Measures

- Issue count and rule keys for every labelled fixture.
- Coverage: which taxonomy families have at least one semantically matching
  built-in Sonar rule.
- Accuracy for a family only when Sonar exposes a rule whose documented intent
  directly matches that family. A transparent `rule_mapping.json` records the
  mapping. Unmatched families count as unsupported, not silently negative.
- Precision, recall, specificity, and false-positive rate on applicable
  fixtures.
- Directional result for any clean/degraded pair: whether the degraded example
  has more relevant issues than its control.
- Repeatability across two unchanged scans.
- Run 13 issue prevalence and rule distribution.
- Scanner upload time and server compute time.

## Interpretation gates

- **Useful offline baseline:** at least two taxonomy families have direct rule
  coverage, mapped-fixture precision is at least 0.80, and results are
  deterministic across two scans.
- **Useful taxonomy complement:** SonarQube reliably covers general code-quality
  or security concerns but leaves taxonomy-specific performance categories
  unsupported. Report the complement; do not collapse all issues into a
  performance label.
- **Not suitable as a reward:** any known false positives on controls, missing
  taxonomy coverage, project-level latency, or server dependence prevents use
  in the online per-completion GRPO path without further validation.

The small fixture set provides pilot evidence only; it is not a claim of
general real-world accuracy.

## Separated exploratory extension

After the two unchanged frozen-dataset scans, one additional scan may add:

- the eight clean/degraded pairs already used in the CodeQual pilot, including
  its shell-injection pair; and
- a snapshot of the current `train.py`, identified by SHA-256.

This extension answers whether SonarQube adds broader maintainability or
security evidence and whether it finds actionable issues in the research
script. It is reported separately and does not alter the frozen-fixture
accuracy or determinism result.
