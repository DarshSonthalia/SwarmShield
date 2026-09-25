from __future__ import annotations

import copy
import math
import random
from typing import Any

from .models import Asset, Interceptor, Scenario, Threat, Vec2


def _velocity_toward(start: Vec2, end: Vec2, speed: float) -> Vec2:
    dx, dy = end.x - start.x, end.y - start.y
    norm = math.hypot(dx, dy) or 1.0
    return Vec2(speed * dx / norm, speed * dy / norm)


def build_scenario(
    threat_count: int = 20,
    interceptor_count: int = 12,
    seed: int = 42,
    duration_s: int = 190,
    enable_events: bool = True,
) -> Scenario:
    """Generate an arbitrary, deterministic scarcity scenario.

    The counts are true model inputs rather than display parameters. Distances
    are metres and time is seconds. Interceptors start north of the inbound
    raid, allowing a same-direction, run-down-from-behind engagement.
    """
    if not 1 <= threat_count <= 200:
        raise ValueError("threat_count must be between 1 and 200")
    if not 0 <= interceptor_count <= 120:
        raise ValueError("interceptor_count must be between 0 and 120")
    if not 30 <= duration_s <= 600:
        raise ValueError("duration_s must be between 30 and 600")
    rng = random.Random(seed)
    assets = [
        Asset("A01", "Command Centre", Vec2(0, -5200), 100, "critical"),
        Asset("A02", "Airbase", Vec2(-6200, -4300), 90, "critical"),
        Asset("A03", "Power Substation", Vec2(4600, -4700), 76, "critical"),
        Asset("A04", "Industrial Zone", Vec2(7600, -3600), 42, "important"),
        Asset("A05", "Open Water", Vec2(-9800, -1500), 6, "low-consequence"),
    ]
    assets_by_id = {asset.id: asset for asset in assets}

    # Deliberately mixed confidence and consequence. T05 begins as a likely
    # decoy bound for open water, then diverts toward A01 during the run.
    asset_pattern = [
        "A01", "A02", "A03", "A01", "A05", "A04", "A02", "A05", "A03", "A04",
        "A05", "A01", "A02", "A04", "A03", "A05", "A04", "A01", "A05", "A02",
    ]
    confidence_pattern = [
        0.97, 0.93, 0.91, 0.88, 0.26, 0.76, 0.89, 0.31, 0.84, 0.70,
        0.18, 0.95, 0.81, 0.62, 0.86, 0.22, 0.67, 0.92, 0.35, 0.79,
    ]
    threats: list[Threat] = []
    row_width = min(24, threat_count)
    for idx in range(threat_count):
        column = idx % row_width
        row = idx // row_width
        fraction = 0.5 if row_width == 1 else column / (row_width - 1)
        x = -10600 + fraction * 21200 + rng.uniform(-180, 180)
        y = 13600 + row * 620 + (idx % 4) * 240 + rng.uniform(-90, 90)
        start = Vec2(x, y)
        speed = 118 + (idx % 5) * 7 + rng.uniform(-2, 2)
        asset_id = asset_pattern[idx % len(asset_pattern)]
        velocity = _velocity_toward(start, assets_by_id[asset_id].position, speed)
        threats.append(
            Threat(
                id=f"T{idx + 1:02d}",
                position=start,
                velocity=velocity,
                p_hostile=max(0.05, min(0.99, confidence_pattern[idx % len(confidence_pattern)] + rng.uniform(-0.025, 0.025))),
                asset_id=asset_id,
                altitude_m=420 + (idx % 5) * 75,
            )
        )

    interceptors: list[Interceptor] = []
    interceptor_row_width = min(20, max(1, interceptor_count))
    for idx in range(interceptor_count):
        # Loose patrol cells trail the inbound swarm from the north.
        group = idx % 3
        column = idx % interceptor_row_width
        row = idx // interceptor_row_width
        fraction = 0.5 if interceptor_row_width == 1 else column / (interceptor_row_width - 1)
        x = -9800 + fraction * 19600
        y = 18100 + row * 620 + (idx % 2) * 280
        fast = idx in {1, 4, 7, 10}
        interceptors.append(
            Interceptor(
                id=f"I{idx + 1:02d}",
                position=Vec2(x, y),
                max_speed_mps=225 if fast else 195,
                range_m=26000 if fast else 30000,
                battery=0.78 + (idx % 4) * 0.055,
                cost=3.0 if fast else 1.0,
                kind="fast" if fast else "light",
                altitude_m=500 + (idx % 3) * 80,
                base_group=group,
            )
        )

    events = []
    if enable_events and threats:
        diversion_index = min(4, len(threats) - 1)
        events.append({
            "time_s": max(5, round(duration_s * 0.17)),
            "type": "threat_diversion",
            "threat_id": threats[diversion_index].id,
            "new_asset_id": "A01",
            "new_confidence": 0.94,
            "label": f"{threats[diversion_index].id} changes course toward Command Centre",
        })
    if enable_events and interceptors:
        failure_index = min(6, len(interceptors) - 1)
        events.append({
            "time_s": max(8, round(duration_s * 0.10)),
            "type": "interceptor_failure",
            "interceptor_id": interceptors[failure_index].id,
            "label": f"{interceptors[failure_index].id} fails before commitment",
        })
    if enable_events:
        events.append({
            "time_s": max(12, round(duration_s * 0.347)),
            "type": "ground_link_loss",
            "label": "Ground link lost - peer coordination continues",
        })
    events.sort(key=lambda event: event["time_s"])
    return Scenario(
        name=f"Saturation Raid {threat_count} v {interceptor_count}",
        duration_s=duration_s,
        step_s=1.0,
        assets=assets,
        threats=threats,
        interceptors=interceptors,
        events=events,
        safety_radius_m=500.0,
    )


def build_hackathon_scenario(seed: int = 42) -> Scenario:
    """Return the reproducible default judging scenario."""
    scenario = build_scenario(20, 12, seed=seed, duration_s=190, enable_events=True)
    t05 = next(threat for threat in scenario.threats if threat.id == "T05")
    # The initial southbound track lies between A01 and A05. Its later turn is
    # ordinary observed geometry, allowing the belief model to move HOLD to COMMIT.
    t05.position = Vec2(2300.0, 13600.0)
    t05.velocity = Vec2(0.0, -146.0)
    scenario.commitment_distance_m = 700.0
    scenario.events = [event for event in scenario.events
                       if event["type"] not in {"threat_diversion", "interceptor_failure"}]
    scenario.events.extend([
        {"time_s": 32, "type": "threat_diversion", "threat_id": "T05",
         "new_asset_id": "A01", "new_confidence": .94,
         "label": "T05 changes course toward Command Centre"},
        {"time_s": 33, "type": "interceptor_failure", "interceptor_id": "I09",
         "label": "I09 fails after T05 commitment"},
    ])
    scenario.events.sort(key=lambda event: event["time_s"])
    return scenario


def clone_scenario(scenario: Scenario) -> Scenario:
    return copy.deepcopy(scenario)


def _finite_number(value: Any, name: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return number


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    number = _finite_number(value, name, minimum, maximum)
    if not number.is_integer():
        raise ValueError(f"{name} must be a whole number")
    return int(number)


def _positive_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 32:
        raise ValueError(f"{name} must be a nonempty ID of at most 32 characters")
    return value


def _vec(value: Any, name: str) -> Vec2:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain x and y")
    return Vec2(
        _finite_number(value.get("x"), f"{name}.x", -100000, 100000),
        _finite_number(value.get("y"), f"{name}.y", -100000, 100000),
    )


def scenario_from_dict(raw: dict[str, Any]) -> Scenario:
    """Load a user-authored synthetic scenario, rejecting invalid state early."""
    if not isinstance(raw, dict):
        raise ValueError("Scenario must be a JSON object")
    name = raw.get("name", "Custom scenario")
    if not isinstance(name, str) or not name or len(name) > 80:
        raise ValueError("name must be a nonempty string of at most 80 characters")
    duration = _integer(raw.get("duration_s", 190), "duration_s", 30, 600)
    step = _finite_number(raw.get("step_s", 1), "step_s", 1, 1)
    raw_assets = raw.get("assets")
    raw_threats = raw.get("threats")
    raw_interceptors = raw.get("interceptors")
    if not isinstance(raw_assets, list) or not 1 <= len(raw_assets) <= 20:
        raise ValueError("assets must contain 1 to 20 entries")
    if not isinstance(raw_threats, list) or not 1 <= len(raw_threats) <= 200:
        raise ValueError("threats must contain 1 to 200 entries")
    if not isinstance(raw_interceptors, list) or len(raw_interceptors) > 120:
        raise ValueError("interceptors must contain 0 to 120 entries")

    assets: list[Asset] = []
    for idx, item in enumerate(raw_assets):
        if not isinstance(item, dict):
            raise ValueError(f"assets[{idx}] must be an object")
        asset_name = item.get("name")
        if not isinstance(asset_name, str) or not asset_name or len(asset_name) > 80:
            raise ValueError(f"assets[{idx}].name must be a short nonempty string")
        kind = item.get("kind", "important")
        if kind not in {"critical", "important", "low-consequence"}:
            raise ValueError(f"assets[{idx}].kind is invalid")
        assets.append(Asset(
            _positive_id(item.get("id"), f"assets[{idx}].id"),
            asset_name,
            _vec(item.get("position"), f"assets[{idx}].position"),
            _finite_number(item.get("consequence"), f"assets[{idx}].consequence", 0, 1000),
            kind,
        ))
    asset_ids = {asset.id for asset in assets}
    if len(asset_ids) != len(assets):
        raise ValueError("Asset IDs must be unique")

    threats: list[Threat] = []
    for idx, item in enumerate(raw_threats):
        if not isinstance(item, dict):
            raise ValueError(f"threats[{idx}] must be an object")
        asset_id = _positive_id(item.get("asset_id"), f"threats[{idx}].asset_id")
        if asset_id not in asset_ids:
            raise ValueError(f"threats[{idx}].asset_id does not name an asset")
        velocity = _vec(item.get("velocity"), f"threats[{idx}].velocity")
        if math.hypot(velocity.x, velocity.y) < 0.1:
            raise ValueError(f"threats[{idx}].velocity must be nonzero")
        threats.append(Threat(
            _positive_id(item.get("id"), f"threats[{idx}].id"),
            _vec(item.get("position"), f"threats[{idx}].position"),
            velocity,
            _finite_number(item.get("p_hostile"), f"threats[{idx}].p_hostile", 0, 1),
            asset_id,
            _finite_number(item.get("altitude_m", 500), f"threats[{idx}].altitude_m", 0, 20000),
        ))
    threat_ids = {threat.id for threat in threats}
    if len(threat_ids) != len(threats):
        raise ValueError("Threat IDs must be unique")

    interceptors: list[Interceptor] = []
    for idx, item in enumerate(raw_interceptors):
        if not isinstance(item, dict):
            raise ValueError(f"interceptors[{idx}] must be an object")
        kind = item.get("kind", "light")
        if not isinstance(kind, str) or len(kind) > 32:
            raise ValueError(f"interceptors[{idx}].kind must be a short string")
        interceptors.append(Interceptor(
            id=_positive_id(item.get("id"), f"interceptors[{idx}].id"),
            position=_vec(item.get("position"), f"interceptors[{idx}].position"),
            max_speed_mps=_finite_number(item.get("max_speed_mps"), f"interceptors[{idx}].max_speed_mps", 1, 1000),
            range_m=_finite_number(item.get("range_m"), f"interceptors[{idx}].range_m", 1, 200000),
            battery=_finite_number(item.get("battery"), f"interceptors[{idx}].battery", 0, 1),
            cost=_finite_number(item.get("cost"), f"interceptors[{idx}].cost", 0, 1000),
            kind=kind,
            altitude_m=_finite_number(item.get("altitude_m", 500), f"interceptors[{idx}].altitude_m", 0, 20000),
            base_group=_integer(item.get("base_group", 0), f"interceptors[{idx}].base_group", 0, 1000),
        ))
    interceptor_ids = {item.id for item in interceptors}
    if len(interceptor_ids) != len(interceptors):
        raise ValueError("Interceptor IDs must be unique")

    raw_events = raw.get("events", [])
    if not isinstance(raw_events, list) or len(raw_events) > 100:
        raise ValueError("events must be a list of at most 100 entries")
    events: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_events):
        if not isinstance(item, dict):
            raise ValueError(f"events[{idx}] must be an object")
        event_type = item.get("type")
        if event_type not in {"threat_diversion", "interceptor_failure", "ground_link_loss"}:
            raise ValueError(f"events[{idx}].type is invalid")
        event_time = _integer(item.get("time_s"), f"events[{idx}].time_s", 0, duration - 1)
        event = {"type": event_type, "time_s": event_time}
        if event_type == "threat_diversion":
            threat_id = _positive_id(item.get("threat_id"), f"events[{idx}].threat_id")
            new_asset_id = _positive_id(item.get("new_asset_id"), f"events[{idx}].new_asset_id")
            if threat_id not in threat_ids or new_asset_id not in asset_ids:
                raise ValueError(f"events[{idx}] refers to an unknown threat or asset")
            event.update(threat_id=threat_id, new_asset_id=new_asset_id,
                         new_confidence=_finite_number(item.get("new_confidence"), f"events[{idx}].new_confidence", 0, 1))
        if event_type == "interceptor_failure":
            interceptor_id = _positive_id(item.get("interceptor_id"), f"events[{idx}].interceptor_id")
            if interceptor_id not in interceptor_ids:
                raise ValueError(f"events[{idx}] refers to an unknown interceptor")
            event["interceptor_id"] = interceptor_id
        event["label"] = str(item.get("label") or event_type.replace("_", " ").title())[:120]
        events.append(event)
    events.sort(key=lambda item: item["time_s"])

    return Scenario(
        name=name, duration_s=duration, step_s=step, assets=assets,
        threats=threats, interceptors=interceptors, events=events,
        safety_radius_m=_finite_number(raw.get("safety_radius_m", 220), "safety_radius_m", 1, 2000),
        hit_radius_m=_finite_number(raw.get("hit_radius_m", 180), "hit_radius_m", 1, 1000),
        commitment_distance_m=_finite_number(raw.get("commitment_distance_m", 2200), "commitment_distance_m", 100, 20000),
        p2p_radius_m=_finite_number(raw.get("p2p_radius_m", 9000), "p2p_radius_m", 100, 100000),
    )


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    return {
        "name": scenario.name,
        "duration_s": scenario.duration_s,
        "step_s": scenario.step_s,
        "assets": [asset.to_dict() for asset in scenario.assets],
        "threats": [
            {
                "id": threat.id,
                "position": threat.position.to_dict(),
                "velocity": threat.velocity.to_dict(),
                "p_hostile": threat.p_hostile,
                "asset_id": threat.asset_id,
                "altitude_m": threat.altitude_m,
            }
            for threat in scenario.threats
        ],
        "interceptors": [
            {
                "id": interceptor.id,
                "position": interceptor.position.to_dict(),
                "max_speed_mps": interceptor.max_speed_mps,
                "range_m": interceptor.range_m,
                "battery": interceptor.battery,
                "cost": interceptor.cost,
                "kind": interceptor.kind,
                "altitude_m": interceptor.altitude_m,
                "base_group": interceptor.base_group,
            }
            for interceptor in scenario.interceptors
        ],
        "events": [dict(event) for event in scenario.events],
        "safety_radius_m": scenario.safety_radius_m,
        "hit_radius_m": scenario.hit_radius_m,
        "commitment_distance_m": scenario.commitment_distance_m,
        "p2p_radius_m": scenario.p2p_radius_m,
    }
