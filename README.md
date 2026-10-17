# better-code-rl-results

Experiments and saved results for **Can AI Learn to Write Better Code on Its Own? Reinforcement Learning for Enhancing LLM Coding Agents**, SOFTENG 700, Project 13 (2026).

Research authors: **Jacky Zhang and Conrad Ang**. Supervisors: James Tizard and Henry Williams, University of Auckland.

This experiments/results repository is at [Jeraych/better-code-rl-results](https://github.com/Jeraych/better-code-rl-results). Both authors have agreed to inclusion of their project code and saved research records, and to MIT licensing of their original project code. Repository visibility is managed separately; preparation and the initial upload were private. It starts with fresh Git history; earlier source commits remain provenance references to restricted repositories. The individual final report is separate and excluded, together with its manuscript sources, the university logo, the Canvas submission package, signatures and the raw named reviewer export.

This snapshot redacts token-like, address-like and path-like strings from 23 early-pilot completion cells, minimises machine/time metadata and omits environment/settings examples. All formal/Base CSVs, recorded numerical outcomes and human-review responses/code remain intact. [Privacy transformations and exclusions](manifests/privacy-transformations.json) record the source and distributed hashes without exposing removed values.

## Recompute saved results

From the repository root, use Python 3.10 or newer; the checks require only its standard library:

```sh
python analysis/verify_all.py
python -m unittest discover -s tests -v
python -m unittest discover -s exploratory/remote_run_bundle/tests -v
python analysis/security_scan.py
```

The verifier checks archived input bytes first, recomputes into temporary output and compares four derived JSON snapshots by parsed content. It does not rewrite tracked evidence. To retain fresh LF JSON, choose a new directory:

```sh
python analysis/verify_all.py --output-dir runs/verification-local
```

Local acceptance on 17 October 2026 passed saved-data recomputation, all 67 CPU tests and the all-file privacy scan.

These commands inspect saved records without training, model inference, generated benchmark-code execution or live Judge requests. Some unit tests run controlled synthetic subprocess fixtures. Optional [plot generation](analysis/make_figures.py) requires [Matplotlib and NumPy](analysis/requirements-figures.txt). See the [verification directory](verification/) for recorded check status and scope.

## Recorded results and evidence

All twelve formal runs are retained: 2,400 held-out outputs and 24,000 training rows, plus 600 archived pretrained Base outputs. Each condition has three seeds, 50 held-out tasks and four generations per task/seed.

| Condition | Test-passing | Ruff-clean | Both |
|---|---:|---:|---:|
| C: correctness-focused | 545/600 | 394/600 | 358/600 |
| S: C + Ruff | 526/600 | 565/600 | 495/600 |
| J: C + Judge | 542/600 | 454/600 | 410/600 |
| SJ: C + Ruff + Judge | 527/600 | 568/600 | 495/600 |

These are descriptive output-level rates, not pass@k or independent task counts. Run 35's 70 training timeout rows affected rewards and limit C–S and S–SJ attribution. The two-author study contains 150 judgments over 140 distinct, both-correct non-identical pairs from 47 tasks. Five of ten independent overlaps agree (pooled κ=0.2537313433). This is conditional author preference evidence, not an external-developer study or proof of Judge finding accuracy.

Use the [evidence map](EVIDENCE_MAP.md) for exact files, fields, denominators and limitations. The [research record](RESEARCH_RECORD.md) contains methods, screening, history, environment and missing-artifact details.

## Repository contents

| Location | Contents |
|---|---|
| [training/historical/](training/historical/) | Identified historical trainer sources and documented privacy derivatives |
| [training/configs/](training/configs/) | Four-condition, three-seed configuration and provenance limits |
| [training/scripts/](training/scripts/) | Reconstruction launcher; dry-run is the default |
| [data/formal/](data/formal/) and [data/base/](data/base/) | All formal training/holdout records and archived Base outputs |
| [data/human-validation/](data/human-validation/) | Pseudonymous formal responses, frozen catalog and source mappings |
| [exploratory/](exploratory/) | Available pilots, screens, failures and clearly labelled prepared-only plans |
| [analysis/](analysis/) and [tests/](tests/) | Offline recalculation, diagnostics and CPU regressions |
| [figures/](figures/) | Three research plots and their plotted data |
| [manifests/](manifests/) and [verification/](verification/) | Provenance, strict input hashes and verification records |
| [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | MIT grant for original project code/documentation and scoped external notices |

## Reconstructing training

```sh
python training/scripts/run_formal.py --condition C --seed 3407 --stage train --dry-run
python training/scripts/run_formal.py --condition SJ --seed 3409 --stage train --dry-run
```

The launcher loads no model unless `--execute` is explicit. Read the [training record](RESEARCH_RECORD.md#historical-training-and-the-new-convenience-launcher) before using it. For authenticated Judge services, set `AI_JUDGE_API_KEY` in the environment; it is passed to the child without inclusion in saved/printed plans. No endpoint or credential is supplied. Complete immutable model/dataset/Judge revisions, original adapters and a solved GPU environment are unavailable, so exact historical retraining is unverified.

## Citation and rights

[CITATION.cff](CITATION.cff) identifies this collaborative experiments/results artifact. Cite the exact commit used and report the access available at that time; this artifact has no DOI or published release identifier.

The [MIT license](LICENSE) covers original project code and original supporting documentation. It does not relicense third-party code, benchmark prompts/tests, model material, generated outputs or recorded study data. The authors have approved inclusion of the minimised study records. These records are pseudonymous rather than guaranteed anonymous; no blanket data or model-output license is added. Consult [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the [retained license texts](licenses/) for the relevant sources and terms. Source/privacy transformations are recorded in [the provenance manifest](manifests/files.csv); raw originals and prior source repositories remain restricted.
