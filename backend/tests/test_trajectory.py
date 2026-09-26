import numpy as np
import pytest
from app.simulation.trajectory import QuinticSegment

def segment():
    return QuinticSegment.connect(12,10,(1,2,3),(.4,.2,.1),(.01,0,-.02),(12,17,8),(.2,0,.3),(0,.01,0))

def test_quintic_start_position_velocity_acceleration():
    p,v,a=segment().sample(12)
    np.testing.assert_allclose(p,[1,2,3],atol=1e-12)
    np.testing.assert_allclose(v,[.4,.2,.1],atol=1e-12)
    np.testing.assert_allclose(a,[.01,0,-.02],atol=1e-12)

def test_quintic_end_position_velocity_acceleration():
    p,v,a=segment().sample(22)
    np.testing.assert_allclose(p,[12,17,8],atol=1e-10)
    np.testing.assert_allclose(v,[.2,0,.3],atol=1e-10)
    np.testing.assert_allclose(a,[0,.01,0],atol=1e-10)

def test_retargeting_interior_is_c2_continuous():
    old=segment();p,v,a=old.sample(16)
    new=QuinticSegment.connect(16,12,p,v,a,(-15,4,50))
    for left,right in zip(old.sample(16),new.sample(16)):
        np.testing.assert_allclose(left,right,atol=1e-12)
    for left,right in zip(old.sample(16-1e-6),new.sample(16+1e-6)):
        np.testing.assert_allclose(left,right,atol=1e-5)

def test_segment_numerical_derivatives_match():
    s=segment();h=1e-4;p,v,a=s.sample(16);pl,vl,_=s.sample(16-h);pr,vr,_=s.sample(16+h)
    np.testing.assert_allclose((pr-pl)/(2*h),v,atol=1e-7)
    np.testing.assert_allclose((vr-vl)/(2*h),a,atol=1e-7)

def test_stationary_segment_has_no_drift():
    s=QuinticSegment.connect(0,12,(3,4,5),(0,0,0),(0,0,0),(3,4,5))
    for time in np.linspace(0,12,50):
        p,v,a=s.sample(time);np.testing.assert_allclose(p,[3,4,5]);assert not np.any(v) and not np.any(a)

def test_nonpositive_duration_rejected():
    with pytest.raises(ValueError):QuinticSegment.connect(0,0,(0,0,0),(0,0,0),(0,0,0),(1,1,1))

def test_dense_samples_have_no_position_jump():
    points=np.array([segment().sample(t)[0] for t in np.linspace(12,22,1001)])
    assert np.linalg.norm(np.diff(points,axis=0),axis=1).max()<.05
