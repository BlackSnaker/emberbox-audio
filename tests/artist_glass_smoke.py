"""Scoped artist glass, readable controls and settled static material in all themes.

Only original fixture text and GTK widgets are used. No player, account, desktop
readback or audio stream is accessed. Whole-photo and bright-portrait contrast
are covered separately by test_artist_header.py.
"""
import time
from pathlib import Path
import sys
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from artist_glass import CSS as ARTIST_GLASS_CSS
from artist_view import CSS as ARTIST_CSS
from fullscreen import CSS as FULLSCREEN_CSS
from header_glass import CSS as HEADER_GLASS_CSS
from seasonal_theme import CSS as WINTER_CSS,NIGHT_CSS,MIRROR_CSS


def settle(seconds=.08):
    deadline=time.monotonic()+seconds;context=GLib.MainContext.default()
    while time.monotonic()<deadline:
        for _ in range(3):
            if context.pending():context.iteration(False)
        time.sleep(.002)


def rgba(value):return tuple(round(getattr(value,channel),5) for channel in ('red','green','blue','alpha'))


def material(widget):
    context=widget.get_style_context();state=widget.get_state_flags()
    padding=context.get_padding(state)
    return (rgba(context.get_color(state)),rgba(context.get_background_color(state)),
            rgba(context.get_border_color(state)),
            (padding.left,padding.right,padding.top,padding.bottom))


def rectangle(widget):
    allocation=widget.get_allocation()
    return allocation.x,allocation.y,allocation.width,allocation.height


def styled(widget,*classes):
    for name in classes:widget.get_style_context().add_class(name)
    return widget


window=styled(Gtk.Window(),'ember-stage');window.set_default_size(1000,440)
base=Gtk.CssProvider();base.load_from_data(FULLSCREEN_CSS+ARTIST_CSS)
# Match real Appearance precedence; artist glass must beat all theme materials.
themes=Gtk.CssProvider();themes.load_from_data(WINTER_CSS+NIGHT_CSS+MIRROR_CSS)
optical=Gtk.CssProvider();optical.load_from_data(HEADER_GLASS_CSS+ARTIST_GLASS_CSS)
Gtk.StyleContext.add_provider_for_screen(window.get_screen(),base,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
Gtk.StyleContext.add_provider_for_screen(window.get_screen(),themes,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+15)
Gtk.StyleContext.add_provider_for_screen(window.get_screen(),optical,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+20)
layout=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);layout.set_margin_start(20);layout.set_margin_end(20)
layout.set_margin_top(16);layout.set_margin_bottom(16);window.add(layout)
room=styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12),'artist-glass-room');layout.pack_start(room,True,True,0)
bar=styled(Gtk.Box(spacing=8),'artist-glass-toolbar');room.pack_start(bar,False,False,0)
selector=styled(Gtk.Box(spacing=3),'stage-nav','artist-glass-selector');bar.pack_start(selector,False,False,0)
filters=[]
for caption in ('Обзор','Все релизы','Синглы и EP'):
    control=styled(Gtk.ToggleButton(label=caption),'stage-tab','stage-artist-filter')
    control.set_has_tooltip(False);control.get_accessible().set_name(caption);selector.pack_start(control,False,False,0);filters.append(control)
filters[0].set_active(True)
panel=styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9),'stage-overview-panel');room.pack_start(panel,True,True,0)
caption=styled(Gtk.Label(label='Emberbox Sessions — история тихих вечеров, музыки и света в комнате'),'stage-overview-story')
caption.set_line_wrap(True);caption.set_max_width_chars(38);caption.set_width_chars(1);caption.set_xalign(0);caption.set_halign(Gtk.Align.START)
panel.pack_start(caption,False,False,0)
controls=Gtk.Box(spacing=10);panel.pack_start(controls,False,False,0)
play=styled(Gtk.Button(label='▶ Слушать'),'stage-accent','artist-play-key')
quiet=styled(Gtk.Button(label='+ В очередь'),'stage-quiet')
for control in (play,quiet):
    control.set_has_tooltip(False);control.get_accessible().set_name(control.get_label());controls.pack_start(control,False,False,0)
# These use the same global classes but sit outside the artist material scope.
outside=styled(Gtk.Box(spacing=12),'stage-overview-panel');layout.pack_end(outside,False,False,0)
outside_button=styled(Gtk.Button(label='Outside artist / album control'),'stage-quiet');outside.pack_start(outside_button,False,False,0)
outside_signature=None;clicked=[];quiet.connect('clicked',lambda *_:clicked.append('queue'))
window.show_all();settle(.35)
try:
    for theme in ('','nocturne-theme','mirrorball-theme','christmas-theme'):
        if theme:window.get_style_context().add_class(theme)
        settle(.35)
        outside_signature=(material(outside),material(outside_button))
        scoped=tuple(material(widget) for widget in (panel,selector,quiet,play))
        assert scoped[0][1][3]<.60,'A lower-priority opaque theme panel must not cover the scoped clear glass'
        geometry=tuple(rectangle(widget) for widget in (panel,selector,*filters,play,quiet))
        assert caption.get_text().endswith('света в комнате') and not caption.get_layout().is_ellipsized()
        assert caption.get_layout().get_line_count()>=2,'The fixture must actually exercise wrapping'
        for state in (Gtk.StateFlags.PRELIGHT,Gtk.StateFlags.ACTIVE):
            for control in (*filters,play,quiet):control.set_state_flags(state,False)
            settle(.30)
            assert tuple(rectangle(widget) for widget in (panel,selector,*filters,play,quiet))==geometry,'Hover/press must not shift artist controls'
            assert all(control.get_mapped() and control.get_accessible().get_name() and not control.get_has_tooltip() for control in (*filters,play,quiet))
            for control in (*filters,play,quiet):control.unset_state_flags(state)
            settle(.30)
        quiet.clicked();assert clicked[-1]=='queue','The glass material must leave real controls clickable'
        room.get_style_context().remove_class('artist-glass-room');settle(.35)
        unscoped=tuple(material(widget) for widget in (panel,selector,quiet,play))
        assert scoped!=unscoped,'Artist glass rules must change actual GTK material, not just declare unused selectors'
        assert (material(outside),material(outside_button))==outside_signature,'Artist materials leaked into unrelated controls'
        room.get_style_context().add_class('artist-glass-room');settle(.70)
        paints=[];clock=window.get_frame_clock();handler=clock.connect('after-paint',lambda *_:paints.append(True))
        try:settle(.18)
        finally:clock.disconnect(handler)
        assert len(paints)<=2,'Settled physical glass must not retain a continuous repaint loop'
        if theme:window.get_style_context().remove_class(theme)
    print('PASS artist glass: scoped real materials, all four themes, stable hover/press geometry, full wrapped text, live accessible controls and settled idle painting')
finally:
    window.destroy()
    Gtk.StyleContext.remove_provider_for_screen(window.get_screen(),optical)
    Gtk.StyleContext.remove_provider_for_screen(window.get_screen(),themes)
    Gtk.StyleContext.remove_provider_for_screen(window.get_screen(),base)
