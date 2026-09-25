import unittest

from swarmshield.allocator import allocate_swarmshield, intercept_solution, threat_risk
from swarmshield.models import Asset, Interceptor, Threat, Vec2
from swarmshield.scenario import build_hackathon_scenario


class AllocatorTests(unittest.TestCase):
    def test_run_down_intercept_is_feasible(self):
        interceptor = Interceptor("I", Vec2(0, 1000), 200, 10000, 1, 1, "light", 500)
        threat = Threat("T", Vec2(0, 0), Vec2(0, -100), .9, "A", 400)
        solution = intercept_solution(interceptor, threat)
        self.assertIsNotNone(solution)
        self.assertAlmostEqual(solution[0], 10, places=4)

    def test_risk_rewards_consequence(self):
        threat = Threat("T", Vec2(0, 1000), Vec2(0, -100), .9, "A", 400)
        low = Asset("A", "low", Vec2(0, 0), 10, "low")
        high = Asset("A", "high", Vec2(0, 0), 100, "critical")
        self.assertGreater(threat_risk(threat, high), threat_risk(threat, low) * 9)

    def test_off_course_track_has_zero_asset_risk(self):
        asset = Asset("A", "asset", Vec2(0, 0), 100, "critical")
        away = Threat("T", Vec2(0, 1000), Vec2(0, 100), .9, "A", 400)
        self.assertEqual(threat_risk(away, asset), 0)

    def test_explicit_leakage_when_threats_exceed_rounds(self):
        scenario = build_hackathon_scenario()
        assignments, _ = allocate_swarmshield(scenario.interceptors, scenario.threats, scenario.asset_map())
        self.assertLessEqual(len(assignments), 12)
        self.assertGreaterEqual(20 - len(set(assignments.values())), 8)

    def test_high_risk_track_receives_round(self):
        scenario = build_hackathon_scenario()
        assignments, _ = allocate_swarmshield(scenario.interceptors, scenario.threats, scenario.asset_map())
        selected = set(assignments.values())
        risks = {t.id: threat_risk(t, scenario.asset_map()[t.asset_id]) for t in scenario.threats}
        highest = max(risks, key=risks.get)
        self.assertIn(highest, selected)


if __name__ == "__main__":
    unittest.main()
