"""C2 cinematic motion in arbitrary scene units. No guidance or interception model."""
from dataclasses import dataclass
import numpy as np

@dataclass
class QuinticSegment:
    start: float
    duration: float
    coefficients: np.ndarray

    @classmethod
    def connect(cls, start, duration, p0, v0, a0, p1, v1=(0,0,0), a1=(0,0,0)):
        if duration <= 0:
            raise ValueError('Segment duration must be positive')
        p0,v0,a0,p1,v1,a1 = [np.asarray(v,dtype=float) for v in (p0,v0,a0,p1,v1,a1)]
        # Coefficients are in normalized segment time for numerical conditioning.
        c0,c1,c2 = p0, v0*duration, .5*a0*duration**2
        rhs = np.array([p1-c0-c1-c2, v1*duration-c1-2*c2, a1*duration**2-2*c2])
        c3,c4,c5 = np.linalg.solve(np.array([[1,1,1],[3,4,5],[6,12,20]],dtype=float),rhs)
        return cls(start,duration,np.array([c0,c1,c2,c3,c4,c5]))

    def sample(self, time):
        u = float(np.clip((time-self.start)/self.duration,0,1))
        c = self.coefficients
        p = sum(c[i]*u**i for i in range(6))
        v = sum(i*c[i]*u**(i-1) for i in range(1,6))/self.duration
        a = sum(i*(i-1)*c[i]*u**(i-2) for i in range(2,6))/self.duration**2
        return p,v,a
