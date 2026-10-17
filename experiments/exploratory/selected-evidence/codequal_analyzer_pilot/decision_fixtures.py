"""Pre-labelled fixtures for the final codequal_analyzer decision test."""

from __future__ import annotations


FIXTURES = [
    {
        "id": "concat_str_conversion_positive",
        "family": "string_concat",
        "rule": "inefficient-string-concatenation",
        "expected": True,
        "entrypoint": "build_text",
        "code": '''def build_text(words):
    result = ""
    for word in words:
        result += str(word)
    return result
''',
    },
    {
        "id": "concat_plain_string_positive",
        "family": "string_concat",
        "rule": "inefficient-string-concatenation",
        "expected": True,
        "entrypoint": "build_text",
        "code": '''def build_text(words):
    result = ""
    for word in words:
        result += word
    return result
''',
    },
    {
        "id": "concat_fstring_positive",
        "family": "string_concat",
        "rule": "inefficient-string-concatenation",
        "expected": True,
        "entrypoint": "build_text",
        "code": '''def build_text(words):
    result = ""
    for word in words:
        result += f"{word}"
    return result
''',
    },
    {
        "id": "concat_join_control",
        "family": "string_concat",
        "rule": "inefficient-string-concatenation",
        "expected": False,
        "entrypoint": "build_text",
        "code": '''def build_text(words):
    return "".join(str(word) for word in words)
''',
    },
    {
        "id": "concat_numeric_sum_control",
        "family": "string_concat",
        "rule": "inefficient-string-concatenation",
        "expected": False,
        "entrypoint": "total_values",
        "code": '''def total_values(values):
    total = 0
    for value in values:
        total += value
    return total
''',
    },
    {
        "id": "resource_file_open_positive",
        "family": "resource_loop",
        "rule": "excessive-resource-consumption",
        "expected": True,
        "entrypoint": "write_lines",
        "code": '''def write_lines(path, lines):
    for line in lines:
        with open(path, "a", encoding="utf-8") as output:
            output.write(line)
''',
    },
    {
        "id": "resource_sleep_positive",
        "family": "resource_loop",
        "rule": "excessive-resource-consumption",
        "expected": True,
        "entrypoint": "wait_for_items",
        "code": '''import time

def wait_for_items(items, delay):
    for _ in items:
        time.sleep(delay)
''',
    },
    {
        "id": "resource_list_growth_positive",
        "family": "resource_loop",
        "rule": "excessive-resource-consumption",
        "expected": True,
        "entrypoint": "copy_values",
        "code": '''def copy_values(values):
    result = []
    for value in values:
        result += [value]
    return result
''',
    },
    {
        "id": "resource_numeric_accumulator_control",
        "family": "resource_loop",
        "rule": "excessive-resource-consumption",
        "expected": False,
        "entrypoint": "total_values",
        "code": '''def total_values(values):
    total = 0
    for value in values:
        total += value
    return total
''',
    },
    {
        "id": "resource_append_control",
        "family": "resource_loop",
        "rule": "excessive-resource-consumption",
        "expected": False,
        "entrypoint": "copy_values",
        "code": '''def copy_values(values):
    result = []
    for value in values:
        result.append(value)
    return result
''',
    },
    {
        "id": "resource_open_handle_control",
        "family": "resource_loop",
        "rule": "excessive-resource-consumption",
        "expected": False,
        "entrypoint": "write_lines",
        "code": '''def write_lines(path, lines):
    with open(path, "a", encoding="utf-8") as output:
        for line in lines:
            output.write(line)
''',
    },
    {
        "id": "exception_bare_positive",
        "family": "exception_handling",
        "rule": "improper-exception-handling",
        "expected": True,
        "entrypoint": "parse_number",
        "code": '''def parse_number(value):
    try:
        return int(value)
    except:
        pass
    return None
''',
    },
    {
        "id": "exception_broad_positive",
        "family": "exception_handling",
        "rule": "improper-exception-handling",
        "expected": True,
        "entrypoint": "parse_number",
        "code": '''def parse_number(value):
    try:
        return int(value)
    except Exception:
        return None
''',
    },
    {
        "id": "exception_specific_control",
        "family": "exception_handling",
        "rule": "improper-exception-handling",
        "expected": False,
        "entrypoint": "parse_number",
        "code": '''def parse_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
''',
    },
    {
        "id": "exception_context_manager_control",
        "family": "exception_handling",
        "rule": "improper-exception-handling",
        "expected": False,
        "entrypoint": "read_text",
        "code": '''def read_text(path):
    with open(path, encoding="utf-8") as source:
        return source.read()
''',
    },
    {
        "id": "structure_many_attributes_positive",
        "family": "data_structure",
        "rule": "excessive-data-structure-complexity",
        "expected": True,
        "entrypoint": "make_record",
        "code": '''class Record:
    def __init__(self):
        self.a = 1
        self.b = 2
        self.c = 3
        self.d = 4
        self.e = 5
        self.f = 6
        self.g = 7
        self.h = 8
        self.i = 9
        self.j = 10
        self.k = 11

def make_record():
    return Record()
''',
    },
    {
        "id": "structure_nested_positive",
        "family": "data_structure",
        "rule": "excessive-data-structure-complexity",
        "expected": True,
        "entrypoint": "nested_value",
        "code": '''def nested_value():
    return [[[[[[1]]]]]]
''',
    },
    {
        "id": "structure_lookup_table_control",
        "family": "data_structure",
        "rule": "excessive-data-structure-complexity",
        "expected": False,
        "entrypoint": "label",
        "code": '''LABELS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}

def label(value):
    return LABELS.get(value, "other")
''',
    },
    {
        "id": "structure_small_dict_control",
        "family": "data_structure",
        "rule": "excessive-data-structure-complexity",
        "expected": False,
        "entrypoint": "coordinates",
        "code": '''def coordinates(x, y):
    return {"x": x, "y": y}
''',
    },
    {
        "id": "complexity_branch_positive",
        "family": "complexity",
        "rule": "complexity-",
        "expected": True,
        "entrypoint": "classify",
        "code": '''def classify(value):
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
    return "other"
''',
    },
    {
        "id": "complexity_lookup_control",
        "family": "complexity",
        "rule": "complexity-",
        "expected": False,
        "entrypoint": "classify",
        "code": '''def classify(value):
    labels = {0: "zero", 1: "one", 2: "two"}
    return labels.get(value, "other")
''',
    },
    {
        "id": "dead_helper_positive",
        "family": "dead_code",
        "rule": "unused-function",
        "expected": True,
        "entrypoint": "double_values",
        "code": '''def legacy_transform(value):
    return value + 100

def double_values(values):
    return [value * 2 for value in values]
''',
    },
    {
        "id": "entrypoint_control",
        "family": "dead_code",
        "rule": "unused-function",
        "expected": False,
        "entrypoint": "rolling_max",
        "code": '''def rolling_max(numbers):
    result = []
    current = None
    for number in numbers:
        current = number if current is None else max(current, number)
        result.append(current)
    return result
''',
    },
]


AST_ONLY_FAMILIES = {
    "string_concat",
    "resource_loop",
    "exception_handling",
    "data_structure",
}
