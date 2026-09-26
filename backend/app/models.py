"""Public contracts. Hidden scenario intent never crosses the observation boundary."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

Vec3 = tuple[float, float, float]
DecisionState = Literal['OBSERVE', 'HOLD', 'COMMIT', 'REASSESS', 'RELEASE', 'REALLOCATE']

class Destination(BaseModel):
    id: str
    name: str
    short_name: str
    position: Vec3
    radius: float = Field(gt=0)
    weight: float = Field(ge=0, le=1)
    category: str

class Site(BaseModel):
    id: str
    name: str
    position: Vec3

class PriorityConfig(BaseModel):
    consequence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    escalation: float = Field(ge=0, le=1)
    scarcity: float = Field(ge=0, le=1)
    switching_penalty: float = Field(ge=0, le=1)

class UncertaintyConfig(BaseModel):
    initial_concentration: float = Field(gt=0)
    max_concentration: float = Field(gt=0)
    evidence_cycles: int = Field(ge=1)
    major_turn_radians: float = Field(gt=0)
    noise_floor: float = Field(gt=0, le=.1)

class HysteresisConfig(BaseModel):
    minimum_assignment_duration: int = Field(ge=0)
    improvement_threshold: float = Field(ge=0, le=1)
    challenger_persistence: int = Field(ge=1)
    reassignment_cooldown: int = Field(ge=0)
    release_persistence_cycles: int = Field(ge=1)
    water_probability: float = Field(ge=0, le=1)
    release_consequence: float = Field(ge=0, le=1)
    release_confidence: float = Field(ge=0, le=1)
    turn_quiet_period: int = Field(ge=0)
    commit_priority: float = Field(ge=0, le=1)
    commit_confidence: float = Field(ge=0, le=1)

class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    seed: int = Field(ge=0, le=2**32-1)
    track_count: int = Field(ge=1, le=20)
    resource_count: int = Field(ge=1, le=12)
    duration: int = Field(ge=20, le=240)
    observation_interval: int = Field(ge=1, le=10)
    allocation_interval: int = Field(ge=1, le=10)
    initial_observation_period: int = Field(ge=1)
    visual_launch_delay: int = Field(ge=0)
    trajectory_duration: int = Field(ge=4)
    priority: PriorityConfig
    uncertainty: UncertaintyConfig
    hysteresis: HysteresisConfig
    destinations: list[Destination]
    sites: list[Site]

    @model_validator(mode='after')
    def unique_world(self):
        if len({d.id for d in self.destinations}) != len(self.destinations):
            raise ValueError('Destination IDs must be unique')
        if {d.id for d in self.destinations} != {f'A{i:02}' for i in range(1,9)}:
            raise ValueError('The authored scenario requires destinations A01–A08')
        if len(self.sites) != 8 or len({s.id for s in self.sites}) != 8:
            raise ValueError('Eight unique staging sites are required')
        if self.initial_observation_period > self.duration:
            raise ValueError('Observation period exceeds duration')
        if self.allocation_interval % self.observation_interval:
            raise ValueError('Allocation must coincide with fresh observations')
        return self

class Observation(BaseModel):
    time: int
    position: Vec3
    velocity: Vec3
    heading: float

class ReasonFactors(BaseModel):
    expected_consequence: float = 0
    confidence: float = 0
    uncertainty: float = 1
    urgency: float = 0
    escalation: float = 0
    scarcity: float = 0
    reassignment_penalty: float = 0
    persistence: int = 0
    consequence_term: float = 0
    uncertainty_term: float = 0
    escalation_term: float = 0
    scarcity_term: float = 0

class AssignmentRecord(BaseModel):
    time: int
    track_id: str
    resource_id: str
    action: str
    reason: str

class Track(BaseModel):
    id: str
    position: Vec3
    animation_velocity: Vec3 = (0,0,0)
    animation_acceleration: Vec3 = (0,0,0)
    velocity: Vec3 = (0,0,0)
    altitude: float = 0
    heading: float = 0
    noise_level: float
    maneuver_uncertainty: float
    observations: list[Observation] = Field(default_factory=list)
    probabilities: dict[str,float] = Field(default_factory=dict)
    confidence: float = 0
    entropy: float = 1
    stability: float = 0
    heading_variance: float = 0
    expected_consequence: float = 0
    priority: float = 0
    urgency: float = 0
    escalation: float = 0
    last_major_turn: int = -1000
    low_consequence_cycles: int = 0
    state: DecisionState = 'OBSERVE'
    assigned_resource: str | None = None
    assignment_history: list[AssignmentRecord] = Field(default_factory=list)
    event_history: list[str] = Field(default_factory=list)
    reason: str = 'Accumulating noisy observations before committing scarce resources.'
    factors: ReasonFactors = Field(default_factory=ReasonFactors)

class Resource(BaseModel):
    id: str
    site_id: str
    position: Vec3
    velocity: Vec3 = (0,0,0)
    acceleration: Vec3 = (0,0,0)
    state: Literal['STAGED','ASSIGNED','MOVING','RETURNING'] = 'STAGED'
    assigned_track: str | None = None
    assignment_start: int | None = None
    last_change: int = -1000
    visual_destination: Vec3
    assignment_history: list[AssignmentRecord] = Field(default_factory=list)
    reason: str = 'Available at staging site.'

class AuditEntry(BaseModel):
    id: int
    time: int
    track_id: str
    resource_id: str | None
    action: str
    leading_destination: str
    previous_leading_destination: str | None = None
    probability: float
    factors: ReasonFactors
    priority: float
    reason: str
    assignments: dict[str,str]

class ComparisonMetrics(BaseModel):
    critical_tracks_covered: int
    critical_tracks: int
    exposure: float
    cumulative_exposure: float
    low_consequence_commitments: int
    reassignments: int
    utilization: float
    stability: float
    critical_assets_covered: int

class Metrics(BaseModel):
    total_tracks: int
    active_tracks: int
    resources_available: int
    resources_committed: int
    high_consequence_tracks: int
    low_consequence_tracks: int
    mean_confidence: float
    mean_uncertainty: float
    assignment_changes: int
    released_resources: int
    critical_assets_covered: int
    swarm: ComparisonMetrics
    baseline: ComparisonMetrics

class ScenarioEvent(BaseModel):
    time: int
    title: str
    description: str
    track_id: str | None = None

class Frame(BaseModel):
    time: int
    tracks: list[Track]
    resources: list[Resource]
    assignments: dict[str,str]
    baseline_assignments: dict[str,str]
    metrics: Metrics
    audit_count: int
    event_ids: list[int]

class RunResponse(BaseModel):
    seed: int
    duration: int
    frames: list[Frame]
    audit: list[AuditEntry]

class ResetRequest(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=2**32-1)

class StepRequest(BaseModel):
    seconds: int = Field(default=1, ge=1, le=120)
