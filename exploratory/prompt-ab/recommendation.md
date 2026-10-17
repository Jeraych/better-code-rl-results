# Recommendation: HISTORICAL_PROMPT

Retain `taxonomy_readability_maintainability_v3` as the continuity baseline for the proposed matched backend migration. Do not replace it with the current standalone V3 instrument on this evidence. No formal configuration has been changed.

Both paths produced 80/80 valid reviews on the same 20 groups. Overall means are close (historical 0.818125; standalone 0.8125), but the paired mean absolute difference is 0.099375 and 26/80 candidates disagree on clean versus findings. Similar averages do not imply equivalent judgments.

Standalone produces materially less within-group signal: 18/20 groups have identical scores, versus 11/20 historically; mean within-group population SD is 0.012990 versus 0.039264. It therefore fails the requested criterion of materially better useful within-group discrimination. Its 100 accepted findings are all low severity, including 56 naming findings; historical accepts 81 findings after discarding nine through its existing sanitizer.

The ten-case assistant spot-check finds unsupported generic-name penalties and taxonomy errors in standalone output. Historical output also includes clear concerns, such as calling a counting loop an Unnecessary Conditional Block, claiming duplication for a derived inverse map, and favoring reference-like compression despite the rubric. Neither instrument is established as a valid human-quality reward. Higher historical variance must not be described as better quality assessment.

Thirteen incidental sets of identical request payloads per instrument had consistent scores, so no score inconsistency was observed in those repetitions. This is a limited incidental check, not a broad repeatability study.

Historical runs 16–19 have equal-group rates 60.6%, 64.0%, 70.0%, 68.2%, and mean within-group SD 0.048994, 0.051710, 0.038262, 0.042279. The current historical-prompt SD is within that range, while its equal-group rate is 55%. These are contextual comparisons across different candidates, gates, failure policies and unverified historical weights, not a matched causal replication.

Use this result to preserve experimental continuity while assessing backend connectivity. Independent human calibration remains necessary before interpreting either score as ground truth or claiming an improvement in training outcomes. Keep the future formal base at committed `8cc4accd0c687a040543a791e472e3f5b236e2e2`; the current `individual_judge.py` bridge and standalone tooling remain calibration-only dependencies.
