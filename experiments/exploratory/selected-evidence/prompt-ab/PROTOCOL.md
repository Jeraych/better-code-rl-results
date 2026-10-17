# Frozen prompt comparison protocol

This is local calibration using saved code. It does not import the trainer, run candidates, launch training, change reward weights, or access the remote GPU server. The two instruments are not interchangeable prompt strings: their context and accepted-finding rules differ.

Historical source: committed `train.py` at `8cc4accd0c687a040543a791e472e3f5b236e2e2`, extracted as pure functions using Python AST. Version `taxonomy_readability_maintainability_v3`; SHA-256 `50d083c5e7100d2e2bf5d5d94e04e18eb1222d851473b8a51b994fd1bd65c660`, computed from version, system prompt and user template joined by newlines. The exact system and taxonomy/template are in `historical_prompt.json`; parsing, numbering, sanitizer and scorer are in `historical_functions.py`.

Intended standalone source: `individual_judge.py` selects `experiments/ai_judge_standalone/prompts/v3_conservative.txt`, which the correctness-judge draft also intends. V1 and V4 are not tested. Instrument version `individual_v3_conservative`; exact UTF-8 request-text SHA-256, with LF newlines, `b237cacd7d45e4ceec41347fb992e7d95daf1441a6659b181076b586588c6c6b`. The frozen Windows `standalone_prompt.txt` uses CRLF and has a separate raw-file hash `5ca568fb1cbe0d0b371a5e2b17b98c8ca5fbed89ff63aace6959aeb29e1aafff`; loading normalizes it to the unchanged LF request text. Existing request construction, literal environment reader, structural validator and scalar scorer are in `standalone_functions.py`.

| Property | Historical instrument | Standalone instrument |
|---|---|---|
| Inputs | Task, numbered code, canonical reference | Numbered code only |
| Prompt | Historical system + task/taxonomy user template | Existing conservative code-only system + code user message |
| Content parser | Historical tolerant object parser, including fenced JSON | Strict JSON parser |
| Structural reliability | Existing standalone validator before historical sanitation | Existing standalone validator |
| Findings accepted | Historical sanitizer; e.g. weak naming and unsupported else findings may be discarded | Structurally valid findings preserved; no historical sanitizer |
| Scalar | Historical severity sum and clamp | Existing `quality_score(..., mode="sum")` |

Both use penalties low 0.15, medium 0.35, high 0.65, critical 1.0 and `J = max(0, 1 - sum(penalties))`. Valid clean `[]` gives 1. Invalid/unavailable reviews give null. The alternative standalone smooth/category-cap scores and correctness-weighted training score are not used. Structural validation does not prove the findings are semantically correct or deduplicated.

Common request settings: same privately configured OpenAI-compatible `/chat/completions` endpoint; model alias `qwen-32b`; user-confirmed backend `Qwen2.5-32B-Instruct-AWQ`; seed 3407, temperature 0.0, top_p 1.0, max_tokens 900, stream false, JSON-object response format, timeout 60 seconds. No thinking/reasoning switch is sent; server-side defaults were not independently recovered. The common timeout follows the standalone draft and differs from the historical trainer's 30-second default.

The repo-root `.env` uses shell `export` prefixes. Calibration normalizes those prefixes in memory and invokes the existing literal reader without executing the file or creating a secret copy. Bearer headers are never logged. Every serialized response is scrubbed for the actual credential. The endpoint is frozen by a SHA-256 identity check rather than disclosed in artifacts.

Run 30 has 500 complete groups of four candidates; 472 have four previously passing, nonempty candidates. Twenty groups were sampled uniformly without replacement with seed 3407, before any scores. All 80 saved code strings are used unchanged for both instruments. The first candidate in the first five sampled groups supplies the five-candidate preflight, whose successful results are reused in Phase B. Request order is shuffled with seed 3408 for the approved retry and Phase B; this is an ordering seed, separate from the selection and API seeds (3407).

Task text matches the saved training prompt for all 2,000 run-30 rows. Reference code is reconstructed from the adjacent repository's local HumanEval+ cache as task prompt plus canonical solution; the historical reference string and dataset revision were not separately saved. Source hashes and selected group IDs are recorded in `manifest.json`.

The historical implementation was permissive about malformed responses. This study applies the existing structural validator before historical sanitation, and requires finish_reason `stop` in both paths, as required by the current reliability rules. Therefore this is an instrument comparison with a shared reliability guard, not a byte-for-byte replay of historical failure handling. Raw historical findings, discarded findings counts and accepted findings are all retained.

Initial sandboxed requests failed locally with no HTTP response. One explicitly authorized retry round repeats only those preflight transport failures, preserving their null-score records in raw diagnostics. There are no automatic service retries or response cache. Effective summaries use the latest record per candidate/instrument; all-attempt summaries preserve the original failures separately.

Phase C chooses up to ten distinct code strings: largest score disagreement, clean/findings disagreement, high or unusual findings where available, and representative agreements. Source labels remain visible. The assistant's preliminary spot-check is not an independent human study; higher variance alone is not a reason to choose the standalone instrument.

The pre-existing 20 dirty files, including `.gitignore`, `train.py`, both draft launch files, `individual_judge.py` and standalone tooling, are protected by content hashes. New files live only under `experiments/ai_judge_prompt_ab_run30/`. Neither calibration bridge nor standalone tooling is added to a formal training dependency chain.
