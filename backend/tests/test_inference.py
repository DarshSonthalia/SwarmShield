import inspect
import numpy as np
import pytest
from pydantic import ValidationError
from app.models import Track, Observation, SimulationConfig
from app.simulation.inference import infer
from app.simulation.uncertainty import normalized_entropy, heading_statistics, angular_difference
from app.simulation.consequence import expected_consequence
from app.simulation.priority import score_priority

def simple_track(config):
    return Track(id='T01',position=(0,10,0),noise_level=.1,maneuver_uncertainty=.02,probabilities={d.id:1/8 for d in config.destinations})

def radial_config(config):
    for i,d in enumerate(config.destinations):
        angle=i*np.pi/4
        d.position=(float(40*np.cos(angle)),0,float(40*np.sin(angle)))
    return config

def test_entropy_uniform_is_maximal():
    assert normalized_entropy(np.ones(8)/8)==pytest.approx(1)

def test_entropy_certain_is_zero():
    assert normalized_entropy(np.array([1,0,0,0]))==0

def test_entropy_single_class_is_zero():
    assert normalized_entropy(np.array([1]))==0

def test_circular_heading_wrap_is_stable():
    variance,stability=heading_statistics([np.pi-.01,-np.pi+.01,np.pi])
    assert variance<.001 and stability>.99

def test_direction_changes_reduce_stability():
    variance,stability=heading_statistics([0,1,2,3])
    assert variance>.3 and stability<.1

def test_angular_difference_uses_shortest_arc():
    assert angular_difference(np.pi-.1,-np.pi+.1)==pytest.approx(.2)

def test_initial_inference_remains_broad(config):
    c=radial_config(config);t=simple_track(c)
    infer(t,Observation(time=0,position=(0,10,0),velocity=(.2,0,0),heading=0),c)
    assert max(t.probabilities.values())<.4 and t.entropy>.8

def test_consistent_heading_identifies_aligned_destination(config):
    c=radial_config(config);t=simple_track(c)
    for time in range(0,62,2):
        infer(t,Observation(time=time,position=(0,10,0),velocity=(.2,0,0),heading=0),c)
    assert max(t.probabilities,key=t.probabilities.get)=='A01'
    assert t.probabilities['A01']>.95 and t.confidence>.85

def test_major_turn_reopens_uncertainty(config):
    c=radial_config(config);t=simple_track(c)
    for time in range(0,42,2):
        infer(t,Observation(time=time,position=(0,10,0),velocity=(.2,0,0),heading=0),c)
    old=t.entropy
    infer(t,Observation(time=42,position=(0,10,0),velocity=(0,0,.2),heading=np.pi/2),c)
    assert t.entropy>old and t.last_major_turn==42
    assert t.event_history

def test_inference_eventually_follows_new_heading(config):
    c=radial_config(config);t=simple_track(c)
    for time in range(0,82,2):
        heading=0 if time<40 else np.pi/2
        infer(t,Observation(time=time,position=(0,10,0),velocity=(.2*np.cos(heading),0,.2*np.sin(heading)),heading=heading),c)
    assert t.probabilities['A03']>.9

def test_inference_has_no_ground_truth_argument():
    assert list(inspect.signature(infer).parameters)==['track','observation','config']
    assert 'true_destination' not in Track.model_fields

def test_consequence_is_weighted_expectation(config):
    probabilities={d.id:0 for d in config.destinations};probabilities['A01']=.75;probabilities['A08']=.25
    assert expected_consequence(probabilities,config.destinations)==pytest.approx(.75*.97+.25*.04)

def test_water_consequence_is_nonzero(config):
    p={d.id:float(d.id=='A08') for d in config.destinations}
    assert expected_consequence(p,config.destinations)==.04

def test_priority_increases_with_consequence(config):
    t=simple_track(config);t.confidence=.8;t.entropy=.2;t.expected_consequence=.2
    score_priority(t,config,.4);low=t.priority
    t.expected_consequence=.9;score_priority(t,config,.4)
    assert t.priority>low

def test_priority_components_explain_exact_score(config):
    t=simple_track(config);t.confidence=.7;t.expected_consequence=.8;t.escalation=.4
    score_priority(t,config,.4);f=t.factors
    assert t.priority==pytest.approx(f.consequence_term+f.uncertainty_term+f.escalation_term+f.scarcity_term-f.reassignment_penalty)

def test_scarcity_favors_high_consequence(config):
    t=simple_track(config);t.expected_consequence=.9
    score_priority(t,config,0);old=t.priority
    score_priority(t,config,1)
    assert t.priority>old

def test_existing_assignment_has_retention_advantage(config):
    t=simple_track(config);t.expected_consequence=.8
    score_priority(t,config,.4);old=t.priority
    t.assigned_resource='I01';score_priority(t,config,.4)
    assert t.priority-old==pytest.approx(config.priority.switching_penalty)

def test_priority_is_bounded(config):
    t=simple_track(config);t.expected_consequence=t.confidence=t.escalation=t.entropy=1
    score_priority(t,config,1)
    assert 0<=t.priority<=1

def test_config_rejects_invalid_capacity(config):
    values=config.model_dump();values['resource_count']=0
    with pytest.raises(ValidationError):SimulationConfig.model_validate(values)

def test_config_rejects_duplicate_destinations(config):
    values=config.model_dump();values['destinations'][1]['id']='A01'
    with pytest.raises(ValidationError):SimulationConfig.model_validate(values)

def test_config_rejects_allocation_without_fresh_observations(config):
    values=config.model_dump();values['allocation_interval']=3
    with pytest.raises(ValidationError):SimulationConfig.model_validate(values)

def test_config_rejects_unknown_fields(config):
    values=config.model_dump();values['guidance_model']='real'
    with pytest.raises(ValidationError):SimulationConfig.model_validate(values)
