from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .allocator import allocate_baseline, allocate_swarmshield, threat_risk, time_to_asset
from .models import Interceptor, Scenario, Threat, Vec2
from .scenario import clone_scenario, scenario_to_dict


def _move_toward(position: Vec2, destination: Vec2, distance: float) -> tuple[Vec2, float]:
    dx, dy = destination.x - position.x, destination.y - position.y
    remaining = math.hypot(dx, dy)
    if remaining <= distance:
        return Vec2(destination.x, destination.y), remaining
    if remaining == 0:
        return Vec2(position.x, position.y), 0.0
    return Vec2(position.x + dx / remaining * distance, position.y + dy / remaining * distance), distance


def _snapshot(time_s: float, threats: list[Threat], interceptors: list[Interceptor]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for threat in threats:
        records.append(
            {
                "t": time_s,
                "kind": "threat",
                "id": threat.id,
                "x": round(threat.position.x, 2),
                "y": round(threat.position.y, 2),
                "z": round(threat.altitude_m, 2),
                "state": threat.state,
                "assignment": threat.assigned_interceptor,
                "risk": round(threat.predicted_risk, 3),
                "confidence": round(threat.p_hostile, 3),
                "asset_id": threat.asset_id,
            }
        )
    for interceptor in interceptors:
        records.append(
            {
                "t": time_s,
                "kind": "interceptor",
                "id": interceptor.id,
                "x": round(interceptor.position.x, 2),
                "y": round(interceptor.position.y, 2),
                "z": round(interceptor.altitude_m, 2),
                "state": interceptor.state,
                "assignment": interceptor.target_id,
                "committed": interceptor.committed,
                "class": interceptor.kind,
            }
        )
    return records


def _connected_components(interceptors: list[Interceptor], radius: float) -> list[list[str]]:
    active = [i for i in interceptors if i.state not in {"failed", "spent"}]
    adjacency: dict[str, set[str]] = {i.id: set() for i in active}
    for left_index, left in enumerate(active):
        for right in active[left_index + 1 :]:
            if left.position.distance_to(right.position) <= radius:
                adjacency[left.id].add(right.id)
                adjacency[right.id].add(left.id)
    components: list[list[str]] = []
    seen: set[str] = set()
    for interceptor in active:
        if interceptor.id in seen:
            continue
        stack = [interceptor.id]
        component: list[str] = []
        seen.add(interceptor.id)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(component))
    return components


def _apply_assignments(
    proposed: dict[str, str],
    interceptors: list[Interceptor],
    threats: list[Threat],
    time_s: float,
    event_log: list[dict[str, Any]],
    reason: str,
    allow_peer_conflicts: bool = False,
) -> int:
    interceptor_map = {item.id: item for item in interceptors}
    threat_map = {item.id: item for item in threats}
    locked_targets = {
        item.target_id
        for item in interceptors
        if item.committed and item.target_id and item.state == "engaging"
    }
    claimed = set(locked_targets)
    for interceptor in interceptors:
        if interceptor.committed or interceptor.state in {"failed", "spent"}:
            continue
        new_target = proposed.get(interceptor.id)
        if new_target in claimed and not allow_peer_conflicts:
            new_target = None
        old_target = interceptor.target_id
        if old_target != new_target:
            if old_target and old_target in threat_map and threat_map[old_target].assigned_interceptor == interceptor.id:
                threat_map[old_target].assigned_interceptor = None
            interceptor.previous_target_id = old_target
            interceptor.target_id = new_target
            if new_target:
                claimed.add(new_target)
                threat_map[new_target].assigned_interceptor = interceptor.id
                if old_target:
                    event_log.append(
                        {
                            "time_s": time_s,
                            "type": "reassignment",
                            "label": f"{interceptor.id} retasked {old_target} -> {new_target}",
                            "interceptor_id": interceptor.id,
                            "from": old_target,
                            "to": new_target,
                            "reason": reason,
                        }
                    )
            interceptor.state = "engaging" if new_target else "holding"
            interceptor.launched = interceptor.launched or bool(new_target)
    # Restore locked target relationships.
    for interceptor in interceptors:
        if interceptor.committed and interceptor.target_id in threat_map:
            threat_map[interceptor.target_id].assigned_interceptor = interceptor.id
    claims: dict[str, list[str]] = defaultdict(list)
    for interceptor in interceptors:
        if interceptor.state == "engaging" and interceptor.target_id:
            claims[interceptor.target_id].append(interceptor.id)
    conflicts = {target_id: ids for target_id, ids in claims.items() if len(ids) > 1}
    if allow_peer_conflicts:
        for target_id, ids in conflicts.items():
            event_log.append({
                "time_s": time_s,
                "type": "peer_conflict",
                "label": f"Disconnected peers both claim {target_id}: {', '.join(ids)}",
                "threat_id": target_id,
                "interceptor_ids": ids,
            })
    return len(conflicts)


def _swarm_assign(
    scenario: Scenario,
    ground_link: bool,
) -> tuple[dict[str, str], dict[str, Any]]:
    assets = scenario.asset_map()
    free = [item for item in scenario.interceptors if not item.committed]
    locked_targets = {
        item.target_id for item in scenario.interceptors
        if item.committed and item.state == "engaging" and item.target_id
    }
    active = [item for item in scenario.threats if item.state == "active" and item.id not in locked_targets]
    if ground_link:
        assignments, _ = allocate_swarmshield(free, active, assets)
        return assignments, {"mode": "central-seeded", "components": [sorted(i.id for i in free)]}

    # Disconnected components have no shared claim ledger. Each group sees
    # only nearby tracks, so conflicting proposals remain visible in output.
    components = _connected_components(free, scenario.p2p_radius_m)
    by_id = {item.id: item for item in free}
    merged: dict[str, str] = {}
    visibility: dict[str, int] = {}
    for component in sorted(components, key=lambda ids: (-len(ids), ids)):
        local_interceptors = [by_id[item_id] for item_id in component]
        visible = [
            threat for threat in active
            if any(item.position.distance_to(threat.position) <= scenario.peer_visibility_m
                   for item in local_interceptors)
        ]
        local, _ = allocate_swarmshield(local_interceptors, visible, assets)
        merged.update(local)
        visibility[component[0]] = len(visible)
    return merged, {"mode": "peer-to-peer", "components": components,
                    "visible_tracks_by_component": visibility,
                    "peer_radius_m": scenario.p2p_radius_m}


def _process_scripted_events(
    scenario: Scenario,
    time_s: float,
    ground_link: bool,
    event_log: list[dict[str, Any]],
) -> tuple[bool, bool]:
    changed = False
    assets = scenario.asset_map()
    threat_map = {item.id: item for item in scenario.threats}
    interceptor_map = {item.id: item for item in scenario.interceptors}
    for event in scenario.events:
        if event["time_s"] != time_s:
            continue
        if event["type"] in {"threat_diversion", "confidence_update"} and threat_map[event["threat_id"]].state != "active":
            event_log.append({
                "time_s": time_s, "type": "stale_event", "original_type": event["type"],
                "label": f"{event['threat_id']} update ignored; track is no longer active",
            })
            continue
        event_log.append(dict(event))
        changed = True
        if event["type"] == "threat_diversion":
            threat = threat_map[event["threat_id"]]
            threat.asset_id = event["new_asset_id"]
            threat.p_hostile = event["new_confidence"]
            asset = assets[threat.asset_id]
            speed = threat.speed()
            dx, dy = asset.position.x - threat.position.x, asset.position.y - threat.position.y
            norm = math.hypot(dx, dy) or 1.0
            threat.velocity = Vec2(speed * dx / norm, speed * dy / norm)
        elif event["type"] == "interceptor_failure":
            interceptor = interceptor_map[event["interceptor_id"]]
            if interceptor.target_id and interceptor.target_id in threat_map:
                threat_map[interceptor.target_id].assigned_interceptor = None
            interceptor.state = "failed"
            interceptor.target_id = None
            interceptor.committed = False
        elif event["type"] == "ground_link_loss":
            ground_link = False
        elif event["type"] == "ground_link_restore":
            ground_link = True
        elif event["type"] == "confidence_update":
            threat_map[event["threat_id"]].p_hostile = event["new_confidence"]
        elif event["type"] == "asset_consequence_change":
            assets[event["asset_id"]].consequence = event["new_consequence"]
        elif event["type"] == "peer_link_degradation":
            scenario.p2p_radius_m = event["new_radius_m"]
    return ground_link, changed


def _collision_avoidance(
    scenario: Scenario,
    planned: dict[str, Vec2],
    event_log: list[dict[str, Any]],
    time_s: float,
) -> int:
    """Replace a conflicting pursuit step with a speed-limited separation step."""
    by_id = {item.id: item for item in scenario.interceptors}
    ids = sorted(planned)
    yielding_ids: set[str] = set()
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1 :]:
            if planned[left_id].distance_to(planned[right_id]) >= scenario.safety_radius_m:
                continue
            yielding_id = max(left_id, right_id)
            if yielding_id in yielding_ids:
                continue
            other_id = min(left_id, right_id)
            yielding = by_id[yielding_id]
            dx = yielding.position.x - planned[other_id].x
            dy = yielding.position.y - planned[other_id].y
            norm = math.hypot(dx, dy)
            if norm < 1e-6:
                dx, dy, norm = 1.0, 0.0, 1.0
            step = yielding.max_speed_mps * scenario.step_s
            planned[yielding_id] = Vec2(
                yielding.position.x + dx / norm * step,
                yielding.position.y + dy / norm * step,
            )
            yielding_ids.add(yielding_id)
            event_log.append({
                "time_s": time_s,
                "type": "collision_avoidance",
                "label": f"{yielding.id} takes a separation waypoint",
                "interceptor_id": yielding.id,
            })
    return len(yielding_ids)


def run_scenario(source: Scenario, strategy: str) -> dict[str, Any]:
    if strategy not in {"baseline", "swarmshield"}:
        raise ValueError("strategy must be baseline or swarmshield")
    scenario = clone_scenario(source)
    assets = scenario.asset_map()
    threats = {item.id: item for item in scenario.threats}
    event_log: list[dict[str, Any]] = []
    for threat in scenario.threats:
        asset = assets[threat.asset_id]
        if threat.position.distance_to(asset.position) <= asset.radius_m:
            threat.state = "leaked"
            event_log.append({
                "time_s": 0.0, "type": "leak", "threat_id": threat.id,
                "asset_id": asset.id, "label": f"{threat.id} begins inside {asset.name}",
            })
    initial_risks = {
        item.id: threat_risk(item, assets[item.asset_id]) for item in scenario.threats
    }
    trajectories: list[dict[str, Any]] = []
    allocation_snapshots: list[dict[str, Any]] = []
    ground_link = True
    collision_conflicts = 0
    peer_conflicts = 0
    reassignment_times: list[float] = []
    total_frames = int(source.duration_s / source.step_s) + 1
    # Preserve every simulation step internally; only downsample the visual
    # output when a very large scenario would overwhelm a browser tab.
    sample_stride = max(1, math.ceil(total_frames * (len(scenario.threats) + len(scenario.interceptors)) / 25000))
    event_times = {event["time_s"] for event in scenario.events}

    if strategy == "baseline":
        initial = allocate_baseline(scenario.interceptors, scenario.threats, assets)
        coordination = {"mode": "naive-static", "components": []}
    else:
        initial, coordination = _swarm_assign(scenario, ground_link)
    _apply_assignments(initial, scenario.interceptors, scenario.threats, 0, event_log, "initial allocation")
    allocation_snapshots.append({"time_s": 0, "assignments": initial, **coordination})

    for step in range(int(source.duration_s / source.step_s) + 1):
        time_s = round(step * source.step_s, 6)

        orphaned_target_id = None
        failure = next(
            (
                event
                for event in scenario.events
                if event["time_s"] == time_s and event["type"] == "interceptor_failure"
            ),
            None,
        )
        if failure:
            failed = next(
                item for item in scenario.interceptors if item.id == failure["interceptor_id"]
            )
            orphaned_target_id = failed.target_id

        ground_link, scripted_change = _process_scripted_events(
            scenario, time_s, ground_link, event_log
        )
        if strategy == "swarmshield" and (scripted_change or step % 5 == 0):
            proposed, coordination = _swarm_assign(scenario, ground_link)
            before_events = len(event_log)
            peer_conflicts += _apply_assignments(
                proposed,
                scenario.interceptors,
                scenario.threats,
                time_s,
                event_log,
                "event response" if scripted_change else "periodic rebid",
                allow_peer_conflicts=not ground_link,
            )
            if len(event_log) > before_events and scripted_change:
                reassignment_times.append(0.0)
            if orphaned_target_id:
                replacement = next(
                    (
                        item.id
                        for item in scenario.interceptors
                        if item.target_id == orphaned_target_id and item.state == "engaging"
                    ),
                    None,
                )
                if replacement:
                    event_log.append(
                        {
                            "time_s": time_s,
                            "type": "failure_recovery",
                            "label": f"{orphaned_target_id} recovered by {replacement} after {failure['interceptor_id']} failure",
                            "failed_interceptor_id": failure["interceptor_id"],
                            "replacement_interceptor_id": replacement,
                            "threat_id": orphaned_target_id,
                            "latency_s": 0.0,
                        }
                    )
                    reassignment_times.append(0.0)
            allocation_snapshots.append(
                {"time_s": time_s, "assignments": proposed, **coordination}
            )

        for threat in scenario.threats:
            if threat.state == "active":
                threat.predicted_risk = threat_risk(threat, assets[threat.asset_id])
        if step % sample_stride == 0 or time_s in event_times or time_s >= source.duration_s:
            trajectories.extend(_snapshot(time_s, scenario.threats, scenario.interceptors))
        if time_s >= source.duration_s:
            break

        # Incoming tracks advance toward their currently predicted impact asset.
        for threat in scenario.threats:
            if threat.state != "active":
                continue
            threat.position = Vec2(
                threat.position.x + threat.velocity.x * source.step_s,
                threat.position.y + threat.velocity.y * source.step_s,
            )

        # Interceptors pursue from behind. Commitment prevents late oscillation.
        planned: dict[str, Vec2] = {}
        for interceptor in scenario.interceptors:
            if interceptor.state != "engaging" or not interceptor.target_id:
                continue
            target = threats.get(interceptor.target_id)
            if not target or target.state != "active":
                interceptor.state = "spent" if target and target.state == "intercepted" else "holding"
                interceptor.target_id = None
                continue
            distance_before = interceptor.position.distance_to(target.position)
            if distance_before <= scenario.commitment_distance_m:
                interceptor.committed = True
            max_step = interceptor.max_speed_mps * source.step_s
            planned[interceptor.id], _ = _move_toward(interceptor.position, target.position, max_step)

        if strategy == "swarmshield":
            collision_conflicts += _collision_avoidance(scenario, planned, event_log, time_s)

        for interceptor in scenario.interceptors:
            if interceptor.id not in planned or not interceptor.target_id:
                continue
            target = threats[interceptor.target_id]
            new_position = planned[interceptor.id]
            interceptor.distance_flown_m += interceptor.position.distance_to(new_position)
            interceptor.position = new_position
            if target.state == "active" and interceptor.position.distance_to(target.position) <= scenario.hit_radius_m:
                target.state = "intercepted"
                target.assigned_interceptor = interceptor.id
                interceptor.state = "spent"
                interceptor.target_id = None
                event_log.append(
                    {
                        "time_s": time_s + source.step_s,
                        "type": "intercept",
                        "label": f"{interceptor.id} intercepts {target.id}",
                        "interceptor_id": interceptor.id,
                        "threat_id": target.id,
                    }
                )

        for threat in scenario.threats:
            if threat.state != "active":
                continue
            asset = assets[threat.asset_id]
            if threat.position.distance_to(asset.position) <= max(asset.radius_m, threat.speed() * source.step_s):
                threat.state = "leaked"
                event_log.append(
                    {
                        "time_s": time_s + source.step_s,
                        "type": "leak",
                        "label": f"{threat.id} reaches {asset.name}",
                        "threat_id": threat.id,
                        "asset_id": asset.id,
                    }
                )

    intercepted = [item for item in scenario.threats if item.state == "intercepted"]
    leaked = [item for item in scenario.threats if item.state == "leaked"]
    unresolved = [item for item in scenario.threats if item.state == "active"]
    # At the simulation horizon, count an unresolved track as projected
    # leakage only if its present velocity intersects the named asset.
    projected = [
        item for item in unresolved
        if math.isfinite(time_to_asset(item, assets[item.asset_id]))
    ]
    off_course = [item for item in unresolved if item not in projected]
    leaked_effective = leaked + projected
    expected_leakage = sum(threat_risk(item, assets[item.asset_id]) for item in leaked_effective)
    critical_leaks = sum(1 for item in leaked_effective if assets[item.asset_id].consequence >= 75)
    used = [item for item in scenario.interceptors if item.launched]
    decisions = []
    initially_assigned = allocation_snapshots[0]["assignments"]
    for threat in scenario.threats:
        assigned = next((iid for iid, tid in initially_assigned.items() if tid == threat.id), None)
        decisions.append(
            {
                "threat_id": threat.id,
                "initial_decision": "intercept" if assigned else "unallocated",
                "interceptor_id": assigned,
                "asset_id": threat.asset_id,
                "risk": round(initial_risks[threat.id], 2),
                "final_risk": round(threat_risk(threat, assets[threat.asset_id]), 2),
                "final_state": threat.state,
            }
        )
    metrics = {
        "strategy": strategy,
        "threats": len(scenario.threats),
        "interceptors": len(scenario.interceptors),
        "intercepted": len(intercepted),
        "leakage": len(leaked_effective),
        "actual_leakage": len(leaked),
        "projected_leakage": len(projected),
        "off_course_unresolved": len(off_course),
        "leakage_percent": round(100 * len(leaked_effective) / len(scenario.threats), 1),
        "critical_leaks": critical_leaks,
        "expected_consequence_leaked": round(expected_leakage, 2),
        "interceptors_launched": len(used),
        "defensive_cost": round(sum(item.cost for item in used), 2),
        "reassignments": sum(1 for event in event_log if event["type"] == "reassignment"),
        "reassignment_latency_s": round(sum(reassignment_times) / len(reassignment_times), 3)
        if reassignment_times
        else None,
        "collision_avoidance_actions": collision_conflicts,
        "ground_link_loss_exercised": any(event["type"] == "ground_link_loss" for event in event_log),
        "peer_coordination_exercised": strategy == "swarmshield" and any(
            item["mode"] == "peer-to-peer" for item in allocation_snapshots
        ),
        "peer_coordination_active_at_end": strategy == "swarmshield" and not ground_link,
        "max_peer_groups": max((len(item["components"]) for item in allocation_snapshots
                                if item["mode"] == "peer-to-peer"), default=0),
        "peer_conflict_snapshots": peer_conflicts,
        "priority_update_events": sum(event["type"] in {
            "threat_diversion", "confidence_update", "asset_consequence_change"
        } for event in event_log),
    }
    return {
        "strategy": strategy,
        "metrics": metrics,
        "decisions": decisions,
        "events": sorted(event_log, key=lambda item: item["time_s"]),
        "allocations": allocation_snapshots,
        "trajectories": trajectories,
        "visual_sample_step_s": sample_stride * source.step_s,
    }


def run_comparison(scenario: Scenario) -> dict[str, Any]:
    baseline = run_scenario(scenario, "baseline")
    swarmshield = run_scenario(scenario, "swarmshield")
    baseline_consequence = baseline["metrics"]["expected_consequence_leaked"]
    swarm_consequence = swarmshield["metrics"]["expected_consequence_leaked"]
    reduction = 0.0
    if baseline_consequence:
        reduction = 100 * (baseline_consequence - swarm_consequence) / baseline_consequence
    return {
        "schema_version": "1.0",
        "scenario": {
            "name": scenario.name,
            "threat_count": len(scenario.threats),
            "interceptor_count": len(scenario.interceptors),
            "duration_s": scenario.duration_s,
            "step_s": scenario.step_s,
            "seed": scenario.seed,
            "profile": scenario.profile,
            "scale": "1 unit = 1 metre",
            "assumptions": [
                "One interceptor can make at most one interception attempt.",
                "Interceptors run targets down from behind.",
                "Unallocated is an explicit optimization decision.",
                "Allocation is advisory/simulated; no weapons or real control interfaces are included.",
                "Peer groups have proximity-based visibility; no radios or message transport are modeled.",
            ],
            "assets": [asset.to_dict() for asset in scenario.assets],
            "definition": scenario_to_dict(scenario),
            "scripted_events": scenario.events,
        },
        "runs": {"baseline": baseline, "swarmshield": swarmshield},
        "headline": {
            "expected_consequence_reduction_percent": round(reduction, 1),
            "critical_leaks_avoided": baseline["metrics"]["critical_leaks"]
            - swarmshield["metrics"]["critical_leaks"],
        },
    }
