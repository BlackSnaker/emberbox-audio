"""Small, bounded beat-grid estimator. No model, network, PCM cache or GTK work.

Only a measured pulse with at least six repeatable attacks is accepted. The
80–180 BPM search is deliberately narrow; half/double-time aliases are resolved
when comparing tracks. A weak/unrelated pulse keeps the ordinary crossfade.
"""
import math
import numpy as np


def detect(points):
    if len(points)<150:return None
    p=np.asarray(points,dtype=np.float64)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)>4000 or not np.all(np.isfinite(p)):return None
    p=p[np.r_[True,np.diff(p[:,0])>.001]]
    if len(p)<150 or p[-1,0]-p[0,0]<3.5:return None
    times=np.arange(p[0,0],p[-1,0],.01)
    low=np.interp(times,p[:,0],p[:,1]);mid=np.interp(times,p[:,0],p[:,2])
    # Relative changes are invariant to master volume; bass carries the pulse,
    # while the mid band also detects tracks built around claps/snare.
    flux=np.maximum(0,np.diff(low,prepend=low[0]))+.35*np.maximum(0,np.diff(mid,prepend=mid[0]))
    flux=np.convolve(flux,[.2,.6,.2],'same')
    threshold=max(.006,float(np.percentile(flux,75))*1.4)
    indices=np.flatnonzero((flux[1:-1]>threshold)&(flux[1:-1]>=flux[:-2])&(flux[1:-1]>flux[2:]))+1
    selected=[]
    for i in indices:
        if selected and times[i]-times[selected[-1]]<.16-1e-6:
            if flux[i]>flux[selected[-1]]:selected[-1]=i
        else:selected.append(i)
    if len(selected)<6:return None
    beats=times[selected];weights=flux[selected];weights=np.minimum(weights,np.percentile(weights,75)*1.5)
    best=None
    for bpm in np.arange(80.,180.01,.25):
        period=60/bpm;phase=beats*2*math.pi/period
        z=np.sum(weights*np.exp(phase*1j))/np.sum(weights)
        z2=np.sum(weights*np.exp(phase*2j))/np.sum(weights);harmonic=1
        coherence=abs(z)
        # Equally strong eighth notes must not cancel the quarter-note pulse.
        # Prefer an unambiguous fundamental; subdivisions receive a penalty.
        if abs(z2)*.8>coherence:coherence=abs(z2)*.8;z=z2;harmonic=2
        # A half-tempo candidate must not win by explaining just every other hit.
        coverage=min(1.,len(beats)*period/max(1.,beats[-1]-beats[0]))
        score=coherence*coverage
        if best is None or score>best[0]:best=(score,bpm,z,harmonic)
    score,bpm,z,harmonic=best;period=60/bpm;step=period/harmonic
    phase=(math.atan2(z.imag,z.real)%(2*math.pi))*step/(2*math.pi)
    errors=np.abs((beats-phase+step/2)%step-step/2)
    aligned=float(np.sum(weights[errors<.055])/np.sum(weights))
    confidence=min(score,aligned)
    # Syncopated drums can alternate strong and weak subdivisions, reducing
    # circular coherence even when the full onset envelope repeats each beat.
    # Require independent envelope recurrence before accepting that case.
    if confidence<.72 and score>=.432 and aligned>=.72:
        novelty=flux-float(np.mean(flux));lag=period/.01;k=int(lag);fraction=lag-k
        shifted=novelty[k:-1]*(1-fraction)+novelty[k+1:]*fraction
        first=novelty[:len(shifted)];norm=float(np.linalg.norm(first)*np.linalg.norm(shifted))
        recurrence=float(np.dot(first,shifted))/norm if norm>1e-12 else 0.
        confidence=min(aligned,score/.6,recurrence/.25)
    if confidence<.72:return None
    # Median onset phase avoids a loud fill pulling an otherwise stable grid.
    signed=(beats-phase+step/2)%step-step/2
    phase=(phase+float(np.median(signed[errors<.055])))%period
    return dict(bpm=round(float(bpm),2),period=float(period),phase=float(phase),confidence=float(confidence),count=len(beats))


def match(outgoing,incoming):
    if not outgoing or not incoming:return None
    if min(outgoing.get('confidence',0),incoming.get('confidence',0))<.72:return None
    candidates=[(abs(outgoing['bpm']/(incoming['bpm']*factor)-1),factor) for factor in (.5,1.,2.)]
    difference,factor=min(candidates)
    if difference>.06:return None
    return dict(rate=outgoing['bpm']/(incoming['bpm']*factor),bpm=outgoing['bpm'],incomingBpm=incoming['bpm']*factor,
                period=outgoing['period'],phase=outgoing['phase'],incomingPhase=incoming['phase'],incomingPeriod=incoming['period'],
                confidence=min(outgoing['confidence'],incoming['confidence']))


class EnergyTap:
    """10 ms energy observations, preserving opposite-phase stereo transients."""
    def __init__(self,rate=48000):
        self.rate=rate;self.hop=rate//100;self.buffer=np.empty((0,2),dtype=np.float32);self.points=[]
        self.history=np.zeros((95,2),dtype=np.float32)
    def feed(self,pcm,end):
        # Boxcar decimation keeps the worker lightweight; the low band uses a
        # short FIR rather than a Python per-sample loop.
        pcm=np.asarray(pcm,dtype=np.float32);self.buffer=np.concatenate((self.buffer,pcm))
        count=len(self.buffer)//self.hop
        if not count:return
        n=count*self.hop;frames=self.buffer[:n].reshape(count,self.hop,2)
        broad=np.sqrt(np.mean(frames*frames,axis=(1,2)))
        smooth=np.concatenate((self.history,frames.reshape(-1,2)))
        kernel=np.ones(96,dtype=np.float32)/96
        low=np.column_stack([np.convolve(smooth[:,c],kernel,'valid') for c in (0,1)]).reshape(count,self.hop,2)
        self.history=smooth[-95:].copy()
        bass=np.sqrt(np.mean(low*low,axis=(1,2)))
        times=end-(len(self.buffer)-np.arange(count)*self.hop-self.hop/2)/self.rate
        self.points.extend((float(t),math.log1p(float(b)*100),math.log1p(float(m)*100)) for t,b,m in zip(times,bass,broad))
        self.points=self.points[-1600:];self.buffer=self.buffer[n:].copy()
    def result(self):return detect(self.points)
