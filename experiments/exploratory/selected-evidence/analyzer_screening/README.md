# Offline analyzer candidate screening

See the [experiment index](EXPERIMENT_INDEX.md) for all protocols, result
artifacts, prior pilots, and current remote-training decisions.

This stage decides which deterministic analyzer signals are sufficiently
available, activating, and variable to justify remote GRPO training. It does
not require a model, GPU, or live AI judge.

The screen:

- uses the Ruff/PEP8-style and dynamic-performance diagnostics already stored
  in run CSVs;
- re-runs the AST-only StringConcat analyzer on test-passing saved code;
- records source hashes, coverage, activation, ceiling rate, within-group
  variation, latency where available, and a frozen candidate decision; and
- writes both machine-readable JSON and a report-ready Markdown record.

Run the first loop from the repository root:

```bash
python experiments/analyzer_screening/screen_candidates.py \
  --input results/12/samples.csv \
  --input results/13/samples.csv \
  --input results/15/all-metrics/samples.csv \
  --output-dir experiments/analyzer_screening/results/first_loop
```

The default gates are screening heuristics fixed before inspecting this
loop's results. They are not universal statistical standards:

- at least 100 available observations;
- at least 90% availability among test-passing completions;
- 5%-95% activation for ordinary static signals;
- at least 10% of comparable GRPO groups with non-zero variation;
- for dynamic performance, no more than 75% at the score ceiling and at least
  25% of comparable groups with non-zero variation.

Only `promote` candidates should be included unchanged in the next remote
training plan. `hold` requires broader data or validation. `redesign` means
the current reward formulation should not consume confirmatory remote compute.

## Extended candidate loop

Loop 2 screens Radon complexity, entry-point-filtered Vulture dead code,
selected Pylint exception and structure rules, Bandit security, and Mypy type
safety. Install the frozen local dependencies and run against the latest
test-passing saved outputs:

```bash
python -m pip install -r experiments/analyzer_screening/requirements-loop2.txt
python experiments/analyzer_screening/screen_extended_candidates.py \
  --python .venv/bin/python \
  --input results/15/all-metrics/samples.csv \
  --output-dir experiments/analyzer_screening/results/loop2
```

On Windows, use `.venv/Scripts/python.exe` for both commands. The labelled
fixtures are frozen in `loop2_fixtures.py`. They are purpose-built development
cases, so passing them establishes candidate feasibility rather than external
validity.

Prior experiments remain separate and are linked from the loop-2 decision
record:

- CodeQual aggregate and custom-family pilot: branch
  `experiment/codequal-analyzer-pilot` at commit `8afbb9e`;
- SonarQube pilot: branch `experiment/sonarqube-pilot` at commit `efcfea6`;
- StringConcat, Ruff, and dynamic-performance loop 1:
  `results/first_loop/` on the current branch.
