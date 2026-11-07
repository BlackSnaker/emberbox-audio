"""Bounded min/max/RMS envelopes from real stereo PCM; no audio-file cache."""
import math
import numpy as np


class PeakBins:
    def __init__(self,rate,seconds,start=0,bins=1024):
        if rate not in (24000,44100,48000,88200,96000,176400,192000):raise ValueError('Invalid peak rate')
        if not math.isfinite(seconds) or not 0<seconds<=64:raise ValueError('Invalid peak window')
        self.rate=rate;self.seconds=float(seconds);self.start=float(start)
        self.limit=round(rate*seconds);self.hop=max(1,math.ceil(self.limit/max(1,min(2048,int(bins)))))
        self.frames=0;self.pending=np.empty((0,2),np.float32);self.values=[];self.done=False

    def add(self,pcm):
        if self.done:return
        value=np.asarray(pcm,dtype=np.float32)
        if value.ndim!=2 or value.shape[1]!=2 or not np.isfinite(value).all():raise ValueError('Invalid peak PCM')
        value=value[:max(0,self.limit-self.frames)];self.frames+=len(value)
        joined=np.concatenate((self.pending,value));count=len(joined)//self.hop
        if count:
            blocks=joined[:count*self.hop].reshape(count,self.hop,2)
            low=blocks.min(axis=(1,2));high=blocks.max(axis=(1,2));rms=np.sqrt(np.mean(blocks.astype(np.float64)**2,axis=(1,2)))
            self.values.extend([round(float(a),5),round(float(b),5),round(float(c),5)] for a,b,c in zip(low,high,rms))
        self.pending=joined[count*self.hop:].copy();self.done=self.frames>=self.limit

    def result(self):
        values=list(self.values)
        if len(self.pending):
            p=self.pending;values.append([round(float(p.min()),5),round(float(p.max()),5),round(float(np.sqrt(np.mean(p.astype(np.float64)**2))),5)])
        return {'start':self.start,'seconds':self.seconds,'covered':self.frames/self.rate,
                'step':self.hop/self.rate,'bins':values,'evidence':'decoded-pcm','rate':self.rate}


def validate(value):
    if not isinstance(value,dict) or value.get('evidence')!='decoded-pcm':raise ValueError('Unmeasured waveform')
    start,seconds,covered,step=[float(value.get(k,0)) for k in ('start','seconds','covered','step')]
    if not all(math.isfinite(v) for v in (start,seconds,covered,step)) or not 0<=start<=86400 or not 0<seconds<=64 or not 0<covered<=seconds+.01 or not 0<step<=1:raise ValueError('Invalid waveform bounds')
    raw=value.get('bins');result=[]
    if not isinstance(raw,list) or not 1<=len(raw)<=2049:raise ValueError('Invalid waveform bins')
    for row in raw:
        if not isinstance(row,(list,tuple)) or len(row)!=3:raise ValueError('Invalid waveform bin')
        a,b,r=map(float,row)
        if not all(math.isfinite(v) for v in (a,b,r)) or not -8<=a<=b<=8 or not 0<=r<=8:raise ValueError('Invalid waveform peak')
        result.append((a,b,r))
    if len(result)*step<covered-1e-5 or (len(result)-1)*step>covered+.01:raise ValueError('Inconsistent waveform timing')
    return dict(start=start,seconds=seconds,covered=covered,step=step,bins=result,evidence='decoded-pcm',rate=int(value.get('rate',48000)))
