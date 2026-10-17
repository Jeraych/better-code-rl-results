# Research record and reconstruction limits

This record documents the methods, source history and limits of the experiments/results repository. It derives from the prior private `better-code-rl` archive at `c8390ecc495c1a50814db0c7737facbe3034baa2`, without importing that repository's Git history. Earlier commit identifiers below are provenance references to restricted source repositories. On 17 October 2026 the user confirmed both authors' agreement to inclusion of their project code and saved research records, and to MIT licensing of original project code. Preparation and the initial upload were private; visibility is managed separately. The final report and its sources, university logo and separate Canvas submission package are excluded. Current entrypoints and rights are in [README.md](README.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Retained verification design

The verifier now checks archived input and snapshot bytes first, recomputes into temporary output, and compares JSON values and structure. Explicit new output directories can retain canonical UTF-8/LF JSON. Archived raw records and their expected hashes were not rewritten to accommodate line endings. Simulated CRLF/LF regression tests cover this boundary; an actual second-OS run is not asserted.

The convenience launcher passes caller `AI_JUDGE_API_KEY` only into the child process environment. Synthetic-key mock tests check that it is absent from dry-run output, stdout/stderr and the saved execution plan. No real training, Judge service request or credential validation was performed. Historical trainers are unchanged.

These statements describe the retained verifier and its prior regression coverage. They do not certify the new repository snapshot before its own checks; [verification/](verification/) records the available verification scope.

## Historical training and the new convenience launcher

[training/historical/judge/train.py](training/historical/judge/train.py) comes from the clean `experiments/correctness-judge-formal` worktree at f2a2c780491a74bc8a93621dacc2aa6412819b0c. Original Windows bytes hash to 98a536d8317a5fc71dcabeafa51d21e686e90afabc0ef2f5b700ff1102b93308; replacing CRLF with LF, and nothing else, gives edb8384bc6812850e623edba14a8ae18272e3f804458abbc0f67108775ceddcc, exactly the six J/SJ runtime source records. The original reliability module normalizes to 2c1940049a7965a0dd221c2e0c6d5e5dbcffa98956dbb8a9f03b291cfdb3829a. Exact raw source is restricted; the candidate substitutes a dummy private endpoint, so its distributed hash is different and recorded in [manifests/files.csv](manifests/files.csv).

[training/historical/cs/train.py](training/historical/cs/train.py) is the actual Git blob at 8cc4accd0c687a040543a791e472e3f5b236e2e2. Startup logs establish C/S configuration and fresh adapters; they do not establish a complete runtime trainer hash. This is the best archived implementation candidate, not a falsely certified exact C/S runtime binary. Dirty current `main`/HumanEval+ trainers were not used in its place.

Historical launchers retain private-repository assumptions and original frozen source checksums. They are reference material, not the portable entrypoint. Use [training/scripts/run_formal.py](training/scripts/run_formal.py); it preserves the reward functions, prompt, correctness gate, dataset boundaries and fresh-adapter policy. Distributed privacy substitutions are recorded in the manifest; raw source snapshots remain restricted.

### Explicit train and evaluation stages

Run on an isolated Linux NVIDIA/CUDA research machine after installing a suitable PyTorch wheel and [training/requirements.txt](training/requirements.txt). Exact recorded package snapshots live alongside formal run evidence; the minimal requirements list avoids copying incompatible optional audio/vision packages. Dependency resolution and GPU execution have not been exercised here.

```sh
python training/scripts/run_formal.py --condition C --seed 3407 --stage train --dry-run
```

All commands in this record assume the repository root. Every stage gets a unique root by default. To actually train, explicitly provide `--execute`; this starts expensive GPU work. Example from the repository root:

```sh
python training/scripts/run_formal.py --condition C --seed 3407 --stage train --output-root runs/C-3407-train --execute
python training/scripts/run_formal.py --condition C --seed 3407 --stage eval-holdout --adapter runs/C-3407-train/adapter --output-root runs/C-3407-holdout --execute
```

Other stages are `base-train`, `base-holdout` and `eval-train`. Seeds are exactly 3407, 3408, 3409; arms C, S, J, SJ. LoRA evaluation requires an explicit completed adapter. Existing output paths are rejected, not resumed or cleared. Dry-run creates no directories and performs no model/API calls. For J/SJ set `AI_JUDGE_BASE_URL` to an authorized OpenAI-compatible service providing alias `qwen-32b`; original backend evidence names Qwen2.5-32B-Instruct-AWQ but does not pin immutable weights. No endpoint or token is supplied. Do not put credentials in command lines or committed files.

All conditions use core weights .1 format + .1 syntax + .3 execution-support + 4.5 tests. Execution-support is 1 for standalone success, .5 for a standalone nonzero return after syntax succeeds, and 0 on timeout/exception; it is not binary test correctness. Add Ruff 1 only in S/SJ and correctness-gated Judge 1 only in J/SJ. Performance contribution is 0. Historical C/S startup prints inactive performance/Judge weights of 1; the baseline profile disables their contribution. The new effective matrix uses explicit zero weights for them. C/S configuration is reconstructed from logs and archived defaults rather than a full environment dump. The optional before/after preview is disabled in this new runner; held-out protocol is unchanged. Judge's own request seed remains 3407 across policy seeds, as recorded in runtime metadata.

Original historical regressions are retained. The current CPU tests adapt their baseline lookup to the archived source rather than requiring private Git history; they test valid scoring/prompt equivalence, fail-closed Judge responses, retry boundaries and the HumanEval+ temporary-script execution fix. No generated benchmark completion is executed by the analysis commands.


## Frozen formal experiment

| Condition | Training runs | Policy seeds | Additional quality reward |
|---|---|---|---|
| C | 30, 31, 32 | 3407, 3408, 3409 | none |
| S | 33, 34, 35 | 3407, 3408, 3409 | Ruff 1 |
| J | 36, 37, 38 | 3407, 3408, 3409 | correctness-gated Judge 1 |
| SJ | 39, 40, 41 | 3407, 3408, 3409 | Ruff 1 + gated Judge 1 |

All retain core weights .1/.1/.3/4.5 (format/syntax/execution-support/tests), performance disabled, Qwen3.6-27B 4-bit all-linear LoRA rank/alpha16, dropout0, 500 updates, four generations, learning rate5e-6. HumanEval+ dataset `evalplus/humanevalplus`, split `test`: train [0,50), holdout [50,100). Every run starts fresh with AUTO_RESUME=0. See the per-run config/evidence rather than generic historical defaults with overlapping 0–164 subsets.

Each holdout has exactly 50 task identities × four generation ordinals = 200 outputs. Across arms/seeds these are 2,400 outputs, not 2,400 independent tasks. Every training CSV has 500 four-member groups = 2,000 rows. Recorded row-level rewards are recomputed without re-executing generated code. Original Run-32 evaluation `_1` and Run-33 training `_1` source names are preserved in the manifest; destination names are normalized for navigation.

Run35 is retained with limitation: 70 training timeout rows in21 groups,27 distinct task/raw-completion keys, concentrated in HumanEval15/39/25. A process-wide diagnostic cache reused timeout diagnostics. Its original cause remains unresolved; this is not an unqualified clean seed-only ablation. Formal Judge reliability is operational/schema evidence, not semantic finding accuracy.


## Complete research-direction index

[exploratory/historical-run-index.json](exploratory/historical-run-index.json) records every numbered slot1–29, actual available row files and their hashes/status counts. Missing run directories are explicitly missing, not fabricated experiments. Selected protocols/aggregates are grouped below. They remain exploratory and never enter the formal twelve-run pool.

| Direction | Actual evidence | Disposition |
|---|---|---|
| Early GRPO/model/format/syntax/correctness/Ruff pipeline, runs1–11 | Historical run index; original commit lineage in restricted inventory | Development, debugging and equipment/model sizing; not final comparison |
| Runtime/memory reward, Run12 | Complete pilot samples; actual e885869 trainer | Mean performance .975;81.1% eligible outputs at max;81.6% two-candidate groups zero total-reward variation in the saved Run12 record. Saturated; disabled in final matrix |
| Contextual Judge pilots13/15 | Run13 samples, actual af88078 trainer, Run15 four eval CSVs and original summaries | Pilots, separate from later reliability-hardened formal J |
| Alternative weights/queue, runs14/16–20/22 | Run index, original per-run summaries where present | Historical performance-inclusive runs; Run20 incomplete, not final evidence. Missing numbered slots are not presumed completed |
| HumanEval+ migration, runs27–29 | Original READMEs and index, corrected recovery source preserved privately | Partially broken reward pilots; not pooled with restart30–35 |
| CodeQual aggregate/custom checks | [exploratory/codequal_analyzer_pilot/](exploratory/codequal_analyzer_pilot/), commit8afbb9e | Labelled fixtures and generated-output pilot; mixed analyzer validity, no general aggregate reward promoted |
| SonarQube | [exploratory/sonarqube_pilot/](exploratory/sonarqube_pilot/), commitefcfea6 | Fixtures and generated-output screening; sparse target activation; offline role |
| Static StringConcat | [exploratory/codequal_training/](exploratory/codequal_training/), commit40dd044 | Fix/validation and negative prevalence result; one activation in2,878 correct outputs under historical source scope |
| Ruff/Radon/Vulture/Pylint/Bandit/Mypy screens | [exploratory/analyzer_screening/](exploratory/analyzer_screening/), commit40dd044; first-loop and loop2 JSON plus frozen fixtures | Predeclared activation, precision, locality, runtime and group-discrimination gates. No new loop2 reward promoted. Radon constant; context-related false positives retained |
| Eight-arm factorial | CodeQual README/analyze_factorial.py | Proposed/deferred; no claim that eight arms were trained |
| Judge prompt calibration144-call plan | [exploratory/ai_judge_prompt_calibration/](exploratory/ai_judge_prompt_calibration/), commit26db49b | Prepared plan, not evidence of144 completed calls |
| Historical vs conservative code-only Judge | [exploratory/prompt-ab/](exploratory/prompt-ab/), local source hashes | Executed saved A/B calibration; formal instrument retained. Structural reliability does not prove human alignment |
| Human review calibration/Play | Restricted final export; frozen protocol source | Calibration separate from Formal; Play excluded from formal result counts. Final export contains zero Play records |

The index represents all locally evidenced directions. Exact equipment serials, informal discussions and absent run numbers are not invented. Source-reported exploratory numbers are labelled separately from this release's freshly recomputed formal/author-study counts. Some historical scripts expect private source roots or third-party tools; their retained role is a traceable record, not a promise that all exploratory pilots are portable one-command jobs.


## Frozen formal author review

Input is the completed revision313 final research export (SHA-2567b8f2ba4df661b25e4526f72063281f5eb3729912fae35761a40c2e754546d70), not the older six-record export. Exact raw bytes, calibration records, reviewer names and precise timestamps remain in restricted source storage and are excluded here. No Play judgments enter Formal.

`formal-anonymized.json` uses an explicit allowlist: pair identity, A/B orientation, contrast/task, ordinal/seed/run/output/source hashes, eligibility, recorded code/status/scores, phase, canonical preference, criterion and frozen assignments. Names become reviewer_1/reviewer_2 and joint. Timestamps, response identifiers, private paths, access codes, calibration responses and Play records are removed. File name describes the intent; in a two-author population this is **pseudonymous**, not guaranteed anonymous. Both author-reviewers' agreement to inclusion of these minimised study records was confirmed by the user on 17 October 2026.

`source/catalog.json`, outputs-B/C/S/J/SJ and provenance preserve matching and eligibility. They contain frozen model outputs, not raw named reviewer records. Historical app protocol/import scripts are references, not a deployed replica. Private-repository and deployment instructions in the frozen source README concern the original review application; they do not describe visibility of this derived results archive or authorise a new app deployment. Offline analysis does not require the original web app or its credentials. [analysis/reproduce_human.py](analysis/reproduce_human.py) verifies the original displayed orientation against canonical preferences and frozen assignments, checks mappings/code hashes, then derives150 responses/140 pairs/47 tasks and5/10 independent agreement,kappa.2537313433. The10 calibration records and proposed legacy schedule counts do not replace executed formal assignments.


## Attribution and license scope

Research authors: Jacky Zhang and Conrad Ang, University of Auckland, SOFTENG700 Project13. Supervisors: James Tizard and Henry Williams. The project code and evidence are collaborative. Recorded commits support Jacky's reward integration, performance/Judge/analyzer investigation and evidence recovery; Conrad's configurable launcher, checkpoints/resumption, dashboards and multiple runs/configurations are distinct team contributions. Commit metadata is partial evidence; it does not prove exclusive authorship, original ideation or all offline work. Code/Choice app attribution should not be inferred solely from the experiment repository.

On 17 October 2026 the user confirmed both authors' agreement to inclusion of their project code and saved research records, and to MIT licensing of their original project code. Approval is recorded from that confirmation; no signed consent document is included. [LICENSE](LICENSE) covers original project code and supporting documentation; [CITATION.cff](CITATION.cff) identifies the new collaborative artifact and repository. The final report remains separate and excluded.

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) scopes the retained HumanEval MIT, EvalPlus Apache 2.0/compatible HumanEval notice and CodeQual MIT material. The CodeQual notice is taken from upstream commit `518360297f59ad7b6569233eb4b934e6b00c083b` and covers the upstream context retained in the Windows compatibility patch. Benchmark/model-derived records are not relicensed under the project MIT grant; no blanket data or output license is added. Installed dependencies and model/adapter weights are not bundled. Raw named responses, university assets and signed submissions are excluded.


## Calibration and validation boundaries

Performance and analyzer validation: retain Run12 pilot rows; CodeQual labelled synthetic/decision fixtures and summaries; SonarQube protocols/aggregate results; StringConcat validation_summary; first-loop and loop2 frozen analyzer decisions. These are exploratory suitability tests, not extra formal seeds or broad analyzer ground truth.

Judge calibration: the saved A/B record compares historical contextual feedback with conservative code-only feedback. Historical source reports55% equal-reward groups and mean population SD.0393 versus90%/.0130; this release retains the actual source record instead of treating preparation-only144-call plans as completed. Prompt texts, hashes, correctness gate and taxonomy/scoring definitions are preserved. Formal operational evidence records2695/2695 J requests and2425/2425 SJ requests successful in summaries, six health PASS, while per-request transport logs are incomplete for some runs. Reproduce group-variation denominators with `python analysis/reproduce_judge_diagnostics.py`.

Run35:70 recorded timeout rows,27 distinct task/raw-completion keys,21 groups;40 HumanEval15,29 HumanEval39,1 HumanEval25. The process-wide cache reused diagnostics. Source cause and host/deadline conditions remain unresolved. Do not interpret70 rows as70 independent timeout events.

Human calibration: final revision313 includes10 calibration records, excluded from the150 Formal responses. The preserved frozen guideline and criterion apply readability/maintainability conditional on both solutions passing and differing. The local candidate retains assignments and original orientation but removes calibration responses, names, timestamps and response identifiers. The two authors are not external participants; pseudonyms do not guarantee anonymity. Ten independent overlaps yield5 agreements and Cohen kappa.2537313433. Play does not enter these statistics.

CPU tests validate transport/schema failure handling, historical valid-response scoring equivalence and temporary-script execution boundaries. They do not validate Judge semantic findings or run new model inference.


## Recorded environment and reconstruction limits

Saved-data checks: Python3.10+ standard library only, Windows/macOS/Linux; no inference or candidate-code execution. Optional plots use Matplotlib and NumPy. The tested plotting versions are recorded in [verification/build-environment.json](verification/build-environment.json).

Training: Linux, two NVIDIA GeForce RTX3090 devices (23.558GiB/device as logged); recorded NVIDIA driver580.173.02 reports CUDA13.0 capability. The loaded PyTorch wheel is2.10.0+cu128 and toolkit12.8, which is a different field from driver capability. Trainer banners record Unsloth2026.5.10, Transformers5.5.0, Triton3.6.0 and Xformers0.0.35 fallback when FlashAttention2 was unavailable. Existing snapshots record TRL0.24.0, unsloth_zoo2026.6.1, datasets4.3.0, peft0.19.1, accelerate1.13.0, bitsandbytes0.49.2 and Ruff0.15.16. Full recorded `packages.txt`/`gpu.txt` files remain next to J/SJ run evidence. Exact Python patch version and device serials are not established by the retained record. Source traceback paths indicate a Python3.12-family historical environment; no patch version is invented.

[training/requirements-original.txt](training/requirements-original.txt) is the historical broad/unlocked intent. [training/requirements.txt](training/requirements.txt) is a minimal reconstruction using recorded package versions, not a solved or GPU-tested lockfile. Install an appropriate CUDA PyTorch build first. Optional historical torchaudio/vision versions do not establish a compatible minimal stack and are not blindly installed. No GPU training environment was provisioned or asserted working during compendium preparation.

Generator identifier: unsloth/Qwen3.6-27B, four-bit, all-linear rank/alpha16 LoRA, dropout0, no thinking, chat template enabled. Immutable generator/tokenizer/dataset revisions, original adapter binaries and Judge weights/revision are incomplete. Dataset task slicing depends on recorded order; do not assume a mutable upstream dataset always preserves that order. Judge alias qwen-32b / user-confirmed backend Qwen2.5-32B-Instruct-AWQ is evidence of configuration, not proof of immutable identical service weights. No weights, libraries, private workstation manuals or credentials are bundled.

Use a clean isolated Linux research environment for any future training, including generated-code execution. Exact historical output reproduction is not promised; offline recomputation of saved rows is the verified entrypoint.


## Evidence-based research chronology

The original histories and dated artifacts determine this reconstruction; this is not a fabricated meeting journal. [exploratory/historical-run-index.json](exploratory/historical-run-index.json) identifies actual evidence for every numbered historical run slot. All twelve formal runs30–41 are retained.

1. Early commits develop GRPO generation, format/syntax/execution/correctness logging and Ruff; multiple small model/equipment and queue experiments precede the final protocol.
2. e885869 adds performance reward and Run12. af88078 records contextual Judge pilot13; b3d6dd7 records Run15. ff4d523 archives performance-inclusive alternative-weight runs16–20, including incomplete20. These are not matched final ablations.
3. 8afbb9e executes CodeQual labelled pilots; efcfea6 executes SonarQube pilots;40dd044 preserves StringConcat and two rounds of analyzer screening, decisions and a deferred factorial design.26db49b prepares remote/calibration work; preparation is not execution.
4. f6f142f configures HumanEval+;6db7215 fixes the OS argument-length issue using temporary scripts. ea1a83f preserves partially broken27–29 and corrected recovery evidence.
5. 8cc4acc archives restart30–35 with fixed split and fresh adapters. Run35 timeout/cache caveat remains material.
6. f2a2c78 identifies the clean formal Judge worktree. Actual archived36–38 and39–41 metadata/CSV/health establish completion. The HumanEval+ branch at1b3ac9be80848bb025a403246ece7d94e601b041 is unmerged; its `main` branch was not substituted.
7. Human review app at42308d97ebfc3daa4ccbd983acc3bd4427448f54 supplies frozen V2 eligibility/catalog. Executed export revision313 supersedes proposed counts:50 joint +50 per author,10 independent overlaps,150 judgments/140 distinct pairs/47 tasks.
8. 15 October 2026: local evidence reconstruction and offline verification, without new training or Judge calls. The prior private archive subsequently retained this work through commit c8390ecc495c1a50814db0c7737facbe3034baa2.
9. 17 October 2026: following user-confirmed agreement by both authors, prepare a new private experiments/results repository with fresh history and MIT for original project code. The individual final report, manuscript sources and university logo are excluded; this action is separate from a Canvas submission.

No standalone meeting/action-log archive was identified in the audited source branches. Existing proposal, midyear material, feedback and project-progress notes are retained in the restricted folder when present. Git attribution is partial evidence of contribution, not proof of all offline intellectual work.


## Future work retained from the research

1. Broaden independent human review with a predeclared criterion, task-aware analysis and more overlap; distinguish author calibration from external assessment.
2. Investigate Run35's original timeout/cache conditions and perform task/seed sensitivity before deciding whether a matched repeat is warranted.
3. Pin immutable generator/tokenizer/dataset/Judge revisions; archive adapters, complete effective settings, evaluation RNG state and a solved container/environment for future experiments.
4. Validate Judge findings against independent labelled evidence and human preferences before optimizing its weight or claiming quality gains.
5. Study context-dependent analyzer usefulness on longer repository-level code. The deferred eight-arm design and sparse signals remain proposals; no new formal training was authorized here.
6. Use measurements beyond proxy cleanliness, including modification/debugging outcomes, without treating Ruff equality or a scalar Judge score as general maintainability.

These are research directions from retained report/decision records, not new runs performed for the compendium.


## Limitations and missing artifacts

- The formal saved-data calculation is reproducible; original adapters, complete immutable model/tokenizer/dataset/Judge revisions and full runtime environment provenance are unavailable. Byte-for-byte retraining/generation is NOT VERIFIED. C/S's complete original trainer hash was not recorded;8cc4acc is the best archived candidate. Six J/SJ trainer hashes do match the exact normalized archived source.
- Evaluation generation lacks an explicitly recorded RNG seed guarantee. Training seeds are matched; that does not guarantee identical evaluation sampling.
- All arms use one generator and a small task subset. Four completions per task are grouped, seeds are only three, and pretraining exposure is unknown. Rates are output-level descriptive results, not pass@4, significance, population correctness or general code-quality proof.
- Run35 cached correctness timeouts affected rewards. Retained results require this limitation; no repeat or selective seed removal was performed.
- Successful API/schema transport does not establish correct findings. Some formal per-request JSONL logs are absent; summaries cannot reconstruct every request.
- Human review is by two project authors, calibrated with joint and independent phases. Only10 pairs are independently double-rated; selection requires both outputs correct and non-identical. It does not establish external-developer productivity or broad maintainability gains. Disabled Judge scores are not measured ties.
- Distributed source and traceback fields have documented privacy substitutions; exact originals stay restricted. Distributed hashes and raw-source hashes are distinct where edits occur.
- Some external pilot tooling is not vendored or portable without original source dependencies. MIT for original project code does not extend to benchmark/model-derived material or third-party implementations.
- Individual final reports, manuscript sources, university assets and the separate Canvas submission package are excluded from this experiments/results repository.


## Decisions supported by records

- Preserve correctness-focused support terms in every formal arm; quality rewards are additions. Performance reward saturation and its limited group discrimination led to exclusion from the final four-condition matrix.
- Do not promote an analyzer merely because it runs. CodeQual, SonarQube, concatenation and loop2 candidates faced predeclared activation/precision/context/variance/cost constraints; negative outcomes and fixture limitations are preserved.
- Retain the contextual historical Judge following saved prompt comparison; harden transport/schema failure handling without changing valid-response scoring/prompt semantics. Retries and valid JSON measure reliability, not finding truth or human alignment.
- Separate broken27–29, performance-inclusive pilots and proposed eight-arm work from final30–41. Retain all three formal seeds, including Run35 with its reward-affecting cache-timeout limitation.
- Freeze held-out output matching, A/B orientation and assignment before formal author judgments; keep calibration, joint consensus, independent review and exploratory Play distinct.
- Report saved output-level rates and two-author preferences conservatively. Do not turn one-output correctness, pass@k, independent tasks, developer productivity and semantic quality into interchangeable claims.
- Prepare this experiments/results repository with fresh history under the jointly approved scope. Preserve restricted originals and recorded transformations; keep the final report and Canvas submission separate.

For actual historical protocol details and source decisions follow [exploratory/](exploratory/); this file summarizes recorded choices and introduces no new experiment approval.


## Source precedence and hashes

Primary source: the restricted Jeraych/UnSloth-RL repository, unmerged experiments-humanevalplus at1b3ac9be80848bb025a403246ece7d94e601b041. Exploratory branches8afbb9e/efcfea6/40dd044/26db49b supply their actual artifacts rather than similarly named substitutes. Formal Judge worktree f2a2c780491a74bc8a93621dacc2aa6412819b0c supplies the actual trainer/reliability chain. The restricted human-code-review repository at42308d97ebfc3daa4ccbd983acc3bd4427448f54 supplies frozen V2 catalog/mappings. These identifiers document source provenance; they are not commits in this new repository's history.

[manifests/files.csv](manifests/files.csv) indexes deliverable files: original repository, path, branch/commit where established, original raw SHA-256, LF-only SHA-256, distributed SHA-256, transformation and inclusion reason. New code/docs name the repository build as their source. Generated analysis/figure files name their input scripts/data. Manifest files exclude themselves from recursive hashing. Git objects and ignored runtime caches are not release files. [manifests/sha256.txt](manifests/sha256.txt) hashes the same payload.

Historical J/SJ trainer exact source LF-normalized hash edb8384bc6812850e623edba14a8ae18272e3f804458abbc0f67108775ceddcc and reliability2c1940049a7965a0dd221c2e0c6d5e5dbcffa98956dbb8a9f03b291cfdb3829a were verified before privacy edits. CRLF→LF is the sole documented normalization for this comparison. Original Windows trainer raw hash differs; do not silently alter data to equal a metadata hash. In J/SJ CSVs the checked-out Windows bytes and Git blob bytes may differ in line endings; both original and blob hashes are recorded where relevant. The frozen human-study records preserve their source holdout hashes.

The restricted final export has SHA-2567b8f2ba4df661b25e4526f72063281f5eb3729912fae35761a40c2e754546d70,1806285 bytes,revision313. The older six-response export is excluded. Distributed human data is an allowlisted derivation, never labelled the identical original. Formal calibration and Play remain separate.

The [evidence map](EVIDENCE_MAP.md) uses E1=formal rows+automatic replication; E2=revision313-derived formal responses+human replication; E3=selected exploratory protocols/aggregates; E4=Run35+historical source+prompt comparison; E5=real SJ run data/metadata plus historical launcher; E6=frozen catalog/provenance/outputs; E7=versioned human review protocol.


## Expanded raw research coverage and exclusions

The single [exploratory/](exploratory/) root groups early pilots, alternative-weight and queue runs, failed-run evidence, protocols, labelled fixtures, analyzer screens and remote preparation scripts by run or study. Each study keeps its available data, code and documentation together. Original run IDs remain in directory names; duplicate evidence shares an indexed retained path, and missing evidence is not fabricated. The consolidation changes locations, not experimental file contents. Historical implementations/configs/dependencies from those branch points remain under [training/historical/](training/historical/).

Raw records are byte-preserved when no privacy edit is needed. When private paths/endpoint/email text require a distributed edit, raw originals remain in restricted source storage with distinct hashes. Exact duplicate files share a retained path recorded in [manifests/duplicate-sources.json](manifests/duplicate-sources.json). Historical duplicate JSONL omissions were checked against CSV keys/values/rows; unique retained JSONL information remains indexed. Original JSONL and historical dashboards remain in restricted source storage. No model checkpoints, installed packages, caches, `.env` files, university/private access manuals, final reports, manuscript sources, university logo, signed submissions or raw named reviewer export enter this repository.

[manifests/excluded-files.json](manifests/excluded-files.json) records historical exclusions and [manifests/files.csv](manifests/files.csv) maps retained files to source/hash/transformation. They preserve provenance for this experiments/results scope; they do not describe an included report or a Canvas submission.


## Verification scope for the new repository

The offline checks cover2,400 formal held-out outputs,24,000 training rows,600 Base outputs,150 formal responses/140 pairs/47 tasks, per-phase and equal-pair-weight sensitivity,10 independent overlaps (5 agreements;kappa0.2537313432835821),70 Run35 timeout rows/27 distinct keys, and all6 Judge service summaries. They match frozen human output identities back to all3,000 source output records and catalog eligibility, and recompute Run12 saturation and the160-candidate/20-group-per-instrument prompt comparison from saved rows. Three plots have a separate regeneration script. Check results and their scope are recorded in [verification/](verification/). No GPU training or live Judge request is part of this work.

Distributed source derivatives retain documented privacy edits where necessary, including prior removals of credential-like generated text and token-shaped tracking text. Originals remain in restricted source repositories, identified by source hashes and redaction locations. Source metadata/provenance hashes and distributed hashes are distinct where edits occur; formal numerical results are preserved.

Runs20,21,24,25,26 have no separately numbered local directory; the historical incomplete-Run20 claim is retained as a source note, not invented data. Exact original transport logs are missing for some formal seeds. Original adapters, immutable upstream revisions and an executable historical GPU lockfile remain unavailable. This results repository uses its own citation metadata and MIT license for original project code, under the authors' user-confirmed agreement. The final report and separate Canvas materials remain outside this repository.
