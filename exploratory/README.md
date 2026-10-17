# Exploratory studies and historical runs

This is the single home for exploratory evidence. A run or study folder keeps its available saved data, code, protocols and findings together. These records explain the screening and development history; they are not extra arms of the twelve-run formal comparison.

| Study | Entry point |
|---|---|
| Candidate feedback screening | [Experiment index](analyzer_screening/EXPERIMENT_INDEX.md) and [method audit](analyzer_screening/ANALYZER_METHOD_AUDIT.md) |
| CodeQual analyzer pilot | [Pilot files](codequal_analyzer_pilot/) |
| CodeQual-inspired AST checks | [Detector source](codequal-source/) and [training/validation pilot](codequal_training/) |
| SonarQube screening | [Protocol](sonarqube_pilot/PROTOCOL.md) and [saved results](sonarqube_pilot/RESULTS.md) |
| Completed Judge prompt comparison | [Report](prompt-ab/REPORT.md) and [candidate rows](prompt-ab/per_candidate.csv) |
| Prepared Judge calibration | [Preparation manifest](ai_judge_prompt_calibration/PREPARATION_MANIFEST.json) and [results status](ai_judge_prompt_calibration/results/README.md); preparation is not a completed study |
| Remote preparation tools | [Bundle](remote_run_bundle/); retained fixtures use synthetic credentials |
| Numbered pilots and failed runs | [Historical run index](historical-run-index.json); `run-*` folders retain the original identifiers |
| HumanEval+ recovery and startup debugging | [Corrected recovery](corrected_20260913/README.md) and [startup records](startup-debug-20260910-084554/) |

The run index uses original source paths and hashes. Current locations and transformations are mapped in [the file manifest](../manifests/files.csv) and [duplicate-source index](../manifests/duplicate-sources.json); a missing numbered folder may represent shared evidence or an explicitly missing record.

Use the root [offline verification commands](../README.md#recompute-saved-results) to recompute supported saved results. Historical scripts may require their original source layout, services and dependencies; they are not promised as portable launchers. No new pilot, model inference or Judge request is needed for offline verification.
