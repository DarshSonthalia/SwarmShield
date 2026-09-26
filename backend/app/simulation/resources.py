"""Illustrative piecewise-quintic paths with C2 joins and finite planning horizons."""
from dataclasses import dataclass
import numpy as np
from ..models import Resource, Track, SimulationConfig
from .trajectory import QuinticSegment

@dataclass
class MotionPlan:
    first: QuinticSegment
    second: QuinticSegment
    assignment: str | None

    @property
    def end(self):
        return self.second.start+self.second.duration

    def sample(self,time):
        return (self.first if time < self.second.start else self.second).sample(time)

def create_resources(config: SimulationConfig) -> list[Resource]:
    return [Resource(id=f'I{i+1:02}',site_id=config.sites[i%8].id,position=config.sites[i%8].position,
                     visual_destination=config.sites[i%8].position) for i in range(config.resource_count)]

def cinematic_plan(resource: Resource, target, terminal_velocity, time: int, config: SimulationConfig) -> MotionPlan:
    origin=np.array(resource.position)
    # Scene-only animation duration. A complete horizon avoids oscillation from
    # repeatedly restarting a long minimum-jerk path every observation cycle.
    half=int(np.ceil(max(config.trajectory_duration, np.linalg.norm(target-origin)/4.5)/2))
    midpoint=(origin+target)/2+np.array([0,5,0])
    tangent=(target-origin)/(2*half)*1.35
    tangent[1]=0
    first=QuinticSegment.connect(time,half,origin,resource.velocity,resource.acceleration,midpoint,tangent)
    second=QuinticSegment.connect(time+half,half,midpoint,tangent,(0,0,0),target,terminal_velocity)
    return MotionPlan(first,second,resource.assigned_track)

def update_resource_motion(resources: list[Resource], tracks: list[Track], segments: dict[str,MotionPlan], time: int, config: SimulationConfig):
    by_id={t.id:t for t in tracks}
    sites={s.id:s for s in config.sites}
    for r in resources:
        plan=segments.get(r.id)
        if plan:
            p,v,a=plan.sample(time)
            r.position,r.velocity,r.acceleration=tuple(p),tuple(v),tuple(a)
        if time < config.initial_observation_period+config.visual_launch_delay:
            continue
        if r.assigned_track:
            r.state='MOVING'
            t=by_id[r.assigned_track]
            # A trailing region in the scene, not a collision or intercept solution.
            target=np.array(t.observations[-1].position)+np.array([3,-2,3])
            terminal_velocity=np.array(t.velocity)
        else:
            target=np.array(sites[r.site_id].position)
            terminal_velocity=np.zeros(3)
            r.state='RETURNING' if np.linalg.norm(target-np.array(r.position))>.1 else 'STAGED'
        if plan is None or plan.assignment!=r.assigned_track or time>=plan.end:
            if r.state=='STAGED' and np.linalg.norm(r.velocity)<1e-8:
                continue
            r.visual_destination=tuple(target)
            segments[r.id]=cinematic_plan(r,target,terminal_velocity,time,config)
