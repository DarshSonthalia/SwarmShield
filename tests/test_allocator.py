import inspect
import unittest

import swarmshield.allocator
from swarmshield.allocator import allocate_baseline, allocate_swarmshield, intercept_solution, score_pair
from swarmshield.models import Interceptor, ObservedThreat, ThreatBelief, Vec2


def observed():
    return ObservedThreat("T", 0, Vec2(0, 0), Vec2(0, -100), .9, "active", 400)


def interceptor():
    return Interceptor("I", Vec2(0, 1000), 200, 10000, 1, 1, "light", 500)


def belief(**changes):
    values = dict(threat_id="T", time_s=0, destination_probabilities={"A": 1},
                  approach_times_s={"A": 30}, top_destination_id="A", top_probability=1,
                  expected_consequence=80, uncertainty=0, uncertainty_label="low",
                  urgency=.8, feasible_horizon_s=30, risk=57.6)
    values.update(changes)
    return ThreatBelief(**values)


class AllocatorTests(unittest.TestCase):
    def test_run_down_intercept_is_feasible(self):
        solution = intercept_solution(interceptor(), observed())
        self.assertIsNotNone(solution)
        self.assertAlmostEqual(solution[0], 10, places=4)

    def test_pair_feasibility_uses_belief_horizon(self):
        score = score_pair(interceptor(), observed(), belief(feasible_horizon_s=25))
        self.assertTrue(score.feasible)
        self.assertLess(score.intercept_time_s, 25)

    def test_uncertainty_can_hold_early_but_not_when_urgent(self):
        early = belief(risk=10, uncertainty=1, urgency=.05)
        urgent = belief(risk=80, uncertainty=1, urgency=.95)
        self.assertEqual(allocate_swarmshield([interceptor()], [observed()], {"T": early})[0], {})
        self.assertEqual(allocate_swarmshield([interceptor()], [observed()], {"T": urgent})[0], {"I": "T"})

    def test_baseline_uses_same_observation_and_horizon(self):
        self.assertEqual(allocate_baseline([interceptor()], [observed()], {"T": belief()}), {"I": "T"})

    def test_allocator_source_has_no_asset_id_read(self):
        self.assertNotIn(".asset_id", inspect.getsource(swarmshield.allocator))


if __name__ == "__main__":
    unittest.main()
