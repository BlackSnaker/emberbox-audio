"""Read-only song rhythm for the theme, using the existing output meter."""
import math
from mirror_timing import Timing


def _text(value):
    return value.get_text() if hasattr(value,'get_text') else str(value or '')


class SongRhythm:
    def __init__(self,consumer):
        self.consumer=consumer;self.timing=Timing();self.meter=None;self.key=None
        self.requested=-math.inf;self.acquired=0.
        self.position=None;self.seen=0.;self.seek_id=0

    def release(self):
        if self.meter and hasattr(self.meter,'request_rhythm'):self.meter.request_rhythm(self.consumer,None)
        self.meter=None;self.key=None;self.requested=-math.inf
        self.position=None;self.seen=0.

    def advance(self,host,now,dt):
        active=bool(host and getattr(host,'playing',False) and not getattr(getattr(host,'sound',None),'muted',False))
        meter=getattr(host,'meter',None) if host else None
        if not active or meter is None:
            self.release();return self.timing.advance(dt,None,now,active=False,fresh=False)
        key=(getattr(host,'source',''),_text(getattr(host,'title','')),_text(getattr(host,'artist','')),
             _text(getattr(host,'album','')),getattr(host,'length',0))
        if meter is not self.meter:
            self.release();self.meter=meter
        if key!=self.key:
            self.key=key;self.acquired=now;self.requested=-math.inf;self.position=None;self.seek_id=0
        position=getattr(host,'position',None)
        if isinstance(position,(int,float)) and math.isfinite(position):
            position/=1e6
            if self.position is not None and abs(position-self.position-(now-self.seen))>2.5:
                self.seek_id+=1;self.acquired=now;self.requested=-math.inf
            self.position=position;self.seen=now
        if now-self.requested>=.5 and hasattr(meter,'request_rhythm'):
            meter.request_rhythm(self.consumer,key+(self.seek_id,));self.requested=now
        fresh=0<=now-getattr(meter,'last_sample',0)<.35 and getattr(meter,'rms_level',.3)>.05
        stamped=getattr(meter,'beat_grid_at',0.)
        grid=getattr(meter,'beat_grid',None) if stamped>=self.acquired and 0<=now-stamped<2.5 else None
        return self.timing.advance(dt,grid,now,active=True,fresh=fresh)
