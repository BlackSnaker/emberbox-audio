"""Sample-based headphone transitions. No codecs, resampling or UI work here."""
import numpy as np

RATE=48000
CHANNELS=2
BLOCK=960
BUFFER=RATE*4


def curve(position):
    t=np.clip(np.asarray(position,dtype=np.float64),0.,1.)
    x=np.where(t<.38,t/.38,np.where(t<.62,(t-.38)/.24,(t-.62)/.38))
    start=np.where(t<.38,0.,np.where(t<.62,.18,.82))
    span=np.where(t<.38,.18,np.where(t<.62,.64,.18))
    return start+span*x*x*x*(x*(x*6.-15.)+10.)


def blend(outgoing,incoming,offset,length,initial=0.):
    if outgoing.shape!=incoming.shape or outgoing.ndim!=2 or outgoing.shape[1]!=CHANNELS:
        raise ValueError('Invalid spatial mix shape')
    t=(offset+np.arange(len(outgoing),dtype=np.float64))/max(1,length-1)
    gain=(initial+(1.-initial)*curve(t)).astype(np.float32)[:,None]
    # Complementary gains preserve peak headroom even for correlated masters.
    return outgoing*(1.-gain)+incoming*gain
