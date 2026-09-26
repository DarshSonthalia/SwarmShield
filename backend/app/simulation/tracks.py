"""Fictional motion authoring. Only this module sees hidden intent.

Coordinates and speeds are arbitrary scene units, with no real-world mapping.
"""
from dataclasses import dataclass
import numpy as np
from ..models import SimulationConfig, Track

@dataclass
class HiddenTrack:
    id: str
    true_destination: str
    position: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray
    speed: float
    behavior: str

def create_tracks(config: SimulationConfig, rng: np.random.Generator) -> tuple[list[HiddenTrack], list[Track]]:
    # Authored positions intentionally offer different geometric evidence quality.
    specs = [
        ('A06',(-58,12,2),'steady'), ('A03',(65,10,18),'steady'),
        ('A04',(-56,11,42),'brief_turn'), ('A07',(42,12,-56),'steady'),
        ('A08',(66,10,58),'steady'), ('A06',(-60,13,-10),'steady'),
        ('A03',(58,11,45),'steady'), ('A08',(74,12,37),'steady'),
        ('A07',(64,10,-31),'steady'), ('A06',(-50,12,-38),'steady'),
        ('A08',(62,15,-3),'water_reveal'), ('A08',(25,11,65),'steady'),
        ('A02',(-8,16,62),'steady'), ('A08',(64,15,62),'ambiguous'),
        ('A01',(-30,14,-64),'steady'), ('A05',(7,16,-64),'steady'),
        ('A01',(-57,12,-28),'late_airport'), ('A04',(-58,13,22),'power_escalation'),
        ('A05',(30,13,-61),'civic_escalation'), ('A02',(3,15,62),'steady'),
    ]
    hidden, visible = [], []
    dests = {d.id: np.array(d.position) for d in config.destinations}
    for i, (dest, pos, behavior) in enumerate(specs[:config.track_count]):
        position = np.array(pos, dtype=float)
        position[[0,2]] += rng.normal(0, .35, 2)
        speed = float(rng.uniform(.19,.28))
        target = dests['A02' if behavior == 'water_reveal' else 'A08' if 'escalation' in behavior or behavior == 'late_airport' else dest].copy()
        target[1] = position[1]
        direction = target-position
        velocity = direction / max(np.linalg.norm(direction), 1e-8) * speed
        tid = f'T{i+1:02}'
        hidden.append(HiddenTrack(tid, dest, position, velocity, np.zeros(3), speed, behavior))
        visible.append(Track(id=tid, position=tuple(position), altitude=float(position[1]), noise_level=.25 if behavior != 'ambiguous' else 1.4,
                             maneuver_uncertainty=.08 if behavior != 'ambiguous' else .82,
                             probabilities={d.id:1/len(dests) for d in config.destinations}))
    return hidden, visible

def advance_motion(track: HiddenTrack, time: int, config: SimulationConfig) -> None:
    destinations = {d.id: np.array(d.position) for d in config.destinations}
    intent = track.true_destination
    if track.behavior == 'water_reveal' and time < 32:
        intent = 'A02'
    if track.behavior == 'late_airport' and time < 66:
        intent = 'A08'
    if track.behavior == 'power_escalation' and time < 76:
        intent = 'A08'
    if track.behavior == 'civic_escalation' and time < 76:
        intent = 'A08'
    target = destinations[intent].copy()
    target[1] = track.position[1]
    delta = target-track.position
    desired = delta / max(np.linalg.norm(delta), 1e-8) * track.speed
    if track.behavior == 'brief_turn' and 50 <= time < 54:
        desired = np.array([-desired[2], 0, desired[0]])
    if track.behavior == 'ambiguous':
        angle = time*.16
        desired = np.array([np.cos(angle),0,np.sin(angle)]) * track.speed
    old_velocity = track.velocity.copy()
    track.velocity += .22 * (desired-track.velocity)
    track.acceleration = track.velocity-old_velocity
    track.position += (track.velocity+old_velocity)*.5
