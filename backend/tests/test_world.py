import numpy as np
import pytest
from app.simulation.world import World,validate_frame
from app.simulation.consequence import expected_consequence

def test_default_scarcity_and_world_shape(world):
    assert len(world.frames)==121 and len(world.frames[0].tracks)==20 and len(world.frames[0].resources)==12
    assert len(world.config.destinations)==8 and len(world.config.sites)==8

def test_every_probability_in_every_frame_is_valid(world):
    for f in world.frames:
        for t in f.tracks:
            assert set(t.probabilities)=={d.id for d in world.config.destinations}
            assert min(t.probabilities.values())>=0
            assert sum(t.probabilities.values())==pytest.approx(1,abs=1e-12)

def test_expected_consequence_matches_full_distribution(world):
    for f in world.frames:
        for t in f.tracks:assert t.expected_consequence==pytest.approx(expected_consequence(t.probabilities,world.config.destinations))

def test_all_frames_obey_assignment_integrity(world):
    for f in world.frames:validate_frame(f,{d.id for d in world.config.destinations})

def test_no_commitment_before_detection_window(world):
    assert all(not f.assignments for f in world.frames[:12])
    assert len(world.frames[12].assignments)>0

def test_resources_start_and_remain_at_staging_until_visual_launch(world):
    sites={s.id:s.position for s in world.config.sites}
    for f in world.frames[:15]:
        for r in f.resources:assert r.position==sites[r.site_id]
    assert any(r.position!=sites[r.site_id] for r in world.frames[18].resources)

def test_observation_precedes_inference_and_allocation(world):
    for a in world.audit:
        t=next(t for t in world.frames[a.time].tracks if t.id==a.track_id)
        assert t.observations[-1].time==a.time
        assert a.priority==t.priority and a.factors.confidence==t.confidence

def test_last_transaction_at_each_timestamp_matches_visible_frame(world):
    for f in world.frames:
        events=[a for a in world.audit if a.time<=f.time]
        assert f.audit_count==len(events)
        assert f.assignments==(events[-1].assignments if events else {})

def test_audit_transactions_reconstruct_the_assignment_map(world):
    state={}
    for a in world.audit:
        if a.action in ('ASSIGN','REALLOCATE'):state[a.resource_id]=a.track_id
        elif a.action in ('RELEASE','DISPLACE'):state.pop(a.resource_id)
        assert state==a.assignments

def test_same_timestamp_release_and_assign_are_in_visible_order(world):
    release=next(a for a in world.audit if a.action=='RELEASE')
    same=[a for a in world.audit if a.time==release.time]
    assert [a.action for a in same][-2:]==['RELEASE','ASSIGN']
    assert world.frame(release.time).assignments==same[-1].assignments

def test_same_seed_reproduces_complete_timeline(world,config):
    other=World(config)
    assert world.run().model_dump()==other.run().model_dump()

def test_new_seed_changes_observations(config,world):
    config.seed+=1;config.duration=20
    other=World(config)
    assert other.frames[0].tracks[0].observations!=world.frames[0].tracks[0].observations

def test_random_access_scrubbing_does_not_mutate_frames(world):
    before=world.frame(52).model_dump()
    for time in [120,0,84,11,52,12]:world.frame(time)
    assert world.frame(52).model_dump()==before

def test_returned_frame_is_isolated(world):
    f=world.frame(40);f.tracks[0].position=(999,999,999);f.assignments.clear()
    assert world.frame(40).tracks[0].position!=(999,999,999)
    assert world.frame(40).assignments

def test_fractional_time_uses_last_completed_decision_frame(world):
    assert world.frame(11.999).time==11 and not world.frame(11.999).assignments
    assert world.frame(12).assignments

@pytest.mark.parametrize('time',[-1,121,float('nan'),float('inf')])
def test_out_of_bounds_time_is_rejected(world,time):
    with pytest.raises(ValueError):world.frame(time)

def test_water_reveal_is_assigned_then_released_with_evidence(world):
    entries=[a for a in world.audit if a.track_id=='T11']
    release=next(a for a in entries if a.action=='RELEASE')
    assert any(a.action=='ASSIGN' and a.time<release.time for a in entries)
    assert any(a.action=='HOLD' and a.time<release.time for a in entries)
    assert release.factors.persistence>=4 and release.factors.confidence>=.65
    assert world.frame(release.time).tracks[10].assigned_resource is None
    assert world.frames[-1].tracks[10].observations[-1].time==120

def test_airport_turn_raises_priority_and_gains_assignment(world):
    early=world.frame(64).tracks[16];late=world.frame(100).tracks[16]
    assert late.probabilities['A01']>early.probabilities['A01']
    assert late.priority>early.priority and late.assigned_resource is not None
    assert any(a.track_id=='T17' and a.action=='REALLOCATE' for a in world.audit)

def test_ambiguous_track_stays_unassigned_and_monitored(world):
    assert all(f.tracks[13].assigned_resource is None for f in world.frames)
    assert world.frames[-1].tracks[13].observations[-1].time==120

def test_brief_turn_preserves_t03_resource(world):
    assert world.frame(48).tracks[2].assigned_resource is not None
    assert world.frame(48).tracks[2].assigned_resource==world.frame(58).tracks[2].assigned_resource

def test_resource_motion_never_teleports_on_assignment_changes(world):
    for before,after in zip(world.frames,world.frames[1:]):
        for a,b in zip(before.resources,after.resources):
            assert np.linalg.norm(np.array(a.position)-np.array(b.position))<12

def test_metrics_account_for_all_resources(world):
    for f in world.frames:
        m=f.metrics
        assert m.resources_available+m.resources_committed==12
        assert m.resources_committed==len(f.assignments)

def test_metrics_exposure_is_uncovered_expectation(world):
    for f in world.frames:
        assert f.metrics.swarm.exposure==pytest.approx(sum(t.expected_consequence for t in f.tracks if t.assigned_resource is None))

def test_cumulative_exposure_integrates_preceding_frames(world):
    for key in ['swarm','baseline']:
        actual=getattr(world.frames[-1].metrics,key).cumulative_exposure
        expected=sum(getattr(f.metrics,key).exposure for f in world.frames[:-1])
        assert actual==pytest.approx(expected)

def test_baseline_retains_first_twelve_tracks(world):
    for f in world.frames[12:]:assert list(f.baseline_assignments.values())==[f'T{i:02}' for i in range(1,13)]

def test_authored_scenario_outperforms_baseline_on_coverage_and_exposure(world):
    m=world.frames[-1].metrics
    assert m.swarm.critical_tracks_covered>m.baseline.critical_tracks_covered
    assert m.swarm.cumulative_exposure<m.baseline.cumulative_exposure
    assert m.swarm.low_consequence_commitments<m.baseline.low_consequence_commitments

def test_audit_actions_have_structured_reasons_and_monotonic_ids(world):
    assert [a.id for a in world.audit]==list(range(1,len(world.audit)+1))
    assert all(a.reason and 0<=a.factors.expected_consequence<=1 for a in world.audit)

def test_invariant_rejects_duplicate_assignment(world):
    f=world.frame(24);r1,r2=list(f.assignments)[:2];f.assignments[r2]=f.assignments[r1]
    with pytest.raises(AssertionError):validate_frame(f,{d.id for d in world.config.destinations})

def test_invariant_rejects_negative_probability(world):
    f=world.frame(24);f.tracks[0].probabilities['A01']=-.2
    with pytest.raises(AssertionError):validate_frame(f,{d.id for d in world.config.destinations})
