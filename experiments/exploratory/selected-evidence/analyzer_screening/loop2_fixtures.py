"""Frozen, purpose-built fixtures for analyzer screening loop 2.

These cases test known tool behaviours and controls. They are development
fixtures, not independently labelled evidence of real-world validity.
"""

from __future__ import annotations


FIXTURES = [
    {
        "id": "radon_many_branches_positive",
        "analyzer": "radon_complexity",
        "expected": True,
        "entrypoint": "classify",
        "code": """def classify(value):
    if value == 0: return "zero"
    if value == 1: return "one"
    if value == 2: return "two"
    if value == 3: return "three"
    if value == 4: return "four"
    if value == 5: return "five"
    if value == 6: return "six"
    if value == 7: return "seven"
    if value == 8: return "eight"
    if value == 9: return "nine"
    if value == 10: return "ten"
    return "other"
""",
    },
    {
        "id": "radon_boolean_paths_positive",
        "analyzer": "radon_complexity",
        "expected": True,
        "entrypoint": "eligible",
        "code": """def eligible(a, b, c, d, e, f, g, h, i, j, k):
    return a and b and c and d and e and f and g and h and i and j and k
""",
    },
    {
        "id": "radon_lookup_control",
        "analyzer": "radon_complexity",
        "expected": False,
        "entrypoint": "classify",
        "code": """def classify(value):
    labels = {0: "zero", 1: "one", 2: "two"}
    return labels.get(value, "other")
""",
    },
    {
        "id": "radon_loop_control",
        "analyzer": "radon_complexity",
        "expected": False,
        "entrypoint": "total",
        "code": """def total(values):
    result = 0
    for value in values:
        result += value
    return result
""",
    },
    {
        "id": "vulture_unused_helper_positive",
        "analyzer": "vulture_dead_code",
        "expected": True,
        "entrypoint": "solve",
        "code": """def legacy_helper(value):
    return value + 100

def solve(values):
    return [value * 2 for value in values]
""",
    },
    {
        "id": "vulture_unused_class_positive",
        "analyzer": "vulture_dead_code",
        "expected": True,
        "entrypoint": "solve",
        "code": """class LegacyFormatter:
    def render(self, value):
        return str(value)

def solve(value):
    return str(value)
""",
    },
    {
        "id": "vulture_entrypoint_control",
        "analyzer": "vulture_dead_code",
        "expected": False,
        "entrypoint": "rolling_max",
        "code": """def rolling_max(numbers):
    result = []
    current = None
    for number in numbers:
        current = number if current is None else max(current, number)
        result.append(current)
    return result
""",
    },
    {
        "id": "vulture_used_helper_control",
        "analyzer": "vulture_dead_code",
        "expected": False,
        "entrypoint": "solve",
        "code": """def double(value):
    return value * 2

def solve(values):
    return [double(value) for value in values]
""",
    },
    {
        "id": "pylint_bare_except_positive",
        "analyzer": "pylint_exceptions",
        "expected": True,
        "entrypoint": "parse_number",
        "code": """def parse_number(value):
    try:
        return int(value)
    except:
        return None
""",
    },
    {
        "id": "pylint_broad_except_positive",
        "analyzer": "pylint_exceptions",
        "expected": True,
        "entrypoint": "parse_number",
        "code": """def parse_number(value):
    try:
        return int(value)
    except Exception:
        return None
""",
    },
    {
        "id": "pylint_specific_except_control",
        "analyzer": "pylint_exceptions",
        "expected": False,
        "entrypoint": "parse_number",
        "code": """def parse_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
""",
    },
    {
        "id": "pylint_context_manager_control",
        "analyzer": "pylint_exceptions",
        "expected": False,
        "entrypoint": "read_text",
        "code": """def read_text(path):
    with open(path, encoding="utf-8") as source:
        return source.read()
""",
    },
    {
        "id": "pylint_many_branches_positive",
        "analyzer": "pylint_structure",
        "expected": True,
        "entrypoint": "classify",
        "code": """def classify(value):
    if value == 0: return "zero"
    if value == 1: return "one"
    if value == 2: return "two"
    if value == 3: return "three"
    if value == 4: return "four"
    if value == 5: return "five"
    if value == 6: return "six"
    if value == 7: return "seven"
    if value == 8: return "eight"
    if value == 9: return "nine"
    if value == 10: return "ten"
    if value == 11: return "eleven"
    if value == 12: return "twelve"
    return "other"
""",
    },
    {
        "id": "pylint_many_locals_positive",
        "analyzer": "pylint_structure",
        "expected": True,
        "entrypoint": "calculate",
        "code": """def calculate(value):
    a = value + 1
    b = value + 2
    c = value + 3
    d = value + 4
    e = value + 5
    f = value + 6
    g = value + 7
    h = value + 8
    i = value + 9
    j = value + 10
    k = value + 11
    l = value + 12
    m = value + 13
    n = value + 14
    o = value + 15
    p = value + 16
    return a + b + c + d + e + f + g + h + i + j + k + l + m + n + o + p
""",
    },
    {
        "id": "pylint_lookup_control",
        "analyzer": "pylint_structure",
        "expected": False,
        "entrypoint": "classify",
        "code": """def classify(value):
    return {0: "zero", 1: "one"}.get(value, "other")
""",
    },
    {
        "id": "pylint_simple_loop_control",
        "analyzer": "pylint_structure",
        "expected": False,
        "entrypoint": "total",
        "code": """def total(values):
    return sum(values)
""",
    },
    {
        "id": "bandit_os_system_positive",
        "analyzer": "bandit_security",
        "expected": True,
        "entrypoint": "run_command",
        "code": """import os

def run_command(command):
    return os.system(command)
""",
    },
    {
        "id": "bandit_eval_positive",
        "analyzer": "bandit_security",
        "expected": True,
        "entrypoint": "parse_expression",
        "code": """def parse_expression(text):
    return eval(text)
""",
    },
    {
        "id": "bandit_literal_eval_control",
        "analyzer": "bandit_security",
        "expected": False,
        "entrypoint": "parse_expression",
        "code": """import ast

def parse_expression(text):
    return ast.literal_eval(text)
""",
    },
    {
        "id": "bandit_numeric_control",
        "analyzer": "bandit_security",
        "expected": False,
        "entrypoint": "square",
        "code": """def square(value):
    return value * value
""",
    },
    {
        "id": "mypy_wrong_return_positive",
        "analyzer": "mypy_type_safety",
        "expected": True,
        "entrypoint": "double",
        "code": """def double(value: int) -> int:
    return str(value * 2)
""",
    },
    {
        "id": "mypy_assignment_positive",
        "analyzer": "mypy_type_safety",
        "expected": True,
        "entrypoint": "label",
        "code": """def label(value: int) -> str:
    result: str = value
    return result
""",
    },
    {
        "id": "mypy_annotated_control",
        "analyzer": "mypy_type_safety",
        "expected": False,
        "entrypoint": "double",
        "code": """def double(value: int) -> int:
    return value * 2
""",
    },
    {
        "id": "mypy_untyped_control",
        "analyzer": "mypy_type_safety",
        "expected": False,
        "entrypoint": "identity",
        "code": """def identity(value):
    return value
""",
    },
]
