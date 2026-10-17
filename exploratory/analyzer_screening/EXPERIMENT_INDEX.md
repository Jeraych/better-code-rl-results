# Analyzer experiment index

This page links the analyzer-selection evidence used by the training research.
Status labels distinguish executed evidence from prepared work.

- [Analyzer method and final-decision audit](ANALYZER_METHOD_AUDIT.md)

## Current branch: deterministic reward candidates

- [Loop 1 protocol and command](README.md)
- [Loop 1 numerical results](results/first_loop/FIRST_LOOP_RESULTS.md)
- [Loop 1 remote decision](results/first_loop/REMOTE_CANDIDATE_DECISION.md)
- [Loop 1 machine-readable artifact](results/first_loop/first_loop_summary.json)
- [Loop 2 frozen fixtures](loop2_fixtures.py)
- [Loop 2 runner](screen_extended_candidates.py)
- [Loop 2 numerical results](results/loop2/LOOP2_RESULTS.md)
- [Loop 2 integration decisions](results/loop2/ANALYZER_INTEGRATION_DECISIONS.md)
- [Loop 2 machine-readable artifact](results/loop2/loop2_summary.json)

GitHub branch:
[`experiment/codequal-metrics-training`](https://github.com/Jeraych/UnSloth-RL/tree/experiment/codequal-metrics-training/experiments/analyzer_screening)

## Prior linked experiments

- CodeQual aggregate/custom-family pilot, commit `8afbb9e`:
  [`experiment/codequal-analyzer-pilot`](https://github.com/Jeraych/UnSloth-RL/tree/experiment/codequal-analyzer-pilot/experiments/codequal_analyzer_pilot)
- SonarQube pilot, commit `efcfea6`:
  [`experiment/sonarqube-pilot`](https://github.com/Jeraych/UnSloth-RL/tree/experiment/sonarqube-pilot/experiments/sonarqube_pilot)
- AI-judge calibration preparation, commit `26db49b`:
  [`experiment/remote-experiment-prep`](https://github.com/Jeraych/UnSloth-RL/tree/experiment/remote-experiment-prep/experiments/ai_judge_prompt_calibration)

## Current remote-training disposition

For the present HumanEval distribution, the only next conditional comparison
is matched `cq-core` versus `cq-pep8` training. No loop-2 analyzer is approved
as a new online reward. This is a pre-remote selection decision, not a claim
that Ruff improves general code quality.
