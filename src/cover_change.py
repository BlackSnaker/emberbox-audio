"""Connect visual cover changes to existing transport facts, never to playback timing."""
import time
from music_library import snapshot
from listening_queue import matches
from cover_ripple import CoverRipple


def identity(source,state):
    key=state.get('uri') or state.get('id') or state.get('catalogId')
    return (source,str(key)) if key else (source,state.get('title',''),state.get('artist',''))


def playback_ready(host):
    if not host.playing or host.length<=0:return False
    if host.source=='apple-music' and host.apple_mode=='native':
        state=host.apple_web.state
        spatial=state.get('spatial') or {}
        if spatial.get('enabled'):
            return spatial.get('phase')=='playing' and not spatial.get('switching')
    if host.source=='youtube' and host.youtube_mode=='native':
        audio=host.youtube
        return bool(getattr(audio,'loaded',False) and not getattr(audio,'loading',False)
                    and not getattr(audio,'failed',False) and not getattr(audio,'error',''))
    return True


def failure_token(host):
    if host.source=='apple-music' and host.apple_mode=='native':
        failed=(host.apple_web.state.get('spatial') or {}).get('switchError')
        if isinstance(failed,dict):return ('apple',str(failed.get('id','')),str(failed.get('code','')))
    if host.source=='youtube' and host.youtube_mode=='native':
        error=getattr(host.youtube,'error','')
        if error:return ('youtube',str(error))
    return None


class CoverChange:
    def __init__(self,stage,layers):
        self.stage=stage;self.surface=CoverRipple()
        layers.add_overlay(self.surface);layers.set_overlay_pass_through(self.surface,True)
        self.state=None;self.key=None;self.pending=False;self.target=None;self.origin=None
        self.generation=None;self.queue_generation=stage.music.play_generation
        self.confirmed=False;self.ready_at=None;self.requested_at=0.;self.loaded_url=None
        self.failure=None

    def eligible(self):
        s=self.stage
        return s.visible and not s.closed and s.page=='playing' and not s.reveal.active

    def current_art(self):
        s=self.stage
        return self.surface.get_pixbuf() or s.motion_image.get_pixbuf() or s.cover.get_pixbuf()

    def request(self,target=None,generation=None):
        if not self.eligible():return
        h=self.stage.host;state=snapshot(h)
        if target and matches(target,state):self.cancel();return
        pixels=self.current_art()
        self.pending=self.surface.begin(pixels)
        self.target=target;self.generation=generation
        self.origin=identity(h.source,state);self.confirmed=False;self.ready_at=None
        self.failure=failure_token(h)
        self.requested_at=time.monotonic()

    def queue_changed(self):
        music=self.stage.music
        if self.queue_generation==music.play_generation:return
        self.queue_generation=music.play_generation
        if music.loading and music.book.active==self.stage.host.source:
            self.request(music.book.current(self.stage.host.source),music.play_generation)
        elif self.pending and self.generation is not None:self.cancel()

    def observe(self):
        s=self.stage;h=s.host;state=snapshot(h);key=identity(h.source,state)
        previous=self.key
        self.key=key;self.state=state
        if previous is None:return
        if previous[0]!=key[0]:self.cancel();return
        if not self.eligible():
            if self.pending:self.cancel()
            return
        changed=key!=previous and bool(state.get('title')) and state.get('valid')
        if changed and not self.pending:
            self.request()
            # Identity already moved: this is an automatic/external change.
            self.origin=previous
        if not self.pending:return
        if not self.surface.active:self.cancel();return
        if self.generation is not None and self.stage.music.play_generation!=self.generation:
            self.cancel();return
        if self.generation is not None and self.stage.music.error:
            self.cancel();return
        failed=failure_token(h)
        if failed and failed!=self.failure:
            if not self.target or failed[0]!='apple' or failed[1]==str(self.target.get('id','')):
                self.cancel();return
        spatial=(getattr(getattr(h,'apple_web',None),'state',{}).get('spatial') or {}) if h.source=='apple-music' else {}
        preparing=(h.source=='apple-music' and (spatial.get('phase') in ('preparing','priming') or spatial.get('switching'))
                   or h.source=='youtube' and getattr(h.youtube,'loading',False))
        if not state.get('valid') and not state.get('title') and not self.stage.music.loading and not preparing:
            self.cancel();return
        self.confirmed=matches(self.target,state) if self.target else key!=self.origin
        if self.confirmed:
            if playback_ready(h):
                if self.ready_at is None:self.ready_at=time.monotonic()
                pixels=s.cover.get_pixbuf()
                if self.loaded_url==(h.art_url or ''):
                    self.surface.supply(pixels);self.surface.resolve()
                elif time.monotonic()-self.ready_at>3:
                    # A stalled image CDN must not keep signalling stalled audio.
                    # A late high-resolution image still uses Artwork's token guard.
                    self.surface.supply(pixels);self.surface.resolve()
        elif self.generation is None and not preparing and time.monotonic()-self.requested_at>3.5:
            # Previous often restarts the current song; it has no new artwork.
            self.cancel()

    def art_ready(self,pixels,url):
        self.loaded_url=url
        if self.pending and self.confirmed and url==(self.stage.host.art_url or ''):
            self.surface.supply(pixels)

    def cancel(self):
        self.surface.cancel();self.pending=False;self.target=None;self.origin=None
        self.generation=None;self.confirmed=False;self.ready_at=None

    def reset(self):
        self.cancel();self.state=self.key=None
        self.queue_generation=self.stage.music.play_generation

    def close(self):
        self.reset();self.surface.close()
