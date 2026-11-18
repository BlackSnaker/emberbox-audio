"""Velvet Jazz on real GTK: cloth, cover light, Mini, persistence and cleanup."""
import json,os,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from cover_tint import CoverTint
from source_picker import text
from gi.repository import Gtk,Gdk,GdkPixbuf,GLib


def settle(seconds=.1):
    until=time.monotonic()+seconds;context=GLib.MainContext.default()
    while time.monotonic()<until:
        for _ in range(4):
            if context.pending():context.iteration(False)
        time.sleep(.002)


def wait(predicate,message,limit=6):
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:settle(.025)
    assert predicate(),message


def solid(value):
    image=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,True,8,96,96)
    image.fill(value);return image


def shot(window,name):
    folder=os.environ.get('EMBERBOX_VELVET_PREVIEW')
    if not folder:return
    settle(.2);window.get_display().sync();w,h=window.get_size()
    Path(folder).mkdir(parents=True,exist_ok=True)
    Gdk.pixbuf_get_from_window(window.get_window(),0,0,w,h).savev(str(Path(folder)/name),'png',[],[])


host=f.FixtureHost();host.appearance=Appearance();host.appearance.bind_audio(host)
host.settings.appearance=host.appearance
mini=None
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected velvet network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.prewarm();stage.open();f.wait_transition(stage)
        commands=list(host.calls);sound_commands=list(host.sound.calls)
        stage.show_settings();host.settings.select_section('appearance');settle(.3)
        menu=host.settings;card=menu.theme_cards['velvet']
        assert card.get_mapped(),'Velvet must be selectable from the real appearance page'
        card.clicked();settle(.2)
        assert host.appearance.velvet and host.appearance.dark and not host.appearance.nocturne
        assert menu.popover.get_style_context().has_class('velvet-theme')
        wait(lambda:stage.background.get_pixbuf().get_width()>1,'Velvet cloth did not finish')
        assert 'velvet-theme' in stage.window.get_style_context().list_classes()
        assert 'VELVET' in stage.edition_label.get_text() or 'БАРХАТ' in stage.edition_label.get_text()
        field=stage.background.get_pixbuf();data=np.frombuffer(field.get_pixels(),np.uint8).reshape(field.get_height(),field.get_rowstride())
        rgb=data[:,:field.get_width()*3].reshape(field.get_height(),field.get_width(),3)
        assert rgb[:,:,0].mean()>rgb[:,:,1].mean()*1.5 and rgb.mean()<50
        assert not stage.winter_surface.mirror.enabled and not stage.winter_surface.snow.active
        assert stage.winter_surface.snow.tick==stage.winter_surface.snow.timer==0
        menu.popover.dismiss();settle(.1)
        light=stage.winter_surface.velvet
        assert light.enabled and light.painter and not light.failed and light.area.get_mapped()
        wait(lambda:not light.tick,'Initial cover light did not settle')
        assert not light.tick,'A settled velvet room must not start a permanent animation'
        assert stage.cover.get_pixbuf().get_pixels()==f.cover.scale_simple(stage.art_size,stage.art_size,GdkPixbuf.InterpType.BILINEAR).get_pixels()
        shot(stage.window,'velvet-fullscreen.png')
        saved=json.loads(host.appearance.path.read_text())
        assert saved['theme']=='velvet' and host.appearance.path.stat().st_mode&0o777==0o600
        restored=Appearance(host.appearance.path)
        try:assert restored.velvet
        finally:restored.close()

        host.cover.set_from_pixbuf(solid(0xe84f33ff));settle(.25)
        first=light.light.values;assert light.tick and light.light.active
        host.cover.set_from_pixbuf(solid(0x386ee8ff))
        assert light.light.values==first,'Rapid cover changes must retain the visible light'
        intermediate=[]
        until=time.monotonic()+5
        while light.tick and time.monotonic()<until:
            settle(.03);intermediate.append(light.light.values)
        assert not light.tick and not light.light.active
        assert len(set(intermediate))>8,'Cover light must pass through smooth intermediate colours'
        assert light.light.values==light.light.target and light.painter.values==light.light.target
        assert light.draws>10 and not light.failed
        host.cover.set_from_pixbuf(f.cover);settle(.15)
        prefs=stage.window.get_settings();animations=prefs.get_property('gtk-enable-animations')
        prefs.set_property('gtk-enable-animations',False)
        assert not light.tick and light.light.values==light.light.target
        prefs.set_property('gtk-enable-animations',animations)

        for width,height in ((1920,1080),(1280,720),(1024,600)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.25)
            f.assert_controls_fit(stage)
        stage.show_settings();menu.select_section('appearance');settle(.3)
        point=menu.theme_cards['velvet'].translate_coordinates(menu.popover,0,0)
        assert point and point[1]+menu.theme_cards['velvet'].get_allocated_height()<=menu.popover.get_allocated_height()
        shot(menu.popover,'velvet-settings.png');menu.popover.dismiss()

        # Exercise the actual card material/child propagation at both sizes.
        mini=Gtk.Window(title='Velvet Jazz / original Ember fixture')
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
        tint=CoverTint(body);surface=host.appearance.attach(mini,overlay)
        for width in (460,320):
            body.get_style_context().add_class('compact') if width==320 else body.get_style_context().remove_class('compact')
            mini.set_default_size(width,190);mini.resize(width,190);mini.show_all();settle(.2)
            tint.set_cover(solid(0x00ccffff));settle(.1)
            assert title.get_mapped() and play.get_mapped() and surface.velvet.draws>0
            assert not surface.velvet.failed and not surface.velvet.tick
            shot(mini,'velvet-'+str(width)+'.png')
        mini.hide();assert not surface.velvet.tick
        mini.destroy();mini=None
        for theme in ('mirrorball','velvet','nocturne','velvet','classic'):
            assert host.appearance.set_theme(theme);settle(.15)
            assert light.enabled==(theme=='velvet')
            if theme!='velvet':assert not light.tick and not light.area.get_visible() and light.painter is None
        assert host.calls==commands and host.sound.calls==sound_commands,'Theme selection altered music playback'
        print('PASS Velvet Jazz: selectable/persistent burgundy cloth, untouched artwork, finite smooth cover light, rapid retargeting, reduced motion, three screens, live Mini children and theme cleanup')
    finally:
        if mini:mini.destroy()
        stage.close();host.appearance.close();host.window.destroy()
