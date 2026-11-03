"""Real GL snow, live shelf geometry, input transparency and idle cleanup."""
import os,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from gi.repository import Gdk,GLib


def settle(seconds):
    until=time.monotonic()+seconds
    context=GLib.MainContext.default()
    while time.monotonic()<until:
        for _ in range(2):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)

host=f.FixtureHost();host.appearance=Appearance()
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        host.appearance.set_christmas(True);stage.prewarm();stage.open();f.wait_transition(stage)
        snow=stage.winter_surface.snow;snow.allow_software=True
        commands=list(host.calls);size=stage.window.get_size()
        snow.begin();settle(.1)
        assert snow.driver and not snow.failed,'Real GLSL snow sprites must compile'
        assert snow.active and snow.tick and snow.area.get_mapped()
        assert snow.area.get_parent().get_overlay_pass_through(snow.area)
        # Advance the exact presentation-time path without waiting 48 seconds.
        # Also render actual deposited/melting flakes through Mesa.
        snow.area.remove_tick_callback(snow.tick);snow.tick=0;snow.start_time=100.
        for age in (0.,2.,4.,6.,8.,10.,12.):
            clock=SimpleNamespace(get_frame_time=lambda t=age:(100.+t)*1e6)
            snow.advance(snow.area,clock);settle(.04)
        assert any(dot[2]<0 for dot in snow.dots),'The real cover/console must catch snow'
        assert stage.window.get_size()==size and host.calls==commands
        stage.next_button.clicked();assert host.calls==commands+[(host.source,'next')]
        commands=list(host.calls)
        target=os.environ.get('EMBERBOX_SNOW_PREVIEW')
        if target:
            p=Path(target);p.parent.mkdir(exist_ok=True,parents=True);w,h=stage.window.get_size()
            Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,w,h).savev(str(p),'png',[],[])
        # Render time after shader warmup is bounded; no per-frame image upload.
        snow.area.make_current();snow.area.attach_buffers()
        samples=[]
        for _ in range(6):
            start=time.perf_counter();snow.driver.draw(*size,1,snow.dots,True);snow.driver.call('Finish')
            samples.append((time.perf_counter()-start)*1000)
        snow.advance(snow.area,SimpleNamespace(get_frame_time=lambda:149e6));settle(.05)
        assert not snow.active and not snow.tick and snow.timer and not snow.area.get_visible()
        assert not snow.dots,'All deposits must thaw and rendering must stop'
        snow.begin();settle(.05)
        stage.window.unfullscreen();stage.window.resize(1280,720);settle(.2)
        assert not snow.active and not snow.tick and snow.timer,'Resize must clear old-geometry deposits and defer the next shower'
        stage.window.resize(*size);settle(.2)
        snow.begin();settle(.05);stage.hide();settle(.05)
        assert not snow.active and snow.tick==snow.timer==0,'Hidden windows must have no snow work'
        stage.open();f.wait_transition(stage)
        settings=stage.window.get_settings();animations=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False)
        try:
            settle(.05);assert snow.tick==snow.timer==0
            snow.begin();assert not snow.active,'Respect reduced-motion settings'
        finally:settings.set_property('gtk-enable-animations',animations)
        host.appearance.set_christmas(False);settle(.05)
        assert snow.tick==snow.timer==0 and not snow.area.get_visible()
        assert stage.window.get_size()==size and host.calls==commands
        print('PASS GL snowfall, edge landing/melt, input transparency, idle/hidden/reduced-motion cleanup; median draw',round(sorted(samples)[len(samples)//2],2),'ms')
    finally:stage.close();host.appearance.close();host.window.destroy()
