"""Real GTK: selection, smooth sound response, reduced motion, lifecycle, badges."""
import os,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from service_icons import service_icon,MARKS
from cover_tint import CoverTint
from gi.repository import Gtk,Gdk,GLib,GdkPixbuf


def settle(seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        for _ in range(6):
            if Gtk.events_pending():Gtk.main_iteration_do(False)
        time.sleep(.003)


host=f.FixtureHost();host.appearance=Appearance();host.appearance.bind_audio(host)
host.settings.appearance=host.appearance
with patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.prewarm();stage.open();f.wait_transition(stage)
        assert host.appearance.set_theme('psychedelic');settle(.6)
        surface=stage.winter_surface.psychedelic
        assert surface.enabled and surface.tick and surface.draws>3 and not surface.failed
        assert stage.window.get_style_context().has_class('psychedelic-theme')
        assert surface.materials and any(item.builds for item in surface.materials)
        material_builds=sum(item.builds for item in surface.materials)
        settle(.15)
        assert sum(item.builds for item in surface.materials)==material_builds, 'Static materials were rebuilt per frame'
        phase=surface.phase;settle(.15);assert surface.phase>phase
        # Inject only a meter reading, without opening an audio capture.
        host.meter=SimpleNamespace(rms_level=1.,last_sample=time.monotonic(),levels=(.3,)*9)
        host.playing=True;settle(.12)
        # GUI dispatch can exceed the requested wall-clock wait on CI.
        # The fixed-step envelope unit test owns the attack bound.
        assert 0 < surface.energy < 1., surface.energy
        host.playing=False;before=surface.energy;settle(.15)
        assert 0 < surface.energy < before
        # Shared measured rhythm drives soft geometric accents; no new meter.
        requests=[]
        host.meter.request_rhythm=lambda consumer,key:requests.append((consumer,key))
        host.playing=True;host.meter.rms_level=.6
        host.meter.levels=(.8,.7,.6,.3,.2,.1,.4,.5,.6)
        origin=time.monotonic();pulses=[];phase=surface.phase
        for _ in range(24):
            now=time.monotonic()
            host.meter.last_sample=now;host.meter.beat_grid_at=now
            host.meter.beat_grid=dict(bpm=120.,period=.5,phase=origin,confidence=.95)
            settle(.05);pulses.append(surface.optics.values[0])
        assert surface.rhythm.timing.bpm==120.
        assert max(pulses)-min(pulses)>.05, pulses
        assert surface.optics.values[2]>.3, 'Bass must affect silhouette dimensions'
        assert surface.phase>phase and requests
        surface.set_suspended(True)
        assert requests[-1][1] is None and not surface.tick
        surface.set_suspended(False)
        host.playing=False;settle(.1)
        # Cover updates retarget from the visible frame, never flash a new hue.
        picture=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,48,48)
        picture.fill(0xd94b36ff)
        visible=surface.liquid.values
        host.cover.set_from_pixbuf(picture)
        assert surface.liquid.values==visible
        assert all(abs(a-b)<1e-6 for a,b in zip(surface.liquid.target[:3],(217/255,75/255,54/255))), surface.liquid.target[:3]
        settle(.2);assert surface.liquid.values!=visible
        old_geometry=surface.liquid.target[15:]
        old_colour=surface.liquid.target[:15]
        title=host.title.get_text();host.title.set_text('Another song on the same album')
        settle(.6)
        assert surface.liquid.target[:15]==old_colour
        assert surface.liquid.target[15:]!=old_geometry
        host.title.set_text(title);host.cover.set_from_pixbuf(f.cover)
        surface.set_suspended(True);assert not surface.tick
        surface.set_suspended(False);assert surface.tick
        prefs=stage.window.get_settings();old=prefs.get_property('gtk-enable-animations')
        prefs.set_property('gtk-enable-animations',False);assert not surface.tick
        assert surface.liquid.values==surface.liquid.target
        prefs.set_property('gtk-enable-animations',old);assert surface.tick
        for key in MARKS:
            image=service_icon(key,30);assert image.get_pixbuf().get_width()==30
        for width,height in ((1920,1080),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.2)
            f.assert_controls_fit(stage)
        stage.show_settings();host.settings.select_section('appearance');settle(1.)
        assert host.settings.theme_cards['psychedelic'].get_mapped()
        folder=os.environ.get('EMBERBOX_PSYCHE_PREVIEW')
        if folder:
            Path(folder).mkdir(exist_ok=True,parents=True)
            def shot(window,name):
                w,h=window.get_size();Gdk.pixbuf_get_from_window(window.get_window(),0,0,w,h).savev(str(Path(folder)/name),'png',[],[])
            shot(host.settings.popover,'settings.png')
            host.settings.select_section('player');settle(1.)
            shot(host.settings.popover,'settings-services.png')
            host.settings.popover.dismiss();stage.window.resize(1920,1080);settle(.3)
            shot(stage.window,'fullscreen.png')
        host.appearance.set_theme('classic');assert not surface.tick and surface.painter is None and not surface.materials
        host.appearance.set_theme('psychedelic');settle(.1)
        stage.window.hide();assert not surface.tick
        # Exercise the actual card material/child propagation at both sizes.
        mini=Gtk.Window(title='Slow Current / original Ember fixture')
        overlay=Gtk.Overlay();mini.add(overlay)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);body.get_style_context().add_class('card')
        body.set_border_width(16);overlay.add(body)
        row=Gtk.Box(spacing=14);body.pack_start(row,True,True,0)
        cover=Gtk.Image.new_from_pixbuf(f.cover.scale_simple(80,80,GdkPixbuf.InterpType.BILINEAR));row.pack_start(cover,False,False,0)
        titles=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
        title=Gtk.Label(label='Afterglow');title.get_style_context().add_class('title');titles.pack_start(title,False,False,0)
        artist=Gtk.Label(label='Emberbox Sessions');artist.get_style_context().add_class('artist');titles.pack_start(artist,False,False,0)
        row.pack_start(titles,True,True,0)
        play=Gtk.Button(label='▶');play.get_style_context().add_class('play');play.get_style_context().add_class('control');body.pack_start(play,False,False,0)
        tint=CoverTint(body);mini_surface=host.appearance.attach(mini,overlay)
        for width in (460,320):
            body.get_style_context().add_class('compact') if width==320 else body.get_style_context().remove_class('compact')
            mini.set_default_size(width,190);mini.resize(width,190);mini.show_all();settle(.2)
            settle(.1)
            assert title.get_mapped() and play.get_mapped() and mini_surface.psychedelic.draws>0
            assert not mini_surface.psychedelic.failed and mini_surface.psychedelic.tick

        mini.hide();assert not mini_surface.psychedelic.tick
        mini.destroy();mini=None
        restored=Appearance(host.appearance.path)
        assert restored.psychedelic
        restored.close()
    finally:
        stage.close();host.appearance.close();host.window.destroy()
print('Slow Current: selection, smoothing, cleanup, reduced motion and service icons passed')
