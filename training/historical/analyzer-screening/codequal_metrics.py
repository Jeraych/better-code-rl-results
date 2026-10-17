"""Fast, deterministic CodeQual-inspired metrics for online GRPO rewards.

This module intentionally does not wrap CodeQual's aggregate score.  Online
training needs a small, auditable signal with no network or subprocess cost.
The first supported rule detects repeated string construction inside loops.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class StringConcatFinding:
    line: int
    variable: str
    form: str

    def as_dict(self) -> dict[str, object]:
        return {"line": self.line, "variable": self.variable, "form": self.form}


def _target_name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _is_confident_string(node: ast.AST, known_strings: set[str]) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        return node.id in known_strings
    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Name) and node.func.id == "str"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_confident_string(node.left, known_strings) or _is_confident_string(
            node.right, known_strings
        )
    return False


def _binop_mentions_name(node: ast.BinOp, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


class _StringConcatVisitor(ast.NodeVisitor):
    """Conservative, order-aware detector for string growth inside loops."""

    def __init__(self) -> None:
        self._known_string_scopes: list[set[str]] = [set()]
        self._loop_depth = 0
        self.findings: list[StringConcatFinding] = []

    @property
    def known_strings(self) -> set[str]:
        return self._known_string_scopes[-1]

    def _visit_function_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._known_string_scopes.append(set())
        for statement in node.body:
            self.visit(statement)
        self._known_string_scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function_scope(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        self._known_string_scopes.append(set())
        self.visit(node.body)
        self._known_string_scopes.pop()

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        target_names = [name for target in node.targets if (name := _target_name(target))]
        for name in target_names:
            if (
                self._loop_depth > 0
                and name in self.known_strings
                and isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.Add)
                and _binop_mentions_name(node.value, name)
            ):
                self.findings.append(StringConcatFinding(node.lineno, name, "assign_add"))

        self.visit(node.value)
        for target in node.targets:
            self.visit(target)

        for name in target_names:
            if _is_confident_string(node.value, self.known_strings):
                self.known_strings.add(name)
            else:
                self.known_strings.discard(name)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None:
            self.visit(node.value)
        name = _target_name(node.target)
        if name:
            if node.value is not None and _is_confident_string(node.value, self.known_strings):
                self.known_strings.add(name)
            else:
                self.known_strings.discard(name)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        name = _target_name(node.target)
        if (
            self._loop_depth > 0
            and name
            and isinstance(node.op, ast.Add)
            and (
                name in self.known_strings
                or _is_confident_string(node.value, self.known_strings)
            )
        ):
            self.findings.append(StringConcatFinding(node.lineno, name, "augmented_add"))
            self.known_strings.add(name)
        self.generic_visit(node)

    def _visit_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self._visit_loop(node)


def analyze_string_concatenation(code: str) -> dict[str, object]:
    """Return a bounded score and evidence without executing candidate code."""

    started = time.perf_counter_ns()
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {
            "status": "invalid_syntax",
            "score": 0.0,
            "finding_count": 0,
            "findings": [],
            "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000.0,
            "error": str(exc),
        }

    visitor = _StringConcatVisitor()
    visitor.visit(tree)

    # Nested traversal can encounter the same statement through unusual AST
    # shapes; keep one auditable finding per source line and target variable.
    unique = {
        (finding.line, finding.variable, finding.form): finding
        for finding in visitor.findings
    }
    findings = [unique[key] for key in sorted(unique)]
    count = len(findings)

    return {
        "status": "ok",
        "score": 1.0 / (1.0 + count),
        "finding_count": count,
        "findings": [finding.as_dict() for finding in findings],
        "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000.0,
        "error": "",
    }
