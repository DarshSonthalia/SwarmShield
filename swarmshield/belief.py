from __future__ import annotations

import math

from .models import Asset, ObservedThreat, ThreatBelief, TrackObservation, Vec2

HISTORY_LIMIT = 5
SOFTMAX_TEMPERATURE = 0.35
MISS_DISTANCE_SCALE_M = 2400.0
MIN_PLAUSIBLE_PROBABILITY = 0.10
PLAUSIBLE_RELATIVE_TO_TOP = 0.25
MAX_UNCERTAINTY_FRICTION = 18.0


def _smoothed_velocity(current: Vec2, history: list[TrackObservation]) -> Vec2:
    velocities = [item.velocity for item in history[-HISTORY_LIMIT:]] or [current]
    return Vec2(
        sum(item.x for item in velocities) / len(velocities),
        sum(item.y for item in velocities) / len(velocities),
    )


def _geometry(position: Vec2, velocity: Vec2, asset: Asset) -> tuple[float, float | None]:
    speed_sq = velocity.x * velocity.x + velocity.y * velocity.y
    if speed_sq <= 1e-9:
        return 0.0, None
    dx, dy = asset.position.x - position.x, asset.position.y - position.y
    distance = math.hypot(dx, dy)
    speed = math.sqrt(speed_sq)
    alignment = (dx * velocity.x + dy * velocity.y) / max(distance * speed, 1e-9)
    approach = (dx * velocity.x + dy * velocity.y) / speed_sq
    if approach <= 0:
        return 2.0 * alignment - distance / MISS_DISTANCE_SCALE_M, None
    miss = math.hypot(dx - velocity.x * approach, dy - velocity.y * approach)
    return 2.0 * alignment - miss / MISS_DISTANCE_SCALE_M, approach


def _probabilities(scores: dict[str, float], stationary: bool) -> dict[str, float]:
    if stationary or not scores or not all(math.isfinite(value) for value in scores.values()):
        probability = 1.0 / max(len(scores), 1)
        return {key: probability for key in scores}
    maximum = max(scores.values())
    weights = {key: math.exp((value - maximum) / SOFTMAX_TEMPERATURE) for key, value in scores.items()}
    total = sum(weights.values())
    return {key: value / total for key, value in weights.items()}


def _entropy(probabilities: dict[str, float]) -> float:
    if len(probabilities) <= 1:
        return 0.0
    raw = -sum(value * math.log(value) for value in probabilities.values() if value > 0)
    return raw / math.log(len(probabilities))


def _urgency(approach_time: float | None) -> float:
    if approach_time is None or not math.isfinite(approach_time):
        return 0.0
    return min(1.0, 95.0 / max(approach_time, 1.0))


def _label(value: float) -> str:
    return "low" if value < .34 else "medium" if value < .67 else "high"


def build_threat_belief(
    observed: ObservedThreat,
    history: list[TrackObservation],
    assets: dict[str, Asset],
) -> ThreatBelief:
    velocity = _smoothed_velocity(observed.velocity, history)
    stationary = math.hypot(velocity.x, velocity.y) <= 1e-6
    geometry = {key: _geometry(observed.position, velocity, asset) for key, asset in assets.items()}
    probabilities = _probabilities({key: value[0] for key, value in geometry.items()}, stationary)
    approach_times = {key: value[1] for key, value in geometry.items()}
    top_id = max(sorted(probabilities), key=probabilities.get)
    expected = sum(probabilities[key] * assets[key].consequence for key in assets)
    urgency = sum(probabilities[key] * _urgency(approach_times[key]) for key in assets)
    threshold = max(MIN_PLAUSIBLE_PROBABILITY, probabilities[top_id] * PLAUSIBLE_RELATIVE_TO_TOP)
    plausible = [approach_times[key] for key in assets
                 if probabilities[key] >= threshold and approach_times[key] is not None]
    horizon = min(plausible, default=float("inf"))
    uncertainty = _entropy(probabilities)
    return ThreatBelief(
        observed.id, observed.time_s, probabilities, approach_times, top_id,
        probabilities[top_id], expected, uncertainty, _label(uncertainty), urgency,
        horizon, observed.p_hostile * expected * urgency,
    )


def uncertainty_friction(belief: ThreatBelief) -> float:
    return MAX_UNCERTAINTY_FRICTION * belief.uncertainty * (1.0 - belief.urgency)
