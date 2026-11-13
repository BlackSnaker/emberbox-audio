"""Mirrorball: real GTK selection, cached optics, cleanup and input isolation."""
import json,os,time
from pathlib import Path
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from gi.repository import Gtk,Gdk,GLib


def settle(seconds=.15):
    until=time.monotonic()+seconds;context=GLib.MainContext.default()
    while time.monotonic()<until:
        for _ in range(3):
            if context.pending():context.iteration(False)
        time.sleep(.002)


def wait(predicate,limit=8):
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:settle(.04)
    assert predicate()


host=f.FixtureHost();host.appearance=Appearance();host.settings.appearance=host.appearance
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network')),patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.open();wait(lambda:not stage.reveal.active);stage.show_settings();settle(.2)
        settings=host.settings;calls=list(host.calls);sound_calls=list(host.sound.calls)
        settings.mirror_switch.set_active(True)
        surface=stage.winter_surface.mirror
        wait(lambda:surface.painter and surface.draws>2)
        assert host.appearance.mirrorball and host.appearance.dark and not host.appearance.nocturne
        assert not settings.night_switch.get_active() and not settings.theme_switch.get_active()
        assert stage.window.get_style_context().has_class('mirrorball-theme')
        assert settings.popover.get_style_context().has_class('mirrorball-theme')
        assert json.loads(host.appearance.path.read_text())['theme']=='mirrorball'
        assert host.appearance.path.stat().st_mode&0o777==0o600
        restored=Appearance(host.appearance.path)
        try:assert restored.mirrorball
        finally:restored.close()
        assert surface.area.get_can_focus() is False
        assert not stage.winter_surface.snow.active and not stage.winter_surface.top.get_visible()
        settings.popover.popdown();settle(.4)
        # Cold tube/heart sprites have their own workers. Do not count their
        # initial bake as continuous optical-animation cost.
        wait(lambda:stage.equalizer.frames_ready,limit=15);settle(.8)
        phase=surface.phase;wall=time.monotonic();cpu=time.process_time();draws=surface.draws
        print('Optical region:',surface.area.get_allocated_width(),surface.area.get_allocated_height(),flush=True)
        settle(1.)
        print('Optics fixture: %.1f draws/s, process CPU %.1f ms/s'%((surface.draws-draws)/(time.monotonic()-wall),(time.process_time()-cpu)*1000/(time.monotonic()-wall)))
        assert surface.phase!=phase and surface.tick
        surface.set_suspended(True);settle(.2)
        wall=time.monotonic();cpu=time.process_time();settle(1.)
        print('Same live player without optical motion CPU %.1f ms/s'%((time.process_time()-cpu)*1000/(time.monotonic()-wall)))
        surface.set_suspended(False);settle(.1)
        target=os.environ.get('EMBERBOX_MIRROR_PREVIEW')
        if target:
            directory=Path(target);directory.mkdir(parents=True,exist_ok=True)
            width,height=stage.window.get_size()
            Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(directory/'mirrorball-fullscreen.png'),'png',[],[])
            stage.show_settings();settle(.3)
            Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(directory/'mirrorball-settings.png'),'png',[],[])
            host.settings.popover.popdown()
        prefs=stage.window.get_settings();animations=prefs.get_property('gtk-enable-animations')
        prefs.set_property('gtk-enable-animations',False);settle(.2)
        assert not surface.tick;phase=surface.phase;settle(.15);assert surface.phase==phase and surface.area.get_visible()
        wall=time.monotonic();cpu=time.process_time();settle(1.)
        print('Static fixture CPU %.1f ms/s'%((time.process_time()-cpu)*1000/(time.monotonic()-wall)))
        prefs.set_property('gtk-enable-animations',animations);settle(.15)
        surface.set_suspended(True);assert not surface.tick
        surface.set_suspended(False);settle(.1);assert surface.tick
        stage.window.hide();settle(.1);assert not surface.tick
        stage.window.show();settle(.15);assert surface.tick
        for width,height in ((1920,1080),(1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.25)
            assert stage.window.get_size()==(width,height)
            f.assert_controls_fit(stage)
        host.appearance.set_theme('nocturne');settle(.1)
        assert not surface.tick and not surface.painter and not surface.area.get_visible()
        assert not stage.window.get_style_context().has_class('mirrorball-theme')
        assert not settings.mirror_switch.get_active()
        host.appearance.set_theme('mirrorball');host.appearance.set_theme('classic');settle(.3)
        assert not surface.tick and not surface.painter,'Stale preparation revived disabled theme'
        assert host.calls==calls and host.sound.calls==sound_calls,'Theme changed sound/transport'
        print('PASS Mirrorball selection, persistence, cached animation, reduced motion, suspension, cleanup and three sizes')
    finally:stage.close();host.window.destroy()
