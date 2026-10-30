"""Float64 headphone EQ after Flow, with finite fades and a linked lookahead.

One stereo processor serves both decks. Filter design happens on the control
thread; scipy's compiled SOS filters run on the audio thread. No per-sample
Python loops, extra decoder, upsampling of the source, or device changes.
"""
import math
import threading
import numpy as np
from headphone_profiles import settings,profile


def biquad(kind,hz,gain,q,rate):
    """RBJ peaking / shelf filters, AutoEq's Q (not shelf slope S)."""
    a=10**(gain/40);w=2*math.pi*hz/rate;c=math.cos(w);s=math.sin(w);alpha=s/(2*q)
    if kind=='PK':
        b=[1+alpha*a,-2*c,1-alpha*a];den=[1+alpha/a,-2*c,1-alpha/a]
    else:
        t=2*math.sqrt(a)*alpha
        if kind=='LSC':
            b=[a*((a+1)-(a-1)*c+t),2*a*((a-1)-(a+1)*c),a*((a+1)-(a-1)*c-t)]
            den=[(a+1)+(a-1)*c+t,-2*((a-1)+(a+1)*c),(a+1)+(a-1)*c-t]
        elif kind=='HSC':
            b=[a*((a+1)+(a-1)*c+t),-2*a*((a-1)+(a+1)*c),a*((a+1)+(a-1)*c-t)]
            den=[(a+1)-(a-1)*c+t,2*((a-1)-(a+1)*c),(a+1)-(a-1)*c-t]
        else:raise ValueError('Invalid headphone filter')
    return np.asarray(b+den,dtype=np.float64)/den[0]


class Chain:
    def __init__(self,scene,rate):
        self.sos=None;self.zi=None;self.gain=1.;self.balance=np.ones(2);self.active=False;self.bypass=False
        self.value=settings(scene.get('headphones'));self.mode=scene.get('mode','headphones')
        if self.mode!='headphones':return
        v=self.value;p=profile(v['profile']);amount=v['strength']/100
        bands=[(kind,hz,gain*amount,q) for kind,hz,gain,q in p['filters'] if gain*amount]
        if v['bass']:bands.append(('LSC',140,v['bass'],.7071))
        if v['treble']:bands.append(('HSC',4500,v['treble'],.7071))
        self.active=bool(bands or v['balance']);self.bypass=v['bypass']
        if bands:
            from scipy.signal import sosfreqz
            self.sos=np.asarray([biquad(*band,rate) for band in bands])
            self.zi=np.zeros((len(bands),2,2),dtype=np.float64)
            _,response=sosfreqz(self.sos,worN=32768,fs=rate)
            # Dense response plus a margin, never AutoEq's positive makeup gain.
            # The same attenuation is used for the dry comparison.
            self.gain=10**(-(max(0.,20*np.log10(max(abs(response))))+1.5)/20)
        balance=v['balance']/20
        self.balance[0 if balance>0 else 1]=1-abs(balance)*.5
        if self.active:
            from scipy.signal import sosfilt,resample_poly
            from scipy.ndimage import maximum_filter1d
            self.filter=sosfilt
            self.resample=resample_poly;self.maximum=maximum_filter1d

    def warm(self,history):
        if self.sos is not None and len(history):_,self.zi=self.filter(self.sos,history,axis=0,zi=self.zi)

    def process(self,data):
        if not self.active:return data
        if self.sos is not None:
            filtered,self.zi=self.filter(self.sos,data,axis=0,zi=self.zi)
        else:filtered=data
        return (data if self.bypass else filtered*self.balance)*self.gain


class HeadphoneProcessor:
    def __init__(self,rate):
        if rate not in (48000,192000):raise ValueError('Invalid headphone rate')
        self.rate=rate;self.lookahead=rate//200;self.chain=Chain({'mode':'speakers'},rate)
        self.pending=None;self.old=None;self.fade=0;self.length=round(rate*.18)
        self.lock=threading.Lock()
        self.history=np.empty((0,2),np.float64);self.delay=np.zeros((self.lookahead,2),np.float64)
        self.peak_history=np.zeros((32,2),np.float64);self.envelope=0.;self.limiting=False
        self.status={'active':False,'headroomDb':0.,'error':''}

    def configure(self,scene):
        try:
            chain=Chain(scene,self.rate)
            with self.lock:self.pending=chain
            return {'active':chain.active,'headroomDb':round(-20*math.log10(chain.gain),1),'error':'',
                    'profile':chain.value['profile'],'bypass':chain.bypass}
        except ImportError:
            return {'active':False,'error':'SCIPY_REQUIRED'}

    def process(self,data):
        data=np.asarray(data,dtype=np.float64)
        if data.ndim!=2 or data.shape[1]!=2 or not np.isfinite(data).all():raise ValueError('Invalid headphone PCM')
        if not len(data):return data.astype('<f4')
        target=None
        if self.old is None:
            with self.lock:target=self.pending;self.pending=None
        if target is not None:
            target.warm(self.history);self.old=self.chain;self.chain=target;self.fade=0
        out=self.chain.process(data)
        active=self.chain.active or self.old is not None and self.old.active
        chain=self.chain if self.chain.active else self.old
        if chain is not None and hasattr(chain,'resample'):
            self.resample,self.maximum=chain.resample,chain.maximum
        if self.old is not None:
            old=self.old.process(data);n=min(len(out),self.length-self.fade)
            t=np.minimum(1,(self.fade+np.arange(len(out)))/max(1,self.length-1))
            t=t*t*t*(t*(t*6-15)+10)
            out=old*(1-t[:,None])+out*t[:,None];self.fade+=n
            if self.fade>=self.length:self.old=None
        # Five milliseconds of future samples protect both ears with one gain.
        combined=np.concatenate((self.delay,out));self.delay=combined[-self.lookahead:].copy()
        result=combined[:len(data)].copy()
        if active or self.envelope>1e-7:
            analysis=np.concatenate((self.peak_history,combined))
            factor=4 if self.rate==48000 else 2
            reconstructed=self.resample(analysis,factor,1,axis=0)
            peaks=np.max(abs(reconstructed[32*factor:32*factor+len(combined)*factor]).reshape(len(combined),factor,2),axis=(1,2))
            need=np.maximum(0,np.log(np.maximum(peaks,1e-30)/.891250938))
            slope=math.log(10)*12/20/self.lookahead
            at=np.arange(len(need),dtype=np.float64)
            future=self.maximum(need-at*slope,size=self.lookahead+1,origin=-(self.lookahead//2),mode='constant',cval=-np.inf)+at*slope
            future=np.maximum(0,future[:len(data)])
            exp=np.exp(np.arange(1,len(data)+1)/(self.rate*.12))
            envelope=np.maximum.accumulate(np.maximum(future*exp,self.envelope))/exp
            self.envelope=float(envelope[-1]);result*=np.exp(-envelope)[:,None]
            self.limiting=bool(np.max(envelope)>.001)
        self.peak_history=combined[len(data)-32:len(data)].copy() if len(data)>=32 else np.concatenate((self.peak_history,result))[-32:]
        self.history=np.concatenate((self.history,data))[-self.rate//4:]
        return result.astype('<f4')
