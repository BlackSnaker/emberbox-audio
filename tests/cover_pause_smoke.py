"""Offline pause geometry, real GL pixels, fallback and transport isolation."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import gi
gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0');gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gdk,GdkPixbuf,GLib,Gtk
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from cover_pause import CoverPause,spring
import cover_pause


def settle(seconds=.04):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        for _ in range(8):
            if not GLib.MainContext.default().pending():break
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)


def wait(predicate,message):
    until=time.monotonic()+4
    while not predicate() and time.monotonic()<until:settle(.02)
    assert predicate(),message


SIZE=320
art=GdkPixbuf.Pixbuf.new_from_file(str(ROOT/'assets/demo-cover.png'))
art=art.scale_simple(SIZE,SIZE,GdkPixbuf.InterpType.BILINEAR)


class Rig:
    def __init__(self,gpu=True):
        self.window=Gtk.Window();self.window.set_decorated(False);self.window.set_resizable(False)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.window.add(body)
        self.layers=Gtk.Overlay();body.pack_start(self.layers,False,False,0)
        self.image=Gtk.Image.new_from_pixbuf(art);self.layers.add(self.image)
        self.pool=ThreadPoolExecutor(max_workers=1);self.surface=CoverPause(self.pool);self.surface.resize(SIZE,22)
        self.layers.add_overlay(self.surface);self.layers.set_overlay_pass_through(self.surface,True)
        self.button=Gtk.Button(label='Transport stays here');body.pack_start(self.button,False,False,0)
        self.window.show_all();settle(.08)
        if gpu:self.surface.warmup(allow_software=True);assert self.surface.driver
        self.surface.sync(True,art,'song');self.baseline=self.geometry()

    def geometry(self):
        return tuple((w.get_allocation().x,w.get_allocation().y,w.get_allocated_width(),w.get_allocated_height())
                     for w in (self.layers,self.button))

    def capture(self,depth,age):
        s=self.surface;s.depth=depth;s.wave=age
        s.area.make_current();s.area.attach_buffers()
        size=SIZE*s.area.get_scale_factor()
        s.driver.draw(size,size,art,None,age,depth,22*s.area.get_scale_factor())
        s.driver.call('Finish')
        read=s.driver.lib.glReadPixels
        read.restype=None;read.argtypes=[C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]
        raw=(C.c_ubyte*(size*size*4))();read(0,0,size,size,0x1908,0x1401,raw)
        return np.ctypeslib.as_array(raw).reshape(size,size,4)[::-1].copy()

    def close(self):self.window.destroy();self.pool.shutdown(wait=True);settle(.03)


settings=Gtk.Settings.get_default();animations=settings.get_property('gtk-enable-animations')
settings.set_property('gtk-enable-animations',True)
rigs=[]
try:
    with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')):
        rig=Rig();rigs.append(rig);s=rig.surface
        uploads=[]
        for name in ('TexImage2D','TexSubImage2D'):
            original=s.driver.functions[name]
            def upload(*args,_original=original):uploads.append(1);return _original(*args)
            s.driver.functions[name]=upload
        s.sync(False,art,'song')
        assert s.tick and s.target==1 and s.depth==0
        wait(lambda:s.depth>.15,'Pause did not reach an intermediate depth')
        assert rig.geometry()==rig.baseline,'Pause must never resize the cover or shift transport'
        depth,velocity=s.depth,s.velocity
        s.sync(True,art,'song')
        assert s.depth==depth and s.velocity==velocity and s.target==0,'Rapid reversal jumped to an endpoint'
        s.sync(False,art,'song')
        wait(lambda:not s.tick,'The pause wave failed to settle and stop')
        assert s.get_visible() and s.depth==1 and s.pixels is art
        s.sync(True,art,'song');s.sync(False,art,'song')
        s.wall_start=GLib.get_monotonic_time()-3_000_000
        wait(lambda:not s.tick,'A stalled compositor did not release the decorative clock')
        assert s.depth==1 and s.wave==s.WAVE_SECONDS,'The time cap must not leave a frozen wave on paused artwork'
        calm=rig.capture(.45,2);wave=rig.capture(.45,.43);later=rig.capture(.45,.68)
        moving=np.max(np.abs(wave.astype(int)-calm.astype(int))[...,:3],axis=-1)
        assert (moving>3).sum()>100,'The paused cover needs a visible local wave'
        assert (moving<=1).sum()>moving.size*.35,'The wave must not flash the whole cover'
        assert np.mean(np.abs(later.astype(int)-wave.astype(int)))>.06,'The wavefront must travel'
        floating=rig.capture(0,2);pressed=rig.capture(1,2)
        scale=s.area.get_scale_factor();edge=round(SIZE*.012*scale)
        assert pressed[SIZE*scale//2,edge,:3].mean()<floating[SIZE*scale//2,edge,:3].mean()*.5,\
            'The cover must reveal the dark socket as it settles into the body'
        assert pressed[0,0,3]==0 and pressed[SIZE*scale//2,SIZE*scale//2,3]==255
        count=len(uploads)
        for depth in (.6,.75,.9,1):rig.capture(depth,2)
        assert len(uploads)==count,'Depth frames must reuse the uploaded cover texture'
        preview=os.environ.get('EMBERBOX_PAUSE_PREVIEW')
        if preview:
            from PIL import Image
            folder=Path(preview);folder.mkdir(parents=True,exist_ok=True)
            for name,data in (('floating',floating),('wave',wave),('pressed',pressed)):
                Image.fromarray(data,'RGBA').save(folder/(name+'.png'))
        s.depth=1;s.wave=2;s.sync(True,art,'song')
        wait(lambda:not s.tick,'Resume did not finish')
        assert not s.get_visible() and s.pixels is None and s.driver.uploaded is None
        s.sync(False,art,'song');assert not s.tick and s.depth==1,'An already paused entry must not replay a wave'
        s.sync(True,art,'song');settle(.1);rig.window.hide();settle()
        assert not s.tick and s.pixels is None and not s.get_visible()
        rig.window.show_all();settle();s.sync(True,art,'song');s.sync(False,art,'song')
        settings.set_property('gtk-enable-animations',False)
        wait(lambda:not s.tick,'Reduced motion did not cancel the wave')
        assert s.pixels is None and not s.get_visible()
        settings.set_property('gtk-enable-animations',True)
        fallback=Rig(gpu=False);rigs.append(fallback)
        with patch.object(cover_pause,'CoverPauseGL',side_effect=RuntimeError('Fixture without GL')):
            fallback.surface.warmup()
        assert fallback.surface.failed and not fallback.surface.driver
        fallback.surface.sync(False,art,'song');settle(.2)
        assert fallback.surface.still.get_mapped() and fallback.surface.rest_image.get_pixbuf() is not None
        assert fallback.geometry()==fallback.baseline
        wait(lambda:not fallback.surface.tick,'Compositor fallback did not settle')
        assert fallback.surface.depth==1
        fallback.surface.sync(True,art,'song')
        wait(lambda:not fallback.surface.tick,'Compositor fallback did not return to live artwork')
        assert not fallback.surface.get_visible()
        driver=s.driver;rig.close()
        assert driver.program==0 and s.closed and s.driver is None
        # The closed-form spring is independent of callback cadence, including
        # mid-flight reversal; it preserves velocity instead of restarting ease.
        values=[]
        for fps in (30,60,144):
            value=velocity=0
            for _ in range(fps):value,velocity=spring(value,velocity,1,1/fps)
            values.append(value)
        assert max(values)-min(values)<1e-10
        print('PASS pause cover: real optical wave and socket, no layout shift, cached texture, continuous reversal, finite idle, compositor fallback, reduced motion and GL cleanup; scale='+str(scale))
        import fullscreen_smoke as fixture
        import fullscreen
        host=fixture.FixtureHost()
        with patch.object(fullscreen,'LyricsClient',fixture.FixtureLyrics),\
             patch.object(fullscreen.Artwork,'load',fixture.image_load):
            settings.set_property('gtk-enable-animations',False)
            stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
            try:
                stage.open();settle(.15)
                stage.window.unfullscreen();stage.window.resize(1024,600);settle(.2)
                # Isolate this cover's frame clock from the unrelated live
                # audio meters during software-GL HiDPI rendering on CI.
                stage.window.remove_tick_callback(stage.tick);stage.tick=0
                GLib.source_remove(stage.timer);stage.timer=0
                settings.set_property('gtk-enable-animations',True)
                stage.cover_pause.warmup(allow_software=True);stage.update()
                commands=list(host.calls)
                geometry=tuple((w.get_allocated_width(),w.get_allocated_height()) for w in (stage.art_shell,stage.footer))
                stage.play_button.clicked();assert host.calls==commands+[(host.source,'toggle')]
                host.playing=False;stage.update()
                assert stage.cover_pause.tick and stage.cover_pause.target==1
                settle(.3)
                assert 0<stage.cover_pause.depth<1
                assert geometry==tuple((w.get_allocated_width(),w.get_allocated_height()) for w in (stage.art_shell,stage.footer))
                stage.play_button.clicked();host.playing=True;stage.update()
                assert stage.cover_pause.target==0 and not stage.motion.playing,'Animated artwork must wait for the cover lift'
                try:wait(lambda:not stage.cover_pause.tick,'Fullscreen resume did not hand back live artwork')
                except AssertionError:
                    p=stage.cover_pause
                    raise AssertionError(('Fullscreen pause clock',p.depth,p.target,p.wave,p.age,p.tick,p.last_now,
                        p.get_mapped(),p.area.get_mapped(),p.area.get_allocated_width(),p.area.get_allocated_height(),p.playing))
                stage.update();assert stage.motion.playing,'Live artwork must resume after the optical handoff'
                assert host.calls==commands+[(host.source,'toggle')]*2,'Pause visuals sent an extra transport command'
                host.playing=False;stage.music.loading=True;stage.update()
                assert not stage.cover_pause.tick and not stage.cover_pause.get_visible(),'Buffering is not a user pause'
                stage.music.loading=False;stage.update()
                assert stage.cover_pause.depth==1 and not stage.cover_pause.tick
                stage.show_page('library');settle(.05)
                assert not stage.cover_pause.get_visible() and stage.cover_pause.pixels is None
                stage.hide();assert not stage.cover_pause.tick
                print('PASS fullscreen pause integration: confirmed playback, transport unchanged, stable footer, no buffering pulse, page and hide cleanup')
            finally:stage.close();host.window.destroy()
finally:
    settings.set_property('gtk-enable-animations',animations)
    for rig in rigs:rig.close()
