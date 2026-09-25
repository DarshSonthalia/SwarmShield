import unittest

from swarmshield.allocator import time_to_asset
from swarmshield.models import Asset, Interceptor, Scenario, Threat, Vec2
from swarmshield.scenario import build_scenario, scenario_from_dict, scenario_to_dict
from swarmshield.simulator import run_scenario
from swarmshield.webapp import generate_payload


class DynamicModelTests(unittest.TestCase):
    def test_confidence_revision_changes_live_priority_and_assignment(self):
        scenario = Scenario(
            "Revised track", 30, 1,
            [Asset("A", "Civic zone", Vec2(0, -10000), 100, "critical")],
            [Threat("T1", Vec2(0, 0), Vec2(0, -100), .72, "A", 400),
             Threat("T2", Vec2(200, 0), Vec2(0, -100), .08, "A", 400)],
            [Interceptor("I1", Vec2(100, 5000), 220, 30000, 1, 1, "light", 450)],
            [{"time_s": 5, "type": "confidence_update", "threat_id": "T2",
              "new_confidence": .99, "label": "T2 assessment revised"}],
        )
        run = run_scenario(scenario, "swarmshield")
        self.assertEqual(run["allocations"][0]["assignments"], {"I1": "T1"})
        at_five = next(item for item in run["allocations"] if item["time_s"] == 5)
        self.assertEqual(at_five["assignments"], {"I1": "T2"})
        self.assertTrue(any(item["type"] == "reassignment" for item in run["events"]))
        before = {item["id"]: item["risk"] for item in run["trajectories"] if item["t"] == 4 and item["kind"] == "threat"}
        after = {item["id"]: item["risk"] for item in run["trajectories"] if item["t"] == 5 and item["kind"] == "threat"}
        self.assertLess(before["T2"], before["T1"])
        self.assertGreater(after["T2"], after["T1"])

    def test_protected_zone_footprint_affects_projection(self):
        track = Threat("T", Vec2(500, 1000), Vec2(0, -100), .9, "A", 400)
        small = Asset("A", "Small", Vec2(0, 0), 100, "critical", 300)
        large = Asset("A", "Large", Vec2(0, 0), 100, "critical", 600)
        self.assertEqual(time_to_asset(track, small), float("inf"))
        self.assertAlmostEqual(time_to_asset(track, large), 6.6833752, places=5)

    def test_peer_partition_exposes_duplicate_claims(self):
        scenario = Scenario(
            "Partition", 30, 1,
            [Asset("A", "Civic zone", Vec2(0, -10000), 100, "critical")],
            [Threat("T", Vec2(0, 0), Vec2(0, -100), .95, "A", 400)],
            [Interceptor("I1", Vec2(-2000, 3000), 250, 30000, 1, 1, "light", 450),
             Interceptor("I2", Vec2(2000, 3000), 250, 30000, 1, 1, "light", 450)],
            [{"time_s": 0, "type": "ground_link_loss", "label": "Link lost"}],
            p2p_radius_m=1000,
            peer_visibility_m=10000,
        )
        run = run_scenario(scenario, "swarmshield")
        self.assertGreaterEqual(run["metrics"]["max_peer_groups"], 2)
        self.assertTrue(any(item["type"] == "peer_conflict" for item in run["events"]))

    def test_profiles_seed_and_custom_events(self):
        mixed = build_scenario(60, 12, seed=17, profile="mixed")
        concentrated = build_scenario(60, 12, seed=17, profile="concentrated")
        self.assertNotEqual([t.asset_id for t in mixed.threats], [t.asset_id for t in concentrated.threats])
        self.assertEqual(scenario_to_dict(mixed), scenario_to_dict(build_scenario(60, 12, seed=17, profile="mixed")))
        restored = scenario_from_dict(scenario_to_dict(mixed))
        self.assertEqual(restored.seed, 17)
        self.assertEqual(len(restored.events), len(mixed.events))
        payload = generate_payload(7, 3, seed=17, duration_s=60, profile="uncertain")
        self.assertEqual(payload["scenario"]["seed"], 17)
        self.assertEqual(payload["scenario"]["profile"], "uncertain")

    def test_asset_consequence_revision_and_link_restoration(self):
        scenario = Scenario(
            "Changing city", 30, 1,
            [Asset("A", "Transit zone", Vec2(0, -10000), 10, "important")],
            [Threat("T", Vec2(0, 10000), Vec2(0, -100), .8, "A", 400)],
            [],
            [{"time_s": 5, "type": "asset_consequence_change", "asset_id": "A",
              "new_consequence": 100, "label": "Crowd arrives"},
             {"time_s": 8, "type": "ground_link_loss", "label": "Loss"},
             {"time_s": 12, "type": "ground_link_restore", "label": "Restored"}],
        )
        run = run_scenario(scenario, "swarmshield")
        risk = {item["t"]: item["risk"] for item in run["trajectories"] if item["kind"] == "threat"}
        self.assertGreater(risk[5], risk[4] * 5)
        self.assertTrue(run["metrics"]["ground_link_loss_exercised"])
        self.assertFalse(run["metrics"]["peer_coordination_active_at_end"])

    def test_track_starting_inside_zone_is_counted_as_leak(self):
        scenario = Scenario(
            "Already inside", 30, 1,
            [Asset("A", "Transit zone", Vec2(0, 0), 80, "critical", 500)],
            [Threat("T", Vec2(0, 0), Vec2(0, 100), .8, "A", 400)],
            [],
        )
        run = run_scenario(scenario, "swarmshield")
        self.assertEqual(run["metrics"]["actual_leakage"], 1)
        self.assertEqual(run["events"][0]["time_s"], 0)

    def test_invalid_event_reference_is_rejected(self):
        raw = scenario_to_dict(build_scenario(3, 1, duration_s=30, enable_events=False))
        raw["events"] = [{"type": "confidence_update", "time_s": 5,
                          "threat_id": "missing", "new_confidence": .9}]
        with self.assertRaises(ValueError):
            scenario_from_dict(raw)


if __name__ == "__main__":
    unittest.main()
