# Analyzer integration decisions after loops 1 and 2

**Evidence status:** pre-remote decision based on controlled offline screens  
**Experiment index:** [`../../EXPERIMENT_INDEX.md`](../../EXPERIMENT_INDEX.md)

For the full description of each analyzer, evaluation method, failure mode, and
justified next action, see the
[`Analyzer method audit`](../../ANALYZER_METHOD_AUDIT.md).

## Current decision

Do not add any loop-2 analyzer as a new GRPO reward on the current HumanEval
dataset. The next remote experiment remains a reduced, matched comparison of
`cq-core` versus the existing Ruff `E,W` configuration (`cq-pep8`) with at
least three matched seeds.

## Why each analyzer is or is not integrated

| Analyzer | Integration decision | Evidence-based reason |
|---|---|---|
| Ruff `E,W` | Conditional remote comparator | Loop 1 had 28.4% activation and 8.1% aggregate group variation; Run 15 alone reached 10.1%. It narrowly missed the frozen aggregate gate but has enough prior signal for a small matched confirmation. |
| AST StringConcat | Do not integrate on current HumanEval | Only 1/2,878 correct saved completions activated. The implementation is fast and passes 12 development fixtures, but the current dataset supplies essentially no learning signal. |
| Dynamic performance | Redesign before integration | 80.9% of measured completions reached the score ceiling and only 12.2% of groups varied, below the 25% performance gate. |
| Radon complexity | Do not integrate on current HumanEval | Zero findings in 960 correct Run 15 outputs, despite detecting its purpose-built fixtures. Use only on harder or repository-scale tasks. |
| Vulture dead code | Offline diagnostic only | Only 2.08% activation and 1.47% group variation. Entry-point filtering reduces a known false positive, but imports and helper functions still require contextual interpretation. |
| Pylint exception rules | Do not integrate on current HumanEval | Zero findings and zero group variation. These rules may be useful on targeted reliability tasks, not the present benchmark. |
| Pylint structure rules | Do not integrate on current HumanEval | Zero findings and zero group variation. Threshold-based project smells do not activate on short HumanEval functions. |
| Bandit security | Offline security audit only | Only two `B101` findings. Penalising valid assertions would not measure functional or general code quality, and subprocess-based execution is unsuitable for the current online reward path. |
| Mypy type safety | Do not integrate in current configuration | Activation was 24.79%, but group variation was only 5.89% and findings were dominated by missing typing names from omitted prompt context. Re-run on reconstructed full modules before treating it as an evaluator. |
| CodeQual aggregate score | Do not integrate | Prior pilot found compressed score resolution, entry-point artefacts, exploitable per-character normalization, known custom-rule false positives, and roughly 0.9 s per solution. Preserve per-rule findings only. |
| CodeQual resource-loop rule | Reject as reward | Prior labelled controls exposed numeric-accumulator false positives and a 0.333 family false-positive rate. |
| CodeQual data-structure rule | Reject as reward | Prior controls exposed ordinary lookup-table false positives and a 0.500 family false-positive rate. |
| SonarQube default profile | Repository QA only | Prior pilot detected 1/12 positives and no issues in 50 sampled generated outputs. It is a reporting/quality-gate layer rather than a per-completion reward. |
| AI judge | Deferred | Live remote access and independent calibration are required. Successful calls or mock responses do not establish label validity. |

## Candidates for a different dataset

The following analyzers remain reasonable research candidates if a targeted
dataset is added and frozen before training:

- StringConcat for repeated string-building tasks;
- Radon and selected Pylint structure rules for longer multi-branch functions;
- Pylint exception handling for reliability tasks containing error paths;
- Bandit for security-specific tasks, as an offline measure;
- Mypy after reconstructing the complete prompt/import context;
- filtered Vulture as a secondary offline maintainability measure.

Results from a targeted dataset must be reported as a separate stratum and
must not be pooled directly with the current HumanEval screen.

## Linked evidence

- [Loop 1 results](../first_loop/FIRST_LOOP_RESULTS.md)
- [Loop 1 decision](../first_loop/REMOTE_CANDIDATE_DECISION.md)
- [Loop 2 numerical results](LOOP2_RESULTS.md)
- [Loop 2 machine-readable summary](loop2_summary.json)
- [CodeQual prior pilot](https://github.com/Jeraych/UnSloth-RL/tree/experiment/codequal-analyzer-pilot/experiments/codequal_analyzer_pilot)
- [SonarQube prior pilot](https://github.com/Jeraych/UnSloth-RL/tree/experiment/sonarqube-pilot/experiments/sonarqube_pilot)
