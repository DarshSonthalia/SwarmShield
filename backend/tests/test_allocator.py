import pytest
from app.models import Track
from app.simulation.allocator import Allocator
from app.simulation.resources import create_resources
from app.simulation.hysteresis import low_consequence_evidence, may_switch

def setup(config):
    config.resource_count=1
    tracks=[Track(id=f'T{i+1:02}',position=(0,10,0),noise_level=.1,maneuver_uncertainty=.1,confidence=.9,
        expected_consequence=.8,priority=.5,probabilities={d.id:1/8 for d in config.destinations}) for i in range(3)]
    return Allocator(config),tracks,create_resources(config),[]

def water(track):
    track.probabilities={k:(.93 if k=='A08' else .01) for k in track.probabilities}
    track.expected_consequence=.12;track.confidence=.9;track.priority=.10

def test_initial_window_preserves_all_capacity(config):
    a,t,r,log=setup(config);a.cycle(t,r,10,log)
    assert r[0].assigned_track is None and not log

def test_scarcity_assigns_highest_ranked_candidate(config):
    a,t,r,log=setup(config);t[2].priority=.9;a.cycle(t,r,12,log)
    assert r[0].assigned_track=='T03'
    assert sum(x.assigned_resource is not None for x in t)==1

def test_ties_are_resolved_deterministically(config):
    a,t,r,log=setup(config);a.cycle(t[::-1],r,12,log)
    assert r[0].assigned_track=='T01'

def test_low_confidence_is_monitored_without_commitment(config):
    a,t,r,log=setup(config)
    for x in t:x.confidence=.01
    a.cycle(t,r,12,log)
    assert not a.mapping(r) and all(x.state=='HOLD' for x in t)

def test_minimum_duration_prevents_immediate_challenger(config):
    a,t,r,log=setup(config);a.cycle(t,r,12,log);t[1].priority=.99
    for time in [14,16,18,20,22]:a.cycle(t,r,time,log)
    assert r[0].assigned_track=='T01'

def test_challenger_must_persist_for_three_cycles(config):
    a,t,r,log=setup(config);a.cycle(t,r,12,log);t[1].priority=.9
    a.cycle(t,r,24,log);a.cycle(t,r,26,log)
    assert r[0].assigned_track=='T01'
    a.cycle(t,r,28,log)
    assert r[0].assigned_track=='T02' and t[0].assigned_resource is None
    assert log[-1].action=='REALLOCATE'

def test_below_margin_never_switches(config):
    a,t,r,log=setup(config);a.cycle(t,r,12,log);t[1].priority=.54
    for time in range(24,60,2):a.cycle(t,r,time,log)
    assert r[0].assigned_track=='T01'

def test_broken_challenger_persistence_resets(config):
    a,t,r,log=setup(config);a.cycle(t,r,12,log);t[1].priority=.9
    a.cycle(t,r,24,log);t[1].priority=.52;a.cycle(t,r,26,log);t[1].priority=.9
    a.cycle(t,r,28,log);a.cycle(t,r,30,log)
    assert r[0].assigned_track=='T01'

def test_reassignment_cooldown_prevents_ping_pong(config):
    a,t,r,log=setup(config);a.cycle(t,r,12,log);t[1].priority=.9
    for time in [24,26,28]:a.cycle(t,r,time,log)
    t[0].priority=1;t[1].priority=.4
    for time in [30,32,34,36,38]:a.cycle(t,r,time,log)
    assert r[0].assigned_track=='T02'
    assert not may_switch(r[0],38,config.hysteresis)

def test_release_requires_four_qualifying_cycles(config):
    a,t,r,log=setup(config);a.assign(t[0],r[0],12,log,r);water(t[0])
    for x in t[1:]:x.priority=0
    for time in [30,32,34]:a.cycle(t,r,time,log)
    assert r[0].assigned_track=='T01'
    a.cycle(t,r,36,log)
    assert r[0].assigned_track is None and t[0].state=='RELEASE'
    assert log[-1].action=='RELEASE' and log[-1].factors.persistence==4

def test_challenger_cannot_bypass_water_release_gates(config):
    a,t,r,log=setup(config);a.assign(t[0],r[0],12,log,r);water(t[0]);t[0].confidence=.2;t[1].priority=.99
    for time in range(24,60,2):a.cycle(t,r,time,log)
    assert r[0].assigned_track=='T01' and not any(x.action=='DISPLACE' for x in log)

def test_release_immediately_makes_capacity_available_to_candidate(config):
    a,t,r,log=setup(config);a.assign(t[0],r[0],12,log,r);water(t[0]);t[1].priority=.9
    for time in [30,32,34,36]:a.cycle(t,r,time,log)
    assert r[0].assigned_track=='T02' and t[0].assigned_resource is None
    assert [x.action for x in log if x.time==36]==['RELEASE','ASSIGN']

def test_recent_turn_blocks_low_consequence_release(config):
    _,t,_,_=setup(config);water(t[0]);t[0].last_major_turn=25
    assert not low_consequence_evidence(t[0],30,config.hysteresis)

def test_low_water_probability_blocks_release(config):
    _,t,_,_=setup(config);water(t[0]);t[0].probabilities['A08']=.6
    assert not low_consequence_evidence(t[0],30,config.hysteresis)

def test_high_consequence_blocks_water_release(config):
    _,t,_,_=setup(config);water(t[0]);t[0].expected_consequence=.5
    assert not low_consequence_evidence(t[0],30,config.hysteresis)

def test_release_evidence_resets_when_a_gate_fails(config):
    a,t,r,log=setup(config);a.assign(t[0],r[0],12,log,r);water(t[0]);a.cycle(t,r,30,log);a.cycle(t,r,32,log)
    t[0].last_major_turn=33;a.cycle(t,r,34,log)
    assert t[0].low_consequence_cycles==0 and r[0].assigned_track=='T01'

def test_audit_keeps_immutable_transaction_snapshots(config):
    a,t,r,log=setup(config);a.cycle(t,r,12,log)
    saved=log[0].model_dump();t[0].factors.confidence=0;t[0].probabilities['A01']=.9
    assert log[0].model_dump()==saved
