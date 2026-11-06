"""Offline Nocturne selection, dark materials and unchanged playback/layout.

All media and metadata are Ember's original fixtures. No account, real audio
stream or microphone is read. The compact material fixture also applies the
real per-cover tint provider, checking that it cannot brighten the night theme.
"""
import json
import os
from pathlib import Path
import time
from unittest.mock import patch

import fullscreen_smoke as f
import fullscreen
import numpy as np
from seasonal_theme import Appearance
from cover_tint import CoverTint
from gi.repository import Gdk, GdkPixbuf, Gtk, GLib


def settle(seconds=.1):
    # Snow may continuously enqueue damage on a software-rendered fullscreen
    # window. Never drain MainContext.pending() without a per-cycle bound.
    until=time.monotonic()+seconds
    context=GLib.MainContext.default()
    while time.monotonic()<until:
        for _ in range(2):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)


def wait(predicate, message, limit=4):
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:
        settle(.03)
    assert predicate(), message


def pixels(image):
    pixbuf=image.get_pixbuf()
    if not pixbuf:return None
    return pixbuf.get_pixels()


def background_mean(image):
    pixbuf=image.get_pixbuf();assert pixbuf
    array=np.frombuffer(pixbuf.get_pixels(),np.uint8).reshape(pixbuf.get_height(),pixbuf.get_rowstride())
    array=array[:,:pixbuf.get_width()*pixbuf.get_n_channels()].reshape(pixbuf.get_height(),pixbuf.get_width(),pixbuf.get_n_channels())
    return array[::max(1,pixbuf.get_height()//48),::max(1,pixbuf.get_width()//64),:3].mean(axis=(0,1))


host=f.FixtureHost();host.appearance=Appearance();host.settings.appearance=host.appearance
mini=None
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected night fixture network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.prewarm();stage.open();f.wait_transition(stage)
        wait(lambda:stage.background.get_pixbuf() is not None,'Classic background was not prepared')
        classic=pixels(stage.background);classic_mean=background_mean(stage.background)
        classic_edition=stage.edition_label.get_text();original=stage.window.get_size()
        commands=list(host.calls);sound_commands=list(host.sound.calls)

        stage.show_settings();settle(.15)
        popup=host.settings.popover
        wait(lambda:popup.get_mapped(),'Settings popup did not map')
        assert not host.settings.night_switch.get_active()
        host.settings.night_switch.set_active(True)
        wait(lambda:pixels(stage.background)!=classic,'Classic → Nocturne must repaint the actual backdrop')
        assert host.appearance.theme=='nocturne' and host.appearance.nocturne and not host.appearance.christmas
        assert 'nocturne-theme' in stage.window.get_style_context().list_classes()
        assert 'nocturne-theme' in popup.get_style_context().list_classes()
        assert not host.settings.theme_switch.get_active(),'Theme choices must be mutually exclusive'
        assert stage.edition_label.get_text()!=classic_edition
        night_mean=background_mean(stage.background)
        assert night_mean.mean()<classic_mean.mean()*.85,('Nocturne is not significantly darker',classic_mean,night_mean)
        assert night_mean.mean()<42 and abs(night_mean[0]-night_mean[2])<5,('The backdrop must remain near-neutral charcoal',night_mean)
        assert stage.window.get_size()==original
        assert not stage.winter_surface.top.get_visible() and not stage.winter_surface.corner.get_visible()
        assert stage.winter_surface.tick==0

        # A snow preference belongs to Winter Glow; editing it must not reset
        # Nocturne or quietly start a second animation in the dark room.
        assert host.appearance.set_snow(True)
        assert host.appearance.theme=='nocturne'
        snow=stage.winter_surface.snow
        assert not snow.active and snow.tick==snow.timer==0
        assert not snow.area.get_visible()
        saved=json.loads(host.appearance.path.read_text())
        assert saved['theme']=='nocturne' and saved['snow'] is True
        assert host.appearance.path.stat().st_mode&0o777==0o600
        restored=Appearance(host.appearance.path)
        try:
            assert restored.nocturne and restored.theme=='nocturne' and restored.snow_enabled
        finally:restored.close()

        target=os.environ.get('EMBERBOX_NIGHT_PREVIEW')
        def shot(name):
            if target:
                directory=Path(target);directory.mkdir(parents=True,exist_ok=True)
                # Wait for a real GTK paint and flush its display requests:
                # queueing damage alone can leave the previous popup frame in
                # an X11 screenshot even after popdown was requested.
                painted=[];clock=stage.window.get_frame_clock()
                handler=clock.connect('after-paint',lambda *_:painted.append(True))
                try:
                    stage.window.queue_draw()
                    wait(lambda:bool(painted),'Preview repaint did not finish')
                finally:clock.disconnect(handler)
                stage.window.get_display().sync()
                width,height=stage.window.get_size()
                Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(directory/name),'png',[],[])
        shot('night-settings.png');popup.popdown()
        wait(lambda:not popup.get_mapped(),'Settings popup did not unmap before the listening-room preview')
        shot('night-fullscreen.png')

        # Switching an already live winter surface to Nocturne must release
        # both seasonal artwork and snow, including stale worker completions.
        assert host.appearance.set_christmas(True);settle(.15)
        assert 'christmas-theme' in stage.window.get_style_context().list_classes()
        assert 'nocturne-theme' not in stage.window.get_style_context().list_classes()
        snow.begin();settle(.05)
        assert snow.active,'The regression must start from real active snowfall'
        assert host.appearance.set_theme('nocturne');settle(.25)
        assert not snow.active and snow.tick==snow.timer==0 and not snow.area.get_visible()
        assert not stage.winter_surface.top.get_visible() and not stage.winter_surface.corner.get_visible()
        assert not stage.winter_surface.tick

        # A second window models the same compact card material as the desktop
        # widget without starting any source adapters or audio processes.
        mini=Gtk.Window(title='Nocturne compact material fixture')
        mini.set_default_size(320,120);overlay=Gtk.Overlay();mini.add(overlay)
        card=Gtk.Box(spacing=12);card.get_style_context().add_class('card');card.get_style_context().add_class('compact')
        overlay.add(card);cover=Gtk.Image.new_from_pixbuf(f.cover.scale_simple(72,72,GdkPixbuf.InterpType.BILINEAR))
        card.pack_start(cover,False,False,0)
        title=Gtk.Label(label='Afterglow');title.get_style_context().add_class('title');card.pack_start(title,True,True,0)
        play=Gtk.Button(label='▶');play.get_style_context().add_class('control');play.get_style_context().add_class('play');card.pack_end(play,False,False,0)
        compact_surface=host.appearance.attach(mini,overlay);tint=CoverTint(card)
        mini.show_all();settle(.2)
        assert 'nocturne-theme' in mini.get_style_context().list_classes()
        initial=card.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        tint.set_cover(f.cover);settle(.1)
        final=card.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        assert max(final.red,final.green,final.blue)<.2,('Cover tint washed out the dark card',final.to_string())
        assert max(abs(a-b) for a,b in zip((initial.red,initial.green,initial.blue),(final.red,final.green,final.blue)))<.01
        assert not compact_surface.top.get_visible() and not compact_surface.snow.area.get_visible()
        assert compact_surface.tick==compact_surface.snow.tick==compact_surface.snow.timer==0
        mini.destroy();mini=None

        for width,height in ((1920,1080),(1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.3)
            assert stage.window.get_size()==(width,height)
            f.assert_controls_fit(stage)

        # Keep an existing popup in sync with external theme changes as well
        # as with its own switches, then check it can be safely destroyed.
        stage.show_settings();settle(.1);popup=host.settings.popover
        assert host.settings.night_switch.get_active() and not host.settings.theme_switch.get_active()
        assert host.appearance.set_christmas(True);settle(.1)
        assert host.settings.theme_switch.get_active() and not host.settings.night_switch.get_active()
        assert 'nocturne-theme' not in popup.get_style_context().list_classes()
        assert 'christmas-theme' in popup.get_style_context().list_classes()
        assert host.appearance.set_theme('nocturne');settle(.1)
        assert host.settings.night_switch.get_active() and not host.settings.theme_switch.get_active()
        host.settings.night_switch.set_active(False);settle(.1)
        assert host.appearance.theme=='classic' and not host.appearance.christmas and not host.appearance.nocturne
        assert 'nocturne-theme' not in stage.window.get_style_context().list_classes()
        assert 'nocturne-theme' not in popup.get_style_context().list_classes()
        popup.destroy();host.settings.popover=None

        settings=stage.window.get_settings();animations=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False)
        try:
            assert host.appearance.set_theme('nocturne');settle(.1)
            assert stage.winter_surface.tick==snow.tick==snow.timer==0
            assert host.appearance.set_theme('classic');settle(.1)
        finally:settings.set_property('gtk-enable-animations',animations)
        assert host.calls==commands and host.sound.calls==sound_commands,'Appearance must never alter transport, source or sound'
        print('PASS Nocturne persistence, neutral charcoal backdrops, compact cover-tint precedence, seasonal cleanup, popup sync and three sizes')
    finally:
        if mini:mini.destroy()
        stage.close();host.appearance.close();host.window.destroy()
