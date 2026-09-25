from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Asset, Interceptor, Threat, Vec2


@dataclass(frozen=True)
class PairScore:
    interceptor_id: str
    threat_id: str
    feasible: bool
    utility: float
    intercept_time_s: float | None
    intercept_point: Vec2 | None
    probability: float
    energy_cost: float


def time_to_asset(threat: Threat, asset: Asset) -> float:
    dx = asset.position.x - threat.position.x
    dy = asset.position.y - threat.position.y
    vx, vy = threat.velocity.x, threat.velocity.y
    speed_squared = vx * vx + vy * vy
    if speed_squared <= 0:
        return float("inf")
    time = (dx * vx + dy * vy) / speed_squared
    if time < 0:
        return float("inf")
    miss_distance = math.hypot(dx - vx * time, dy - vy * time)
    if miss_distance > 300.0:
        return float("inf")
    return time


def threat_risk(threat: Threat, asset: Asset) -> float:
    tti = time_to_asset(threat, asset)
    if not math.isfinite(tti):
        return 0.0
    urgency = min(1.0, 95.0 / max(tti, 1.0))
    return threat.p_hostile * asset.consequence * (0.45 + 0.55 * urgency)


def intercept_solution(interceptor: Interceptor, threat: Threat) -> tuple[float, Vec2] | None:
    """Solve |target + velocity*t - interceptor| = interceptor_speed*t."""
    rx = threat.position.x - interceptor.position.x
    ry = threat.position.y - interceptor.position.y
    vx, vy = threat.velocity.x, threat.velocity.y
    speed = interceptor.max_speed_mps
    a = vx * vx + vy * vy - speed * speed
    b = 2.0 * (rx * vx + ry * vy)
    c = rx * rx + ry * ry
    if abs(a) < 1e-9:
        if abs(b) < 1e-9:
            return None
        roots = [-c / b]
    else:
        disc = b * b - 4.0 * a * c
        if disc < 0:
            return None
        root = math.sqrt(disc)
        roots = [(-b - root) / (2.0 * a), (-b + root) / (2.0 * a)]
    valid = [value for value in roots if value > 0]
    if not valid:
        return None
    t = min(valid)
    point = Vec2(threat.position.x + vx * t, threat.position.y + vy * t)
    return t, point


def score_pair(interceptor: Interceptor, threat: Threat, asset: Asset) -> PairScore:
    # Layer 3 assumes a same-direction pursuit, not a head-on meeting.
    relative_x = interceptor.position.x - threat.position.x
    relative_y = interceptor.position.y - threat.position.y
    if relative_x * threat.velocity.x + relative_y * threat.velocity.y >= 0:
        return PairScore(interceptor.id, threat.id, False, -1e9, None, None, 0.0, 0.0)
    solution = intercept_solution(interceptor, threat)
    if solution is None:
        return PairScore(interceptor.id, threat.id, False, -1e9, None, None, 0.0, 0.0)
    intercept_time, point = solution
    distance = interceptor.position.distance_to(point)
    effective_range = interceptor.range_m * max(0.35, interceptor.battery)
    before_impact = intercept_time < time_to_asset(threat, asset) - 2.0
    feasible = distance <= effective_range and before_impact and interceptor.state not in {"failed", "spent"}
    if not feasible:
        return PairScore(interceptor.id, threat.id, False, -1e9, intercept_time, point, 0.0, distance)

    speed_margin = max(0.0, interceptor.max_speed_mps - threat.speed())
    probability = min(0.97, 0.58 + speed_margin / 260.0 + 0.12 * interceptor.battery)
    risk = threat_risk(threat, asset)
    time_penalty = min(3.0, intercept_time * 0.012)
    resource_penalty = interceptor.cost * 0.35
    energy_penalty = 0.65 * distance / max(effective_range, 1.0)
    # A modest switching cost prevents assignments from oscillating every
    # auction round while leaving a newly critical track able to win a rebid.
    continuity_bonus = 0.65 * risk if interceptor.target_id == threat.id else 0.0
    utility = risk * probability - time_penalty - resource_penalty - energy_penalty + continuity_bonus
    return PairScore(
        interceptor.id,
        threat.id,
        True,
        utility,
        intercept_time,
        point,
        probability,
        distance,
    )


def _hungarian(cost: list[list[float]]) -> list[int]:
    """Rectangular Hungarian algorithm; returns selected column per row."""
    n = len(cost)
    if n == 0:
        return []
    m = len(cost[0])
    if m < n:
        raise ValueError("Hungarian implementation requires columns >= rows")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                current = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if current < minv[j]:
                    minv[j] = current
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            assignment[p[j] - 1] = j - 1
    return assignment


def allocate_swarmshield(
    interceptors: list[Interceptor],
    threats: list[Threat],
    assets: dict[str, Asset],
) -> tuple[dict[str, str], dict[tuple[str, str], PairScore]]:
    available = [i for i in interceptors if i.state not in {"failed", "spent"} and not i.committed]
    active = [t for t in threats if t.state == "active"]
    if not available or not active:
        return {}, {}
    scores: dict[tuple[str, str], PairScore] = {}
    rows: list[list[float]] = []
    for interceptor in available:
        utilities = []
        for threat in active:
            score = score_pair(interceptor, threat, assets[threat.asset_id])
            scores[(interceptor.id, threat.id)] = score
            utilities.append(score.utility if score.feasible else -1e6)
        # One zero-utility dummy per interceptor makes non-engagement explicit.
        utilities.extend([0.0] * len(available))
        rows.append([-value for value in utilities])
    columns = _hungarian(rows)
    result: dict[str, str] = {}
    for row, col in enumerate(columns):
        if 0 <= col < len(active):
            score = scores[(available[row].id, active[col].id)]
            if score.feasible and score.utility > 0:
                result[available[row].id] = active[col].id
    return result, scores


def allocate_baseline(
    interceptors: list[Interceptor], threats: list[Threat], assets: dict[str, Asset]
) -> dict[str, str]:
    """Naive one-round-per-target baseline: nearest feasible pair first."""
    pairs: list[tuple[float, str, str]] = []
    for interceptor in interceptors:
        if interceptor.state in {"failed", "spent"}:
            continue
        for threat in threats:
            if threat.state != "active":
                continue
            score = score_pair(interceptor, threat, assets[threat.asset_id])
            if score.feasible:
                pairs.append((interceptor.position.distance_to(threat.position), interceptor.id, threat.id))
    assignments: dict[str, str] = {}
    used_targets: set[str] = set()
    for _, interceptor_id, threat_id in sorted(pairs):
        if interceptor_id in assignments or threat_id in used_targets:
            continue
        assignments[interceptor_id] = threat_id
        used_targets.add(threat_id)
    return assignments
