"""Render an existing SwarmShield version-1.0 recording; no simulation logic lives here."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA = "1.0"
TRAIL_SECONDS = 20.0


class DemoDataError(ValueError):
    pass


def _run(recording: dict[str, Any]) -> dict[str, Any]:
    try:
        run = recording["runs"]["swarmshield"]
    except (KeyError, TypeError) as exc:
        raise DemoDataError("run does not contain a SwarmShield recording") from exc
    if not isinstance(run, dict):
        raise DemoDataError("SwarmShield run must be an object")
    return run


def load_recording(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise DemoDataError(f"input file does not exist: {source}")
    try:
        recording = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoDataError(f"input is not valid JSON: {exc}") from exc
    if not isinstance(recording, dict) or recording.get("schema_version") != SUPPORTED_SCHEMA:
        found = recording.get("schema_version") if isinstance(recording, dict) else None
        raise DemoDataError(f"unsupported run schema version: {found!r}; expected {SUPPORTED_SCHEMA!r}")
    assets = recording.get("scenario", {}).get("assets")
    if not isinstance(assets, list) or not assets:
        raise DemoDataError("run does not contain protected asset definitions")
    trajectories = _run(recording).get("trajectories")
    if not isinstance(trajectories, list) or not trajectories:
        raise DemoDataError("run does not contain trajectory frames")
    threats = []
    for row in trajectories:
        if not isinstance(row, dict) or not isinstance(row.get("t"), (int, float)) or not math.isfinite(row["t"]):
            raise DemoDataError("trajectory timestamps must be finite numbers")
        if row.get("kind") == "threat":
            threats.append(row)
            probabilities = row.get("belief", {}).get("destination_probabilities")
            if not isinstance(probabilities, dict) or not probabilities:
                raise DemoDataError("run does not contain destination belief data; generate an uncertainty-aware SwarmShield run first")
    if not threats:
        raise DemoDataError("run does not contain threat trajectory frames")
    return recording


def available_threats(recording: dict[str, Any]) -> list[str]:
    return sorted({row["id"] for row in _run(recording)["trajectories"]
                   if row.get("kind") == "threat" and row.get("belief")})


def select_focus_threat(recording: dict[str, Any], requested: str | None = None) -> str:
    threats = available_threats(recording)
    if requested:
        if requested not in threats:
            raise DemoDataError(f"requested threat {requested!r} was not found; available: {', '.join(threats)}")
        return requested
    kinds = {threat_id: set() for threat_id in threats}
    for event in _run(recording).get("events", []):
        if event.get("threat_id") in kinds:
            kinds[event["threat_id"]].add(event.get("type"))

    def priority(threat_id: str):
        values = kinds[threat_id]
        rank = (0 if {"hold", "commit", "retask"} <= values else
                1 if {"hold", "commit"} <= values else
                2 if values & {"commit", "retask"} else 3)
        return rank, threat_id
    if not threats:
        raise DemoDataError("run has no threats with valid belief data")
    return min(threats, key=priority)


def build_frame_index(run: dict[str, Any]) -> dict[str, Any]:
    frames: dict[float, dict[str, dict[str, Any]]] = {}
    for row in run.get("trajectories", []):
        frames.setdefault(float(row["t"]), {})[row["id"]] = row
    return {"times": sorted(frames), "frames": frames}


def frame_at(index: dict[str, Any], time_s: float) -> dict[str, dict[str, Any]]:
    if not index["times"]:
        raise DemoDataError("run does not contain trajectory frames")
    selected = min(index["times"], key=lambda value: (abs(value - time_s), value))
    return index["frames"][selected]


def probability_rows(frame: dict[str, Any], assets: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    probabilities = frame["belief"]["destination_probabilities"]
    names = {asset["id"]: asset.get("name", asset["id"]) for asset in assets}
    return sorted(((key, names.get(key, key), float(value)) for key, value in probabilities.items()),
                  key=lambda row: (-row[2], row[0]))


def events_at(run: dict[str, Any], time_s: float) -> list[dict[str, Any]]:
    return [event for event in run.get("events", [])
            if isinstance(event.get("time_s"), (int, float)) and math.isclose(float(event["time_s"]), time_s)]


def focus_view(run: dict[str, Any], frame: dict[str, Any], time_s: float) -> dict[str, Any]:
    """Overlay only same-timestamp recorded decision evidence on a copied frame."""
    viewed = dict(frame)
    transitions = [event for event in events_at(run, time_s)
                   if event.get("threat_id") == frame.get("id")
                   and event.get("type") in {"commit", "retask"}]
    if transitions:
        event = transitions[-1]
        viewed["decision"] = "COMMIT" if event["type"] == "commit" else "RETASK"
        viewed["assignment"] = event.get("interceptor_id")
        if isinstance(event.get("evidence"), dict):
            viewed["belief"] = dict(event["evidence"])
    return viewed


def _decision(run, threat_id, time_s, frame):
    transitions = [(index, event) for index, event in enumerate(run.get("events", []))
                   if event.get("threat_id") == threat_id
                   and event.get("type") in {"hold", "commit", "retask"}
                   and float(event.get("time_s", math.inf)) <= time_s]
    if transitions:
        _, event = max(transitions, key=lambda item: (float(item[1]["time_s"]), item[0]))
        if event["type"] == "retask":
            return f"RETASK {event.get('interceptor_id', 'NONE')} -> {threat_id}"
        if event["type"] == "commit":
            return f"COMMIT {event.get('interceptor_id', 'NONE')} -> {threat_id}"
    return "HOLD / PRESERVE" if frame.get("decision") == "HOLD" else str(frame.get("decision", "UNKNOWN"))


def _load_matplotlib():
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
    except ImportError as exc:
        raise DemoDataError("Matplotlib is required for the standalone 3D demo.\nInstall it with:\n    pip install matplotlib") from exc
    return plt, FuncAnimation


class UspDemo3D:
    def __init__(self, recording, threat_id, interval_ms=120):
        self.recording, self.run = recording, _run(recording)
        self.assets = recording["scenario"]["assets"]
        self.assets_by_id = {item["id"]: item for item in self.assets}
        self.threat_id, self.index = threat_id, build_frame_index(self.run)
        self.times, self.position, self.playing = self.index["times"], 0, True
        self.interval_ms = interval_ms
        self.plt, self.FuncAnimation = _load_matplotlib()
        self.figure = self.plt.figure(figsize=(14, 8), facecolor="#07110f")
        self.axis = self.figure.add_axes((.04, .08, .68, .84), projection="3d")
        self.panel = self.figure.text(.75, .92, "", va="top", family="monospace", color="#dff7eb", fontsize=10)
        self.banner = self.figure.text(.38, .96, "", ha="center", color="#ffbd59", weight="bold")
        self.figure.canvas.mpl_connect("key_press_event", self._on_key)
        self.animation = None

    def _trail(self, entity_id, time_s):
        return [self.index["frames"][stamp][entity_id] for stamp in self.times
                if time_s - TRAIL_SECONDS <= stamp <= time_s and entity_id in self.index["frames"][stamp]]

    def _setup_axis(self):
        self.axis.set_facecolor("#091713")
        self.axis.set(xlabel="X (m)", ylabel="Y (m)", zlabel="Altitude Z (m)")
        self.axis.view_init(elev=28, azim=-58)

    def _draw(self, frame, time_s):
        for asset in self.assets:
            x, y = asset["position"]["x"], asset["position"]["y"]
            self.axis.scatter(x, y, 0, marker="s", s=80, color="#60d394")
            self.axis.text(x, y, 0, f"{asset['name']}\nC={asset['consequence']}", color="#dff7eb", fontsize=7)
        for row in frame.values():
            focus = row["id"] == self.threat_id
            if row["kind"] == "threat":
                color, marker, size = ("#ffbd59" if focus else "#ff6678"), "^", (85 if focus else 28)
            else:
                color, marker, size = ("#59645f" if row.get("state") == "failed" else "#9df5bf"), "o", 38
            self.axis.scatter(row["x"], row["y"], row["z"], color=color, marker=marker, s=size)
            if focus or row["kind"] == "interceptor":
                self.axis.text(row["x"], row["y"], row["z"], row["id"], color=color, fontsize=7)
            trail = self._trail(row["id"], time_s)
            if len(trail) > 1:
                self.axis.plot([p["x"] for p in trail], [p["y"] for p in trail], [p["z"] for p in trail],
                               color=color, alpha=.7 if focus else .22, linewidth=2 if focus else .7)
        focus = frame[self.threat_id]
        assigned = focus.get("assignment")
        if assigned and assigned in frame:
            item = frame[assigned]
            self.axis.plot([focus["x"], item["x"]], [focus["y"], item["y"]], [focus["z"], item["z"]],
                           color="#9df5bf", linestyle="--", linewidth=1.8)
        for asset_id, _, probability in probability_rows(focus, self.assets):
            asset = self.assets_by_id.get(asset_id)
            if asset:
                self.axis.plot([focus["x"], asset["position"]["x"]], [focus["y"], asset["position"]["y"]],
                               [focus["z"], 0], color="#73b8ff", alpha=.08 + .82 * probability,
                               linewidth=.4 + 5 * probability)

    def _panel_text(self, focus, time_s):
        belief = focus["belief"]
        probabilities = "\n".join(f"  {name[:20]:20} {p:6.1%}" for _, name, p in probability_rows(focus, self.assets))
        top = self.assets_by_id.get(belief["top_destination_id"], {}).get("name", belief["top_destination_id"])
        return (f"TIME\nT+{time_s:05.1f} s\n\nTHREAT\n{self.threat_id}\n\nDESTINATION BELIEF\n{probabilities}\n\n"
                f"TOP DESTINATION\n{top}  {belief['top_probability']:.1%}\n\nUNCERTAINTY\n"
                f"{str(belief['uncertainty_label']).upper()}  {belief['uncertainty']:.3f}\n\n"
                f"EXPECTED CONSEQUENCE\n{belief['expected_consequence']:.1f}\n\nURGENCY\n{belief['urgency']:.3f}\n\n"
                f"RISK\n{belief['risk']:.1f}\n\nDECISION\n{_decision(self.run, self.threat_id, time_s, focus)}\n\n"
                f"ASSIGNED RESOURCE\n{focus.get('assignment') or 'NONE'}\n\nSPACE pause  LEFT/RIGHT step  R restart")

    def render(self, position):
        self.position = max(0, min(position, len(self.times) - 1))
        time_s, frame = self.times[self.position], self.index["frames"][self.times[self.position]]
        display_frame = dict(frame)
        display_frame[self.threat_id] = focus_view(self.run, frame[self.threat_id], time_s)
        for event in events_at(self.run, time_s):
            if event.get("type") == "interceptor_failure" and event.get("interceptor_id") in display_frame:
                failed_id = event["interceptor_id"]
                display_frame[failed_id] = {**display_frame[failed_id], "state": "failed"}
        self.axis.clear(); self._setup_axis(); self._draw(display_frame, time_s)
        self.axis.set_title(f"Recorded SwarmShield run — focus {self.threat_id}", color="#dff7eb")
        self.panel.set_text(self._panel_text(display_frame[self.threat_id], time_s))
        important = [event for event in events_at(self.run, time_s) if event.get("type") in
                     {"threat_diversion", "commit", "interceptor_failure", "retask", "failure_recovery", "ground_link_loss"}
                     and (event.get("threat_id") in {None, self.threat_id}
                          or event.get("type") in {"interceptor_failure", "ground_link_loss"})]
        self.banner.set_text("  |  ".join(str(event.get("label", event["type"])).upper() for event in important))
        return self.axis, self.panel, self.banner

    def _tick(self, _):
        if self.playing:
            self.position = (self.position + 1) % len(self.times)
        return self.render(self.position)

    def _on_key(self, event):
        if event.key == " ": self.playing = not self.playing
        elif event.key == "left": self.playing = False; self.render(self.position - 1)
        elif event.key == "right": self.playing = False; self.render(self.position + 1)
        elif str(event.key).lower() == "r": self.position = 0; self.render(0)
        self.figure.canvas.draw_idle()

    def show(self):
        self.render(0)
        self.animation = self.FuncAnimation(self.figure, self._tick, interval=self.interval_ms,
                                            blit=False, cache_frame_data=False)
        self.plt.show()


def build_parser():
    parser = argparse.ArgumentParser(description="Visualize a recorded SwarmShield USP run in 3D")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--threat")
    parser.add_argument("--interval-ms", type=int, default=120)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        recording = load_recording(args.input)
        UspDemo3D(recording, select_focus_threat(recording, args.threat), max(20, args.interval_ms)).show()
    except DemoDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
