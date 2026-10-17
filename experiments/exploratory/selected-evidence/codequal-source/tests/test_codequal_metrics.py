import unittest

from codequal_metrics import analyze_string_concatenation


class StringConcatenationMetricTests(unittest.TestCase):
    def assert_findings(self, code: str, expected: int) -> None:
        result = analyze_string_concatenation(code)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["finding_count"], expected)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)

    def test_detects_plain_value_growth_from_empty_string(self) -> None:
        self.assert_findings(
            "def join(values):\n    result = ''\n    for value in values:\n        result += value\n    return result\n",
            1,
        )

    def test_detects_str_call_and_f_string(self) -> None:
        self.assert_findings(
            "def render(values):\n    result = ''\n    for value in values:\n        result += str(value)\n        result += f'[{value}]'\n    return result\n",
            2,
        )

    def test_detects_expanded_assignment_form(self) -> None:
        self.assert_findings(
            "def join(values):\n    result = ''\n    for value in values:\n        result = result + value\n    return result\n",
            1,
        )

    def test_does_not_flag_numeric_accumulation(self) -> None:
        self.assert_findings(
            "def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n",
            0,
        )

    def test_does_not_flag_list_growth_or_join(self) -> None:
        self.assert_findings(
            "def join(values):\n    parts = []\n    for value in values:\n        parts.append(str(value))\n    return ''.join(parts)\n",
            0,
        )

    def test_does_not_flag_single_concatenation_outside_loop(self) -> None:
        self.assert_findings("def greet(name):\n    return 'Hello ' + name\n", 0)

    def test_nested_function_does_not_inherit_outer_string_state(self) -> None:
        self.assert_findings(
            "def outer(values):\n    result = ''\n    def inner(numbers):\n        result = 0\n        for number in numbers:\n            result += number\n        return result\n    return inner(values)\n",
            0,
        )

    def test_invalid_syntax_is_reported(self) -> None:
        result = analyze_string_concatenation("def broken(:\n")
        self.assertEqual(result["status"], "invalid_syntax")
        self.assertEqual(result["score"], 0.0)


if __name__ == "__main__":
    unittest.main()
