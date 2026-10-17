"""Frozen paired interventions for AI-judge prompt calibration."""

from __future__ import annotations

from textwrap import dedent


def code(value: str) -> str:
    return dedent(value).strip() + "\n"


PAIRS = [
    {
        "pair_id": "naming_builtin_shadow",
        "category": "Readability",
        "subcategory": "Confusing Variable Naming",
        "task_prompt": "Write collect_positive(values) returning positive values in order.",
        "clean": code('''
            def collect_positive(values):
                positives = []
                for value in values:
                    if value > 0:
                        positives.append(value)
                return positives
        '''),
        "degraded": code('''
            def collect_positive(values):
                list = []
                for value in values:
                    if value > 0:
                        list.append(value)
                return list
        '''),
        "seeded_evidence": "The local variable list shadows the built-in list type.",
    },
    {
        "pair_id": "naming_reused_meaning",
        "category": "Readability",
        "subcategory": "Confusing Variable Naming",
        "task_prompt": "Write normalized(values) returning each value divided by the total.",
        "clean": code('''
            def normalized(values):
                total = sum(values)
                normalized_values = [value / total for value in values]
                return normalized_values
        '''),
        "degraded": code('''
            def normalized(values):
                result = sum(values)
                result = [value / result for value in values]
                return result
        '''),
        "seeded_evidence": "result changes meaning from a numeric total to the output list.",
    },
    {
        "pair_id": "naming_misleading_boolean",
        "category": "Readability",
        "subcategory": "Confusing Variable Naming",
        "task_prompt": "Write average(values) returning the arithmetic mean.",
        "clean": code('''
            def average(values):
                total = sum(values)
                return total / len(values)
        '''),
        "degraded": code('''
            def average(values):
                is_empty = sum(values)
                return is_empty / len(values)
        '''),
        "seeded_evidence": "is_empty sounds Boolean but stores a numeric sum.",
    },
    {
        "pair_id": "subreadable_map_filter_chain",
        "category": "Readability",
        "subcategory": "Sub-readable Code Exists",
        "task_prompt": "Write even_squares(values) returning squares of even values.",
        "clean": code('''
            def even_squares(values):
                return [value * value for value in values if value % 2 == 0]
        '''),
        "degraded": code('''
            def even_squares(values):
                return list(map(lambda value: value * value, filter(lambda value: value % 2 == 0, values)))
        '''),
        "seeded_evidence": "A nested map/filter/lambda chain replaces a direct comprehension.",
    },
    {
        "pair_id": "subreadable_nested_ternary",
        "category": "Readability",
        "subcategory": "Sub-readable Code Exists",
        "task_prompt": "Write temperature_label(value) returning cold, warm, or hot.",
        "clean": code('''
            def temperature_label(value):
                if value < 10:
                    return "cold"
                if value < 25:
                    return "warm"
                return "hot"
        '''),
        "degraded": code('''
            def temperature_label(value):
                return "cold" if value < 10 else ("warm" if value < 25 else "hot")
        '''),
        "seeded_evidence": "A nested conditional expression compresses three branches into one line.",
    },
    {
        "pair_id": "subreadable_avoidable_nesting",
        "category": "Readability",
        "subcategory": "Sub-readable Code Exists",
        "task_prompt": "Write active_names(records) for enabled records with non-empty names.",
        "clean": code('''
            def active_names(records):
                names = []
                for record in records:
                    if not record["enabled"]:
                        continue
                    if not record["name"]:
                        continue
                    names.append(record["name"])
                return names
        '''),
        "degraded": code('''
            def active_names(records):
                names = []
                for record in records:
                    if record["enabled"]:
                        if record["name"]:
                            if len(record["name"]) > 0:
                                names.append(record["name"])
                return names
        '''),
        "seeded_evidence": "Redundant checks create three avoidable nesting levels.",
    },
    {
        "pair_id": "duplication_format_branches",
        "category": "Maintainability",
        "subcategory": "Code Duplication",
        "task_prompt": "Write describe_users(users) with one formatted line per user.",
        "clean": code('''
            def describe_users(users):
                lines = []
                for user in users:
                    status = "active" if user["active"] else "inactive"
                    lines.append(f"{user['name']} ({user['age']}): {status}")
                return lines
        '''),
        "degraded": code('''
            def describe_users(users):
                lines = []
                for user in users:
                    if user["active"]:
                        name = user["name"].strip()
                        age = str(user["age"])
                        lines.append(name + " (" + age + "): active")
                    else:
                        name = user["name"].strip()
                        age = str(user["age"])
                        lines.append(name + " (" + age + "): inactive")
                return lines
        '''),
        "seeded_evidence": "Both branches repeat name, age, and formatting preparation.",
    },
    {
        "pair_id": "duplication_validation_blocks",
        "category": "Maintainability",
        "subcategory": "Code Duplication",
        "task_prompt": "Write rectangle_area(width, height), rejecting non-positive dimensions.",
        "clean": code('''
            def rectangle_area(width, height):
                for name, value in (("width", width), ("height", height)):
                    if value <= 0:
                        raise ValueError(f"{name} must be positive")
                return width * height
        '''),
        "degraded": code('''
            def rectangle_area(width, height):
                if width <= 0:
                    message = "width must be positive"
                    raise ValueError(message)
                if height <= 0:
                    message = "height must be positive"
                    raise ValueError(message)
                return width * height
        '''),
        "seeded_evidence": "Near-identical validation and exception blocks are repeated.",
    },
    {
        "pair_id": "duplication_transform_blocks",
        "category": "Maintainability",
        "subcategory": "Code Duplication",
        "task_prompt": "Write cleaned_groups(primary, secondary) returning stripped non-empty strings.",
        "clean": code('''
            def cleaned_groups(primary, secondary):
                def clean(values):
                    return [value.strip() for value in values if value.strip()]
                return clean(primary), clean(secondary)
        '''),
        "degraded": code('''
            def cleaned_groups(primary, secondary):
                first = []
                for value in primary:
                    cleaned = value.strip()
                    if cleaned:
                        first.append(cleaned)
                second = []
                for value in secondary:
                    cleaned = value.strip()
                    if cleaned:
                        second.append(cleaned)
                return first, second
        '''),
        "seeded_evidence": "The same stripping, filtering, and appending block is repeated.",
    },
    {
        "pair_id": "comment_duplication_branches",
        "category": "Maintainability",
        "subcategory": "Comment Duplication",
        "task_prompt": "Write bucket(values) separating negative, zero, and positive values.",
        "clean": code('''
            def bucket(values):
                groups = {"negative": [], "zero": [], "positive": []}
                for value in values:
                    if value < 0:
                        groups["negative"].append(value)
                    elif value == 0:
                        groups["zero"].append(value)
                    else:
                        groups["positive"].append(value)
                return groups
        '''),
        "degraded": code('''
            def bucket(values):
                groups = {"negative": [], "zero": [], "positive": []}
                for value in values:
                    if value < 0:
                        # Add the value to the correct output group.
                        groups["negative"].append(value)
                    elif value == 0:
                        # Add the value to the correct output group.
                        groups["zero"].append(value)
                    else:
                        # Add the value to the correct output group.
                        groups["positive"].append(value)
                return groups
        '''),
        "seeded_evidence": "The same uninformative output-group comment appears in all branches.",
    },
    {
        "pair_id": "comment_duplication_counters",
        "category": "Maintainability",
        "subcategory": "Comment Duplication",
        "task_prompt": "Write count_types(values) counting ints, strings, and other values.",
        "clean": code('''
            def count_types(values):
                counts = {"int": 0, "str": 0, "other": 0}
                for value in values:
                    if isinstance(value, int):
                        counts["int"] += 1
                    elif isinstance(value, str):
                        counts["str"] += 1
                    else:
                        counts["other"] += 1
                return counts
        '''),
        "degraded": code('''
            def count_types(values):
                counts = {"int": 0, "str": 0, "other": 0}
                for value in values:
                    if isinstance(value, int):
                        # Increment the matching counter.
                        counts["int"] += 1
                    elif isinstance(value, str):
                        # Increment the matching counter.
                        counts["str"] += 1
                    else:
                        # Increment the matching counter.
                        counts["other"] += 1
                return counts
        '''),
        "seeded_evidence": "The identical counter comment is repeated three times.",
    },
    {
        "pair_id": "comment_duplication_adjacent",
        "category": "Maintainability",
        "subcategory": "Comment Duplication",
        "task_prompt": "Write clamp(value, lower, upper) limiting value to the inclusive range.",
        "clean": code('''
            def clamp(value, lower, upper):
                if value < lower:
                    return lower
                if value > upper:
                    return upper
                return value
        '''),
        "degraded": code('''
            def clamp(value, lower, upper):
                # Keep the value inside the allowed range.
                if value < lower:
                    return lower
                # Keep the value inside the allowed range.
                if value > upper:
                    return upper
                # Keep the value inside the allowed range.
                return value
        '''),
        "seeded_evidence": "The same range comment precedes every return path.",
    },
    {
        "pair_id": "else_after_return",
        "category": "Maintainability",
        "subcategory": "Unnecessary Else",
        "task_prompt": "Write sign_label(value) returning negative or non-negative.",
        "clean": code('''
            def sign_label(value):
                if value < 0:
                    return "negative"
                return "non-negative"
        '''),
        "degraded": code('''
            def sign_label(value):
                if value < 0:
                    return "negative"
                else:
                    return "non-negative"
        '''),
        "seeded_evidence": "The else follows a branch that always returns.",
    },
    {
        "pair_id": "else_after_continue",
        "category": "Maintainability",
        "subcategory": "Unnecessary Else",
        "task_prompt": "Write non_empty(values) returning non-empty strings stripped.",
        "clean": code('''
            def non_empty(values):
                result = []
                for value in values:
                    if not value.strip():
                        continue
                    result.append(value.strip())
                return result
        '''),
        "degraded": code('''
            def non_empty(values):
                result = []
                for value in values:
                    if not value.strip():
                        continue
                    else:
                        result.append(value.strip())
                return result
        '''),
        "seeded_evidence": "The else follows a loop branch that always continues.",
    },
    {
        "pair_id": "else_after_raise",
        "category": "Maintainability",
        "subcategory": "Unnecessary Else",
        "task_prompt": "Write reciprocal(value), rejecting zero.",
        "clean": code('''
            def reciprocal(value):
                if value == 0:
                    raise ValueError("zero has no reciprocal")
                return 1 / value
        '''),
        "degraded": code('''
            def reciprocal(value):
                if value == 0:
                    raise ValueError("zero has no reciprocal")
                else:
                    return 1 / value
        '''),
        "seeded_evidence": "The else follows a branch that always raises.",
    },
    {
        "pair_id": "conditional_boolean_return",
        "category": "Maintainability",
        "subcategory": "Unnecessary Conditional Block",
        "task_prompt": "Write is_even(value) returning whether value is even.",
        "clean": code('''
            def is_even(value):
                return value % 2 == 0
        '''),
        "degraded": code('''
            def is_even(value):
                if value % 2 == 0:
                    return True
                return False
        '''),
        "seeded_evidence": "The conditional directly restates its Boolean condition.",
    },
    {
        "pair_id": "conditional_boolean_assignment",
        "category": "Maintainability",
        "subcategory": "Unnecessary Conditional Block",
        "task_prompt": "Write has_items(values) returning whether values is non-empty.",
        "clean": code('''
            def has_items(values):
                return bool(values)
        '''),
        "degraded": code('''
            def has_items(values):
                result = False
                if len(values) > 0:
                    result = True
                return result
        '''),
        "seeded_evidence": "The temporary and conditional only convert the condition to Boolean.",
    },
    {
        "pair_id": "conditional_redundant_branch",
        "category": "Maintainability",
        "subcategory": "Unnecessary Conditional Block",
        "task_prompt": "Write normalized_name(name) returning a stripped lowercase name.",
        "clean": code('''
            def normalized_name(name):
                return name.strip().lower()
        '''),
        "degraded": code('''
            def normalized_name(name):
                if name:
                    result = name.strip().lower()
                else:
                    result = name.strip().lower()
                return result
        '''),
        "seeded_evidence": "Both conditional branches perform the identical assignment.",
    },
]
