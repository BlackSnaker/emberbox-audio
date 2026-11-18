"""Burgundy velvet, brushed warm metal and restrained artwork lamplight."""
import ctypes as C
import weakref
from gi.repository import Gtk, GLib
from cover_pause_paint import bindings, rounded
from velvet_art import Light, colours

CSS = b'''
.velvet-theme .card { background-color: #26131d;
 background-image: linear-gradient(125deg,#3b1d2b,#25131c 56%,#1d1018);
 box-shadow: inset 0 1px rgba(245,212,169,.075),inset 0 -1px rgba(6,2,6,.45); }
window.ember-stage.velvet-theme { background-color: #1b0d14; }
window.ember-stage.velvet-theme.stage-opening { background-color: transparent; }
.velvet-theme .stage-opening-card { background-color: #26131d; }
.velvet-theme .title, .velvet-theme .stage-track-title, .velvet-theme .record-title label,
.velvet-theme .stage-library-title, .velvet-theme .dj-title, .velvet-theme .editorial-title { color: #f1e0c9; }
.velvet-theme .artist, .velvet-theme .stage-artist, .velvet-theme .editorial-body { color: #cbb6aa; }
.velvet-theme .album, .velvet-theme .stage-album, .velvet-theme .caption,
.velvet-theme .record-artist label, .velvet-theme .record-album, .velvet-theme .record-duration { color: #b29a8f; }
.velvet-theme .eyebrow, .velvet-theme .stage-brand, .velvet-theme .stage-overline,
.velvet-theme .drawer-heading, .velvet-theme .dj-frequency, .velvet-theme .album-header-kicker { color: #d4af7b; }
.velvet-theme .stage-console { background-color: #24151d;
 background-image: linear-gradient(150deg,rgba(67,35,46,.96),rgba(33,19,28,.98));
 border-color: rgba(227,183,139,.10); box-shadow: inset 0 1px rgba(243,210,169,.065),0 10px 28px rgba(8,2,6,.28); }
.velvet-theme .cover-surface, .velvet-theme .stage-art-shell {
 background-color: #201019;
 background-image: linear-gradient(135deg,rgba(230,192,157,.12),rgba(48,22,34,.7) 27%,rgba(12,6,13,.85) 79%,rgba(198,139,128,.09));
 box-shadow: inset 0 1px rgba(243,205,162,.17),inset 0 -1px rgba(211,153,135,.07),0 18px 40px rgba(7,2,6,.38); }
.velvet-theme .lamp-well { background-color: #1b0e16;
 box-shadow: inset 2px 3px 8px rgba(8,2,6,.6),inset 0 -1px rgba(238,198,157,.04); }
.velvet-theme button.control, .velvet-theme button.mini-button, .velvet-theme button.stage-transport,
.velvet-theme button.record-action { background-image: linear-gradient(145deg,#492d38,#2c1a25);
 color: #dcc4a4; box-shadow: inset 0 1px rgba(245,216,180,.055),2px 4px 8px rgba(9,2,7,.30); }
.velvet-theme button.control:hover, .velvet-theme button.mini-button:hover,
.velvet-theme button.stage-transport:hover { background-image: linear-gradient(145deg,#53323e,#35202c); color: #f1d5a6; }
.velvet-theme button.control:active, .velvet-theme button.stage-transport:active {
 background-image: linear-gradient(145deg,#24131e,#3a202c); box-shadow: inset 1px 3px 6px rgba(8,1,5,.5); }
.velvet-theme button.play, .velvet-theme button.stage-play, .velvet-theme button.stage-accent,
.velvet-theme button.warm-button, .velvet-theme button.album-play-button {
 background-color: #b88e60; color: #2c1820;
 background-image: linear-gradient(145deg,#e4c39a,#bd946b 57%,#a67a59);
 box-shadow: inset 0 1px rgba(255,238,205,.40),inset 0 -1px rgba(75,36,30,.32),0 5px 14px rgba(10,2,7,.30); }
.velvet-theme button.play:hover, .velvet-theme button.stage-play:hover { background-image: linear-gradient(145deg,#edcfa8,#cba17a); color: #2c1820; }
.velvet-theme button.control:disabled, .velvet-theme button.stage-transport:disabled,
.velvet-theme button:disabled { color: #8c736a; background-image: linear-gradient(145deg,#301b26,#24151f);
 box-shadow: inset 0 1px rgba(239,208,170,.025); }
.velvet-theme .progress trough, .velvet-theme scale trough { background-color: #140a11; }
.velvet-theme .progress progress, .velvet-theme scale highlight,
.velvet-theme .editorial-progress progress { background-image: linear-gradient(to right,#81503f,#d3ac7d); }
.velvet-theme scale slider { background-color: #d9b58b; }
.velvet-theme button.discovery-toggle, .velvet-theme button.filter-chip,
.velvet-theme button.mix-tile { background-image: linear-gradient(145deg,#422734,#2c1a25); color: #d1b9a3; }
.velvet-theme .record-panel { background-color: rgba(25,11,21,.64); border-color: rgba(217,167,140,.09); }
.velvet-theme .record-list row.record-row, .velvet-theme .stage-track-row { background-color: rgba(24,11,20,.44); }
.velvet-theme .record-list row.record-row:hover { background-color: rgba(179,118,129,.055); }
.velvet-theme .record-list row.record-row.record-current, .velvet-theme .dj-track.dj-current {
 background-color: rgba(134,67,82,.12); border-color: rgba(217,172,125,.23); }
.velvet-theme .stage-queue-current, .velvet-theme .stage-overview-panel,
.velvet-theme .stage-artist-reading, .velvet-theme .editorial-card, .velvet-theme .dj-desk,
.velvet-theme .dj-hero, .velvet-theme .karaoke-panel, .velvet-theme .mashup-hero,
.velvet-theme .mashup-deck, .velvet-theme .mashup-deck-b, .velvet-theme .flow-desk {
 background-color: #291620; background-image: linear-gradient(140deg,rgba(62,30,42,.80),rgba(29,15,23,.94));
 border-color: rgba(228,183,143,.085); box-shadow: inset 0 1px rgba(239,205,166,.04),0 6px 18px rgba(8,2,6,.20); }
.velvet-theme .stage-artist-banner, .velvet-theme .album-header { background-color: #26141f; }
.velvet-theme .stage-artist-banner.stage-artist-capture,
.velvet-theme .stage-artist-hero.stage-artist-banner-content { background-color: transparent; background-image: none; }
.velvet-theme .artist-glass-room .stage-overview-panel, .velvet-theme .artist-glass-room .editorial-card { background-color: rgba(30,13,24,.42); }
.velvet-theme .dj-track, .velvet-theme .mashup-row { background-color: #21111b;
 background-image: linear-gradient(to right,rgba(47,23,35,.88),rgba(26,13,22,.88)); }
.velvet-theme entry.stage-search, .velvet-theme entry.track-search, .velvet-theme entry.dj-entry {
 background-color: #190d15; background-image: linear-gradient(to bottom,#190d15,#26141f);
 color: #e7d4bb; border-color: rgba(216,169,130,.15); }
.velvet-theme .dj-preferences, .velvet-theme .mashup-settings, .velvet-theme .karaoke-control-well { background-color: rgba(20,9,17,.5); }
.velvet-theme button.stage-line { color: #938078; }
.velvet-theme button.stage-line.stage-line-active, .velvet-theme button.stage-line.stage-line-active:hover,
.velvet-theme .karaoke-current { color: #ffe3b5; text-shadow: 0 0 5px rgba(246,176,98,.24),0 0 18px rgba(220,119,71,.15); }
.velvet-theme button.ember-flow.ember-flow-lamp { background-image: linear-gradient(to bottom,#1a0d16,#2b1721); }
.velvet-theme button.ember-flow.ember-flow-lamp:checked { background-image: linear-gradient(to bottom,#25131b,#3b202c); color: #e1bb88; }
.velvet-theme.favorite-note { background-color: #2b1722; background-image: linear-gradient(145deg,#3c2230,#21131d); color: #e8d6bf; }
.velvet-theme.ember-quality-popover { background-color: #291722; color: #e4d0b5; }
.velvet-theme .stage-header-glass .stage-top-nav, .velvet-theme .stage-header-glass button.stage-quiet { background-color: rgba(51,22,36,.14); }
'''


class VelvetPaint:
    """One small retained light canvas; widget children are drawn live, above it."""
    def __init__(self, surface, widget, card=False):
        from winter_surface_cache import MaterialCache
        self.owner = weakref.ref(surface)
        self.widget, self.card = widget, card
        self.c, self.g, self.pointer = bindings()
        self.ptr = self.pointer(widget.__gpointer__, None)
        self.canvas = self.c.cairo_image_surface_create(0, 360, 216)
        self.cr = self.c.cairo_create(self.canvas)
        self.values = None
        self.closed = False
        self.material = MaterialCache(widget, surface) if card else None
        # Replace MaterialCache's handler: keep its cached CSS surface/build
        # routines, insert light before its normal child propagation.
        if self.material:
            self.g.g_signal_handler_disconnect(self.ptr, self.material.handler)
            self.material.handler = 0
        self.callback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_void_p)(self.draw)
        self.handler = self.g.g_signal_connect_data(self.ptr, b'draw', self.callback, None, None, 0)

    def compose(self, values):
        if self.values == values:
            return
        self.values = values
        c, cr = self.c, self.cr
        c.cairo_set_operator(cr, 0)
        c.cairo_paint(cr)
        c.cairo_set_operator(cr, 2)
        # Retained 360x216 analytic pools, no live blur or full-room readback.
        for color, x, y, rx, ry, strength in ((values[:3], .39, .40, .48, .59, .17),
                                             (values[3:], .68, .33, .39, .52, .10)):
            c.cairo_save(cr)
            c.cairo_translate(cr, x*360, y*216)
            c.cairo_scale(cr, rx*360, ry*216)
            pattern = c.cairo_pattern_create_radial(0., 0., 0., 0., 0., 1.)
            for offset, emission in ((0., 1.), (.20, .86), (.45, .48), (.7, .15), (1., 0.)):
                c.cairo_pattern_add_color_stop_rgba(pattern, offset, *color, strength*emission)
            c.cairo_set_source(cr, pattern)
            c.cairo_paint(cr)
            c.cairo_pattern_destroy(pattern)
            c.cairo_restore(cr)

    def draw(self, _widget, cr, _data):
        owner = self.owner()
        if self.closed or not owner or not owner.enabled or owner.failed:
            return False
        c = self.c
        w, h = self.widget.get_allocated_width(), self.widget.get_allocated_height()
        if w < 2 or h < 2:
            return False
        saved = False
        try:
            c.cairo_save(cr)
            saved = True
            if self.card:
                scale = max(1, self.widget.get_scale_factor())
                if (w+176)*(h+176)*scale*scale > self.material.MAX_PIXELS:
                    c.cairo_restore(cr)
                    saved = False
                    return False
                if self.material.key != (w, h, scale):
                    self.material.build(w, h, scale)
                c.cairo_set_source_surface(cr, self.material.surface, -88., -88.)
                c.cairo_paint(cr)
                rounded(c, cr, 0., 0., w, h, 18. if w <= 340 else 22.)
                c.cairo_clip(cr)
            self.compose(owner.light.values)
            c.cairo_scale(cr, w/360, h/216)
            c.cairo_set_source_surface(cr, self.canvas, 0., 0.)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr), 1)
            c.cairo_paint(cr)
            c.cairo_restore(cr)
            saved = False
            if self.card:
                for child in self.widget.get_children():
                    self.material.gtk.gtk_container_propagate_draw(self.ptr, self.pointer(child.__gpointer__, None), cr)
            owner.draws += 1
            return self.card
        except (OSError, RuntimeError, AttributeError):
            if saved:c.cairo_restore(cr)
            owner.failed = True
            owner.stop()
            return False

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.g.g_signal_handler_disconnect(self.ptr, self.handler)
        if self.material:
            self.material.close()
        self.c.cairo_destroy(self.cr)
        self.c.cairo_surface_destroy(self.canvas)


class VelvetSurface:
    def __init__(self, appearance, window, overlay, stage=False):
        self.appearance, self.window, self.overlay, self.stage = appearance, window, overlay, stage
        self.enabled = self.closed = self.failed = self.suspended = False
        self.light = Light()
        self.tick = 0
        self.last = None
        self.draws = 0
        self.draw_key = None
        self.painter = None
        self.area = None
        if stage:
            self.area = Gtk.DrawingArea()
            self.area.set_has_window(False)
            self.area.set_can_focus(False)
            self.area.set_no_show_all(True)
            self.area.set_halign(Gtk.Align.FILL)
            self.area.set_valign(Gtk.Align.FILL)
            overlay.add_overlay(self.area)
            # Background is overlay0; layout is overlay1. Light stays behind
            # every live control and is included in owned room snapshots.
            overlay.reorder_overlay(self.area, 1)
            overlay.set_overlay_pass_through(self.area, True)
        self.widget = self.area if stage else overlay.get_child()
        self.signals = [(window, window.connect('map', lambda *_: self.resume())),
                        (window, window.connect('unmap', lambda *_: self.stop())),
                        (window.get_settings(), window.get_settings().connect('notify::gtk-enable-animations', lambda *_: self.resume()))]

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.stop()
        if not enabled:
            if self.area:
                self.area.hide()
            if self.painter:
                self.painter.close()
                self.painter = None
            return
        self.failed = False
        if not self.painter:
            self.painter = VelvetPaint(self, self.widget, card=not self.stage)
        if self.area:
            self.area.show()
        host = self.appearance.audio_host
        cover = getattr(host, 'cover', None)
        self.set_cover(cover.get_pixbuf() if cover else None, animate=False)
        self.widget.queue_draw()

    def set_cover(self, picture, animate=True):
        if not self.enabled or self.closed:
            return
        from mirror_palette import swatches
        animate = animate and self.window.get_mapped() and self.window.get_settings().get_property('gtk-enable-animations')
        changed = self.light.set(colours(swatches(picture)), animate)
        if changed:
            self.widget.queue_draw()
            self.resume()

    def resume(self):
        self.stop(settle=False)
        if self.closed or not self.enabled or not self.window.get_mapped():
            return
        if not self.window.get_settings().get_property('gtk-enable-animations'):
            self.light.settle()
            self.widget.queue_draw()
        elif self.light.active:
            self.tick = self.widget.add_tick_callback(self.advance)

    def advance(self, _widget, clock):
        now = clock.get_frame_time()/1e6
        dt = max(0., min(.1, now-self.last)) if self.last is not None else 0.
        self.last = now
        self.light.advance(dt)
        # The frame clock stays continuous, but do not damage the room for
        # sub-visible colour changes. At this emission, a 1/128 source step
        # contributes less than half an 8-bit output level to either pool.
        key = tuple(round(value*128) for value in self.light.values)
        if key != self.draw_key or not self.light.active:
            self.draw_key = key
            self.widget.queue_draw()
        if not self.light.active:
            self.tick = 0
            self.last = None
            return False
        return True

    def stop(self, settle=True):
        if self.tick:
            self.widget.remove_tick_callback(self.tick)
            self.tick = 0
        self.last = None
        if settle:
            self.light.settle()

    def close(self):
        if self.closed:
            return
        self.set_enabled(False)
        self.closed = True
        for obj, signal in self.signals:
            if obj.handler_is_connected(signal):
                obj.disconnect(signal)
        if self.area:
            self.area.destroy()
