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
    profile: str = "mixed",
) -> Scenario:
    """Generate a reproducible synthetic scenario across several stress profiles.

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
    if profile not in {"mixed", "concentrated", "dispersed", "uncertain"}:
        raise ValueError("profile must be mixed, concentrated, dispersed, or uncertain")
    rng = random.Random(seed)
    assets = [
        Asset("A01", "Command Centre", Vec2(0, -5200), 100, "critical", 450),
        Asset("A02", "Airbase", Vec2(-6200, -4300), 90, "critical", 950),
        Asset("A03", "Power Substation", Vec2(4600, -4700), 76, "critical", 420),
        Asset("A04", "Industrial Zone", Vec2(7600, -3600), 42, "important", 1100),
        Asset("A05", "Open Water", Vec2(-9800, -1500), 6, "low-consequence", 1250),
    ]
    assets_by_id = {asset.id: asset for asset in assets}

    weights = {
        "mixed": [3.0, 2.3, 2.2, 1.8, 1.6],
        "concentrated": [7.0, 1.1, 1.0, 0.6, 0.3],
        "dispersed": [1.0, 1.0, 1.0, 1.0, 1.0],
        "uncertain": [2.0, 2.0, 2.0, 1.5, 2.0],
    }[profile]
    threats: list[Threat] = []
    row_width = min(24, threat_count)
    for idx in range(threat_count):
        column = idx % row_width
        row = idx // row_width
        fraction = 0.5 if row_width == 1 else column / (row_width - 1)
        x = -10600 + fraction * 21200 + rng.uniform(-180, 180)
        y = 13600 + row * 620 + (idx % 4) * 240 + rng.uniform(-90, 90)
        start = Vec2(x, y)
        speed = rng.uniform(116, 148)
        asset_id = rng.choices(list(assets_by_id), weights=weights, k=1)[0]
        confidence = rng.uniform(0.18, 0.76) if profile == "uncertain" else rng.betavariate(3.2, 1.55)
        if asset_id == "A05":
            confidence *= rng.uniform(0.45, 0.75)
        velocity = _velocity_toward(start, assets_by_id[asset_id].position, speed)
        threats.append(
            Threat(
                id=f"T{idx + 1:02d}",
                position=start,
                velocity=velocity,
                p_hostile=max(0.05, min(0.99, confidence)),
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
        fast = idx % 4 == 1
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

    events: list[dict[str, Any]] = []
    if enable_events:
        if interceptors:
            from .allocator import allocate_swarmshield

            initial, _ = allocate_swarmshield(interceptors, threats, assets_by_id)
            failure_id = rng.choice(sorted(initial)) if initial else interceptors[0].id
            events.append({
                "time_s": max(5, round(duration_s * 0.10)),
                "type": "interceptor_failure",
                "interceptor_id": failure_id,
                "label": f"{failure_id} loses availability",
            })
        if threats:
            water_tracks = [item for item in threats if item.asset_id == "A05"]
            diversion = min(water_tracks or threats, key=lambda item: item.p_hostile)
            destination = "A01" if diversion.asset_id != "A01" else "A02"
            events.append({
                "time_s": max(6, round(duration_s * 0.17)),
                "type": "threat_diversion",
                "threat_id": diversion.id,
                "new_asset_id": destination,
                "new_confidence": 0.94,
                "label": f"{diversion.id} changes course toward {assets_by_id[destination].name}",
            })
        if len(threats) > 1:
            revised = max((item for item in threats if item.id != diversion.id), key=lambda item: item.p_hostile)
            events.append({
                "time_s": max(7, round(duration_s * 0.22)),
                "type": "confidence_update",
                "threat_id": revised.id,
                "new_confidence": 0.18,
                "label": f"{revised.id} assessment revised downward",
            })
        events.extend([
            {"time_s": max(8, round(duration_s * 0.13)), "type": "ground_link_loss",
             "label": "Ground link lost; local peer groups take over"},
            {"time_s": max(9, round(duration_s * 0.19)), "type": "peer_link_degradation",
             "new_radius_m": 3500.0, "label": "Peer connectivity degrades"},
            {"time_s": max(10, round(duration_s * 0.27)), "type": "asset_consequence_change",
             "asset_id": "A04", "new_consequence": 82.0,
             "label": "Industrial district consequence increases"},
            {"time_s": max(11, round(duration_s * 0.38)), "type": "ground_link_restore",
             "label": "Ground link restored"},
        ])
    events.sort(key=lambda event: event["time_s"])
    return Scenario(
        name=f"{profile.title()} City Scenario · {threat_count} tracks / {interceptor_count} interceptors",
        duration_s=duration_s,
        step_s=1.0,
        assets=assets,
        threats=threats,
        interceptors=interceptors,
        events=events,
        safety_radius_m=500.0,
        seed=seed,
        profile=profile,
    )


def build_hackathon_scenario(seed: int = 42) -> Scenario:
    """Return the reproducible default judging scenario."""
    return build_scenario(20, 12, seed=seed, duration_s=190, enable_events=True)


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
            _finite_number(item.get("radius_m", 300), f"assets[{idx}].radius_m", 50, 5000),
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
        if event_type not in {
            "threat_diversion", "confidence_update", "asset_consequence_change",
            "interceptor_failure", "ground_link_loss", "ground_link_restore",
            "peer_link_degradation",
        }:
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
        if event_type == "confidence_update":
            threat_id = _positive_id(item.get("threat_id"), f"events[{idx}].threat_id")
            if threat_id not in threat_ids:
                raise ValueError(f"events[{idx}] refers to an unknown threat")
            event.update(
                threat_id=threat_id,
                new_confidence=_finite_number(item.get("new_confidence"), f"events[{idx}].new_confidence", 0, 1),
            )
        if event_type == "asset_consequence_change":
            changed_asset_id = _positive_id(item.get("asset_id"), f"events[{idx}].asset_id")
            if changed_asset_id not in asset_ids:
                raise ValueError(f"events[{idx}] refers to an unknown asset")
            event.update(
                asset_id=changed_asset_id,
                new_consequence=_finite_number(item.get("new_consequence"), f"events[{idx}].new_consequence", 0, 1000),
            )
        if event_type == "peer_link_degradation":
            event["new_radius_m"] = _finite_number(item.get("new_radius_m"), f"events[{idx}].new_radius_m", 100, 100000)
        event["label"] = str(item.get("label") or event_type.replace("_", " ").title())[:120]
        events.append(event)
    events.sort(key=lambda item: item["time_s"])

    seed = raw.get("seed")
    if seed is not None:
        seed = _integer(seed, "seed", 0, 1_000_000)
    return Scenario(
        name=name, duration_s=duration, step_s=step, assets=assets,
        threats=threats, interceptors=interceptors, events=events,
        safety_radius_m=_finite_number(raw.get("safety_radius_m", 220), "safety_radius_m", 1, 2000),
        hit_radius_m=_finite_number(raw.get("hit_radius_m", 180), "hit_radius_m", 1, 1000),
        commitment_distance_m=_finite_number(raw.get("commitment_distance_m", 2200), "commitment_distance_m", 100, 20000),
        p2p_radius_m=_finite_number(raw.get("p2p_radius_m", 9000), "p2p_radius_m", 100, 100000),
        peer_visibility_m=_finite_number(raw.get("peer_visibility_m", 28000), "peer_visibility_m", 100, 200000),
        seed=seed,
        profile="custom",
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
        "peer_visibility_m": scenario.peer_visibility_m,
        "seed": scenario.seed,
        "profile": scenario.profile,
    }
