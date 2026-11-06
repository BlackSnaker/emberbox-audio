"""Transition-only three-band cuts, with a proven sample peak budget.

Two fixed one-pole crossovers form complementary low/mid/high bands. Only
their gains move, sample by sample; there is no filter redesign on the render
thread. The impulse L1 bound reserves headroom even for adversarial PCM.
"""
import math
import numpy as np
from scipy.signal import lfilter


def bands(value):
    if not isinstance(value,(list,tuple)) or len(value)!=3:raise ValueError('Invalid transition EQ')
    result=[float(v) for v in value]
    if not all(math.isfinite(v) and -12<=v<=0 for v in result):raise ValueError('Invalid transition EQ')
    return result


def ease(position):
    t=np.clip(position,0.,1.);return t*t*t*(t*(t*6-15)+10)


class BandEQ:
    def __init__(self,rate,db):
        self.db=bands(db);self.gains=10**(np.asarray(self.db)/20)
        self.alphas=[1-math.exp(-2*math.pi*f/rate) for f in (180,5000)]
        self.states=[np.zeros((1,2),np.float64) for _ in range(2)]
        n=math.ceil(rate*.03);axis=np.arange(n);low,high=self.alphas;g=self.gains
        impulse=(g[0]-g[1])*low*(1-low)**axis+(g[1]-g[2])*high*(1-high)**axis
        impulse[0]+=g[2]
        tail=abs(g[0]-g[1])*(1-low)**n+abs(g[1]-g[2])*(1-high)**n
        self.reserve=max(1.,float(np.sum(abs(impulse)))+tail)
        self.amount=0.

    def process(self,data,amount):
        value=np.asarray(data,dtype=np.float64)
        low,self.states[0]=lfilter([self.alphas[0]],[1,self.alphas[0]-1],value,axis=0,zi=self.states[0])
        high,self.states[1]=lfilter([self.alphas[1]],[1,self.alphas[1]-1],value,axis=0,zi=self.states[1])
        filtered=(self.gains[2]*value+(self.gains[1]-self.gains[2])*high+(self.gains[0]-self.gains[1])*low)/self.reserve
        weights=np.asarray(amount,dtype=np.float64)
        if weights.ndim==0:weights=np.full(len(data),weights)
        weights=np.clip(weights,0,1)[:,None]
        if len(weights):self.amount=float(weights[-1,0])
        return (value*(1-weights)+filtered*weights).astype(np.float32)

    def warm(self,history):
        if len(history):self.process(history,0.)
