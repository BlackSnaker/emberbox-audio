"""Transparent stereo peak protection for buffered karaoke stems.

The caller supplies a short piece of already available future audio. This lets
the gain approach an overload smoothly, without delaying audio or running the
separator again. Only peaks that would exceed the ceiling change the signal.
"""
import math

import numpy as np
from scipy.ndimage import maximum_filter1d


RATE=48000
FUTURE=1536                 # 32 ms; fits the separator's existing future context.
PEAK_HOLD=192               # Hold a real crest for 4 ms; do not follow its carrier.


class StereoPeakLimiter:
    """Stereo-linked, finite-lookahead peak limiter with a carried release.

    Both channels receive exactly the same gain. Exponential attack and release
    envelopes use vectorized running maxima rather than Python sample loops.
    The attack has a finite horizon; at its edge its maximum contribution is
    below 1e-6 gain. A short crest hold avoids flattening waveform peaks while
    the attack/release envelope changes. Release eventually reaches exact unity.
    """
    required_future=FUTURE

    def __init__(self,rate=RATE,ceiling=.98,attack_ms=2.,release_ms=100.):
        if (not all(math.isfinite(value) for value in (rate,ceiling,attack_ms,release_ms))
                or rate<=0 or not 0<ceiling<1 or attack_ms<=0 or release_ms<=0):
            raise ValueError('Invalid limiter parameters')
        self.ceiling=float(np.nextafter(np.float32(ceiling),np.float32(0.)))
        self.attack=rate*attack_ms/1000
        self.release=rate*release_ms/1000
        self.deficit=0.

    def process(self,pcm_with_future,frames):
        """Return ``frames`` stereo samples; retain only the release state.

        Future samples are examined but are neither emitted nor consumed. The
        next call must begin at the first sample after the returned frames.
        """
        pcm=np.asarray(pcm_with_future)
        if (pcm.ndim!=2 or pcm.shape[1]!=2 or not isinstance(frames,(int,np.integer))
                or frames<0 or len(pcm)<frames+self.required_future):
            raise ValueError('Expected stereo frames and limiter future context')
        if frames==0:return np.empty((0,2),dtype='<f4')
        pcm=np.nan_to_num(pcm[:frames+self.required_future].astype(np.float64),
                          nan=0.,posinf=0.,neginf=0.)
        peak=np.max(np.abs(pcm),axis=1)
        requested=np.maximum(0.,1-self.ceiling/np.maximum(peak,self.ceiling))
        if self.deficit==0 and not np.any(requested):
            return pcm[:frames].astype('<f4')
        log_request=np.full(len(requested),-np.inf,np.float64)
        np.log(requested,out=log_request,where=requested>0)
        # Hold a future crest before calculating its anticipatory attack. With
        # no hold, the envelope can follow the carrier up to each crest, which
        # produces small flat tops despite avoiding out-of-range samples.
        held=maximum_filter1d(log_request,size=PEAK_HOLD+1,
                               origin=-PEAK_HOLD//2,
                               mode='constant',cval=-np.inf)
        attack_future=self.required_future-PEAK_HOLD
        # D[n] = max(held[n+j] * exp(-j/attack), j=0..attack_future).
        # Taking logs turns the weighted maximum into a fast flat sliding max.
        # Offsets cancel before exponentiation, avoiding exponential overflow.
        index=np.arange(len(requested),dtype=np.float64)
        future=maximum_filter1d(held-index/self.attack,
                                size=attack_future+1,
                                origin=-attack_future//2,
                                mode='constant',cval=-np.inf)[:frames]
        attack_log=future+index[:frames]/self.attack
        # D[n] = max(attack[n], previous_D * exp(-1/release)). The transformed
        # cumulative maximum gives the exact recurrence in one vectorized pass.
        release_index=index[:frames]/self.release
        release_log=attack_log+release_index
        if self.deficit>0:
            release_log[0]=max(release_log[0],math.log(self.deficit)-1/self.release)
        deficit=np.exp(np.maximum.accumulate(release_log)-release_index)
        # Below float32's useful gain resolution the release is fully settled.
        deficit[deficit<1e-8]=0.
        self.deficit=float(deficit[-1])
        gain=1-deficit
        # The demand recurrence bounds peaks mathematically. This direct bound
        # also covers cancellation rounding for malformed very large samples.
        gain=np.minimum(gain,self.ceiling/np.maximum(peak[:frames],self.ceiling))
        return (pcm[:frames]*gain[:,None]).astype('<f4')
