import json
import unittest

from swarmshield.scenario import build_hackathon_scenario
from swarmshield.simulator import run_comparison, run_scenario


class SimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = build_hackathon_scenario()
        cls.result = run_comparison(cls.scenario)

    def test_deterministic(self):
        again = run_comparison(build_hackathon_scenario())
        self.assertEqual(self.result["headline"], again["headline"])
        self.assertEqual(self.result["runs"]["swarmshield"]["metrics"], again["runs"]["swarmshield"]["metrics"])

    def test_ground_link_loss_uses_peer_mode(self):
        allocations = self.result["runs"]["swarmshield"]["allocations"]
        self.assertTrue(any(item["mode"] == "peer-to-peer" for item in allocations if item["time_s"] >= 66))

    def test_failure_and_diversion_are_exercised(self):
        types = {item["type"] for item in self.result["runs"]["swarmshield"]["events"]}
        self.assertIn("interceptor_failure", types)
        self.assertIn("threat_diversion", types)
        self.assertIn("reassignment", types)
        self.assertIn("failure_recovery", types)

    def test_schema_is_json_serializable(self):
        encoded = json.dumps(self.result)
        self.assertIn('"schema_version": "1.0"', encoded)

    def test_swarmshield_reduces_consequence(self):
        baseline = self.result["runs"]["baseline"]["metrics"]
        shield = self.result["runs"]["swarmshield"]["metrics"]
        self.assertLess(shield["expected_consequence_leaked"], baseline["expected_consequence_leaked"])
        self.assertLessEqual(shield["critical_leaks"], baseline["critical_leaks"])

    def test_twenty_threats_twelve_rounds(self):
        metrics = self.result["runs"]["swarmshield"]["metrics"]
        self.assertEqual(metrics["threats"], 20)
        self.assertEqual(metrics["interceptors"], 12)

    def test_collision_avoidance_is_exercised(self):
        metrics = self.result["runs"]["swarmshield"]["metrics"]
        self.assertGreater(metrics["collision_avoidance_actions"], 0)


if __name__ == "__main__":
    unittest.main()
