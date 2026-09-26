from copy import deepcopy
import numpy as np
from ..models import SimulationConfig, Frame, RunResponse
from .tracks import create_tracks, advance_motion
from .observation import observe
from .inference import infer
from .priority import score_priority
from .allocator import Allocator
from .resources import create_resources, update_resource_motion
from .baseline import first_come_first_served
from .metrics import compute_metrics
from .events import EVENTS

def validate_frame(frame: Frame, destinations: set[str]) -> None:
    tracks = {t.id:t for t in frame.tracks}
    resources = {r.id:r for r in frame.resources}
    assert len(tracks)==len(frame.tracks) and len(resources)==len(frame.resources)
    assert len(set(frame.assignments.values()))==len(frame.assignments)
    for rid,tid in frame.assignments.items():
        assert rid in resources and tid in tracks
        assert resources[rid].assigned_track==tid and tracks[tid].assigned_resource==rid
    for t in frame.tracks:
        assert set(t.probabilities)==destinations
        assert all(np.isfinite(p) and p>=0 for p in t.probabilities.values())
        assert abs(sum(t.probabilities.values())-1)<1e-9
        assert (t.assigned_resource is not None)==(t.id in frame.assignments.values())
        assert t.state not in ('COMMIT','REALLOCATE') or t.assigned_resource is not None
        assert t.state not in ('OBSERVE','HOLD','RELEASE') or t.assigned_resource is None
    for r in frame.resources:
        assert (r.assigned_track is not None)==(r.id in frame.assignments)
        assert all(np.isfinite(x) for x in (*r.position,*r.velocity,*r.acceleration))

class World:
    def __init__(self, config: SimulationConfig):
        self.config = config.model_copy(deep=True)
        self.audit = []
        self.frames: list[Frame] = []
        self.cursor = 0
        self._build()

    def _build(self):
        cfg = self.config
        rng = np.random.default_rng(cfg.seed)
        hidden,tracks = create_tracks(cfg,rng)
        resources = create_resources(cfg)
        allocator = Allocator(cfg)
        segments = {}
        cumulative = {'swarm':0.0,'baseline':0.0}
        for time in range(cfg.duration+1):
            # 1. Motion -> 2. observation -> 3. inference -> 4. allocation
            for h,t in zip(hidden,tracks):
                if time:
                    advance_motion(h,time,cfg)
                t.position,t.animation_velocity,t.animation_acceleration = tuple(h.position),tuple(h.velocity),tuple(h.acceleration)
                t.altitude = float(h.position[1])
                if time % cfg.observation_interval==0:
                    infer(t,observe(h,t,time,rng),cfg)
            if time % cfg.allocation_interval==0:
                for t in tracks:
                    score_priority(t,cfg,max(0,1-len(resources)/len(tracks)))
                # 5. The allocator records transactions before we publish any frame.
                allocator.cycle(tracks,resources,time,self.audit)
            update_resource_motion(resources,tracks,segments,time,cfg)
            assignments = allocator.mapping(resources)
            baseline = first_come_first_served(tracks,resources,time,cfg.initial_observation_period)
            # Left rectangle integration: the preceding state occupies [t-1,t).
            if self.frames:
                cumulative['swarm'] += self.frames[-1].metrics.swarm.exposure
                cumulative['baseline'] += self.frames[-1].metrics.baseline.exposure
            metrics = compute_metrics(tracks,resources,assignments,baseline,self.audit,cumulative,cfg)
            # 6. Deep snapshots make replay independent of cursor and later mutations.
            frame = Frame(time=time,tracks=deepcopy(tracks),resources=deepcopy(resources),assignments=dict(assignments),baseline_assignments=baseline,
                metrics=metrics,audit_count=len(self.audit),event_ids=[i for i,e in enumerate(EVENTS) if e.time<=time])
            validate_frame(frame,{d.id for d in cfg.destinations})
            self.frames.append(frame)

    def frame(self,time: float) -> Frame:
        if not np.isfinite(time) or time<0 or time>self.config.duration:
            raise ValueError('Time outside scenario bounds')
        return self.frames[int(time)].model_copy(deep=True)

    def step(self,seconds: int) -> Frame:
        self.cursor = min(self.config.duration,self.cursor+seconds)
        return self.frame(self.cursor)

    def run(self) -> RunResponse:
        return RunResponse(seed=self.config.seed,duration=self.config.duration,frames=self.frames,audit=self.audit)
