import unittest

from swarmshield.scenario import build_scenario, scenario_from_dict, scenario_to_dict
from swarmshield.simulator import run_comparison


class ScenarioMatrixTests(unittest.TestCase):
    def test_varied_force_sizes_preserve_invariants(self):
        cases = [(1, 0, 30), (1, 1, 60), (3, 10, 90), (20, 12, 190), (50, 8, 120), (12, 30, 120), (80, 60, 90)]
        for threats, interceptors, duration in cases:
            with self.subTest(threats=threats, interceptors=interceptors):
                result = run_comparison(build_scenario(threats, interceptors, seed=threats * 100 + interceptors, duration_s=duration))
                self.assertEqual(result["scenario"]["threat_count"], threats)
                self.assertEqual(result["scenario"]["interceptor_count"], interceptors)
                for run in result["runs"].values():
                    metrics = run["metrics"]
                    self.assertEqual(metrics["intercepted"] + metrics["leakage"] + metrics["off_course_unresolved"], threats)
                    self.assertLessEqual(metrics["interceptors_launched"], interceptors)
                    self.assertLessEqual(metrics["critical_leaks"], metrics["leakage"])
                    initial = run["allocations"][0]["assignments"]
                    self.assertEqual(len(initial), len(set(initial.values())))
                    self.assertLessEqual(len(initial), min(threats, interceptors))

    def test_custom_scenario_roundtrip(self):
        original = build_scenario(7, 3, seed=5, duration_s=90)
        restored = scenario_from_dict(scenario_to_dict(original))
        self.assertEqual(len(restored.threats), 7)
        self.assertEqual(len(restored.interceptors), 3)
        self.assertEqual(restored.events, original.events)
        result = run_comparison(restored)
        self.assertEqual(result["scenario"]["threat_count"], 7)

    def test_invalid_custom_references_are_rejected(self):
        definition = scenario_to_dict(build_scenario(3, 2))
        definition["threats"][0]["asset_id"] = "MISSING"
        with self.assertRaises(ValueError):
            scenario_from_dict(definition)

    def test_invalid_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            build_scenario(0, 5)
        with self.assertRaises(ValueError):
            build_scenario(5, -1)
        with self.assertRaises(ValueError):
            build_scenario(5, 2, duration_s=10)


if __name__ == "__main__":
    unittest.main()
