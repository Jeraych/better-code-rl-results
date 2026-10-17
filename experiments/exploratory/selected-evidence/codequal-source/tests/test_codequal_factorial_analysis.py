import unittest

from experiments.codequal_training.analyze_factorial import factorial_effects


class FactorialEffectTests(unittest.TestCase):
    def test_recovers_main_and_pairwise_effects(self) -> None:
        cells = {}
        for style in (0, 1):
            for concat in (0, 1):
                for performance in (0, 1):
                    cells[(style, concat, performance)] = (
                        2 * style
                        + 3 * concat
                        + 5 * performance
                        + 7 * style * concat
                    )

        effects = factorial_effects(cells)
        self.assertIsNotNone(effects)
        self.assertEqual(effects["pep8_style:string_concat"], 7)
        self.assertEqual(effects["pep8_style:performance"], 0)
        self.assertEqual(effects["string_concat:performance"], 0)

    def test_incomplete_matrix_returns_none(self) -> None:
        self.assertIsNone(factorial_effects({(0, 0, 0): 1.0}))


if __name__ == "__main__":
    unittest.main()
