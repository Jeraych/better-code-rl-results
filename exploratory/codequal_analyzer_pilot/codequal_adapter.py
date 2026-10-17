"""Non-invasive adapter used to evaluate codequal_analyzer integration.

This module returns rule-level findings only. It does not execute candidate code
and deliberately does not expose the library's aggregate score as a reward.
"""

from __future__ import annotations

import ast
import tempfile
import time
from pathlib import Path
from typing import Any


SELECTED_RULES = {
    "inefficient-string-concatenation",
    "excessive-resource-consumption",
    "improper-exception-handling",
    "excessive-data-structure-complexity",
    "unused-function",
}


def is_selected_rule(rule_id: str) -> bool:
    return rule_id in SELECTED_RULES or rule_id.startswith("complexity-")


def _filter_entrypoint(
    findings: dict[str, list[dict[str, Any]]],
    entrypoint: str | None,
) -> dict[str, list[dict[str, Any]]]:
    return {
        characteristic: [
            finding
            for finding in items
            if not (
                entrypoint
                and finding.get("analyzer") == "vulture"
                and finding.get("rule_id") == "unused-function"
                and finding.get("raw_data", {}).get("name") == entrypoint
            )
        ]
        for characteristic, items in findings.items()
    }


def _run_ast_only(directory: Path) -> dict[str, list[dict[str, Any]]]:
    from pycq_analyzer.analyzers.data_structure_analyzer import (
        DataStructureComplexityAnalyzer,
    )
    from pycq_analyzer.analyzers.exception_handling_analyzer import (
        ExceptionHandlingAnalyzer,
    )
    from pycq_analyzer.analyzers.resource_consumption_analyzer import (
        ResourceConsumptionAnalyzer,
    )
    from pycq_analyzer.analyzers.string_concat_analyzer import (
        StringConcatenationAnalyzer,
    )

    analyzers = [
        StringConcatenationAnalyzer(directory),
        ResourceConsumptionAnalyzer(directory),
        DataStructureComplexityAnalyzer(directory),
        ExceptionHandlingAnalyzer(directory),
    ]
    findings = {
        "maintainability": [],
        "security": [],
        "performance": [],
        "reliability": [],
    }
    for analyzer in analyzers:
        findings[analyzer.characteristic].extend(analyzer.analyze())
    return findings


def analyze_candidate(
    code: str,
    entrypoint: str | None,
    mode: str = "quick",
) -> dict[str, Any]:
    """Analyze a code string without executing it."""
    started = time.perf_counter()
    try:
        ast.parse(code)
    except SyntaxError as error:
        return {
            "status": "invalid_syntax",
            "error": f"{error.msg} at line {error.lineno}",
            "mode": mode,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "findings": [],
            "rule_ids": [],
        }

    with tempfile.TemporaryDirectory(prefix="codequal_decision_") as temp:
        directory = Path(temp)
        (directory / "candidate.py").write_text(code, encoding="utf-8")
        if mode == "quick":
            from pycq_analyzer.api import run_selected_analyzers

            findings = run_selected_analyzers(
                directory,
                verbose=False,
                max_jobs=4,
                complexity_threshold="C",
                ignore_solution_unused=False,
            )
        elif mode == "ast_only":
            findings = _run_ast_only(directory)
        else:
            raise ValueError(f"Unsupported analysis mode: {mode}")

    filtered = _filter_entrypoint(findings, entrypoint)
    selected = [
        finding
        for items in filtered.values()
        for finding in items
        if is_selected_rule(finding.get("rule_id", ""))
    ]
    return {
        "status": "ok",
        "error": "",
        "mode": mode,
        "elapsed_ms": (time.perf_counter() - started) * 1000,
        "findings": selected,
        "rule_ids": sorted({finding.get("rule_id", "") for finding in selected}),
    }
