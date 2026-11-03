"""Opt-in Winter Glow theme. Local preference, scoped CSS and finite decoration."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
from gi.repository import Gdk,Gtk,GLib
from paths import CONFIG_DIR
from source_picker import text
from winter_art import winter_image

CSS=b'''
.christmas-theme .card {
 padding-top: 30px;
 background-color: #20322b;
 background-image: linear-gradient(135deg,#2a3c32,#1d2c26 58%,#202b26);
 box-shadow: inset 0 1px rgba(255,227,166,.12), inset 0 -1px rgba(5,12,9,.35);
}
.christmas-theme .card.compact { padding-top: 40px; }
.christmas-theme .title, .christmas-theme .stage-track-title { color: #fff0cd; }
.christmas-theme .artist, .christmas-theme .stage-artist { color: #d1c4a7; }
.christmas-theme .album, .christmas-theme .stage-album, .christmas-theme .time { color: #a9ae95; }
.christmas-theme .eyebrow, .christmas-theme .stage-brand { color: #e5c585; }
.christmas-theme .stage-overline { color: #b8ab80; }
.christmas-theme .cover-surface, .christmas-theme .stage-art-shell {
 background-color: #15231d;
 background-image: linear-gradient(140deg,rgba(227,198,132,.15),rgba(18,32,25,.4) 38%,rgba(7,17,13,.6) 78%,rgba(197,161,96,.12));
 box-shadow: inset 0 1px rgba(255,229,174,.22), inset 0 -1px rgba(224,193,129,.12), 0 12px 30px rgba(3,10,6,.28);
}
.christmas-theme .lamp-well { background-color: #17271f;
 box-shadow: inset 2px 3px 7px rgba(2,9,5,.48), inset -1px -1px rgba(235,208,151,.06); }
.christmas-theme button.control, .christmas-theme button.mini-button {
 background-image: linear-gradient(140deg,#394a3b,#25382c);
 color: #e9d6ae; box-shadow: -1px -1px 4px rgba(236,216,171,.07), 3px 4px 7px rgba(1,9,4,.32);
}
.christmas-theme button.play, .christmas-theme button.stage-transport.stage-play {
 background-color: #a04845; background-image: linear-gradient(145deg,#c67561,#98433f 55%,#713439);
 color: #fff1ce; box-shadow: inset 0 1px rgba(255,224,172,.48), inset 0 -1px rgba(39,9,14,.55), 0 5px 13px rgba(11,4,5,.32);
}
.christmas-theme button.play:hover, .christmas-theme button.stage-transport.stage-play:hover {
 background-image: linear-gradient(145deg,#d68b71,#aa5148); color: #fff5d7;
}
.christmas-theme button.play:active, .christmas-theme button.stage-transport.stage-play:active {
 background-image: linear-gradient(145deg,#783235,#a34c43); box-shadow: inset 2px 3px 5px rgba(28,7,10,.35);
}
.christmas-theme button.discovery-toggle, .christmas-theme button.filter-chip,
.christmas-theme button.mix-tile { background-image: linear-gradient(140deg,#324638,#24342b); color: #d9cdad; }
.christmas-theme .discovery-name { color: #edd198; }
.christmas-theme .progress progress { background-image: linear-gradient(to right,#c79153,#f1d595); }
window.ember-stage.christmas-theme { background-color: #12221c; }
window.ember-stage.christmas-theme.stage-opening { background-color: transparent; }
.christmas-theme .stage-console {
 background-image: linear-gradient(145deg,rgba(45,64,48,.95),rgba(21,38,28,.96));
 border-color: rgba(222,193,135,.1); box-shadow: inset 0 1px rgba(249,218,161,.09), 0 8px 24px rgba(1,9,4,.22);
}
.christmas-theme button.stage-transport { background-image: linear-gradient(145deg,#40513d,#24382a); color: #ead7b0; }
.christmas-theme button.stage-quiet { background-color: rgba(218,187,124,.045); border-color: rgba(218,187,124,.09); color: #d6c9a7; }
.christmas-theme .stage-nav { background-color: rgba(10,26,18,.65); }
.christmas-theme button.stage-tab:checked {
 background-image: linear-gradient(145deg,#5e3d32,#3b3028); color: #f3d394;
 box-shadow: inset 0 1px rgba(241,208,143,.12);
}
.christmas-theme .record-panel { background-color: rgba(12,28,20,.45); border-color: rgba(224,195,134,.1); }
.christmas-theme .record-list row.record-row.record-current { background-color: rgba(175,101,65,.14); border-color: rgba(226,186,117,.22); }
.christmas-theme button.stage-accent, .christmas-theme button.warm-button {
 background-image: linear-gradient(145deg,#f3d49a,#c49651); color: #30271b;
}
.christmas-theme entry.stage-search, .christmas-theme entry.track-search { background-color: rgba(8,23,16,.55); color: #f1e4c6; }
.christmas-theme .settings-popover, .christmas-theme.settings-popover,
.christmas-theme .source-popover, .christmas-theme.source-popover {
 background-color: #203228; color: #eee0be; border-color: #52604a;
}
.christmas-theme.settings-popover button.settings-action { background-image: linear-gradient(145deg,#354636,#24362b);
 color: #e4d6b7; border: none; border-radius: 11px; padding: 7px 12px; min-height: 24px;
 box-shadow: inset 0 1px rgba(242,220,173,.045), 0 2px 4px rgba(4,13,7,.18); }
.christmas-theme.settings-popover button.warm-button { background-image: linear-gradient(145deg,#f3d49a,#c49651); color: #30271b; }
.theme-choice { border: 1px solid rgba(224,194,134,.14); border-radius: 14px; background-color: #1d2b24; padding: 9px; }
.theme-choice-title { color: #f3d9a5; font-size: 12px; font-weight: bold; }
.theme-choice-note { color: #b4b69e; font-size: 10px; }
.theme-choice switch { min-width: 36px; min-height: 20px; border-radius: 12px; background: #16231c; border: 1px solid #4a5b44; }
.theme-choice switch:checked { background: #a65847; border-color: #c49267; }
.theme-choice switch slider { background-image: linear-gradient(145deg,#f4ddab,#baa06a); min-width: 17px; min-height: 17px;
 border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.25); }
'''


class Appearance:
    def __init__(self,path=None):
        self.path=Path(path or CONFIG_DIR/'appearance.json');self.christmas=False;self.snow_enabled=False
        try:
            if self.path.stat().st_size<4096:
                data=json.loads(self.path.read_text());self.christmas=data.get('theme')=='christmas'
                self.snow_enabled=data.get('snow') is True
        except (OSError,ValueError,TypeError,AttributeError):pass
        self.listeners=[];self.surfaces=[];self.closed=False
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-winter-art')
        self.provider=Gtk.CssProvider();self.provider.load_from_data(CSS)
        self.screen=Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(self.screen,self.provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+15)

    def subscribe(self,callback):
        self.listeners.append(callback)
        return lambda:self.listeners.remove(callback) if callback in self.listeners else None

    def set_christmas(self,enabled):
        if self.closed:return False
        enabled=bool(enabled)
        if enabled==self.christmas:return True
        return self.save_preferences(enabled,self.snow_enabled)

    def set_snow(self,enabled):
        if self.closed:return False
        if bool(enabled)==self.snow_enabled:return True
        return self.save_preferences(self.christmas,bool(enabled))

    def save_preferences(self,enabled,snow):
        temporary=self.path.with_suffix('.next.json')
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as file:json.dump({'theme':'christmas' if enabled else 'classic','snow':snow},file)
            temporary.chmod(0o600);temporary.replace(self.path)
        except OSError:return False
        theme_changed=self.christmas!=enabled
        self.christmas=enabled;self.snow_enabled=snow
        for surface in tuple(self.surfaces):
            if theme_changed:surface.apply(animate=True)
            else:surface.snow.set_enabled(enabled and snow)
        for callback in tuple(self.listeners):callback()
        return True

    def attach(self,window,overlay,stage=False):
        surface=WinterSurface(self,window,overlay,stage);self.surfaces.append(surface)
        return surface

    def decorate_popup(self,popup):
        def update():
            context=popup.get_style_context()
            context.add_class('christmas-theme') if self.christmas else context.remove_class('christmas-theme')
        update();unsubscribe=self.subscribe(update)
        popup.connect('destroy',lambda *_:unsubscribe())

    def close(self):
        if self.closed:return
        self.closed=True
        for surface in tuple(self.surfaces):surface.close()
        self.listeners.clear();self.pool.shutdown(wait=False,cancel_futures=True)
        Gtk.StyleContext.remove_provider_for_screen(self.screen,self.provider)


class WinterSurface:
    def __init__(self,appearance,window,overlay,stage):
        self.appearance,self.window,self.stage=appearance,window,stage
        self.closed=False;self.generation=0;self.key=None;self.tick=0;self.started=None
        self.top=Gtk.Image();self.top.set_halign(Gtk.Align.FILL);self.top.set_valign(Gtk.Align.START)
        self.corner=Gtk.Image();self.corner.set_halign(Gtk.Align.END);self.corner.set_valign(Gtk.Align.END)
        for image in (self.top,self.corner):
            image.set_no_show_all(True);image.set_can_focus(False)
            overlay.add_overlay(image);overlay.set_overlay_pass_through(image,True)
        from winter_snow import WinterSnow
        self.snow=WinterSnow(window,overlay,stage)
        self.size_signal=window.connect('size-allocate',lambda *_:self.render())
        self.unmap_signal=window.connect('unmap',lambda *_:self.settle())
        self.destroy_signal=window.connect('destroy',lambda *_:self.close())
        self.apply()

    def apply(self,animate=False):
        if self.closed:return
        context=self.window.get_style_context();enabled=self.appearance.christmas
        context.add_class('christmas-theme') if enabled else context.remove_class('christmas-theme')
        self.generation+=1;self.key=None;self.settle()
        self.snow.set_enabled(enabled and self.appearance.snow_enabled)
        if enabled:
            self.render()
            if animate and self.window.get_mapped() and self.window.get_settings().get_property('gtk-enable-animations'):
                self.top.set_opacity(0.);self.corner.set_opacity(0.)
                self.tick=self.window.add_tick_callback(self.fade)
        else:self.top.hide();self.corner.hide()

    def render(self):
        if self.closed or not self.appearance.christmas:return
        width=max(1,self.window.get_allocated_width())
        if width<100:return
        self.top.set_margin_top(10 if not self.stage and width<=320 else 0)
        key=(width,self.stage)
        if self.key==key:return
        self.key=key;generation=self.generation
        # Width changes are rare. Rasterise the small decoration outside GTK,
        # reuse it at rest, and discard stale resize/theme completions.
        def draw():
            return winter_image(width,186 if self.stage else 43),winter_image(88,70,'corner') if self.stage else None
        future=self.appearance.pool.submit(draw)
        def done(result):
            try:top,corner=result.result()
            except Exception:return
            def apply():
                if self.closed or generation!=self.generation or self.key!=key or not self.appearance.christmas:return False
                self.top.set_from_pixbuf(top);self.top.show()
                if corner:self.corner.set_from_pixbuf(corner);self.corner.show()
                return False
            GLib.idle_add(apply)
        future.add_done_callback(done)

    def fade(self,_window,clock):
        now=clock.get_frame_time()/1e6
        if self.started is None:self.started=now
        t=min(1.,(now-self.started)/1.15);value=t*t*(3-2*t)
        self.top.set_opacity(value);self.corner.set_opacity(value)
        if t>=1 or not self.window.get_settings().get_property('gtk-enable-animations'):
            self.tick=0;self.started=None;self.top.set_opacity(1.);self.corner.set_opacity(1.);return False
        return True

    def settle(self):
        if self.tick:self.window.remove_tick_callback(self.tick);self.tick=0
        self.started=None;self.top.set_opacity(1.);self.corner.set_opacity(1.)

    def close(self):
        if self.closed:return
        self.closed=True;self.settle();self.snow.close();self.generation+=1
        for signal in (self.size_signal,self.unmap_signal,self.destroy_signal):
            if self.window.handler_is_connected(signal):self.window.disconnect(signal)
        for image in (self.top,self.corner):image.destroy()
        if self in self.appearance.surfaces:self.appearance.surfaces.remove(self)


def theme_choice(appearance):
    """One compact, keyboard-accessible preview/toggle inside player settings."""
    tile=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);tile.get_style_context().add_class('theme-choice')
    picture=Gtk.Overlay();picture.add(Gtk.Image.new_from_pixbuf(winter_image(222,86,'preview')))
    name=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
    name.set_valign(Gtk.Align.CENTER);name.set_halign(Gtk.Align.START);name.set_margin_start(12)
    title=Gtk.Label(label=text('Winter Glow','Тёплое Рождество'));title.set_xalign(0);title.get_style_context().add_class('theme-choice-title');name.pack_start(title,False,False,0)
    subtitle=Gtk.Label(label=text('CHRISTMAS EDITION','РОЖДЕСТВЕНСКИЙ ЭФИР'));subtitle.set_xalign(0)
    subtitle.get_style_context().add_class('theme-choice-note');name.pack_start(subtitle,False,False,0)
    picture.add_overlay(name);picture.set_overlay_pass_through(name,True);tile.pack_start(picture,False,False,0)
    row=Gtk.Box(spacing=10);tile.pack_start(row,False,False,0)
    label=Gtk.Label(label=text('Christmas theme','Рождественская тема'));label.set_xalign(0);label.get_style_context().add_class('theme-choice-title')
    row.pack_start(label,True,True,0)
    switch=Gtk.Switch();switch.set_active(appearance.christmas);switch.set_valign(Gtk.Align.CENTER)
    switch.set_has_tooltip(False);switch.get_accessible().set_name(label.get_text());label.set_mnemonic_widget(switch)
    row.pack_end(switch,False,False,0)
    note=Gtk.Label(label=text('Pine, brass & candlelight','Хвоя, латунь и свет свечей'));note.set_xalign(0);note.get_style_context().add_class('theme-choice-note');tile.pack_start(note,False,False,0)
    def changed(_switch,_param):
        if switch.get_active()==appearance.christmas:return
        if not appearance.set_christmas(switch.get_active()):
            switch.set_active(appearance.christmas);note.set_text(text('Could not save the theme','Не удалось сохранить тему'))
    switch.connect('notify::active',changed)
    snow_row=Gtk.Box(spacing=10);tile.pack_start(snow_row,False,False,0)
    snow_label=Gtk.Label(label=text('Light snow','Лёгкий снег'));snow_label.set_xalign(0)
    snow_label.get_style_context().add_class('theme-choice-title');snow_row.pack_start(snow_label,True,True,0)
    snow_switch=Gtk.Switch();snow_switch.set_active(appearance.snow_enabled);snow_switch.set_valign(Gtk.Align.CENTER)
    snow_switch.set_has_tooltip(False);snow_switch.get_accessible().set_name(snow_label.get_text())
    snow_row.pack_end(snow_switch,False,False,0);tile.snow_switch=snow_switch
    def change_snow(_switch,_param):
        if snow_switch.get_active()!=appearance.snow_enabled and not appearance.set_snow(snow_switch.get_active()):
            snow_switch.set_active(appearance.snow_enabled);note.set_text(text('Could not save the setting','Не удалось сохранить настройку'))
    snow_switch.connect('notify::active',change_snow)
    def sync():
        switch.set_active(appearance.christmas);snow_switch.set_active(appearance.snow_enabled)
        snow_switch.set_sensitive(appearance.christmas)
    sync();unsubscribe=appearance.subscribe(sync)
    tile.connect('destroy',lambda *_:unsubscribe())
    return tile,switch
