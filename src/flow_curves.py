"""A monotone, draggable handover knot. Complementary gains share headroom."""
import math


def point(value=None):
    if value is None:return [.5,.5]
    if not isinstance(value,(list,tuple)) or len(value)!=2:raise ValueError('Invalid flow curve')
    knee,level=map(float,value)
    if not math.isfinite(knee) or not math.isfinite(level) or not .1<=knee<=.9 or not .05<=level<=.95:raise ValueError('Invalid flow curve')
    return [knee,level]


def slope(knee,level):
    left=level/knee;right=(1-level)/(1-knee)
    a,b=2-knee,1+knee
    return min(3*min(left,right),(a+b)/(a/left+b/right))


def custom(t,knee=.5,level=.5):
    t=max(0.,min(1.,t));m=slope(knee,level)
    if t<=knee:
        u=t/knee;result=(-2*u**3+3*u*u)*level+(u**3-u*u)*knee*m
    else:
        u=(t-knee)/(1-knee)
        result=(2*u**3-3*u*u+1)*level+(u**3-2*u*u+u)*(1-knee)*m-2*u**3+3*u*u
    return max(0.,min(1.,result))
