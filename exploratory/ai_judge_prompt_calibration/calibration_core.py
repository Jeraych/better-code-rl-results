"""Standalone request, parsing, validation, and scoring helpers."""

from __future__ import annotations

import json
import re
from typing import Any


ALLOWED_SUBCATEGORIES = {
    "Readability": {
        "Confusing Variable Naming",
        "Sub-readable Code Exists",
    },
    "Maintainability": {
        "Code Duplication",
        "Comment Duplication",
        "Unnecessary Else",
        "Unnecessary Conditional Block",
    },
}
SEVERITY_WEIGHTS = {"low": 0.15, "medium": 0.35, "high": 0.65, "critical": 1.0}


def numbered_python_code(code: str) -> str:
    return "\n".join(
        f"{line_number:>4}: {line}"
        for line_number, line in enumerate(code.splitlines(), start=1)
    )


def build_user_prompt(profile: Any, case: dict[str, Any]) -> str:
    return profile.user_template.format(
        task_prompt=case["task_prompt"].strip(),
        numbered_code=numbered_python_code(case["candidate_code"]),
        reference_code=case["reference_code"].strip(),
    )


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = str(text).strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Judge response is not a JSON object")
    return parsed


def code_lines_for_span(code: str, line_start: int, line_end: int) -> str:
    lines = code.splitlines()
    if line_start <= 0 or line_end <= 0:
        return ""
    start_index = max(0, line_start - 1)
    end_index = min(len(lines), max(line_start, line_end))
    return "\n".join(lines[start_index:end_index])


def sanitize_findings(raw_response: dict[str, Any], code: str) -> list[dict[str, Any]]:
    findings = raw_response.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings is not a list")

    sanitized = []
    for finding in findings[:8]:
        if not isinstance(finding, dict):
            continue
        category = str(finding.get("category", "")).strip()
        subcategory = str(finding.get("subcategory", "")).strip()
        severity = str(finding.get("severity", "")).strip().lower()
        if category not in ALLOWED_SUBCATEGORIES:
            continue
        if subcategory not in ALLOWED_SUBCATEGORIES[category]:
            continue
        if severity not in SEVERITY_WEIGHTS:
            continue

        evidence = str(finding.get("evidence", "")).strip()[:300]
        reason = str(finding.get("reason", "")).strip()[:500]
        weak_naming_reason = re.search(
            r"\bnot descriptive\b|\bmore descriptive\b|\bdescriptive enough\b",
            reason,
            re.IGNORECASE,
        )
        conventional_names = re.search(r"\b(i|j|idx|idx2|elem|elem2|x|y)\b", evidence)
        stronger_naming_issue = re.search(
            r"\bshadow|built-?in|reuse|reused|ambiguous|ambiguity|misleading|"
            r"different meanings|same identifier\b",
            reason,
            re.IGNORECASE,
        )
        if (
            subcategory == "Confusing Variable Naming"
            and weak_naming_reason
            and conventional_names
            and not stronger_naming_issue
        ):
            continue

        try:
            line_start = int(finding.get("line_start", 0))
            line_end = int(finding.get("line_end", line_start))
        except (TypeError, ValueError):
            line_start = 0
            line_end = 0
        span_text = code_lines_for_span(code, line_start, line_end)
        if subcategory == "Unnecessary Else" and not re.search(
            r"\belse\s*:", f"{evidence}\n{span_text}"
        ):
            continue
        sanitized.append(
            {
                "category": category,
                "subcategory": subcategory,
                "severity": severity,
                "line_start": max(0, line_start),
                "line_end": max(0, line_end),
                "evidence": evidence,
                "reason": reason,
            }
        )
    return sanitized


def score_findings(findings: list[dict[str, Any]]) -> float:
    penalty = sum(SEVERITY_WEIGHTS[item["severity"]] for item in findings)
    return max(0.0, min(1.0, 1.0 - penalty))
