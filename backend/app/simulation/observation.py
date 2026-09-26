import numpy as np
from ..models import Observation, Track
from .tracks import HiddenTrack

def observe(hidden: HiddenTrack, track: Track, time: int, rng: np.random.Generator) -> Observation:
    # The only bridge into inference: noisy measurements, never an intent label.
    decay = .45 + .55*np.exp(-time/22)
    pos = hidden.position + rng.normal(0, track.noise_level*decay, 3)
    vel = hidden.velocity + rng.normal(0, .011*decay*(1+track.maneuver_uncertainty*6), 3)
    vel[1] = 0
    return Observation(time=time, position=tuple(pos), velocity=tuple(vel), heading=float(np.arctan2(vel[2],vel[0])))
