"""A briefly preloaded second mpv deck; both streams retain their source quality."""
import time
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

    def prepare(self,item):
        self.cancel();self.key=item['entry']
        self.standby=YouTubeAudio(lambda:None,persistent=False)
        self.standby.play(dict(item,channel=item['artist'],duration=item['duration_ms']/1000))

    @property
    def ready(self):return bool(self.standby and self.standby.loaded and not self.standby.failed)

    def transition(self,duration):
        if not self.ready:return False
        old=self.host.youtube;new=self.standby;self.standby=None;self.outgoing=old
        old.changed=lambda:None;old.persistent=False
        new.persistent=True;new.changed=old_callback=self.host.on_youtube_changed
        new.enabled=True;new.paused=False
        new.mpv.command_async('set','volume',0)
        self.host.youtube=new;new.flow_cancel=self.cancel
        new.mpv.command_async('set','pause','no')
        self.started=time.monotonic();self.duration=max(.3,float(duration))
        self.waiting=True;self.wait_until=self.started+2
        self.timer=GLib.timeout_add(16,self.advance)
        old_callback();return True

    def advance(self):
        new=self.host.youtube;old=self.outgoing
        if not old or not new.mpv or new.paused or new.failed:
            self.timer=0;self.cancel();return False
        now=time.monotonic()
        if self.waiting:
            # Loading headers alone does not prove audio is running. Leave the
            # outgoing deck audible until the new playback clock has advanced.
            if new.position<=.01 and now<self.wait_until:return True
            self.waiting=False;self.started=now
        t=(now-self.started)/self.duration;a,b=curve(t)
        # mpv's percentage uses a cubic gain law. Undo it so the actual PCM
        # envelopes remain complementary instead of dipping deeply mid-fade.
        if old.mpv:old.mpv.command_async('set','volume',a**(1/3)*100)
        new.mpv.command_async('set','volume',b**(1/3)*100)
        if t>=1:self.timer=0;self.cancel();return False
        return True

    def cancel(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        for deck in (self.standby,self.outgoing):
            if deck:
                deck.flow_cancel=None;deck.persistent=False
                if deck.mpv:deck.mpv.command_async('set','pause','yes')
                deck.close()
        self.standby=self.outgoing=None;self.key=''
        current=self.host.youtube
        if getattr(current,'flow_cancel',None):
            current.flow_cancel=None
            if current.mpv:current.mpv.command_async('set','volume',100)
