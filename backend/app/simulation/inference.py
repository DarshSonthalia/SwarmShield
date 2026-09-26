"""Observation-only geometric intent estimator; no access to hidden tracks."""
import numpy as np
from ..models import Track, SimulationConfig, Observation
from .uncertainty import angular_difference, heading_statistics, normalized_entropy
from .consequence import expected_consequence

def infer(track: Track, observation: Observation, config: SimulationConfig) -> None:
    previous = track.observations[-1] if track.observations else None
    changed = previous is not None and angular_difference(previous.heading, observation.heading) > config.uncertainty.major_turn_radians
    if changed:
        track.last_major_turn = observation.time
        track.event_history.append(f'T+{observation.time:03}: observed heading change; evidence confidence reduced.')
        track.event_history = track.event_history[-12:]
    track.observations.append(observation)
    # Retain enough history for the evidence model; visible inspector shows recent rows.
    track.observations = track.observations[-32:]
    track.velocity = observation.velocity
    track.heading = observation.heading
    headings = [o.heading for o in track.observations[-5:]]
    track.heading_variance, track.stability = heading_statistics(headings)
    stable_time = max(0, observation.time-track.last_major_turn)
    evidence = min(1, len(track.observations)/config.uncertainty.evidence_cycles)
    recovery = min(1, stable_time/12)
    reliability = evidence * track.stability * recovery * (1-track.maneuver_uncertainty*.7)
    concentration = config.uncertainty.initial_concentration + config.uncertainty.max_concentration*reliability
    pos = np.array(observation.position)[[0,2]]
    # Filter recent headings so one noisy measurement cannot dominate.
    velocity = np.mean([np.array(o.velocity)[[0,2]] for o in track.observations[-3:]], axis=0)
    velocity /= max(np.linalg.norm(velocity), 1e-9)
    scores = []
    for dest in config.destinations:
        delta = np.array(dest.position)[[0,2]]-pos
        distance = np.linalg.norm(delta)
        alignment = np.dot(delta/max(distance, 1e-9), velocity)
        scores.append(concentration*alignment - .12*np.log1p(distance/30))
    scores = np.array(scores)
    likelihood = np.exp(scores-np.max(scores))
    likelihood /= likelihood.sum()
    old = np.array([track.probabilities[d.id] for d in config.destinations])
    # A turn discards stale certainty; subsequent evidence gradually sharpens it.
    update = .72 if changed else .5
    p = (1-update)*old + update*likelihood
    uniform_mix = max(config.uncertainty.noise_floor, (1-reliability)*.12)
    p = (1-uniform_mix)*p + uniform_mix/len(p)
    p /= p.sum()
    track.probabilities = {d.id:float(p[i]) for i,d in enumerate(config.destinations)}
    track.entropy = normalized_entropy(p)
    track.confidence = float(np.clip((1-track.entropy)*.65 + reliability*.35, 0,1))
    old_consequence = track.expected_consequence
    track.expected_consequence = expected_consequence(track.probabilities, config.destinations)
    recent_change = max(0, 1-stable_time/12)
    track.escalation = float(np.clip(max(0,track.expected_consequence-old_consequence)*4 + recent_change*.3, 0,1))
