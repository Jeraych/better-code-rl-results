# Final codequal_analyzer decision

## Decision

- **Research evaluation: GO, with restrictions.** Use selected rule findings as
  an offline comparison metric and report the limitations explicitly.
- **Online GRPO reward in `train.py`: NO-GO.** Do not add the current analyser
  or its scalar score to the reward path.
- **Existing dynamic performance reward: retain.** The analyser's static loop
  heuristics must not replace controlled runtime and memory measurements.

This decision follows the gates frozen in `FINAL_TEST_PROTOCOL.md` before the
test was run.

## Controlled accuracy results

The full quick configuration evaluated 23 pre-labelled fixtures twice:

| Metric | Result | Offline gate |
|---|---:|---:|
| Precision | 0.833 | >= 0.80 |
| Recall | 0.833 | >= 0.70 |
| False-positive rate | 0.182 | <= 0.20 |
| Mean time per solution | 926 ms | <= 2,000 ms |
| Deterministic | Yes | Required |

The aggregate offline gate passed, but reliability differed substantially by
rule family:

| Rule family | Precision | Recall | False-positive rate | Result |
|---|---:|---:|---:|---|
| Cyclomatic complexity | 1.000 | 1.000 | 0.000 | Passed pilot |
| Dead code | 1.000 | 1.000 | 0.000 | Passed pilot |
| Exception handling | 1.000 | 1.000 | 0.000 | Passed pilot |
| Data-structure complexity | 0.667 | 1.000 | 0.500 | Failed precision/control gate |
| Resource use in loops | 0.750 | 1.000 | 0.333 | Failed false-positive gate |
| String concatenation | 1.000 | 0.333 | 0.000 | Failed recall gate |

These estimates use very small, purpose-built samples. A family marked
"passed" is suitable for a controlled comparison, not a claim of general
real-world accuracy.

## Exact failure cases

- String concatenation detected `result += str(value)` but missed the common
  forms `result += value` and `result += f"{value}"`.
- Resource-consumption analysis correctly detected file operations, sleeping,
  and list growth in loops, but also marked ordinary numeric accumulation
  (`total += value`) as excessive resource consumption.
- Data-structure analysis detected deep nesting and classes with many
  attributes, but also penalized a legitimate 11-entry lookup dictionary.

These failures directly affect the performance-related rules most relevant to
the current research. Their raw findings should be treated as heuristic flags,
not ground truth or rewards.

## Robustness and integration results

- Arbitrary HumanEval entry-point names were successfully removed from Vulture
  dead-code findings.
- Adding 80 comments did not change the selected rule findings.
- Renaming an entry point while supplying the new name did not change findings.
- Invalid syntax was rejected before analysis.
- Candidate code was never executed.
- Results were deterministic across both repetitions.

The AST-only adapter was also dry-run on 50 existing Run 13 completions:

- 50/50 analyses completed successfully.
- Entry points were extracted for 50/50 examples.
- Eight examples received findings, all from the resource-consumption rule.
- Mean time was 10.9 ms per solution; maximum was 69.4 ms.

Technical integration is therefore feasible, but the AST-only accuracy gate
failed:

| Metric | Result | Online gate |
|---|---:|---:|
| Precision | 0.800 | >= 0.80 |
| Recall | 0.800 | >= 0.80 |
| False-positive rate | 0.222 | <= 0.10 |
| Mean fixture time | 4.2 ms | <= 100 ms |

The failure is validity, not speed. Adding these rules to GRPO would reward and
penalize known incorrect cases, especially numeric accumulators and ordinary
lookup dictionaries.

## How it can help the research

Use it offline to report:

- Cyclomatic-complexity findings.
- Dead-code findings after filtering the known task entry point.
- Exception-handling findings as a separate reliability dimension.
- Static performance/data-structure flags only as explicitly labelled
  heuristics with false-positive caveats.

Do not use:

- `overall_per_kchar`.
- The released aggregate score as ground truth.
- Resource-loop, string-concatenation, or data-structure findings directly as
  GRPO rewards.
- Static flags as substitutes for the existing runtime/memory benchmark.

## Mapping to `train.py`

The current script already has appropriate separation:

- Syntax and compilation gates.
- Functional tests.
- Style reward.
- Dynamic performance reward using repeated runtime and memory comparison.
- AI judge for taxonomy-defined readability and maintainability issues.

If codequal results are later exposed in the script, they should initially be
diagnostic-only fields written to evaluation CSVs. They should not contribute
to `reward_total` until a larger externally labelled validation demonstrates
that the selected rules are reliable.

## Next step

Freeze this codequal result and move to SonarQube. Reuse the same 23 labelled
fixtures and the same deterministic 50-output Run 13 sample so the comparison
covers accuracy, false positives, coverage, runtime, and integration effort.
