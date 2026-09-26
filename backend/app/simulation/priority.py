import numpy as np
from ..models import Track, SimulationConfig, ReasonFactors

def score_priority(track: Track, config: SimulationConfig, scarcity: float) -> None:
    observed_position = np.array(track.observations[-1].position) if track.observations else np.array(track.position)
    distance = sum(track.probabilities[d.id]*np.linalg.norm((np.array(d.position)-observed_position)[[0,2]]) for d in config.destinations)
    track.urgency = float(np.clip(1-distance/110, .12, .98))
    w = config.priority
    consequence_term = w.consequence * track.expected_consequence * (.55+.45*track.urgency) * (.6+.4*track.confidence)
    uncertainty_term = w.uncertainty * track.entropy * track.expected_consequence
    escalation_term = w.escalation * track.escalation
    scarcity_term = w.scarcity * scarcity * track.expected_consequence**2
    penalty = w.switching_penalty if track.assigned_resource is None else 0
    track.priority = float(np.clip(consequence_term+uncertainty_term+escalation_term+scarcity_term-penalty, 0,1))
    track.factors = ReasonFactors(expected_consequence=track.expected_consequence, confidence=track.confidence,
        uncertainty=track.entropy, urgency=track.urgency, escalation=track.escalation, scarcity=scarcity,
        reassignment_penalty=penalty, persistence=track.low_consequence_cycles,
        consequence_term=consequence_term, uncertainty_term=uncertainty_term,
        escalation_term=escalation_term, scarcity_term=scarcity_term)
