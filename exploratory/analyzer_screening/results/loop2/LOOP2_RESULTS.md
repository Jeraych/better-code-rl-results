# Extended analyzer screening: loop 2 results

**Evidence status:** controlled offline screening  
**Input:** `results/15/all-metrics/samples.csv`  
**Input SHA-256:** `d111b74189b3bad0005c56ca35b089308cebb6f8ffcb7fa99fb37cf83f02f468`  
**Rows:** 1,000 total; 960 test-passing completions screened

## Frozen protocol

Six analyzer families were selected before inspecting saved-output outcomes:
Radon complexity, entry-point-filtered Vulture dead code, selected Pylint
exception and structure rules, Bandit security, and Mypy type safety.

Each analyzer was run twice on four purpose-built fixtures: two expected
positives and two negative controls. All six produced precision 1.00, recall
1.00, false-positive rate 0.00, and identical findings across both repetitions.
These small development fixtures establish intended configuration behaviour,
not external validity.

Frozen saved-output gates required 90% availability, 5%-95% activation, and
non-zero reward variation in at least 10% of comparable GRPO groups. An online
candidate also needed in-process execution and mean analysis time no greater
than 5 ms.

## Saved-output results

| Analyzer | Version | Availability | Activations | Activation rate | Groups varying | Variation rate | Mean ms/item | Automatic disposition |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Radon complexity | 6.0.1 | 960/960 | 0 | 0.000% | 0/475 | 0.000% | 0.096 | Reject current dataset |
| Vulture dead code | 2.16 | 960/960 | 20 | 2.083% | 7/475 | 1.474% | 0.182 | Offline evaluator only |
| Pylint exception rules | 4.0.6 | 960/960 | 0 | 0.000% | 0/475 | 0.000% | 2.498* | Reject current dataset |
| Pylint structure rules | 4.0.6 | 960/960 | 0 | 0.000% | 0/475 | 0.000% | 2.498* | Reject current dataset |
| Bandit security | 1.9.4 | 960/960 | 2 | 0.208% | 2/475 | 0.421% | 1.853* | Offline evaluator only |
| Mypy type safety | 2.3.1 | 960/960 | 238 | 24.792% | 28/475 | 5.895% | 3.524* | Offline evaluator only |

`*` Pylint, Bandit, and Mypy timings are total batch time divided by the number
of files. They do not establish the latency of invoking the tool once per GRPO
completion.

## Finding composition

- Vulture: 10 unused `List` imports; six `encode_cyclic` functions; and a small
  number of functions, variables, or imports. Prompt-derived HumanEval entry
  points were filtered before counting findings.
- Bandit: both findings were `B101` (`assert` use). One verified example was
  the valid HumanEval `string_xor` implementation asserting equal input
  lengths, illustrating that a security warning is not automatically a useful
  training penalty.
- Mypy: 278 `name-defined`, 11 `var-annotated`, two `assignment`, and one
  `return` finding. A verified `name-defined` example used `List[int]` from the
  task context without repeating the import in the extracted completion.
  Completion-only Mypy therefore confounds type quality with omitted prompt
  context.

## Reproducibility

Run from the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r experiments\analyzer_screening\requirements-loop2.txt
.\.venv\Scripts\python.exe experiments\analyzer_screening\screen_extended_candidates.py --python .\.venv\Scripts\python.exe --input results\15\all-metrics\samples.csv --output-dir experiments\analyzer_screening\results\loop2
```

The full metrics, fixture rows, criteria, tool versions, and limitations are in
[`loop2_summary.json`](loop2_summary.json).
