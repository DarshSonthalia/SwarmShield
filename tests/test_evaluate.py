import unittest

from evaluate import evaluate


class EvaluateTests(unittest.TestCase):
    def test_stress_summary_covers_all_outcomes(self):
        result = evaluate(7, 3, 60, 4, 2, ["mixed", "uncertain"])
        self.assertEqual(result["scenario_count"], 4)
        self.assertEqual(result["better_count"] + result["equal_count"] + result["worse_count"], 4)
        self.assertEqual(len(result["cases"]), 4)

    def test_invalid_seed_count_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(7, 3, 60, 0, 0, ["mixed"])


if __name__ == "__main__":
    unittest.main()
