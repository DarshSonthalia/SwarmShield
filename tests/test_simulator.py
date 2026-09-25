import json
import inspect
import unittest

from swarmshield.scenario import build_hackathon_scenario
from swarmshield import simulator
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

    def test_operational_snapshots_expose_belief_not_truth(self):
        rows = [row for row in self.result["runs"]["swarmshield"]["trajectories"]
                if row["kind"] == "threat"]
        self.assertTrue(all("asset_id" not in row for row in rows))
        self.assertTrue(all("belief" in row and "decision" in row for row in rows))

    def test_prediction_metrics_use_first_commit(self):
        evaluation = self.result["runs"]["swarmshield"]["metrics"]["prediction_evaluation"]
        self.assertEqual(evaluation["committed_count"] + evaluation["uncommitted_count"], 20)
        if evaluation["committed_count"]:
            self.assertGreaterEqual(evaluation["top_destination_accuracy"], 0)
            self.assertLessEqual(evaluation["brier_score"], 2)

    def test_decision_events_are_sparse_and_evidenced(self):
        events = self.result["runs"]["swarmshield"]["events"]
        decisions = [event for event in events if event["type"] in {"hold", "commit", "retask"}]
        keys = [(event["time_s"], event["type"], event["threat_id"]) for event in decisions]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all("evidence" in event for event in decisions))

    def test_decision_helpers_do_not_read_destination_truth(self):
        source = inspect.getsource(simulator._update_beliefs) + inspect.getsource(simulator._swarm_assign)
        self.assertNotIn("asset_id", source)

    def test_t05_demonstrates_hold_commit_and_failure_recovery(self):
        events = self.result["runs"]["swarmshield"]["events"]
        t05 = [event for event in events if event.get("threat_id") == "T05"]
        sequence = [event["type"] for event in t05]
        self.assertIn("hold", sequence)
        self.assertIn("commit", sequence)
        self.assertTrue(any(kind in sequence for kind in ("retask", "failure_recovery")))
        self.assertLess(sequence.index("hold"), sequence.index("commit"))


if __name__ == "__main__":
    unittest.main()
