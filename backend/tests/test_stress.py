from app.simulation.stress import aggregate_runs

def test_stress_aggregation_uses_real_metric_names_and_is_deterministic():
    runs=[
        {'seed':1,'swarmshield':{'critical_tracks_covered':8,'critical_tracks':10,'cumulative_exposure':80.0},'baseline':{'critical_tracks_covered':5,'critical_tracks':10,'cumulative_exposure':100.0}},
        {'seed':2,'swarmshield':{'critical_tracks_covered':9,'critical_tracks':10,'cumulative_exposure':90.0},'baseline':{'critical_tracks_covered':6,'critical_tracks':10,'cumulative_exposure':120.0}},
    ]
    summary=aggregate_runs(runs)
    assert summary=={
        'swarmshield_mean_critical_coverage':0.85,
        'baseline_mean_critical_coverage':0.55,
        'swarmshield_mean_cumulative_exposure':85.0,
        'baseline_mean_cumulative_exposure':110.0,
        'mean_exposure_reduction_percent':22.5,
        'runs_swarmshield_lower_exposure':2,
    }
