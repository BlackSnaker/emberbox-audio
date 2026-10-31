"""Offline pause pixels, frame cost, geometry and transport isolation."""
from concurrent.futures import Future,ThreadPoolExecutor
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
from room_snapshot import snapshot
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
    def __init__(self):
        self.window=Gtk.Window();self.window.set_decorated(False);self.window.set_resizable(False)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.window.add(body)
        self.layers=Gtk.Overlay();body.pack_start(self.layers,False,False,0)
        self.image=Gtk.Image.new_from_pixbuf(art);self.layers.add(self.image)
        self.pool=ThreadPoolExecutor(max_workers=1);self.surface=CoverPause(self.pool);self.surface.resize(SIZE,22)
        self.layers.add_overlay(self.surface);self.layers.set_overlay_pass_through(self.surface,True)
        self.button=Gtk.Button(label='Transport stays here');body.pack_start(self.button,False,False,0)
        self.window.show_all();settle(.08)
        self.surface.sync(True,art,'song');self.baseline=self.geometry()

    def geometry(self):
        return tuple((w.get_allocation().x,w.get_allocation().y,w.get_allocated_width(),w.get_allocated_height())
                     for w in (self.layers,self.button))

    def capture(self,depth,age,live=False):
        s=self.surface;s.depth=depth;s.wave=age;s.queue_frame()
        if live:s.rest_image.hide();s.canvas.show()
        rect=Gdk.Rectangle();rect.width=rect.height=SIZE
        width,height,raw=snapshot(s,rect)
        return np.frombuffer(raw,dtype=np.uint8).reshape(height,width,4)[...,[2,1,0,3]].copy()

    def close(self):self.window.destroy();self.pool.shutdown(wait=True);settle(.03)


settings=Gtk.Settings.get_default();animations=settings.get_property('gtk-enable-animations')
settings.set_property('gtk-enable-animations',True)
rigs=[]
try:
    with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')):
        rig=Rig();rigs.append(rig);s=rig.surface
        assert not any(isinstance(w,Gtk.GLArea) for w in s.get_children()),'Pause must not create a nested GL surface'
        deferred=Future()
        with patch.object(rig.pool,'submit',return_value=deferred):s.sync(False,art,'song')
        settle(.06)
        assert not s.tick and s.target==1 and s.depth==0 and s.wave==0,\
            'Cold preparation must not consume undisplayed animation frames'
        deferred.set_result(cover_pause.cover_frames((bytes(art.get_pixels()),SIZE,SIZE,art.get_has_alpha(),art.get_rowstride()),SIZE,22))
        wait(lambda:s.tick,'Ready artwork did not start its presentation clock')
        wait(lambda:s.depth>.15,'Pause did not reach an intermediate depth')
        assert rig.geometry()==rig.baseline,'Pause must never resize the cover or shift transport'
        depth,velocity,crest=s.depth,s.velocity,s.wave
        s.sync(True,art,'song')
        assert s.depth==depth and s.velocity==velocity and s.target==0,'Rapid reversal jumped to an endpoint'
        assert s.wave==crest,'Release must preserve the existing reflection rather than replace it'
        s.sync(False,art,'song')
        assert s.wave==crest,'A rapid second pause must not flash a fresh circle over the old one'
        wait(lambda:not s.tick,'The pause wave failed to settle and stop')
        assert s.get_visible() and s.depth==1 and s.pixels is art
        s.sync(True,art,'song');s.sync(False,art,'song')
        s.wall_start=GLib.get_monotonic_time()-3_000_000
        wait(lambda:not s.tick,'A stalled compositor did not release the decorative clock')
        assert s.depth==1 and s.wave==s.WAVE_SECONDS,'The time cap must not leave a frozen wave on paused artwork'
        wait(lambda:s.painter.surface is not None,'Cached print did not arrive')
        calm=rig.capture(.45,2);wave=rig.capture(.45,.43);later=rig.capture(.45,.68)
        moving=np.max(np.abs(wave.astype(int)-calm.astype(int))[...,:3],axis=-1)
        assert (moving>3).sum()>100,'The paused cover needs a visible local wave'
        assert (moving<=1).sum()>moving.size*.35,'The wave must not flash the whole cover'
        assert np.mean(np.abs(later.astype(int)-wave.astype(int)))>.06,'The wavefront must travel'
        floating=rig.capture(0,2);pressed=rig.capture(1,2)
        scale=1;edge=max(0,int(SIZE*.03)-1)
        assert pressed[SIZE//2,edge,:3].mean()<floating[SIZE//2,edge,:3].mean()*.82,\
            'The molded seat must remain distinct from the photograph'
        settled=rig.capture(1,2,live=True)
        assert np.max(np.abs(settled.astype(int)-pressed.astype(int)))<=2,\
            'The animated endpoint must match the static paused picture exactly'
        assert pressed[0,0,3]==0 and pressed[SIZE*scale//2,SIZE*scale//2,3]==255
        surface=s.painter.surface;well=s.painter.well;buffer=s.painter.buffer;prepared=s.frame_serial;durations=[]
        for depth in (.6,.75,.9,1):
            start=time.perf_counter();rig.capture(depth,2);durations.append(time.perf_counter()-start)
        assert s.painter.surface==surface and s.painter.well==well and s.painter.buffer==buffer and s.frame_serial==prepared,\
            'Frames must reuse the cached print, relief and logical-resolution buffer'
        preview=os.environ.get('EMBERBOX_PAUSE_PREVIEW')
        if preview:
            from PIL import Image
            folder=Path(preview);folder.mkdir(parents=True,exist_ok=True)
            for name,data in (('floating',floating),('wave',wave),('pressed',pressed)):
                Image.fromarray(data,'RGBA').save(folder/(name+'.png'))
        s.depth=1;s.wave=2;s.sync(True,art,'song')
        wait(lambda:not s.tick,'Resume did not finish')
        assert not s.get_visible() and s.pixels is None and s.painter.surface is None and s.painter.well is None
        s.sync(False,art,'song');assert not s.tick and s.depth==1,'An already paused entry must not replay a wave'
        s.sync(True,art,'song');settle(.1);rig.window.hide();settle()
        assert not s.tick and s.pixels is None and not s.get_visible()
        rig.window.show_all();settle();s.sync(True,art,'song');s.sync(False,art,'song')
        settings.set_property('gtk-enable-animations',False)
        wait(lambda:not s.tick,'Reduced motion did not cancel the wave')
        assert s.pixels is None and not s.get_visible()
        settings.set_property('gtk-enable-animations',True)
        painter=s.painter;rig.close()
        assert painter.closed and painter.surface is None and painter.well is None and painter.buffer is None and painter.context is None and not painter.handler
        SIZE=720;art=art.scale_simple(SIZE,SIZE,GdkPixbuf.InterpType.BILINEAR)
        large=Rig();rigs.append(large);large.surface.sync(False,art,'large-cover')
        wait(lambda:large.surface.painter.surface is not None,'Large cached print did not arrive')
        costs=[];serial=large.surface.frame_serial
        for age in (.25,.4,.55,.7,.85):
            start=time.perf_counter();large.capture(.5,age);costs.append(time.perf_counter()-start)
        assert large.surface.frame_serial==serial,'A large wave must not regenerate artwork every frame'
        assert max(costs)<.08,('The720px pause painter is blocking a frame',costs)
        # Measure actual native drawing separately from the screenshot's pixel
        # readback/copy. At 2x only the final image composite scales up.
        painter=large.surface.painter;c=painter.cairo;scale=large.surface.get_scale_factor()
        output=c.cairo_image_surface_create(0,SIZE*scale,SIZE*scale);context=c.cairo_create(output)
        c.cairo_scale(context,scale,scale);native=[];buffer=painter.buffer
        try:
            for index in range(60):
                large.surface.wave=.20+index*.012
                started=time.perf_counter();painter.draw(None,context,None);c.cairo_surface_flush(output)
                native.append(time.perf_counter()-started)
            p95=float(np.percentile(native,95))
            limit=.012 if os.environ.get('EMBERBOX_FPS_ASSERT')=='1' else .040
            assert p95<limit,('Pause native drawing budget',scale,p95,limit)
            assert painter.buffer==buffer,'The native draw must retain its buffer'
        finally:c.cairo_destroy(context);c.cairo_surface_destroy(output)
        print('PASS720px native draw '+str(scale)+'x: p95='+str(round(p95*1000,2))+'ms, retained buffer')
        # Real mapped GTK frame-clock cadence, with no screenshot/readback in
        # the loop. Strict cadence is opt-in on a quiet reference machine;
        # shared CI CPU scheduling cannot promise monitor presentation times.
        large.surface.sync(True,art,'large-cover');wait(lambda:not large.surface.tick,'Cadence lift did not finish')
        clock=large.window.get_frame_clock();times=[]
        def presented(frame_clock):
            if large.surface.tick and large.surface.age>.08:times.append(frame_clock.get_frame_time())
        handler=clock.connect('after-paint',presented)
        try:
            large.surface.sync(True,art,'large-cover');large.surface.sync(False,art,'large-cover')
            wait(lambda:large.surface.tick,'Cadence preparation did not finish')
            wait(lambda:not large.surface.tick,'Cadence pause did not finish')
        finally:clock.disconnect(handler)
        assert len(times)>20,'The mapped animation must present moving frames'
        gaps=np.diff(times)/1000;fps=(len(times)-1)*1e6/(times[-1]-times[0]);gap95=float(np.percentile(gaps,95))
        if os.environ.get('EMBERBOX_FPS_ASSERT')=='1':
            assert fps>=58.5 and gap95<18.5,('60Hz presentation cadence',fps,gap95)
        print('GTK720px '+str(scale)+'x presentation: '+str(round(fps,2))+' FPS; p95 interval='+str(round(gap95,2))+'ms')
        large.close()
        print('PASS720px cover frame budget: max='+str(round(max(costs)*1000,2))+'ms, one cached print')
        # The closed-form spring is independent of callback cadence, including
        # mid-flight reversal; it preserves velocity instead of restarting ease.
        values=[]
        for fps in (30,60,144):
            value=velocity=0
            for _ in range(fps):value,velocity=spring(value,velocity,1,1/fps)
            values.append(value)
        assert max(values)-min(values)<1e-10
        print('PASS pause cover: soft crests and socket, no nested GL, stable layout, cached print, reversal, finite idle, reduced motion and native cleanup; max320px frame='+str(round(max(durations)*1000,2))+'ms')
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
                stage.update()
                commands=list(host.calls)
                geometry=tuple((w.get_allocated_width(),w.get_allocated_height()) for w in (stage.art_shell,stage.footer))
                stage.play_button.clicked();assert host.calls==commands+[(host.source,'toggle')]
                host.playing=False;stage.update()
                wait(lambda:stage.cover_pause.tick,'Fullscreen prepared cover did not start')
                assert stage.cover_pause.target==1
                settle(.3)
                assert 0<stage.cover_pause.depth<1
                assert geometry==tuple((w.get_allocated_width(),w.get_allocated_height()) for w in (stage.art_shell,stage.footer))
                stage.play_button.clicked();host.playing=True;stage.update()
                assert stage.cover_pause.target==0 and not stage.motion.playing,'Animated artwork must wait for the cover lift'
                try:wait(lambda:not stage.cover_pause.tick,'Fullscreen resume did not hand back live artwork')
                except AssertionError:
                    p=stage.cover_pause
                    raise AssertionError(('Fullscreen pause clock',p.depth,p.target,p.wave,p.age,p.tick,p.last_now,
                        p.get_mapped(),p.canvas.get_mapped(),p.canvas.get_allocated_width(),p.canvas.get_allocated_height(),p.playing))
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
