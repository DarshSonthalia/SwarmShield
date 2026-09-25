import inspect
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from demo.demo_usp_3d import (
    DemoDataError, available_threats, build_frame_index, events_at,
    focus_view, frame_at, load_recording, probability_rows, select_focus_threat,
)
from run import build_selected_scenario


def recording():
    assets = [
        {"id": "A1", "name": "Alpha", "position": {"x": 0, "y": 0}, "consequence": 100},
        {"id": "A2", "name": "Beta", "position": {"x": 10, "y": 0}, "consequence": 20},
    ]
    belief = {"destination_probabilities": {"A1": .7, "A2": .3},
              "top_destination_id": "A1", "top_probability": .7,
              "expected_consequence": 76, "uncertainty": .4,
              "uncertainty_label": "medium", "urgency": .8, "risk": 54}
    rows = [
        {"t": 0, "kind": "threat", "id": "T1", "x": 1, "y": 2, "z": 3,
         "state": "active", "assignment": None, "belief": belief, "decision": "HOLD"},
        {"t": 0, "kind": "interceptor", "id": "I1", "x": 1, "y": 8, "z": 4,
         "state": "engaging", "assignment": None},
        {"t": 1, "kind": "threat", "id": "T1", "x": 1, "y": 1, "z": 3,
         "state": "active", "assignment": "I1", "belief": belief, "decision": "COMMIT"},
        {"t": 1, "kind": "interceptor", "id": "I1", "x": 1, "y": 7, "z": 4,
         "state": "engaging", "assignment": "T1"},
    ]
    events = [
        {"time_s": 0, "type": "hold", "threat_id": "T1", "label": "T1 HOLD"},
        {"time_s": 1, "type": "commit", "threat_id": "T1", "interceptor_id": "I1", "label": "I1 COMMIT T1"},
        {"time_s": 2, "type": "retask", "threat_id": "T1", "interceptor_id": "I2", "label": "I2 RETASK T1"},
    ]
    return {"schema_version": "1.0", "scenario": {"assets": assets},
            "runs": {"swarmshield": {"trajectories": rows, "events": events, "allocations": []}}}


class DemoHelpersTests(unittest.TestCase):
    def write_recording(self, value):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            json.dump(value, handle)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_loads_valid_recording_without_matplotlib(self):
        before = set(sys.modules)
        value = load_recording(self.write_recording(recording()))
        self.assertEqual(value["schema_version"], "1.0")
        self.assertFalse(any(name.startswith("matplotlib") for name in set(sys.modules) - before))

    def test_rejects_missing_file_and_bad_schema(self):
        with self.assertRaisesRegex(DemoDataError, "does not exist"):
            load_recording(Path("missing-run.json"))
        for value in ({}, {"schema_version": "2.0"},
                      {"schema_version": "1.0", "scenario": {"assets": []},
                       "runs": {"swarmshield": {"trajectories": [], "events": []}}}):
            with self.subTest(value=value), self.assertRaises(DemoDataError):
                load_recording(self.write_recording(value))

    def test_rejects_missing_belief_data(self):
        value = recording()
        del value["runs"]["swarmshield"]["trajectories"][0]["belief"]
        with self.assertRaisesRegex(DemoDataError, "destination belief"):
            load_recording(self.write_recording(value))

    def test_selects_requested_or_deterministic_best_sequence(self):
        value = recording()
        self.assertEqual(select_focus_threat(value, "T1"), "T1")
        self.assertEqual(select_focus_threat(value), "T1")
        with self.assertRaisesRegex(DemoDataError, "not found"):
            select_focus_threat(value, "T9")
        self.assertEqual(available_threats(value), ["T1"])

    def test_auto_selection_priority_is_deterministic(self):
        value = recording()
        template = value["runs"]["swarmshield"]["trajectories"][0]
        for threat_id in ("T3", "T2"):
            extra = dict(template)
            extra["id"] = threat_id
            value["runs"]["swarmshield"]["trajectories"].append(extra)
        value["runs"]["swarmshield"]["events"].extend([
            {"time_s": 0, "type": "hold", "threat_id": "T2"},
            {"time_s": 1, "type": "commit", "threat_id": "T2"},
            {"time_s": 0, "type": "commit", "threat_id": "T3"},
        ])
        self.assertEqual(select_focus_threat(value), "T1")

    def test_frame_lookup_probability_sorting_and_recorded_events(self):
        run = recording()["runs"]["swarmshield"]
        index = build_frame_index(run)
        self.assertEqual(frame_at(index, .8)["T1"]["t"], 1)
        rows = probability_rows(frame_at(index, 0)["T1"], recording()["scenario"]["assets"])
        self.assertEqual([row[0] for row in rows], ["A1", "A2"])
        self.assertEqual(events_at(run, 1)[0]["type"], "commit")

    def test_probability_extraction_does_not_read_ground_truth(self):
        import demo.demo_usp_3d as module
        self.assertNotIn("asset_id", inspect.getsource(module.probability_rows))

    def test_focus_view_applies_same_timestamp_recorded_transition_without_mutation(self):
        value = recording()
        frame = build_frame_index(value["runs"]["swarmshield"])["frames"][1.0]["T1"]
        original = json.loads(json.dumps(frame))
        viewed = focus_view(value["runs"]["swarmshield"], frame, 1.0)
        self.assertEqual(viewed["assignment"], "I1")
        self.assertEqual(viewed["decision"], "COMMIT")
        self.assertEqual(frame, original)

    def test_usp_demo_flag_only_selects_reproducible_scenario(self):
        args = Namespace(usp_demo=True, seed=42, threats=3, interceptors=2,
                         duration=30, no_events=True)
        scenario = build_selected_scenario(args)
        self.assertEqual((len(scenario.threats), len(scenario.interceptors), scenario.duration_s), (20, 12, 190))
        self.assertTrue(any(event.get("threat_id") == "T05" for event in scenario.events))

        args.usp_demo = False
        scenario = build_selected_scenario(args)
        self.assertEqual((len(scenario.threats), len(scenario.interceptors), scenario.duration_s), (3, 2, 30))


if __name__ == "__main__":
    unittest.main()
