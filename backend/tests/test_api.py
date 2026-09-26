import pytest
from fastapi.testclient import TestClient
from app import main

@pytest.fixture
def client(world,monkeypatch):
    monkeypatch.setattr(main,'world',world)
    original=world.cursor
    with TestClient(main.app) as c:yield c
    world.cursor=original

def test_health_and_scenario_contract(client):
    assert client.get('/health').json()['status']=='ok'
    scenario=client.get('/api/scenario').json()
    assert len(scenario['config']['destinations'])==8 and len(scenario['events'])>=5

def test_config_is_exposed(client):
    assert client.get('/api/config').json()['seed']==2407

def test_frame_endpoint_returns_completed_allocation(client):
    f=client.get('/api/frame/12').json()
    assert f['assignments'] and f['audit_count']>0

def test_frame_endpoint_rejects_invalid_time(client):
    assert client.get('/api/frame/-1').status_code==422

def test_track_detail_respects_requested_frame(client):
    t=client.get('/api/tracks/T11?time=52').json()
    assert t['state']=='RELEASE' and t['assigned_resource'] is None

def test_unknown_track_and_resource_return_404(client):
    assert client.get('/api/tracks/T99').status_code==404
    assert client.get('/api/resources/I99').status_code==404

def test_audit_does_not_leak_future_decisions(client):
    entries=client.get('/api/audit?time=40&track_id=T11').json()
    assert entries and all(a['time']<=40 and a['track_id']=='T11' for a in entries)
    assert not any(a['action']=='RELEASE' for a in entries)

def test_step_moves_cursor_and_clamps_to_duration(client):
    assert client.post('/api/step',json={'seconds':120}).json()['time']==120
    assert client.post('/api/step',json={'seconds':1}).json()['time']==120

def test_step_rejects_negative_duration(client):
    assert client.post('/api/step',json={'seconds':-1}).status_code==422

def test_run_is_non_mutating_replay_bundle(client,world):
    old=world.cursor;r=client.post('/api/run').json()
    assert len(r['frames'])==121 and world.cursor==old

def test_resource_and_metrics_endpoints_share_timestamp(client):
    f=client.get('/api/frame/52').json();resources=client.get('/api/resources?time=52').json()
    assert resources==f['resources'] and client.get('/api/metrics?time=52').json()==f['metrics']

def test_baseline_endpoint_uses_same_frame(client):
    b=client.get('/api/baseline?time=84').json()
    assert b['time']==84 and len(b['assignments'])==12

def test_reset_reproduces_default_and_resets_cursor(client):
    f=client.post('/api/reset',json={}).json()
    assert f['time']==0 and not f['assignments'] and main.world.cursor==0

def test_reset_rejects_negative_seed(client):
    assert client.post('/api/reset',json={'seed':-1}).status_code==422
