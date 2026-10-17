# Run-30 local AI-judge prompt evaluation

**Recommendation: HISTORICAL_PROMPT for experimental continuity.** Standalone does not meet the criterion of better useful within-group discrimination. Neither instrument is validated as human quality ground truth.

Completed 20 frozen four-candidate groups (80 saved candidates, 160 valid reviews). No training, candidate execution, formal reward change or remote GPU operation was performed.

## Instruments and settings

Historical: `taxonomy_readability_maintainability_v3` from committed train.py at `8cc4accd0c687a040543a791e472e3f5b236e2e2`; SHA-256 `50d083c5e7100d2e2bf5d5d94e04e18eb1222d851473b8a51b994fd1bd65c660` over version, system and template joined with newlines. Exact text: [historical_prompt.json](historical_prompt.json).
Standalone: `individual_v3_conservative`, intended by individual_judge.py, using v3_conservative.txt only; SHA-256 `b237cacd7d45e4ceec41347fb992e7d95daf1441a6659b181076b586588c6c6b` over UTF-8 LF request text. Exact text: [standalone_prompt.txt](standalone_prompt.txt). The frozen CRLF file has a separate raw-byte hash recorded in verification.json and PROTOCOL.md.
Same privately configured endpoint and qwen-32b alias; user-confirmed backend Qwen2.5-32B-Instruct-AWQ. Both send seed 3407, temperature 0, top_p 1, max_tokens 900, stream false, JSON-object response format; timeout 60 seconds. No reasoning/thinking switch is sent; server-side defaults are unverified.
Historical receives task, numbered code and reference and uses its existing sanitizer. Standalone receives numbered code only and preserves its structurally valid findings. Both use J=max(0,1-sum(penalties)), with low/medium/high/critical penalties 0.15/0.35/0.65/1.0. Alternative standalone scoring modes and training_score are not used.
Shared structural validation and finish_reason=stop protect against malformed/truncated clean rewards. This guard and the 60-second timeout differ from historical failure handling/default timeout; prompts and scalar scoring are preserved.
Full phase-0 inspection, input/validation differences, sampling and hashing details: [PROTOCOL.md](PROTOCOL.md).

## Phase A: five paired saved candidates

All ten authorized preflight requests returned qwen-32b, strict valid JSON, a valid schema and finish_reason stop. Their responses were reused in Phase B. Tokens below are input/output counts.

| Candidate | Historical J | Standalone J | Historical latency s | Standalone latency s | Historical tokens | Standalone tokens |
|---|---:|---:|---:|---:|---:|---:|
| run30-step-30-candidate-0 | 1.00 | 0.85 | 1.94 | 13.72 | 913/16 | 543/125 |
| run30-step-232-candidate-0 | 0.85 | 0.70 | 17.97 | 26.09 | 1236/162 | 730/238 |
| run30-step-73-candidate-0 | 1.00 | 1.00 | 11.44 | 1.74 | 1058/102 | 624/11 |
| run30-step-182-candidate-0 | 0.85 | 0.70 | 27.47 | 24.60 | 1293/250 | 690/224 |
| run30-step-116-candidate-0 | 0.85 | 0.70 | 12.31 | 25.68 | 1011/112 | 589/234 |

Preflight mean J: 0.91 / 0.79; no authorized API/parse failures.

## Phase B: completed 20-group comparison

| Metric | Historical | Standalone |
|---|---:|---:|
| HTTP success / valid reviews | 80/80 / 80/80 | 80/80 / 80/80 |
| Successful-request rate | 100% | 100% |
| J mean | 0.818125 | 0.812500 |
| J population SD | 0.139697 | 0.133112 |
| J min / max | 0.50 / 1.00 | 0.70 / 1.00 |
| Clean J=1 | 20/80 (25%) | 24/80 (30%) |
| Equal-score groups | 11/20 (55%) | 18/20 (90%) |
| Mean within-group population SD | 0.039264 | 0.012990 |
| Median / p95 latency s | 13.77 / 29.10 | 18.44 / 32.06 |
| Malformed / timeout / other endpoint errors | 0 / 0 / 0 | 0 / 0 / 0 |
| Accepted / sanitizer-discarded findings | 81 / 9 | 100 / 0 |
| Input / output tokens | 89,892 / 10,987 | 51,616 / 11,751 |

Paired mean absolute score difference: 0.099375; clean/findings disagreement: 26/80 (32.5%). Similar overall means conceal different candidate judgments. Thirteen incidental identical-payload sets per instrument had no score conflicts; this is not a separately sampled repeatability study.

| Accepted finding | Historical | Standalone |
|---|---:|---:|
| Confusing Variable Naming | 0 | 56 |
| Sub-readable Code Exists | 59 | 10 |
| Code Duplication | 10 | 2 |
| Comment Duplication | 0 | 0 |
| Unnecessary Else | 3 | 3 |
| Unnecessary Conditional Block | 9 | 29 |

Category totals: readability 59/66; maintainability 22/34. Severities: historical 69 low, 12 medium; standalone 100 low. Neither returned high or critical findings.

All 160 responses were strict JSON with complete token usage and finish_reason stop. Total usage: 141,508 input and 22,738 output tokens; no monetary estimate is made without deployment billing rates.

Initial sandboxed preflight attempts failed locally (ten transport errors, no HTTP responses). After the user's explicit destination/data-transfer authorization, one retry round succeeded. There are no automatic service retries or response cache. Raw diagnostics retain 170 attempts; all-attempt success is 160/170 (94.12%, 80/85 per instrument). Effective endpoint results above use the 160 successful authorized reviews; initial failures keep null scores.

## Historical statistics for context

| Saved run | Equal-score groups | Mean within-group population SD |
|---|---:|---:|
| 16 | 60.6% | 0.048994 |
| 17 | 64.0% | 0.051710 |
| 18 | 70.0% | 0.038262 |
| 19 | 68.2% | 0.042279 |

The current historical-prompt within-group SD falls within the old range. These are contextual comparisons across different candidates, eligibility gates, infrastructure-score treatment and unverified historical weights, not matched causal baselines.

## Phase C and recommendation

Ten distinct code strings were selected automatically, with source labels visible: four largest disagreements, two clean/findings disagreements, two agreements and two additional coverage cases. There were no high/critical or Comment Duplication cases to fill the unusual-finding quota.
Review code and both findings/scores: [manual_review.md](manual_review.md) or manual_review.html (historical private source link; see source manifest). Assistant observations: [spot_check_notes.md](spot_check_notes.md).
Standalone makes some reasonable clean calls, but also unsupported generic-name penalties and taxonomy errors. Historical has its own over-penalties and category mistakes. Standalone has less within-group signal and no demonstrated useful-discrimination advantage, so preserve historical continuity. This is not a claim that historical findings are accurate or that either reward will improve training. Full rationale: [recommendation.md](recommendation.md).

## Reproducibility and limits

Sampling was fixed before scores: uniform 20-group sample with seed 3407 from 472 previously all-pass complete groups among 500 run-30 groups. Phase-A retry/Phase-B request ordering uses seed 3408; API and sample seeds remain 3407. Both prompts use exactly the same saved code. These are training-run candidates, not an independent held-out quality benchmark, and correctness was not rerun.
Task strings exactly match saved training prompts; canonical references are reconstructed from a local dataset cache using the historical prompt+canonical_solution construction. The historical dataset revision and separately logged reference strings are unavailable. Backend weights are user-confirmed, not independently fingerprinted. Context, sanitizer and failure-policy differences prevent calling this a prompt-only or exact historical replay.
The assistant spot-check is unblinded and disagreement-enriched; no independent human judgments or population false-positive estimates are claimed. One trial per candidate/instrument was issued, with incidental identical-input repeats only.
Root .env is loaded literally with in-memory export-prefix normalization. No secret copy or authentication header is saved. Private endpoint identity is frozen by hash. Pre-existing files are protected by hashes; final checks are in [verification.json](verification.json).

## Exact artifacts and commands

All additions are under experiments/ai_judge_prompt_ab_run30/. No pre-existing file was changed. Complete file inventory: [FILES.md](FILES.md). Exact workflow commands and failure history: [COMMANDS.md](COMMANDS.md).
Per-candidate data: [per_candidate.csv](per_candidate.csv); all attempt payloads/raw responses: raw_diagnostics.jsonl (historical private source link; see source manifest); full metrics: [summary.json](summary.json); frozen candidates/provenance: [manifest.json](manifest.json).
contract-diagnostics contains synthetic transport/parser checks only; manual_review_pending files are archived pre-authorization previews and are not the final review set.

## Recommended API Migration Plan

For later authorized formal work, start from committed 8cc4accd0c687a040543a791e472e3f5b236e2e2, retain the historical prompt/context/sanitizer/scalar and experimental reward settings, and replace only the judge backend/model. Keep individual_judge.py and standalone calibration tools outside the formal dependency chain. No migration or training is implemented by this evaluation.
