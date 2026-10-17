# Analyzer method, evidence, and final-decision audit

**Purpose:** explain what each analyzer measures, how it was evaluated, what
the observed result means, why it was or was not selected, and what should
happen next.  
**Current experiment branch:** `experiment/codequal-metrics-training`  
**Numerical evidence:** [experiment index](EXPERIMENT_INDEX.md)

## Interpretation boundary

The screened tools generally **worked as validators**. A tool was not promoted
when it failed as a reward for this dataset and training design. These are
different questions:

1. **Technical operation:** can the tool execute deterministically and detect
   its configured examples?
2. **Fixture validity:** does it separate known positives from negative
   controls?
3. **Dataset fit:** does the target problem distribution contain the property?
4. **Reward suitability:** do candidates for the same prompt receive different
   scores often enough for group-relative optimisation?
5. **Construct validity:** does a warning represent the quality property being
   claimed rather than missing context, formatting, or a different concern?
6. **Operational suitability:** is the analyzer sufficiently local, fast, and
   reliable for repeated online calls?

A popular repository validator may pass questions 1 and 2 while failing 3-6
for short, already-correct HumanEval completions.

## Evaluation protocol

### Loop 1

Loop 1 screened Ruff/PEP8-style, the repaired AST StringConcat rule, and the
existing dynamic-performance score across saved Runs 12, 13, and 15:

- 3,000 completions total;
- 2,878 test-passing completions eligible for quality screening;
- 1,423 comparable generation groups with at least two candidates;
- StringConcat also used 12 handcrafted development fixtures.

### Loop 2

Loop 2 froze six analyzer configurations before examining Run 15 outcomes:

- Radon 6.0.1 complexity;
- Vulture 2.16 dead code with prompt-derived entry-point filtering;
- Pylint 4.0.6 exception and structure rules;
- Bandit 1.9.4 security checks;
- Mypy 2.3.1 type checking.

For each family, two positive and two negative-control fixtures were executed
twice. All configurations produced precision 1.00, recall 1.00, false-positive
rate 0.00, and identical repeated fixture findings. This only verifies the
small purpose-built configurations; it is not independently labelled external
validation.

Each tool then screened all 960 test-passing Run 15 completions. For every
analyzer the experiment recorded:

- availability and analyzer errors;
- activation prevalence;
- finding types;
- a bounded score `1 / (1 + finding_count)`;
- the fraction of 475 comparable GRPO groups with non-zero score variation;
- elapsed time; and
- whether execution was in-process or batch/subprocess based.

The pre-result promotion gates required at least 90% availability, 5%-95%
activation, and non-zero variation in at least 10% of comparable groups. An
online candidate additionally required in-process execution and mean analysis
time no greater than 5 ms. These are project screening heuristics, not universal
standards.

## Per-analyzer audit

### Ruff `E,W` / PEP8-style

**What it is.** Ruff is a fast Python linter. The pipeline selects its `E` and
`W` pycodestyle-derived rule families, which cover issues such as indentation,
whitespace, and selected PEP 8 conventions. This is a style proxy, not a test
of correctness, security, performance, or maintainability as a whole. Official
rule catalogue: <https://docs.astral.sh/ruff/rules/>.

**How evaluated.** Loop 1 reused the Ruff results already recorded for 2,878
test-passing completions. It measured violation activation and score variation
within comparable generation groups. Earlier paired base/LoRA evaluations were
kept separate from this screening gate.

**Observed result.** Violations activated on 28.4% of eligible outputs. Only
8.1% of groups varied overall, below the frozen 10% gate, although Run 15 alone
reached 10.1%. Previous Run 15 evaluation showed a large Ruff-clean change but
no correctness improvement.

**Why it was not fully promoted.** The aggregate reward-density gate was missed
narrowly, and the existing learning result comes from one confounded
all-metrics run rather than matched repeated Ruff-only training.

**Final decision.** Retain as the only **conditional online comparator**. Run
matched `cq-core` versus `cq-pep8` with at least three identical seeds and
report correctness alongside style. Do not call Ruff a general code-quality
metric.

### AST StringConcat

**What it is.** A custom, conservative AST rule derived from the CodeQual
string-concatenation concept. It detects repeated string growth such as
`result += text` or `result = result + text` inside loops. It does not execute
code and does not claim that every concatenation is inefficient.

**How evaluated.** Twelve handcrafted cases covered string growth variants and
controls such as numeric accumulation, list append plus join, bytes growth, and
concatenation outside loops. The rule was then executed directly on all 2,878
correct saved outputs from Runs 12, 13, and 15.

**Observed result.** Fixture precision and recall were 1.00 with no false
positives and approximately 0.068 ms mean analysis time. Only 1/2,878 real
completions activated, and only 1/1,423 comparable groups varied.

**Why it was not integrated.** The implementation works, but HumanEval almost
never presents the target behaviour. A constant reward cannot teach GRPO to
avoid string growth.

**Final decision.** Keep as a fast offline diagnostic. Reconsider as an online
reward only on a frozen targeted dataset containing natural string-building
alternatives and independent controls.

### Dynamic performance

**What it is.** The project executes correct candidate and reference solutions
repeatedly and compares elapsed time and `tracemalloc` peak memory. It is a
controlled relative measurement, not a static validator and not a universal
hardware-independent speed measurement.

**How evaluated.** Loop 1 read the recorded performance diagnostics for 1,920
correct completions from performance-enabled Runs 12 and 15, measuring score
ceiling and within-group variation.

**Observed result.** 80.9% of measured candidates received the maximum score;
only 12.2% of comparable groups varied, below the frozen 25% performance gate.

**Why it was not integrated unchanged.** The current input sizes and score
mapping make most correct HumanEval solutions indistinguishable. This is reward
saturation, not evidence that runtime measurement is unimportant.

**Final decision.** Redesign before further remote training: use harder/scaled
inputs, operation-count or complexity-sensitive tasks, a less-saturated score,
and repeated noise estimates. Preserve correctness gating.

### Radon complexity

**What it is.** Radon computes Python code metrics from the AST. The screened
configuration flags functions with cyclomatic complexity greater than 10,
corresponding to Radon's C-or-worse range. Cyclomatic complexity counts decision
paths; it is not a direct runtime or correctness metric. Official documentation:
<https://radon.readthedocs.io/en/stable/commandline.html>.

**How evaluated.** Two high-branch/boolean-path fixtures and two simple controls
were repeated twice, followed by in-process analysis of 960 correct Run 15
outputs.

**Observed result.** The fixtures were classified correctly and deterministically
at about 0.096 ms per saved output. No Run 15 completion exceeded the threshold;
therefore 0/475 groups varied.

**Why it was not integrated.** Short HumanEval functions rarely cross a
repository-oriented complexity threshold. Lowering the threshold after seeing
the results would be post-hoc and could penalise ordinary control flow.

**Final decision.** Do not integrate on the current dataset. Retest on longer,
multi-branch tasks with a threshold frozen before outcome inspection.

### Vulture dead code

**What it is.** Vulture statically searches for defined but apparently unused
functions, classes, imports, variables, and unreachable code. Its own
documentation warns that dynamic or implicit use can create missed findings or
false positives; confidence values below 100% are rough estimates. Official
project documentation: <https://github.com/jendrikseipp/vulture>.

**How evaluated.** Two dead-helper/class fixtures and two controls were repeated
twice. For saved completions, the HumanEval entry point was recovered from the
prompt and filtered so the required target function was not automatically
called unused. The experiment used Vulture's 60% minimum confidence.

**Observed result.** Fixtures passed and mean in-process time was 0.182 ms. It
activated on 20/960 outputs (2.08%), with only 7/475 groups varying (1.47%).
Findings included unused typing imports and a few helper functions.

**Why it was not integrated.** The reward is too sparse, and some findings need
whole-task or implicit-call context. Penalising a helper that appears unused in
one extracted snippet could be wrong.

**Final decision.** Use as a secondary offline diagnostic only, with entry-point
filtering and manual inspection of reported categories. Do not use it as the
current online reward.

### Pylint exception handling

**What it is.** The selected Pylint rules flag bare `except` and overly broad
`except Exception` handlers, which may hide unrelated failures. Official rule
example: <https://pylint.readthedocs.io/en/stable/user_guide/messages/warning/broad-exception-caught.html>.

**How evaluated.** Bare and broad exception fixtures were paired with specific
exception and context-manager controls, repeated twice. Pylint then processed
960 correct saved outputs in one batch.

**Observed result.** Fixtures passed, but no correct Run 15 output triggered the
selected rules and no group varied. The reported 2.498 ms per item is batch
time divided across inputs, not single-call online latency.

**Why it was not integrated.** HumanEval tasks rarely require meaningful error
handling, so the benchmark cannot train or evaluate this property.

**Final decision.** Do not integrate on HumanEval. Retest on targeted reliability
or API/file-processing tasks containing explicit failure paths.

### Pylint structure

**What it is.** The selected Pylint design rules flag too many branches, locals,
or statements—threshold-based proxies for functions that may be difficult to
follow. Pylint describes `too-many-branches` as a function having enough
branches to become hard to follow. Official rule documentation:
<https://pylint.readthedocs.io/en/stable/user_guide/messages/refactor/too-many-branches.html>.

**How evaluated.** High-branch and high-local fixtures were paired with lookup
and simple-function controls, repeated twice, followed by batched analysis of
960 correct outputs.

**Observed result.** Fixtures passed, but there were zero findings and zero
varying groups in Run 15.

**Why it was not integrated.** The configured thresholds describe larger
functions than HumanEval normally generates. Relaxing them post-hoc would risk
turning normal short algorithms into violations and would overlap with Radon.

**Final decision.** Do not integrate on the current dataset. Consider as an
offline measure on longer code-editing or repository-level tasks.

### Bandit security

**What it is.** Bandit builds Python ASTs and runs plugins that look for common
security issues. Its warnings are security heuristics, not general code-quality
or correctness labels. Official documentation:
<https://bandit.readthedocs.io/en/latest/man/bandit.html>.

**How evaluated.** `os.system` and `eval` positives were paired with safe parsing
and ordinary numeric controls, repeated twice. The default Bandit plugins then
screened 960 correct outputs in one batch.

**Observed result.** Fixtures passed. Only 2/960 outputs triggered, both `B101`
for use of `assert`; only 2/475 groups varied. One verified finding was a valid
HumanEval `string_xor` implementation asserting equal input lengths. Bandit
documents that B101 warns because assertions disappear under optimized Python,
which is a real deployment concern but not automatically a bad algorithmic
solution: <https://bandit.readthedocs.io/en/1.7.5/plugins/b101_assert_used.html>.

**Why it was not integrated.** HumanEval is not a security benchmark, the signal
is extremely sparse, and penalising every assertion would conflate deployment
hardening with the task's intended quality objective.

**Final decision.** Retain only as an offline security audit. Use a dedicated
security benchmark and selected, justified rules before considering training.

### Mypy type safety

**What it is.** Mypy statically checks code using type annotations and available
typing/import context. Its documentation notes that useful diagnostics depend
on annotations and that unimported typing names produce errors. Official
documentation: <https://mypy.readthedocs.io/en/stable/getting_started.html>.

**How evaluated.** Incorrect-return and assignment fixtures were paired with
valid annotated and untyped controls, repeated twice. Mypy then checked the
extracted completion files with `--check-untyped-defs`, ignored missing
third-party imports, and recorded error codes.

**Observed result.** Fixtures passed. It activated on 238/960 outputs (24.79%),
but only 28/475 groups varied (5.89%). Findings were dominated by 278
`name-defined` errors; a verified example used `List[int]` supplied by task
context but absent from the extracted completion file. Other counts were 11
`var-annotated`, two `assignment`, and one `return`.

**Why it was not integrated.** The present input representation omits context
required by the type checker, so most findings do not isolate candidate type
quality. The signal also failed the group-variation gate and currently requires
batch/subprocess execution.

**Final decision.** Reject the current configuration. Reconstruct a complete
module from prompt imports plus completion, filter environment/context errors,
then rerun fixtures and saved-output screening before using Mypy even as a
primary offline measure.

### CodeQual aggregate and custom families

**What they are.** CodeQual combines third-party and custom analyzers across
maintainability, performance heuristics, reliability, security, and type safety.
Its released aggregate converts heterogeneous findings into a scalar score.

**How evaluated.** The prior pilot tested eight synthetic clean/degraded pairs,
50 correct Run 13 outputs, adversarial length padding, and a later 23-fixture
family-level decision test. See the linked
[CodeQual experiment](https://github.com/Jeraych/UnSloth-RL/tree/experiment/codequal-analyzer-pilot/experiments/codequal_analyzer_pilot).

**Observed result.** The aggregate was directionally sensitive on seeded pairs,
but real-output resolution was compressed and dominated by entry-point and a
few static findings. The per-character score improved when comments were added.
Resource-loop and data-structure families produced known false positives;
analysis cost was roughly 0.9 seconds per solution.

**Why it was not integrated.** The scalar mixes constructs, is exploitable by
padding, is slow for online use, and includes rules that failed negative
controls. Aggregate score changes would not reveal which quality dimension
changed.

**Final decision.** Never use the released aggregate or `overall_per_kchar` as
ground truth or an online reward. Preserve selected per-rule findings only as
offline evidence. Resource-loop and data-structure rules remain rejected until
redesigned and independently revalidated.

### SonarQube

**What it is.** SonarQube is a repository-oriented static-analysis and quality-
gate platform. In this project it also served as a possible reporting layer for
external Python analyzer findings.

**How evaluated.** The prior pilot ran its default Python profile on labelled
fixtures and 50 generated Run 13 outputs. See the linked
[SonarQube experiment](https://github.com/Jeraych/UnSloth-RL/tree/experiment/sonarqube-pilot/experiments/sonarqube_pilot).

**Observed result.** It detected 1/12 positive fixtures, no negative controls,
and no findings in the 50 generated outputs.

**Why it was not integrated.** The default profile had insufficient coverage
for the selected constructs, and repository/service operation is not suitable
for a per-completion reward call.

**Final decision.** Retain for repository quality assurance, dashboards, and
quality gates—not online GRPO reward generation.

### AI judge

**What it is.** A taxonomy-constrained language-model evaluator for contextual
readability and maintainability findings not easily represented by fixed rules.

**How evaluated so far.** Runs 13 and 15 established endpoint integration,
correctness gating, structured-output parsing, coverage, latency failures, and
finding distributions. A labelled calibration suite and blind human comparison
are prepared but not yet executed with the unavailable remote endpoint.

**Why it is not currently selected as evidence or reward.** Successful calls do
not establish label validity. Timeouts, prompt sensitivity, dominant low-
severity findings, and evaluator circularity remain unresolved.

**Final decision.** Defer judge-as-reward training. When remote access returns,
first run fixed-label calibration and a blinded human-reviewed comparison on
saved outputs. A judge-trained model must not be evaluated only by the same
judge configuration.

## Final justified plan

### Current HumanEval remote experiment

Run only:

1. `cq-core`: correctness and core rewards;
2. `cq-pep8`: identical configuration plus Ruff `E,W`;
3. at least three matched seeds;
4. identical model, task split, steps, generation settings, and evaluator
   versions;
5. paired held-out correctness, style, output length, variance, and runtime
   reporting.

This comparison is justified because Ruff is the only current signal with both
substantial activation and prior evidence of a learnable output change. It is
still conditional because aggregate group variation narrowly missed the frozen
gate and prior training was confounded by other rewards.

### Before expanding the matrix

1. Add and freeze a targeted dataset stratum for string construction, longer
   control flow, exception handling, security, and typed code.
2. Reconstruct full prompt/import context for Mypy.
3. Redesign and re-screen dynamic performance on harder/scaled inputs.
4. Repeat the same fixture, coverage, variation, latency, and correctness gates.
5. Promote at most two new signals; retain all others as offline evaluators or
   documented exclusions.
6. Report HumanEval and targeted-dataset outcomes separately rather than pooling
   them into one score.

### Publication claim boundary

The defensible result is not that popular validators failed. It is that
repository-oriented static analyzers differ sharply in their suitability as
dense per-completion RL rewards. The current evidence supports a dataset-fit
and reward-density analysis, while training-effect claims still require the
matched remote runs.
