from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import hypot
from typing import Any


@dataclass
class Vec2:
    x: float
    y: float

    def distance_to(self, other: "Vec2") -> float:
        return hypot(self.x - other.x, self.y - other.y)

    def to_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 3), "y": round(self.y, 3)}


@dataclass
class Asset:
    id: str
    name: str
    position: Vec2
    consequence: float
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "position": self.position.to_dict(),
            "consequence": self.consequence,
            "kind": self.kind,
        }


@dataclass
class Threat:
    id: str
    position: Vec2
    velocity: Vec2
    p_hostile: float
    asset_id: str
    altitude_m: float
    state: str = "active"
    assigned_interceptor: str | None = None
    predicted_risk: float = 0.0

    def speed(self) -> float:
        return hypot(self.velocity.x, self.velocity.y)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["position"] = self.position.to_dict()
        data["velocity"] = self.velocity.to_dict()
        return data


@dataclass(frozen=True)
class TrackObservation:
    time_s: float
    position: Vec2
    velocity: Vec2


@dataclass(frozen=True)
class ObservedThreat:
    id: str
    time_s: float
    position: Vec2
    velocity: Vec2
    p_hostile: float
    state: str
    altitude_m: float

    def speed(self) -> float:
        return hypot(self.velocity.x, self.velocity.y)


@dataclass(frozen=True)
class ThreatBelief:
    threat_id: str
    time_s: float
    destination_probabilities: dict[str, float]
    approach_times_s: dict[str, float | None]
    top_destination_id: str
    top_probability: float
    expected_consequence: float
    uncertainty: float
    uncertainty_label: str
    urgency: float
    feasible_horizon_s: float
    risk: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Interceptor:
    id: str
    position: Vec2
    max_speed_mps: float
    range_m: float
    battery: float
    cost: float
    kind: str
    altitude_m: float
    state: str = "available"
    target_id: str | None = None
    committed: bool = False
    launched: bool = False
    previous_target_id: str | None = None
    distance_flown_m: float = 0.0
    base_group: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["position"] = self.position.to_dict()
        return data


@dataclass
class Scenario:
    name: str
    duration_s: int
    step_s: float
    assets: list[Asset]
    threats: list[Threat]
    interceptors: list[Interceptor]
    events: list[dict[str, Any]] = field(default_factory=list)
    safety_radius_m: float = 220.0
    hit_radius_m: float = 180.0
    commitment_distance_m: float = 2200.0
    p2p_radius_m: float = 9000.0

    def asset_map(self) -> dict[str, Asset]:
        return {asset.id: asset for asset in self.assets}

