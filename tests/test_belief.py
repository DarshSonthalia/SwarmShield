import math
import unittest
from dataclasses import fields, replace

from swarmshield.models import Asset, ObservedThreat, ThreatBelief, TrackObservation, Vec2
from swarmshield.belief import (
    MAX_UNCERTAINTY_FRICTION,
    build_threat_belief,
    uncertainty_friction,
)


class BeliefModelTests(unittest.TestCase):
    def test_observed_threat_cannot_carry_ground_truth_destination(self):
        self.assertNotIn("asset_id", {field.name for field in fields(ObservedThreat)})
        observed = ObservedThreat("T1", 4.0, Vec2(1, 2), Vec2(3, 4), 0.8, "active", 500)
        self.assertEqual(observed.id, "T1")

    def test_belief_serializes_operational_evidence(self):
        belief = ThreatBelief("T1", 4.0, {"A": .75, "B": .25}, {"A": 10, "B": 30},
                              "A", .75, 70, .51, "medium", .8, 10, 50.4)
        self.assertEqual(belief.to_dict()["top_destination_id"], "A")
        self.assertNotIn("asset_id", belief.to_dict())

    def test_probabilities_normalize_and_favor_aligned_asset(self):
        assets = {
            "A": Asset("A", "ahead", Vec2(0, 0), 90, "critical"),
            "B": Asset("B", "side", Vec2(4000, 4000), 20, "low"),
        }
        observed = ObservedThreat("T", 0, Vec2(0, 4000), Vec2(0, -100), .9, "active", 500)
        belief = build_threat_belief(observed, [TrackObservation(0, observed.position, observed.velocity)], assets)
        self.assertAlmostEqual(sum(belief.destination_probabilities.values()), 1)
        self.assertEqual(belief.top_destination_id, "A")
        self.assertTrue(math.isclose(belief.risk, .9 * belief.expected_consequence * belief.urgency))

    def test_stationary_track_falls_back_to_uniform_probabilities(self):
        assets = {
            "A": Asset("A", "one", Vec2(0, -100), 90, "critical"),
            "B": Asset("B", "two", Vec2(100, 0), 20, "low"),
        }
        observed = ObservedThreat("T", 0, Vec2(0, 0), Vec2(0, 0), .8, "active", 100)
        belief = build_threat_belief(observed, [], assets)
        self.assertEqual(set(belief.destination_probabilities.values()), {.5})

    def test_horizon_is_earliest_materially_plausible_arrival(self):
        assets = {
            "A": Asset("A", "near", Vec2(0, 1000), 90, "critical"),
            "B": Asset("B", "far", Vec2(0, 2000), 20, "low"),
        }
        observed = ObservedThreat("T", 0, Vec2(0, 0), Vec2(0, 100), .8, "active", 100)
        belief = build_threat_belief(observed, [], assets)
        self.assertEqual(belief.feasible_horizon_s, 10)

    def test_uncertainty_friction_is_bounded_and_fades_with_urgency(self):
        base = ThreatBelief("T", 0, {"A": .5, "B": .5}, {"A": 10, "B": 20},
                            "A", .5, 50, 1, "high", .1, 10, 5)
        urgent = replace(base, urgency=.9)
        self.assertLessEqual(uncertainty_friction(base), MAX_UNCERTAINTY_FRICTION)
        self.assertLess(uncertainty_friction(urgent), uncertainty_friction(base))


if __name__ == "__main__":
    unittest.main()
