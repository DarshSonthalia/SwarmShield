from ..models import Track, Resource, AuditEntry, ComparisonMetrics, Metrics, SimulationConfig

def comparison(tracks: list[Track], assignments: dict[str,str], capacity: int, reassignments: int, cumulative: float, config: SimulationConfig) -> ComparisonMetrics:
    covered = set(assignments.values())
    critical = [t for t in tracks if t.expected_consequence >= .72]
    weights = {d.id:d.weight for d in config.destinations}
    assets = {max(t.probabilities,key=t.probabilities.get) for t in critical if t.id in covered}
    return ComparisonMetrics(critical_tracks_covered=sum(t.id in covered for t in critical), critical_tracks=len(critical),
        exposure=sum(t.expected_consequence for t in tracks if t.id not in covered), cumulative_exposure=cumulative,
        low_consequence_commitments=sum(t.expected_consequence < .3 and t.id in covered for t in tracks),
        reassignments=reassignments, utilization=len(covered)/capacity,
        stability=max(0,1-reassignments/max(1,len(assignments)+reassignments)),
        critical_assets_covered=sum(weights[d]>=.9 for d in assets))

def compute_metrics(tracks: list[Track], resources: list[Resource], assignments: dict[str,str], baseline: dict[str,str], audit: list[AuditEntry], cumulative: dict[str,float], config: SimulationConfig) -> Metrics:
    swaps = sum(a.action=='REALLOCATE' for a in audit)
    swarm = comparison(tracks,assignments,len(resources),swaps,cumulative['swarm'],config)
    base = comparison(tracks,baseline,len(resources),0,cumulative['baseline'],config)
    return Metrics(total_tracks=len(tracks),active_tracks=len(tracks), resources_available=len(resources)-len(assignments),resources_committed=len(assignments),
        high_consequence_tracks=swarm.critical_tracks,low_consequence_tracks=sum(t.expected_consequence<.3 for t in tracks),
        mean_confidence=sum(t.confidence for t in tracks)/len(tracks),mean_uncertainty=sum(t.entropy for t in tracks)/len(tracks),
        assignment_changes=sum(a.action in ('ASSIGN','RELEASE','REALLOCATE','DISPLACE') for a in audit),
        released_resources=sum(a.action=='RELEASE' for a in audit),critical_assets_covered=swarm.critical_assets_covered,swarm=swarm,baseline=base)
