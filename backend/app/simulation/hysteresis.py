from ..models import Track, Resource, HysteresisConfig

def low_consequence_evidence(track: Track, time: int, config: HysteresisConfig) -> bool:
    return (track.probabilities['A08'] >= config.water_probability
        and track.expected_consequence <= config.release_consequence
        and track.confidence >= config.release_confidence
        and time-track.last_major_turn >= config.turn_quiet_period)

def may_switch(resource: Resource, time: int, config: HysteresisConfig) -> bool:
    return (resource.assignment_start is not None
        and time-resource.assignment_start >= config.minimum_assignment_duration
        and time-resource.last_change >= config.reassignment_cooldown)

def release_ready(track: Track, resource: Resource, time: int, config: HysteresisConfig) -> bool:
    return track.low_consequence_cycles >= config.release_persistence_cycles and may_switch(resource,time,config)
