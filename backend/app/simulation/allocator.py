"""Scarce abstract capacity allocation. Operates only on estimated track fields."""
from ..models import Track, Resource, SimulationConfig, AuditEntry, AssignmentRecord
from .hysteresis import low_consequence_evidence, may_switch, release_ready
from .audit import record

class Allocator:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.contests: dict[tuple[str,str],int] = {}
        self.leaders: dict[str,str] = {}

    @staticmethod
    def mapping(resources: list[Resource]) -> dict[str,str]:
        return {r.id:r.assigned_track for r in resources if r.assigned_track is not None}

    def assign(self, track, resource, time, audit, resources, action='ASSIGN'):
        reason = 'Expected consequence and confidence justify scarce capacity; resource available.' if action == 'ASSIGN' else 'Challenger advantage persisted beyond the switching margin; minimum duration and cooldown satisfied.'
        resource.assigned_track,track.assigned_resource = track.id,resource.id
        resource.assignment_start = resource.last_change = time
        resource.state = 'ASSIGNED'
        track.state = 'COMMIT' if action == 'ASSIGN' else 'REALLOCATE'
        resource.reason = track.reason = reason
        item = AssignmentRecord(time=time,track_id=track.id,resource_id=resource.id,action=action,reason=reason)
        track.assignment_history.append(item)
        resource.assignment_history.append(item)
        record(audit,time,track,resource,action,reason,self.mapping(resources))

    def detach(self, track, resource, time, audit, resources, action='RELEASE'):
        reason = 'Persistent low-consequence evidence: open-water probability, confidence, quiet heading, and persistence gates satisfied. Monitoring continues.' if action == 'RELEASE' else 'Capacity moved to a persistently higher-priority track after hysteresis gates.'
        track.assigned_resource = resource.assigned_track = None
        track.state = 'RELEASE' if action == 'RELEASE' else 'HOLD'
        track.reason = resource.reason = reason
        resource.assignment_start = None
        resource.last_change = time
        resource.state = 'RETURNING'
        item = AssignmentRecord(time=time,track_id=track.id,resource_id=resource.id,action=action,reason=reason)
        track.assignment_history.append(item)
        resource.assignment_history.append(item)
        record(audit,time,track,resource,action,reason,self.mapping(resources))

    def cycle(self, tracks: list[Track], resources: list[Resource], time: int, audit: list[AuditEntry]):
        cfg = self.config.hysteresis
        by_id = {t.id:t for t in tracks}
        if time < self.config.initial_observation_period:
            return
        for t in tracks:
            lead = max(t.probabilities,key=t.probabilities.get)
            previous = self.leaders.get(t.id)
            self.leaders[t.id] = lead
            t.low_consequence_cycles = t.low_consequence_cycles+1 if low_consequence_evidence(t,time,cfg) else 0
            t.factors.persistence = t.low_consequence_cycles
            recent = time-t.last_major_turn < cfg.turn_quiet_period
            if t.assigned_resource:
                t.state = 'REASSESS' if recent else 'COMMIT'
                t.reason = 'Observed heading change; retain coverage while intent is reassessed.' if recent else 'Assignment retained: no persistent challenger exceeds the switching margin.'
                if previous and previous != lead:
                    record(audit,time,t,next(r for r in resources if r.id==t.assigned_resource),'REASSESS',t.reason,self.mapping(resources),previous)
                if lead == 'A08' and t.expected_consequence < .45 and 0 <= t.low_consequence_cycles < cfg.release_persistence_cycles:
                    t.reason = f'Open-water trend under review ({t.low_consequence_cycles}/{cfg.release_persistence_cycles} qualifying cycles). Maintain assignment until all release gates hold.'
                    record(audit,time,t,next(r for r in resources if r.id==t.assigned_resource),'HOLD',t.reason,self.mapping(resources),previous)
            else:
                t.state = 'REASSESS' if recent else 'RELEASE' if t.assignment_history and t.assignment_history[-1].action=='RELEASE' else 'HOLD'
                t.reason = 'Observed behavior changed; collecting fresh evidence.' if recent else 'Continuously monitored; limited capacity reserved for stronger consequence-weighted evidence.'
        for r in resources:
            if r.assigned_track and release_ready(by_id[r.assigned_track],r,time,cfg):
                self.detach(by_id[r.assigned_track],r,time,audit,resources)
        candidates = sorted((t for t in tracks if t.assigned_resource is None and t.priority >= cfg.commit_priority and t.confidence >= cfg.commit_confidence
            and t.low_consequence_cycles < cfg.release_persistence_cycles), key=lambda t:(-t.priority,t.id))
        free = [r for r in resources if r.assigned_track is None]
        for r,t in zip(free,candidates):
            self.assign(t,r,time,audit,resources)
        candidates = [t for t in candidates if t.assigned_resource is None]
        active_contests = {}
        used = set()
        for challenger in candidates:
            # Suspected water reclassification must satisfy release gates, not bypass them as a swap.
            eligible = [r for r in resources if r.assigned_track and r.id not in used and may_switch(r,time,cfg)
                and not (by_id[r.assigned_track].probabilities['A08'] >= .4 and by_id[r.assigned_track].expected_consequence < .5)]
            if not eligible:
                break
            weakest = min(eligible,key=lambda r:(by_id[r.assigned_track].priority,r.id))
            incumbent = by_id[weakest.assigned_track]
            if challenger.priority-incumbent.priority < cfg.improvement_threshold:
                continue
            key = (weakest.id,challenger.id)
            active_contests[key] = self.contests.get(key,0)+1
            used.add(weakest.id)
            if active_contests[key] >= cfg.challenger_persistence:
                self.detach(incumbent,weakest,time,audit,resources,'DISPLACE')
                self.assign(challenger,weakest,time,audit,resources,'REALLOCATE')
                del active_contests[key]
        self.contests = active_contests
        # Entries retain transaction order. The final snapshot for a timestamp is the visible frame.
