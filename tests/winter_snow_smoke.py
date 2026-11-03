"""Local Cairo damage, whole-window responsiveness and snow lifecycle."""
import os,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from gi.repository import Gdk,GLib,Gtk


def settle(seconds):
    until=time.monotonic()+seconds
    context=GLib.MainContext.default()
    while time.monotonic()<until:
        for _ in range(2):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)

host=f.FixtureHost();legacy=Path(f.fixture.name)/'legacy-appearance.json'
legacy.write_text('{"theme":"christmas"}')
host.appearance=Appearance(legacy);host.settings.appearance=host.appearance
assert host.appearance.christmas and not host.appearance.snow_enabled,'Existing themed installations must recover with snow disabled'
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        host.appearance.set_christmas(True);stage.prewarm();stage.open();f.wait_transition(stage)
        snow=stage.winter_surface.snow
        assert not host.appearance.snow_enabled and snow.tick==snow.timer==0,'Snow is opt-in after the GL compositor regression'
        assert isinstance(snow.area,Gtk.DrawingArea) and not isinstance(snow.area,Gtk.GLArea)
        assert not snow.area.get_has_window(),'Snow must share GTK’s existing drawing target'
        def responsiveness(seconds=.6):
            beats=[]
            timer=GLib.timeout_add(10,lambda:beats.append(time.monotonic()) or True)
            start=time.process_time();settle(seconds);cpu=time.process_time()-start
            GLib.source_remove(timer)
            gaps=sorted(b-a for a,b in zip(beats,beats[1:]))
            assert len(beats)>=8,'UI timers stalled during snow'
            return cpu,gaps[min(len(gaps)-1,int(len(gaps)*.95))]
        baseline_cpu,baseline_gap=responsiveness()
        stage.show_settings();settle(.05)
        assert not host.settings.snow_switch.get_active()
        host.settings.snow_switch.set_active(True);host.settings.popover.popdown()
        assert host.appearance.snow_enabled
        restored=Appearance(host.appearance.path)
        assert restored.christmas and restored.snow_enabled
        restored.close()
        commands=list(host.calls);size=stage.window.get_size()
        # An unrelated damage clip must not invoke any snow masks.

        snow.begin();settle(.1)
        assert snow.painter and not snow.failed,'Existing Cairo drawing must be available without Pycairo or OpenGL'
        assert snow.active and snow.tick and snow.area.get_mapped()
        assert snow.area.get_parent().get_overlay_pass_through(snow.area)
        # Advance the exact presentation-time path without waiting 48 seconds.
        # Also render actual deposited/melting flakes through GTK’s damage regions.
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
        assert snow.painter.draws>0,'Cairo must paint the live snow layer'
        from cover_pause_paint import bindings
        c,_,_=bindings();output=c.cairo_image_surface_create(0,32,32);cr=c.cairo_create(output)
        try:
            original=snow.dots;snow.dots=[(1000.,1000.,2.,.5,2.)]
            paints=snow.painter.draws;snow.painter.draw(None,cr,None)
            assert snow.painter.draws==paints,'Snow outside GTK damage must not be drawn'
            snow.dots=original
        finally:c.cairo_destroy(cr);c.cairo_surface_destroy(output)
        assert snow.damage_pixels<size.width*size.height*.03,'Invalidate tiny footprints rather than a fullscreen surface'
        # Keep measuring the normal advancing path, not just its tiny painter.
        snow.model.start(*size);snow.start_time=stage.window.get_frame_clock().get_frame_time()/1e6-8.
        snow.tick=snow.area.add_tick_callback(snow.advance)
        active_cpu,active_gap=responsiveness()
        assert active_gap<baseline_gap+.04,('Whole-window responsiveness regressed',baseline_gap,active_gap)
        snow.area.remove_tick_callback(snow.tick);snow.tick=0;snow.start_time=100.
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
        print('PASS local Cairo snowfall, edge landing/melt, sparse damage and lifecycle; whole-window timer p95 baseline/active',round(baseline_gap*1000,1),round(active_gap*1000,1),'ms; CPU',round(baseline_cpu,3),round(active_cpu,3),'s')
    finally:stage.close();host.appearance.close();host.window.destroy()
