from statistics import fmean

def aggregate_runs(runs: list[dict]) -> dict:
    def coverage(policy: str, run: dict) -> float:
        metrics=run[policy]
        return metrics['critical_tracks_covered']/max(1,metrics['critical_tracks'])
    reductions=[100*(1-run['swarmshield']['cumulative_exposure']/run['baseline']['cumulative_exposure']) if run['baseline']['cumulative_exposure'] else 0 for run in runs]
    return {
        'swarmshield_mean_critical_coverage':round(fmean(coverage('swarmshield',run) for run in runs),6),
        'baseline_mean_critical_coverage':round(fmean(coverage('baseline',run) for run in runs),6),
        'swarmshield_mean_cumulative_exposure':round(fmean(run['swarmshield']['cumulative_exposure'] for run in runs),6),
        'baseline_mean_cumulative_exposure':round(fmean(run['baseline']['cumulative_exposure'] for run in runs),6),
        'mean_exposure_reduction_percent':round(fmean(reductions),6),
        'runs_swarmshield_lower_exposure':sum(run['swarmshield']['cumulative_exposure']<run['baseline']['cumulative_exposure'] for run in runs),
    }
