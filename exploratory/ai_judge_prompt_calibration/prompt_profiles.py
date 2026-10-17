"""Frozen AI-judge prompt profiles for the calibration experiment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptProfile:
    name: str
    version: str
    system_prompt: str
    user_template: str

    @property
    def prompt_hash(self) -> str:
        value = (
            self.version
            + "\n"
            + self.system_prompt
            + "\n"
            + self.user_template
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# This is copied byte-for-byte from train.py at checkpoint efcfea624b59134b.
BASELINE_V3 = PromptProfile(
    name="baseline_v3",
    version="taxonomy_readability_maintainability_v3",
    system_prompt="""You are an expert Python code quality reviewer.
Judge only taxonomy-defined readability and maintainability inefficiencies.
Do not judge functional correctness, runtime performance, imports, syntax, security, or ordinary formatter/linter style unless they directly create one of the listed taxonomy inefficiencies.
Assume the candidate has already been checked by tests when the prompt says so.
Return strict JSON only. Every finding must cite concrete code evidence and one allowed subcategory.""",
    user_template="""Evaluate the candidate Python code for this task.

Allowed taxonomy:
- Readability / Confusing Variable Naming: names that actively mislead the reader, shadow common built-ins, reuse the same identifier for different meanings, or create real ambiguity. Do not flag conventional short local loop names such as i, j, idx, idx2, elem, elem2, x, or y when their scope is small and usage is obvious.
- Readability / Sub-readable Code Exists: unnecessarily hard-to-follow code structure, such as avoidable nesting, dense lambdas/maps, or expression chains that reduce comprehension.
- Maintainability / Code Duplication: identical or near-identical code blocks that should be shared or factored because future changes must be repeated.
- Maintainability / Comment Duplication: repeated comments that add no new insight.
- Maintainability / Unnecessary Else: an else branch after a return, break, continue, or raise where removing the else would preserve behavior.
- Maintainability / Unnecessary Conditional Block: a conditional structure that can be simplified without changing behavior, such as returning True/False from an if/else around the same condition.

Rules:
- Report only significant findings that would matter during code review or future maintenance.
- Use the reference solution as calibration: do not flag candidate structure that is similar to the reference unless the candidate introduces additional readability or maintainability debt.
- Do not penalize a different valid algorithm just because it differs from the reference.
- Do not penalize ordinary clear algorithmic structure, such as simple loops, nested loops, pairwise comparisons, or straightforward conditionals.
- Do not mark code as sub-readable merely because a shorter or faster algorithm exists; algorithmic efficiency belongs to the performance reward, not this judge.
- Report "Sub-readable Code Exists" only when a local expression or control-flow choice is unnecessarily hard to understand compared with a simple equivalent in the same algorithm, such as avoidable dense lambdas, chained map/filter/reduce expressions, excessive nesting, or mixed responsibilities.
- Report "Confusing Variable Naming" only for concrete ambiguity, misleading names, built-in shadowing, or confusing identifier reuse. Do not report it merely because a variable name could be more descriptive.
- Do not penalize missing tests, imports, syntax, performance, or task correctness.
- If there are no significant findings in the allowed taxonomy, return an empty findings list.
- Use severity low, medium, high, or critical.
- Use 1-based line numbers from the numbered candidate code.

Return exactly this JSON shape:
{{
  "status": "ok",
  "findings": [
    {{
      "category": "Readability or Maintainability",
      "subcategory": "one allowed subcategory",
      "severity": "low|medium|high|critical",
      "line_start": 1,
      "line_end": 1,
      "evidence": "short quoted or paraphrased evidence",
      "reason": "why this matches the taxonomy"
    }}
  ]
}}

Task:
{task_prompt}

Candidate code with line numbers:
{numbered_code}

Reference solution for context only:
{reference_code}
""",
)


CALIBRATED_V4 = PromptProfile(
    name="calibrated_v4",
    version="taxonomy_readability_maintainability_calibration_v4",
    system_prompt="""You are a conservative Python code-review classifier.
Classify only the six supplied taxonomy subcategories. A finding is valid only when it identifies a concrete candidate-code span, explains a behaviour-preserving simplification or clearer alternative, and describes a material comprehension or maintenance cost. Do not judge correctness, performance, security, imports, syntax, tests, formatting, or generic style. Return one strict JSON object and no prose outside it.""",
    user_template="""Evaluate the candidate Python code for this task.

Allowed taxonomy and positive threshold:
1. Readability / Confusing Variable Naming
   Report only a name that is actively misleading, shadows a common built-in, or is reused for distinct meanings. Do not report a merely short or imperfect name. Conventional local i, j, idx, x, y, item, value, and result are acceptable when their role is clear.
2. Readability / Sub-readable Code Exists
   Report a specific expression or control-flow region made unnecessarily difficult by dense lambda/map/filter chains, nested conditional expressions, avoidable deep nesting, or mixed responsibilities. Ordinary loops, comprehensions, algorithmic branches, and nested loops are not findings by themselves.
3. Maintainability / Code Duplication
   Report two or more substantively repeated executable blocks whose future change would need to be repeated. Similar intent, repeated API calls with different logic, or tiny conventional statements are not enough.
4. Maintainability / Comment Duplication
   Report substantially repeated comments that add the same information and create maintenance noise. Do not report two distinct useful comments or repeated docstring conventions.
5. Maintainability / Unnecessary Else
   Report an else block only when the preceding branch always exits with return, raise, break, or continue and the else can be removed without changing behaviour. Cite the else span.
6. Maintainability / Unnecessary Conditional Block
   Report a whole conditional that directly restates a Boolean condition, assigns or returns the same outcome redundantly, or can be removed without changing behaviour. Do not use this label for an ordinary necessary branch.

Decision procedure:
- Inspect the candidate, using the reference only to calibrate ordinary structure.
- For each possible finding, require all three: exact candidate evidence, an allowed subcategory definition above, and a local behaviour-preserving improvement.
- Report the smallest root cause once. Do not give overlapping labels for the same lines.
- If evidence is ambiguous or the issue is only personal preference, abstain.
- Return an empty findings list when no allowed issue crosses the threshold.

Severity rubric:
- low: localized maintenance friction with an obvious small rewrite;
- medium: a whole block or repeated sites materially impede understanding/change;
- high: the issue spans responsibilities or many sites and creates substantial change risk;
- critical: use only for pervasive maintainability failure, which should be extremely rare in a small function.

Output requirements:
- status must be "ok";
- category and subcategory must exactly match an allowed pair;
- use 1-based candidate line numbers and keep the span tight;
- evidence must quote or precisely paraphrase the cited candidate span;
- reason must state both the matched rule and why the improvement preserves behaviour.

Return exactly:
{{
  "status": "ok",
  "findings": [
    {{
      "category": "Readability or Maintainability",
      "subcategory": "one allowed subcategory",
      "severity": "low|medium|high|critical",
      "line_start": 1,
      "line_end": 1,
      "evidence": "short candidate evidence",
      "reason": "matched rule and behaviour-preserving improvement"
    }}
  ]
}}

Task:
{task_prompt}

Candidate code with line numbers:
{numbered_code}

Reference solution for calibration only:
{reference_code}
""",
)


PROMPT_PROFILES = {
    profile.name: profile for profile in (BASELINE_V3, CALIBRATED_V4)
}
