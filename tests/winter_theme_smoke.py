"""Offline seasonal preference, fullscreen geometry and finite decoration checks."""
import os
from pathlib import Path
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from gi.repository import Gdk

host=f.FixtureHost();host.appearance=Appearance();host.settings.appearance=host.appearance
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.prewarm();stage.open();f.wait_transition(stage)
        original=stage.window.get_size();commands=list(host.calls)
        stage.show_settings();f.settle(.2)
        host.settings.theme_switch.set_active(True);host.settings.popover.popdown();f.settle(1.6)
        assert host.appearance.christmas and stage.winter_surface.top.get_mapped()
        assert not stage.winter_surface.tick,'Seasonal entrance must stop after settling'
        assert stage.winter_surface.top.get_parent().get_overlay_pass_through(stage.winter_surface.top)
        assert stage.winter_surface.corner.get_parent().get_overlay_pass_through(stage.winter_surface.corner)
        assert stage.window.get_size()==original and host.calls==commands
        assert 'christmas-theme' in stage.window.get_style_context().list_classes()
        f.assert_controls_fit(stage)
        restored=Appearance(host.appearance.path)
        assert restored.christmas,'Theme must survive a player restart'
        assert host.appearance.path.stat().st_mode&0o777==0o600
        restored.close()
        target=os.environ.get('EMBERBOX_WINTER_PREVIEW')
        def shot(name):
            if target:
                folder=Path(target);folder.mkdir(parents=True,exist_ok=True);w,h=stage.window.get_size()
                Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,w,h).savev(str(folder/name),'png',[],[])
        shot('winter-fullscreen.png')
        stage.show_settings();f.settle(.2);shot('winter-fullscreen-settings.png');host.settings.popover.popdown()
        for w,h in ((1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(w,h);f.settle(.4)
            assert stage.window.get_size()==(w,h)
            f.assert_controls_fit(stage)
        host.appearance.set_christmas(False);f.settle(.2)
        assert not stage.winter_surface.top.get_visible()
        assert 'christmas-theme' not in stage.window.get_style_context().list_classes()
        settings=stage.window.get_settings();animations=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False)
        try:
            host.appearance.set_christmas(True);f.settle(.3)
            assert stage.winter_surface.tick==0 and stage.winter_surface.top.get_opacity()==1.
            host.appearance.set_christmas(False);f.settle(.2)
            assert not stage.winter_surface.top.get_visible(),'Stale render completion must not resurrect disabled decorations'
        finally:settings.set_property('gtk-enable-animations',animations)
        assert host.calls==commands,'A visual theme must never change audio or playback'
        print('PASS winter theme persistence, live settings, unchanged transport, small screens and finite decoration')
    finally:stage.close();host.appearance.close();host.window.destroy()
