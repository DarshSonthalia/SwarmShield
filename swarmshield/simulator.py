from __future__ import annotations

import math
from collections import defaultdict, deque
from statistics import mean
from typing import Any

from .allocator import allocate_baseline, allocate_swarmshield
from .belief import HISTORY_LIMIT, build_threat_belief
from .models import (Interceptor, ObservedThreat, Scenario, Threat, ThreatBelief,
                     TrackObservation, Vec2)
from .scenario import clone_scenario, scenario_to_dict


def _move_toward(position: Vec2, destination: Vec2, distance: float) -> tuple[Vec2, float]:
    dx, dy = destination.x - position.x, destination.y - position.y
    remaining = math.hypot(dx, dy)
    if remaining <= distance:
        return Vec2(destination.x, destination.y), remaining
    if remaining == 0:
        return Vec2(position.x, position.y), 0.0
    return Vec2(position.x + dx / remaining * distance, position.y + dy / remaining * distance), distance


def _observe(threat: Threat, time_s: float) -> ObservedThreat:
    return ObservedThreat(threat.id, time_s, threat.position, threat.velocity,
                          threat.p_hostile, threat.state, threat.altitude_m)


def _update_beliefs(time_s, threats, assets, histories):
    observed = {threat.id: _observe(threat, time_s) for threat in threats}
    for item in observed.values():
        histories[item.id].append(TrackObservation(time_s, item.position, item.velocity))
    beliefs = {item.id: build_threat_belief(item, list(histories[item.id]), assets)
               for item in observed.values()}
    return observed, beliefs


def _belief_evidence(belief: ThreatBelief) -> dict[str, Any]:
    return {
        "destination_probabilities": {key: round(value, 4) for key, value in belief.destination_probabilities.items()},
        "top_destination_id": belief.top_destination_id,
        "top_probability": round(belief.top_probability, 4),
        "expected_consequence": round(belief.expected_consequence, 3),
        "uncertainty": round(belief.uncertainty, 4),
        "uncertainty_label": belief.uncertainty_label,
        "urgency": round(belief.urgency, 4),
        "risk": round(belief.risk, 3),
    }


def _snapshot(time_s: float, threats: list[Threat], interceptors: list[Interceptor],
              beliefs: dict[str, ThreatBelief], decisions: dict[str, str]) -> list[dict[str, Any]]:
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
                "risk": round(beliefs[threat.id].risk, 3),
                "belief": _belief_evidence(beliefs[threat.id]),
                "decision": decisions.get(threat.id, "HOLD"),
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
) -> None:
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
        if new_target in claimed:
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


def _swarm_assign(
    scenario: Scenario,
    ground_link: bool,
    observed: dict[str, ObservedThreat],
    beliefs: dict[str, ThreatBelief],
) -> tuple[dict[str, str], dict[str, Any]]:
    free = [item for item in scenario.interceptors if not item.committed]
    locked_targets = {
        item.target_id for item in scenario.interceptors
        if item.committed and item.state == "engaging" and item.target_id
    }
    active = [observed[item.id] for item in scenario.threats if item.state == "active" and item.id not in locked_targets]
    if ground_link:
        assignments, _ = allocate_swarmshield(free, active, beliefs)
        return assignments, {"mode": "central-seeded", "components": [sorted(i.id for i in free)]}

    # Under ground-link loss, each connected peer component runs the same local
    # auction. A deterministic claim ledger models bids forwarded between
    # components whenever a bridging peer becomes available.
    components = _connected_components(free, scenario.p2p_radius_m)
    by_id = {item.id: item for item in free}
    claimed: set[str] = set()
    merged: dict[str, str] = {}
    for component in sorted(components, key=lambda ids: (-len(ids), ids)):
        local_interceptors = [by_id[item_id] for item_id in component]
        visible = [threat for threat in active if threat.id not in claimed]
        local, _ = allocate_swarmshield(local_interceptors, visible, beliefs)
        merged.update(local)
        claimed.update(local.values())
    return merged, {"mode": "peer-to-peer", "components": components}


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


def _ground_truth_time_to_asset(threat: Threat, asset) -> float:
    dx, dy = asset.position.x - threat.position.x, asset.position.y - threat.position.y
    speed_squared = threat.velocity.x ** 2 + threat.velocity.y ** 2
    if speed_squared <= 0:
        return float("inf")
    time = (dx * threat.velocity.x + dy * threat.velocity.y) / speed_squared
    if time < 0:
        return float("inf")
    miss = math.hypot(dx - threat.velocity.x * time, dy - threat.velocity.y * time)
    return time if miss <= 300 else float("inf")


def _prediction_evaluation(commit_records, threats, asset_ids):
    committed = list(commit_records.values())
    if not committed:
        return {"evaluation_point": "first_commit", "committed_count": 0,
                "uncommitted_count": len(threats), "top_destination_accuracy": None,
                "mean_normalized_entropy": None, "brier_score": None}
    accuracy = mean(record.top_destination_id == asset_ids[tid]
                    for tid, record in commit_records.items())
    brier = mean(sum((record.destination_probabilities[aid] - (aid == asset_ids[tid])) ** 2
                     for aid in record.destination_probabilities)
                  for tid, record in commit_records.items())
    return {"evaluation_point": "first_commit", "committed_count": len(committed),
            "uncommitted_count": len(threats) - len(committed),
            "top_destination_accuracy": round(accuracy, 4),
            "mean_normalized_entropy": round(mean(r.uncertainty for r in committed), 4),
            "brier_score": round(brier, 4)}


def run_scenario(source: Scenario, strategy: str) -> dict[str, Any]:
    if strategy not in {"baseline", "swarmshield"}:
        raise ValueError("strategy must be baseline or swarmshield")
    scenario = clone_scenario(source)
    assets = scenario.asset_map()
    threats = {item.id: item for item in scenario.threats}
    histories = {item.id: deque(maxlen=HISTORY_LIMIT) for item in scenario.threats}
    observed, beliefs = _update_beliefs(0, scenario.threats, assets, histories)
    initial_beliefs = dict(beliefs)
    decision_states = {item.id: "HOLD" for item in scenario.threats}
    commit_records: dict[str, ThreatBelief] = {}
    event_log: list[dict[str, Any]] = []
    trajectories: list[dict[str, Any]] = []
    allocation_snapshots: list[dict[str, Any]] = []
    ground_link = True
    collision_conflicts = 0
    reassignment_times: list[float] = []

    if strategy == "baseline":
        initial = allocate_baseline(scenario.interceptors, list(observed.values()), beliefs)
        coordination = {"mode": "naive-static", "components": []}
    else:
        initial, coordination = _swarm_assign(scenario, ground_link, observed, beliefs)
    _apply_assignments(initial, scenario.interceptors, scenario.threats, 0, event_log, "initial allocation")
    for threat in scenario.threats:
        assigned = next((iid for iid, tid in initial.items() if tid == threat.id), None)
        decision_states[threat.id] = "COMMIT" if assigned else "HOLD"
        if assigned:
            commit_records[threat.id] = beliefs[threat.id]
        event_log.append({"time_s": 0, "type": "commit" if assigned else "hold",
                          "label": f"{threat.id} {'COMMIT' if assigned else 'HOLD'}",
                          "threat_id": threat.id, "interceptor_id": assigned,
                          "evidence": _belief_evidence(beliefs[threat.id])})
    allocation_snapshots.append({"time_s": 0, "assignments": initial, **coordination})

    for step in range(int(source.duration_s / source.step_s) + 1):
        time_s = round(step * source.step_s, 6)
        observed, beliefs = _update_beliefs(time_s, scenario.threats, assets, histories)
        trajectories.extend(_snapshot(time_s, scenario.threats, scenario.interceptors, beliefs, decision_states))
        if time_s >= source.duration_s:
            break

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
            if scripted_change:
                observed, beliefs = _update_beliefs(time_s, scenario.threats, assets, histories)
            old_assignments = {item.id: item.target_id for item in scenario.interceptors}
            proposed, coordination = _swarm_assign(scenario, ground_link, observed, beliefs)
            before_events = len(event_log)
            _apply_assignments(
                proposed,
                scenario.interceptors,
                scenario.threats,
                time_s,
                event_log,
                "event response" if scripted_change else "periodic rebid",
            )
            for interceptor_id, threat_id in proposed.items():
                previous = old_assignments.get(interceptor_id)
                first_commit = threat_id not in commit_records
                transition = "commit" if first_commit else "retask"
                if first_commit:
                    commit_records[threat_id] = beliefs[threat_id]
                if first_commit or (previous is not None and previous != threat_id):
                    event_log.append({"time_s": time_s, "type": transition,
                                      "label": f"{interceptor_id} {transition.upper()} {threat_id}",
                                      "threat_id": threat_id, "interceptor_id": interceptor_id,
                                      "evidence": _belief_evidence(beliefs[threat_id])})
                decision_states[threat_id] = "COMMIT"
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
            if threat.position.distance_to(asset.position) <= max(260.0, threat.speed() * source.step_s):
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
        if math.isfinite(_ground_truth_time_to_asset(item, assets[item.asset_id]))
    ]
    off_course = [item for item in unresolved if item not in projected]
    leaked_effective = leaked + projected
    expected_leakage = sum(item.p_hostile * assets[item.asset_id].consequence for item in leaked_effective)
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
                "likely_destination_id": initial_beliefs[threat.id].top_destination_id,
                "risk": round(initial_beliefs[threat.id].risk, 2),
                "final_risk": round(beliefs[threat.id].risk, 2),
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
        "ground_link_loss_exercised": not ground_link,
        "peer_coordination_active": strategy == "swarmshield" and not ground_link,
        "prediction_evaluation": _prediction_evaluation(
            commit_records, scenario.threats,
            {threat.id: threat.asset_id for threat in scenario.threats},
        ),
    }
    return {
        "strategy": strategy,
        "metrics": metrics,
        "decisions": decisions,
        "events": sorted(event_log, key=lambda item: item["time_s"]),
        "allocations": allocation_snapshots,
        "trajectories": trajectories,
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
            "seed": 42,
            "scale": "1 unit = 1 metre",
            "assumptions": [
                "One interceptor can make at most one interception attempt.",
                "Interceptors run targets down from behind.",
                "Unallocated is an explicit optimization decision.",
                "Allocation is advisory/simulated; no weapons or real control interfaces are included.",
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
