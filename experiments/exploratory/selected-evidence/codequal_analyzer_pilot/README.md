# codequal_analyzer pilot

This directory contains a short, local evaluation of
[`MaximeRobeyns/codequal_analyzer`](https://github.com/MaximeRobeyns/codequal_analyzer)
at commit `518360297f59ad7b6569233eb4b934e6b00c083b`.

The experiment deliberately avoids human labels and model inference. It uses:

1. Eight paired synthetic programs with known seeded static-quality defects.
2. A deterministic random sample of 50 correct, successfully judged Run 13
   generations from a population of 934 eligible outputs.
3. A padding probe that adds comments without changing executable code or
   findings.

The synthetic experiment is a sensitivity/sanity check, not evidence of
real-world accuracy. The Run 13 comparison measures agreement with existing AI
judge and style scores, not ground-truth validity.

## Environment

- Python 3.12
- Isolated virtual environment outside this repository
- Dependency versions pinned in `requirements-pilot.txt`
- Quick/static analyser set: Pylint, Bandit, Radon, Vulture, and four bundled
  AST analysers
- No generated code is executed

The upstream project uses the Unix-only `which` command when checking tool
availability, so it does not recognize installed analysers on Windows. Apply
`patches/windows-compat.patch` to a dedicated branch of the analyser clone. The
patch also corrects the `run_analyzer`/`run_analyzers` typo in the full feedback
API. Neither change alters a scoring rule.

## Reproduction

From this directory, with the analyser cloned under
`SOFTENG700/tmp/research_codequal_analyzer`:

```powershell
python -m venv ..\..\..\tmp\codequal_pilot_venv
..\..\..\tmp\codequal_pilot_venv\Scripts\python.exe -m pip install -r requirements-pilot.txt
$pilot = (Get-Location).Path
git -C ..\..\..\tmp\research_codequal_analyzer apply "$pilot\patches\windows-compat.patch"
..\..\..\tmp\codequal_pilot_venv\Scripts\python.exe run_pilot.py --sample-size 50 --synthetic-repetitions 3
..\..\..\tmp\codequal_pilot_venv\Scripts\python.exe summarize_results.py
```

Outputs are written to `results/`. See `RESULTS.md` for the interpretation.

The final decision-oriented test is specified in `FINAL_TEST_PROTOCOL.md` and
run with:

```powershell
..\..\..\tmp\codequal_pilot_venv\Scripts\python.exe run_decision_test.py --repetitions 2
..\..\..\tmp\codequal_pilot_venv\Scripts\python.exe run_script_smoke.py
```

See `FINAL_DECISION.md` for the resulting research and `train.py` recommendation.
