"""A briefly preloaded second mpv deck; both streams retain their source quality."""
import math,time
from gi.repository import GLib
from youtube_audio import YouTubeAudio


def curve(position):
    """Introduce the new song, hand over the foreground, dissolve the tail.

    The short middle handover limits competing vocals/bass. The longer outer
    phases let the listener hear the incoming texture and outgoing ambience.
    Every join has zero first/second derivative; gains share one peak budget.
    Keep this in sync with mixCurve in apple_web_host/flow.cjs.
    """
    t=max(0.,min(1.,position))
    if t<.38:x=t/.38;start,span=0.,.18
    elif t<.62:x=(t-.38)/.24;start,span=.18,.64
    else:x=(t-.62)/.38;start,span=.82,.18
    incoming=start+span*x*x*x*(x*(x*6-15)+10)
    return 1-incoming,incoming


class YouTubeDecks:
    def __init__(self,host):
        self.host=host;self.standby=None;self.outgoing=None;self.timer=0;self.key=''
        self.beat_sync=True;self.preview=None;self.beat_plan=None;self.start_at=0.;self.play_sent=False;self.prepared_rate=1.
        self.recovery=0.;self.recovering=False

    def prepare(self,item):
        self.cancel();self.key=item['entry']
        self.standby=YouTubeAudio(lambda:None,persistent=False)
        self.standby.play(dict(item,channel=item['artist'],duration=item['duration_ms']/1000))

    @property
    def ready(self):
        loaded=bool(self.standby and self.standby.loaded and not self.standby.failed)
        if loaded and self.beat_sync and getattr(getattr(self.host,'meter',None),'rhythm_key',None):
            if self.preview is None:
                from flow_preview import Preview
                self.preview=Preview(self.standby)
            if self.preview.future.done():
                from flow_beats import match
                plan=match(getattr(self.host.meter,'beat_grid',None),self.preview.future.result())
                rate=plan['rate'] if plan else 1.
                if abs(rate-self.prepared_rate)>.0001:
                    self.standby.mpv.command_async('set','audio-pitch-correction','yes')
                    self.standby.mpv.command_async('set','speed',rate);self.prepared_rate=rate
                return True
            return False
        return loaded

    def transition(self,duration):
        if not self.ready:return False
        old=self.host.youtube;new=self.standby;self.standby=None;self.outgoing=old
        old.changed=lambda:None;old.persistent=False
        new.persistent=True;new.changed=old_callback=self.host.on_youtube_changed
        new.enabled=True;new.paused=False
        new.mpv.command_async('set','volume',0)
        self.beat_plan=None
        if self.preview and self.preview.future.done():
            from flow_beats import match
            try:
                intro=self.preview.future.result();self.beat_plan=match(getattr(self.host.meter,'beat_grid',None),intro)
            except Exception:self.beat_plan=None
            self.preview.cancel();self.preview=None
        self.start_at=time.monotonic();self.play_sent=False
        self.recovery=0.;self.recovering=False
        if not self.beat_plan and self.prepared_rate!=1.:
            new.mpv.command_async('set','speed',1)
        if self.beat_plan:
            p=self.beat_plan;new.mpv.command_async('set','audio-pitch-correction','yes')
            new.mpv.command_async('set','speed',p['rate'])
            first=p['incomingPhase']/p['rate'];minimum=self.start_at+.12+first
            beat=p['phase']+math.ceil((minimum-p['phase'])/p['period'])*p['period']
            self.start_at=beat-first
            self.last_rate=p['rate']
            self.recovery=max(1.5,min(3.5,240/p['bpm']))
        self.host.youtube=new;new.flow_cancel=self.cancel
        self.started=time.monotonic();self.duration=max(.3,float(duration))
        self.waiting=True;self.wait_until=self.start_at+2
        self.timer=GLib.timeout_add(16,self.advance)
        old_callback();return True

    def advance(self):
        new=self.host.youtube;old=self.outgoing
        if (not old and not self.recovering) or not new.mpv or new.failed or (new.paused and self.play_sent and not self.waiting):
            self.timer=0;self.cancel();return False
        now=time.monotonic()
        if not self.play_sent:
            if now<self.start_at:return True
            self.play_sent=True;new.mpv.command_async('set','pause','no')
        if self.waiting:
            # Loading headers alone does not prove audio is running. Leave the
            # outgoing deck audible until the new playback clock has advanced.
            if new.position<=.01 and now<self.wait_until:return True
            self.waiting=False;self.started=now
        t=(now-self.started)/self.duration;a,b=curve(t)
        # mpv's percentage uses a cubic gain law. Undo it so the actual PCM
        # envelopes remain complementary instead of dipping deeply mid-fade.
        if old and old.mpv:old.mpv.command_async('set','volume',a**(1/3)*100)
        new.mpv.command_async('set','volume',b**(1/3)*100)
        if self.beat_plan:
            # Hold the shared beat until the old song is gone, then release
            # the new one to its original tempo over four beats.
            x=max(0.,min(1.,(now-self.started-self.duration)/self.recovery));ease=x*x*(3-2*x)
            rate=self.beat_plan['rate']+(1-self.beat_plan['rate'])*ease
            if abs(rate-self.last_rate)>.0002:
                new.mpv.command_async('set','speed',rate);self.last_rate=rate
        if t>=1:
            if old:
                old.flow_cancel=None;old.persistent=False;old.close();self.outgoing=None
            if self.beat_plan and x<1:self.recovering=True;return True
            self.timer=0;self.cancel();return False
        return True

    def cancel(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        if self.preview:self.preview.cancel();self.preview=None
        for deck in (self.standby,self.outgoing):
            if deck:
                deck.flow_cancel=None;deck.persistent=False
                if deck.mpv:deck.mpv.command_async('set','pause','yes')
                deck.close()
        self.standby=self.outgoing=None;self.key=''
        self.recovering=False;self.prepared_rate=1.
        current=self.host.youtube
        if getattr(current,'flow_cancel',None):
            current.flow_cancel=None
            if current.mpv:
                current.mpv.command_async('set','volume',100);current.mpv.command_async('set','speed',1)
