import unittest

from swarmshield.webapp import generate_payload


class WebAppTests(unittest.TestCase):
    def test_payload_has_both_runs(self):
        payload = generate_payload()
        self.assertEqual(set(payload["runs"]), {"baseline", "swarmshield"})
        self.assertTrue(payload["runs"]["swarmshield"]["trajectories"])

    def test_payload_accepts_custom_force_sizes(self):
        payload = generate_payload(7, 3, seed=9, duration_s=75)
        self.assertEqual(payload["scenario"]["threat_count"], 7)
        self.assertEqual(payload["scenario"]["interceptor_count"], 3)
        self.assertEqual(payload["scenario"]["duration_s"], 75)


if __name__ == "__main__":
    unittest.main()
