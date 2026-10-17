# SonarQube pilot results

## Decision

- **Use SonarQube for offline repository and `train.py` quality assurance.** It
  found several concrete maintainability findings that the taxonomy evaluator
  is not intended to replace.
- **Use it as a secondary comparison baseline, not the research metric.** Its
  sparse results provide useful evidence about what a general static analyser
  does and does not cover.
- **Do not add it to the online GRPO reward.** The local server dependency,
  project-level latency, thresholded rules, and very low recall make it a poor
  per-completion reward source.
- **Keep the existing taxonomy-grounded AI judge and dynamic performance
  measurements.** SonarQube did not detect the tested string accumulation,
  repeated resource use, data-structure, or runtime-performance patterns.

## Frozen comparison result

The first two scans used exactly the same 23 labelled fixtures and deterministic
50-output Run 13 sample as the CodeQual decision test. Candidate code was never
executed.

| Result | SonarQube default Python profile |
|---|---:|
| Active Python rules | 362 |
| Labelled fixtures | 23 |
| Positive fixtures detected | 1/12 |
| Negative controls flagged | 0/11 |
| Run 13 outputs with issues | 0/50 |
| Issues in either unchanged scan | 1 |
| Identical rule/file/line/message | Yes |

The sole finding was `python:S5754` on a bare `except`. For the eight fixtures
belonging to families with at least partial direct Sonar rule coverage, the
metrics were precision 1.00, recall 0.25, specificity 1.00, and false-positive
rate 0.00 (TP=1, TN=4, FP=0, FN=3). Unsupported families were not silently
treated as if Sonar had evaluated them.

| Taxonomy-related family | Sonar coverage | Positive detections | Control flags |
|---|---|---:|---:|
| Exception handling | Direct bare-except rule | 1/2 | 0/2 |
| Complexity | Direct but thresholded at 15 | 0/1 | 0/1 |
| Dead code | Partial scope only | 0/1 | 0/1 |
| String concatenation | Unsupported by a directly matching active rule | 0/3 | 0/2 |
| Resource use in loops | Unsupported by a generic matching active rule | 0/3 | 0/3 |
| Data-structure complexity | Unsupported by a directly matching active rule | 0/2 | 0/2 |

This is high precision caused partly by conservative reporting, not strong
taxonomy coverage. The zero findings on all 50 Run 13 outputs also means the
default profile supplies no ranking or reward signal on that sample.

## Exploratory clean/degraded pairs

A separate post-freeze scan added the eight pairs already used in the CodeQual
pilot. SonarQube assigned more issues to the degraded program in 1/8 pairs (the
bare-exception pair), tied on 7/8, and reversed none. It did not distinguish the
string concatenation, file-open-in-loop, branch, shell-injection, unused public
function, nested allocation, or blocking-loop pairs under the default profile.

These ties are meaningful missing coverage; they should not be reported as
correct classifications.

## Findings on the research script

The same exploratory scan analysed a SHA-256-identified snapshot of `train.py`
and reported 12 issues:

| Rule | Count | Interpretation |
|---|---:|---|
| Cognitive complexity (`python:S3776`) | 4 | Useful refactoring candidates, especially `analyze_completion` at complexity 43 |
| Duplicate literals (`python:S1192`) | 4 | Mixed value; taxonomy labels and repeated mock code are partly intentional |
| Redundant exception types (`python:S5713`) | 2 | Valid: `JSONDecodeError` is already covered by `ValueError` |
| Nested conditional (`python:S3358`) | 1 | Readability improvement candidate |
| Regex character class (`python:S6353`) | 1 | Valid but minor simplification |

This is where SonarQube helps most: independent maintainability checks on the
research implementation. These findings were recorded only; the pilot did not
change `train.py`.

## Timing and deployment cost

| Scan | Python analyser | End to end | Outcome |
|---|---:|---:|---|
| Frozen scan 1, 73 files | 2.237 s | 24.231 s | Quality gate passed |
| Frozen scan 2, unchanged | 2.533 s | 15.895 s | Quality gate passed |
| Exploratory scan, 90 files | 4.990 s | 20.254 s | Quality gate failed |

Docker image download (68.1 s) and server initialization (36.6 s) were one-time
setup costs and were excluded from scan latency. The exploratory quality gate
failed because new coverage was 0%, duplicated-line density was 3.762%, and 13
issues were new relative to the preceding version. That gate is useful for a
repository workflow but is not a valid scalar score for isolated generated
functions without tests and a controlled baseline.

## Comparison with CodeQual

| Property | CodeQual pilot | SonarQube pilot |
|---|---|---|
| Main strength | Fast selectable AST heuristics; broader fixture recall | Mature project-level maintainability rules; low false alarms here |
| Labelled-fixture result | Precision 0.833, recall 0.833, FPR 0.182 | Mapped precision 1.00, recall 0.25, FPR 0.00 |
| Run 13 signal | 8/50 flagged by AST resource heuristic | 0/50 flagged |
| Known weakness | False positives in resource/data-structure rules | Most tested performance families absent or below thresholds |
| Online reward suitability | No-go because of validity | No-go because of coverage, latency, and server dependency |
| Best research use | Restricted offline heuristic comparison | Offline repository QA and conservative secondary baseline |

The results support the research gap: existing pipelines and generic static
analysers can supply infrastructure and broad quality checks, but they do not
operationalize the project-specific inefficiency taxonomy. The taxonomy-grounded
approach adds explicit category definitions, per-category coverage reporting,
negative-control validation, and links between static judgement and controlled
runtime/memory evidence. This prevents a sparse general-purpose tool result from
being mistaken for a complete performance-quality measure.

## Files to cite or show

- `results/summary.json`: compact machine-readable outcome.
- `results/fixture_results.csv`: every labelled decision.
- `results/pair_results.csv`: all eight clean/degraded comparisons.
- `results/train_py_issues.csv`: exact `train.py` findings and line numbers.
- `results/run13_results.csv`: all 50 sampled generations.
- `rule_mapping.json`: transparent taxonomy-to-rule mapping.
- `PROTOCOL.md`: pre-specified core protocol and separated extension.
