"""An interactive record jacket with a perspective turn and a sliding LP."""
import ctypes as C
from ctypes.util import find_library
import math

from gi.repository import Gdk, GLib, Gtk, Pango

from cover_pause_paint import bindings, ease, gradient, rounded
from cover_tint import cover_color
from record_projection import RecordProjection
from source_picker import text


CSS = b'''
.record-inspector { padding: 13px 17px 16px; border-radius: 23px;
  border: 1px solid rgba(222,181,129,.32);
  background-color: #211a16;
  box-shadow: inset 0 1px rgba(252,217,164,.11); }
.record-inspector-well { border-radius: 17px; border: 1px solid rgba(230,182,126,.20);
  background-color: #211915;
  box-shadow: inset 0 -1px rgba(239,196,145,.12); }
.record-inspector-card { padding: 14px; border: 1px solid rgba(231,193,145,.16);
  border-radius: 17px; background-image: linear-gradient(135deg,rgba(248,213,165,.08),rgba(0,0,0,.12));
  box-shadow: inset 0 1px rgba(252,217,164,.10); }
.record-inspector-title { color: #f7e8d3; font-size: 25px; font-weight: bold; letter-spacing: -.5px; }
.record-inspector-meta { color: #d3bc9f; font-size: 12px; }
.record-inspector-hint { color: #c4a88a; font-size: 11px; }
.ember-stage button.record-inspector-key { color: #efd8b7; font-size: 12px; padding: 6px 10px;
  min-height: 18px; border: 1px solid rgba(232,190,132,.19); border-radius: 11px;
  background-image: linear-gradient(to bottom,#3b2f26,#241c17);
  box-shadow: inset 0 1px rgba(251,217,169,.11); }
.ember-stage button.record-inspector-key:hover, .ember-stage button.record-inspector-key:focus {
  border-color: rgba(245,195,132,.63); }
.ember-stage button.record-inspector-key:checked {
  color: #ffe0a4; border-color: rgba(245,195,132,.39);
  background-image: linear-gradient(to bottom,#523823,#35241a); }
.record-inspector.record-inspector-dense { padding: 7px 10px 9px; }
.record-inspector-dense .record-inspector-card { padding: 9px; }
.record-inspector-dense .record-inspector-title { font-size: 19px; }
.ember-stage .record-inspector-dense button.record-inspector-key {
  min-height: 16px; padding: 4px 7px; font-size: 11px; }
.ember-stage button.record-inspect-cover { padding: 3px 4px 4px; border-radius: 12px;
  border: 1px solid transparent; background: transparent; box-shadow: none; }
.ember-stage button.record-inspect-cover:hover, .ember-stage button.record-inspect-cover:focus {
  color: #fbdeb2; background-color: rgba(218,164,100,.09); border-color: rgba(238,187,127,.42); }
.ember-stage button.record-inspect-sleeve { min-height: 0; min-width: 0; padding: 0;
  border: none; background: transparent; box-shadow: none; }
.ember-stage button.record-inspect-sleeve:focus { outline: 1px solid rgba(248,193,122,.75); border-radius: 9px; }
'''

FACE_SIZE = 560
INSPECT_ART_SIZE = 1280
LIGHT_SIZE = 192
CAIRO_BILINEAR = 4
PERSPECTIVE_PIXELS = 520


def wash(c, cr, x0, y0, x1, y1, stops):
    paint = gradient(c, x0, y0, x1, y1, stops)
    c.cairo_set_source(cr, paint)
    c.cairo_fill(cr)
    c.cairo_pattern_destroy(paint)


def polygon(c, cr, *points):
    c.cairo_new_path(cr)
    c.cairo_move_to(cr, *points[0])
    for point in points[1:]:
        c.cairo_line_to(cr, *point)
    c.cairo_close_path(cr)


def control(label, callback=None, kind=Gtk.Button):
    button = kind(label=label)
    button.get_style_context().add_class('record-inspector-key')
    if callback:
        button.connect('clicked', lambda *_: callback())
    return keyboard_click(button)


def keyboard_click(button):
    def activate(widget, event):
        if event.keyval not in (Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return False
        if widget.is_sensitive():
            widget.clicked()
        return True
    button.ember_key_handler = activate
    return button


def label(value, style, lines=1):
    widget = Gtk.Label(label=value, xalign=0)
    widget.get_style_context().add_class(style)
    widget.set_width_chars(1)
    widget.set_ellipsize(Pango.EllipsizeMode.END)
    widget.set_line_wrap(lines > 1)
    widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    widget.set_lines(lines)
    return widget


def release_caption(release):
    year = str(release.get('releaseDate') or release.get('year') or '')[:4]
    count = str(release.get('trackCount') or '')
    count = text(f'Tracks: {count}', f'Треков: {count}') if count.isdecimal() and int(count) > 0 else ''
    return ' · '.join(value for value in (str(release.get('artist') or ''), year, count) if value)


class Jacket(Gtk.DrawingArea):
    def __init__(self, face_changed):
        super().__init__(can_focus=True, hexpand=True, vexpand=True)
        self.face_changed = face_changed
        self.angle = self.target = self.pitch = 0.
        self.disc_position = self.disc_target = 0.
        self.tick = 0
        self.drag = None
        self.release = {}
        self.paper = (.27, .17, .115)
        self.faces = {}
        self.vinyl = None
        self.c, signals, self.pointer = bindings()
        self.projection = RecordProjection(self.c)
        self.halo = self.shadow = None
        self.pending_art = None
        self.art_idle = 0
        self.damage = None
        self.gdk = C.CDLL(find_library('gdk-3'))
        self.gdk.gdk_cairo_set_source_pixbuf.argtypes = [C.c_void_p] * 2 + [C.c_double] * 2
        self.gdk.gdk_cairo_set_source_pixbuf.restype = None
        self.pango = C.CDLL(find_library('pangocairo-1.0'))
        self.pango.pango_cairo_show_layout.argtypes = [C.c_void_p] * 2
        self.pango.pango_cairo_show_layout.restype = None
        self.draw_callback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_void_p)(self.draw_surface)
        pointer = self.pointer(self.__gpointer__, None)
        draw_handler = signals.g_signal_connect_data(pointer, b'draw', self.draw_callback, None, None, 0)
        self.connect('destroy', lambda *_: signals.g_signal_handler_disconnect(pointer, draw_handler))
        self.connect('destroy', self.dispose)
        self.connect('unmap', lambda *_: self.settle())
        self.gesture = Gtk.GestureDrag.new(self)
        self.gesture.set_button(1)
        self.gesture.connect('drag-begin', self.drag_begin)
        self.gesture.connect('drag-update', self.drag_update)
        self.gesture.connect('drag-end', self.drag_end)
        self.gesture.connect('cancel', self.drag_cancel)
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect('enter-notify-event', lambda *_: self.cursor('grab'))
        self.connect('leave-notify-event', lambda *_: self.cursor(None) if self.drag is None else False)
        self.ember_key_handler = self.on_key
        self.get_accessible().set_name(text('Rotate the album jacket', 'Повернуть конверт альбома'))
        self.get_accessible().set_description(text('Drag or use the arrow keys.', 'Потяни мышью или нажми стрелку.'))

    @property
    def face(self):
        return 'back' if round(self.target / math.pi) % 2 else 'front'

    def reset(self, release, art):
        self.target = self.disc_target = 0.
        self.settle()
        self.release = release
        self.set_art(art)

    def set_art(self, art):
        self.clear_faces()
        if art:
            tint = cover_color(art)
            self.paper = tuple(base + (part - neutral) / 95 for base, part, neutral in
                               zip((.27, .17, .115), tint, (44, 44, 41)))
        else:
            self.paper = (.27, .17, .115)
        pixels = FACE_SIZE*self.get_scale_factor()
        if art:
            pixels = min(INSPECT_ART_SIZE, max(pixels, art.get_width(), art.get_height()))
        self.faces['front'] = (self.bake(lambda cr: self.print_face(cr, art, False), pixels), pixels)
        pixels = FACE_SIZE*self.get_scale_factor()
        self.faces['back'] = (self.bake(lambda cr: self.print_face(cr, None, True), pixels), pixels)
        self.vinyl = self.bake(self.cut_record)
        self.halo = self.light(((0, *self.paper, .86), (.55, *self.paper, .41), (1, *self.paper, 0)))
        self.shadow = self.light(((0, 0, 0, 0, .63), (.48, 0, 0, 0, .45), (1, 0, 0, 0, 0)))
        self.queue_draw()

    def offer_art(self, pixels):
        self.pending_art = pixels
        if not (self.tick or self.drag or self.art_idle):
            self.art_idle = GLib.idle_add(self.apply_art, priority=GLib.PRIORITY_LOW)

    def apply_art(self):
        self.art_idle = 0
        if self.pending_art and not (self.tick or self.drag):
            self.set_art(self.pending_art)
        return False

    def clear_faces(self):
        if self.art_idle:
            GLib.source_remove(self.art_idle)
            self.art_idle = 0
        self.pending_art = None
        for surface, _ in self.faces.values():
            self.projection.release(surface)
            self.c.cairo_surface_destroy(surface)
        self.faces.clear()
        if self.vinyl:
            self.c.cairo_surface_destroy(self.vinyl)
            self.vinyl = None
        for surface in (self.halo, self.shadow):
            if surface:
                self.c.cairo_surface_destroy(surface)
        self.halo = self.shadow = None

    def dispose(self, *_):
        self.settle()
        self.clear_faces()
        self.projection.clear_buffer()

    def bake(self, paint, pixels=FACE_SIZE):
        surface = self.c.cairo_image_surface_create(0, pixels, pixels)
        cr = self.c.cairo_create(surface)
        try:
            self.c.cairo_scale(cr, pixels/FACE_SIZE, pixels/FACE_SIZE)
            paint(cr)
        finally:
            self.c.cairo_destroy(cr)
        return surface

    def light(self, stops):
        c = self.c
        def paint(cr):
            center = FACE_SIZE/2
            pattern = c.cairo_pattern_create_radial(center, center, center*.03, center, center, center)
            for stop in stops:
                c.cairo_pattern_add_color_stop_rgba(pattern, *stop)
            c.cairo_set_source(cr, pattern)
            c.cairo_paint(cr)
            c.cairo_pattern_destroy(pattern)
        return self.bake(paint, LIGHT_SIZE)

    def paint_light(self, cr, surface, x, y, width, height):
        c = self.c
        c.cairo_save(cr)
        c.cairo_translate(cr, x-width, y-height)
        c.cairo_scale(cr, 2*width/LIGHT_SIZE, 2*height/LIGHT_SIZE)
        c.cairo_set_source_surface(cr, surface, 0, 0)
        c.cairo_pattern_set_filter(c.cairo_get_source(cr), CAIRO_BILINEAR)
        c.cairo_rectangle(cr, 0, 0, LIGHT_SIZE, LIGHT_SIZE)
        c.cairo_fill(cr)
        c.cairo_restore(cr)

    def print_text(self, cr, value, x, y, font, color, width, lines=1):
        layout = self.create_pango_layout(value)
        layout.set_width(width * Pango.SCALE)
        layout.set_font_description(Pango.FontDescription.from_string(font))
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_height(-lines)
        self.c.cairo_set_source_rgba(cr, *color)
        self.c.cairo_move_to(cr, x, y)
        self.pango.pango_cairo_show_layout(cr, self.pointer(layout.__gpointer__, None))

    def print_face(self, cr, art, reverse):
        c = self.c
        size = FACE_SIZE
        tone = self.paper
        c.cairo_rectangle(cr, 0, 0, size, size)
        wash(c, cr, 0, 0, size, size, ((0, *tone, 1), (.62, .095, .071, .057, 1),
                                       (1, .054, .039, .031, 1)))
        if art:
            scale = min((size-8) / art.get_width(), (size-8) / art.get_height())
            c.cairo_save(cr)
            rounded(c, cr, 4, 4, size-8, size-8, 4)
            c.cairo_clip(cr)
            c.cairo_translate(cr, (size-art.get_width()*scale)/2, (size-art.get_height()*scale)/2)
            c.cairo_scale(cr, scale, scale)
            self.gdk.gdk_cairo_set_source_pixbuf(cr, self.pointer(art.__gpointer__, None), 0, 0)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr), CAIRO_BILINEAR)
            c.cairo_paint(cr)
            c.cairo_restore(cr)
        else:
            cream, brass = (1., .91, .75, 1.), (.90, .69, .45, 1.)
            for radius in (79, 94, 110, 124):
                c.cairo_new_path(cr)
                c.cairo_arc(cr, 375, 158, radius, 0, math.tau)
                c.cairo_set_source_rgba(cr, .99, .75, .47, .15)
                c.cairo_set_line_width(cr, 1.3)
                c.cairo_stroke(cr)
            c.cairo_rectangle(cr, 40, 290, 480, 2)
            wash(c, cr, 40, 290, 520, 290, ((0, .91, .67, .42, .65), (1, .91, .67, .42, .04)))
            self.print_text(cr, text('REVERSE', 'ОБОРОТ') if reverse else text('ALBUM', 'АЛЬБОМ'),
                            40, 263, 'Sans Bold 12', brass, 290)
            self.print_text(cr, str(self.release.get('title') or ''), 40, 307,
                            'Sans Bold 29', cream, 480, lines=2)
            self.print_text(cr, release_caption(self.release), 40, 418, 'Sans 16', brass, 480, lines=2)
            if reverse:
                self.print_text(cr, text('Ember jacket', 'Оформление Ember'), 40, 496, 'Sans 12', cream, 460)

    def cut_record(self, cr):
        c = self.c
        c.cairo_translate(cr, FACE_SIZE / 2, FACE_SIZE / 2)
        c.cairo_arc(cr, 0, 0, FACE_SIZE*.491, 0, math.tau)
        wash(c, cr, -190, -180, 180, 185, ((0, .022, .02, .018, 1), (.36, .075, .067, .058, 1),
             (.45, .17, .144, .117, 1), (.53, .043, .038, .034, 1), (.78, .11, .084, .062, 1),
             (.86, .21, .155, .101, 1), (1, .034, .03, .025, 1)))
        for n in range(48):
            radius = 80+n*3.97
            c.cairo_new_path(cr)
            c.cairo_arc(cr, 0, 0, radius, 0, math.tau)
            c.cairo_set_source_rgba(cr, .96, .78, .57, .24 if n in (7, 20, 32, 47) else .10)
            c.cairo_set_line_width(cr, 1.6 if n % 3 == 0 else .8)
            c.cairo_stroke(cr)
        c.cairo_arc(cr, 0, 0, 72, 0, math.tau)
        wash(c, cr, -60, -60, 60, 60, ((0, .79, .53, .29, 1), (.48, *self.paper, 1), (1, .17, .10, .069, 1)))
        for radius, alpha in ((67, .4), (25, .4), (12, .25), (4.5, .9)):
            c.cairo_new_path(cr)
            c.cairo_arc(cr, 0, 0, radius, 0, math.tau)
            c.cairo_set_source_rgba(cr, .96, .78, .57, alpha)
            c.cairo_set_line_width(cr, 1.5)
            c.cairo_stroke(cr)
        c.cairo_arc(cr, 0, 0, 3.8, 0, math.tau)
        c.cairo_set_source_rgba(cr, .04, .026, .018, 1)
        c.cairo_fill(cr)

    def draw_surface(self, _widget, cr, _data):
        if not self.faces:
            return False
        c = self.c
        w, h = self.get_allocated_width(), self.get_allocated_height()
        size = self.jacket_size(w, h)
        if size < 10:
            return False
        cos, sin = math.cos(self.angle), math.sin(self.angle)
        side, span = (1 if cos >= 0 else -1), abs(cos)
        offset = self.disc_position*size*.57
        c.cairo_save(cr)
        c.cairo_translate(cr, w*.50, h*.43)
        self.paint_light(cr, self.halo, 0, 0, size*.94, size*.72)
        c.cairo_translate(cr, -side*offset*span*.32, h*.05)
        self.paint_light(cr, self.shadow, size*.03, size*.53,
                         size*(.59+.10*self.disc_position), size*.14)
        c.cairo_rotate(cr, self.pitch)
        if offset > .25 and span > .015:
            c.cairo_save(cr)
            c.cairo_translate(cr, side*offset*span, size*.012)
            c.cairo_scale(cr, span*size/FACE_SIZE, size*.966/FACE_SIZE)
            c.cairo_set_source_surface(cr, self.vinyl, -FACE_SIZE/2, -FACE_SIZE/2)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr), CAIRO_BILINEAR)
            c.cairo_rectangle(cr, -FACE_SIZE/2, -FACE_SIZE/2, FACE_SIZE, FACE_SIZE)
            c.cairo_fill(cr)
            c.cairo_restore(cr)
        surface, pixels = self.faces['front' if cos >= 0 else 'back']
        self.draw_print(cr, surface, pixels, size, span, sin*side)
        c.cairo_restore(cr)
        return False

    @staticmethod
    def jacket_size(width, height):
        return min(height*.77, width*.63, 520.)

    def redraw_jacket(self):
        width, height = self.get_allocated_width(), self.get_allocated_height()
        size = self.jacket_size(width, height)
        cosine = math.cos(self.angle)
        span = abs(cosine)
        shift = math.copysign(self.disc_position*span*.57, cosine)
        center = width*.5-shift*size*.32
        left = math.floor(center+size*min(-.58*span-.05, shift-.50*span-.03, -.57))
        right = math.ceil(center+size*max(.58*span+.05, shift+.50*span+.03, .62))
        top = math.floor(height*.48-size*.625)
        bottom = math.ceil(height*.48+size*.68)
        bounds = (left, top, right, bottom)
        if self.damage:
            old_left, old_top, old_right, old_bottom = self.damage
            left, top = min(left, old_left), min(top, old_top)
            right, bottom = max(right, old_right), max(bottom, old_bottom)
        self.damage = bounds
        left, top = max(0,left), max(0,top)
        right, bottom = min(width,right), min(height,bottom)
        if right > left and bottom > top:
            self.queue_draw_area(left, top, right-left, bottom-top)

    def draw_print(self, cr, surface, pixels, size, span, skew):
        c = self.c
        if abs(skew) < .012:
            c.cairo_save(cr)
            rounded(c, cr, -size/2, -size/2, size, size, size*.011)
            c.cairo_clip(cr)
            c.cairo_scale(cr, size/pixels, size/pixels)
            c.cairo_set_source_surface(cr, surface, -pixels/2, -pixels/2)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr), CAIRO_BILINEAR)
            c.cairo_paint(cr)
            c.cairo_restore(cr)
            rounded(c, cr, -size/2+.55, -size/2+.55, size-1.1, size-1.1, size*.011)
            c.cairo_set_source_rgba(cr, 1, .87, .65, .51)
            c.cairo_set_line_width(cr, 1.1)
            c.cairo_stroke(cr)
            return
        focal = 3.2
        a, b = focal/(focal+skew/2), focal/(focal-skew/2)
        lx, rx = -.5*span*size*a, .5*span*size*b
        ly, ry = size*a/2, size*b/2
        width = size*.020*skew
        edge, height = (rx, ry) if width > 0 else (lx, ly)
        polygon(c, cr, (edge, -height), (edge+width, -height*.989),
                (edge+width, height*.989), (edge, height))
        wash(c, cr, edge, 0, edge+width, 0,
             ((0, .22, .126, .073, 1), (.4, .64, .43, .25, 1), (1, .23, .14, .085, 1)))
        if span < .018:
            return

        face = ((lx, -ly), (rx, -ry), (rx, ry), (lx, ly))
        c.cairo_save(cr)
        polygon(c, cr, *face)
        c.cairo_clip(cr)
        # Spend the animation budget on the changing plane. Once it faces
        # the viewer again the flat blit uses the original texture directly.
        scale = min(self.get_scale_factor(), PERSPECTIVE_PIXELS/size)
        projected = self.projection.project(surface, pixels, size, span, skew/focal,
                                            (lx, rx, max(ly, ry)), scale)
        if projected:
            buffer, x, y = projected
            c.cairo_save(cr)
            c.cairo_translate(cr, x, y)
            c.cairo_scale(cr, 1/scale, 1/scale)
            c.cairo_set_source_surface(cr, buffer, 0, 0)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr), CAIRO_BILINEAR)
            c.cairo_paint(cr)
            c.cairo_restore(cr)
        c.cairo_restore(cr)
        polygon(c, cr, *face)
        c.cairo_set_source_rgba(cr, 1, .87, .65, .44)
        c.cairo_set_line_width(cr, 1.1)
        c.cairo_stroke(cr)

    def cursor(self, name):
        window = self.get_window()
        if window:
            window.set_cursor(Gdk.Cursor.new_from_name(window.get_display(), name) if name else None)
        return False

    def drag_begin(self, _gesture, _x, _y):
        self.grab_focus()
        self.drag = (self.angle, self.target, max(80., min(250., self.get_allocated_width()*.27)))
        self.cursor('grabbing')

    def drag_update(self, gesture, dx, dy):
        if self.drag is None:
            return
        if abs(dx) > 5 and gesture is not None:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        start, _, travel = self.drag
        self.angle = start+dx/travel*math.pi
        self.pitch = .045*math.tanh(dy/110)
        self.redraw_jacket()

    def drag_end(self, _gesture, dx, _dy):
        if self.drag is None:
            return
        _, target, _ = self.drag
        self.drag = None
        self.cursor('grab')
        half_turn = round(self.angle/math.pi)
        if abs(dx) > 25 and (half_turn*math.pi == target):
            half_turn += 1 if dx > 0 else -1
        self.turn_to(half_turn*math.pi)

    def drag_cancel(self, *_):
        if self.drag is not None:
            _, target, _ = self.drag
            self.drag = None
            self.cursor(None)
            self.turn_to(target)

    def set_face(self, face):
        if self.face != face:
            desired = 1 if face == 'back' else 0
            turns = self.angle/math.pi
            nearest = math.floor((turns-desired)/2+.5)*2+desired
            self.turn_to(nearest*math.pi)

    def turn_to(self, angle):
        self.target = angle
        self.animate()

    def toggle_disc(self, shown):
        self.disc_target = float(shown)
        self.animate()

    def on_key(self, _widget, event):
        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_space):
            direction = -1 if event.keyval == Gdk.KEY_Left else 1
            turns = round((self.angle-self.target)/math.tau)
            self.turn_to(self.target+math.pi*direction+math.tau*turns)
            return True
        return False

    def settle(self):
        if self.tick:
            self.remove_tick_callback(self.tick)
            self.tick = 0
        self.drag = None
        self.angle, self.pitch, self.disc_position = self.target, 0., self.disc_target
        self.face_changed(self.face)
        self.redraw_jacket()
        if self.pending_art:
            self.offer_art(self.pending_art)

    def animate(self):
        settings = Gtk.Settings.get_default()
        if not self.get_mapped() or not settings.get_property('gtk-enable-animations'):
            self.settle()
            return
        self.start = (self.angle, self.pitch, self.disc_position)
        self.started = None
        if not self.tick:
            self.tick = self.add_tick_callback(self.animate_frame)

    def animate_frame(self, _widget, clock):
        time = clock.get_frame_time()
        if self.started is None:
            self.started = time
        t = min(1., (time-self.started)/490_000)
        progress = ease(t)
        start_angle, pitch, disc = self.start
        if self.drag is None:
            self.angle = start_angle+(self.target-start_angle)*progress
            self.pitch = pitch*(1-progress)
        self.disc_position = disc+(self.disc_target-disc)*progress
        self.redraw_jacket()
        if t >= 1.:
            self.tick = 0
            if self.drag is None:
                self.face_changed(self.face)
            if self.pending_art:
                self.offer_art(self.pending_art)
            return False
        return True


class RecordInspector(Gtk.Box):
    def __init__(self, close, details):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.compact = False
        self.get_style_context().add_class('record-inspector')
        top = Gtk.Box(spacing=10)
        self.close_button = control('‹ '+text('Back to shelf', 'На полку'), close)
        top.pack_start(self.close_button, False, False, 0)
        self.pack_start(top, False, False, 0)

        display = Gtk.Box(spacing=14)
        self.pack_start(display, True, True, 0)
        self.canvas = Jacket(self.update_face)
        well = Gtk.Box()
        well.get_style_context().add_class('record-inspector-well')
        well.pack_start(self.canvas, True, True, 0)
        display.pack_start(well, True, True, 0)
        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7, valign=Gtk.Align.CENTER)
        self.rail = rail
        rail.set_size_request(238, -1)
        rail.get_style_context().add_class('record-inspector-card')
        display.pack_end(rail, False, False, 0)

        self.title = label('', 'record-inspector-title', 2)
        rail.pack_start(self.title, False, False, 0)
        self.meta = label('', 'record-inspector-meta', 2)
        rail.pack_start(self.meta, False, False, 0)
        sides = Gtk.Box(spacing=4, homogeneous=True)
        self.front_button = Gtk.RadioButton.new_with_label(None, text('Cover', 'Обложка'))
        self.back_button = Gtk.RadioButton.new_with_label_from_widget(self.front_button, text('Back', 'Оборот'))
        for button, face in ((self.front_button, 'front'), (self.back_button, 'back')):
            button.set_mode(False)
            keyboard_click(button)
            button.get_style_context().add_class('record-inspector-key')
            button.connect('toggled', lambda btn, side=face: self.canvas.set_face(side) if btn.get_active() else None)
            sides.pack_start(button, True, True, 0)
        rail.pack_start(sides, False, False, 0)
        self.actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.disc_button = control(text('Slide out the record', 'Достать пластинку'), kind=Gtk.ToggleButton)
        self.disc_button.connect('toggled', self.change_disc)
        self.actions.pack_start(self.disc_button, True, True, 0)
        self.actions.pack_start(control(text('Album details', 'Об альбоме')+'  ›', details), True, True, 0)
        rail.pack_start(self.actions, False, False, 0)
        hint = label(text('Drag the jacket to turn it.', 'Потяни конверт, чтобы повернуть его.'),
                     'record-inspector-hint', 2)
        rail.pack_start(hint, False, False, 0)

    def set_compact(self, compact):
        if self.compact == compact:
            return
        self.compact = compact
        style = self.get_style_context()
        (style.add_class if compact else style.remove_class)('record-inspector-dense')
        self.rail.set_spacing(5 if compact else 7)
        self.set_spacing(5 if compact else 9)
        self.actions.set_orientation(Gtk.Orientation.HORIZONTAL if compact else Gtk.Orientation.VERTICAL)

    def open(self, release, art):
        self.canvas.reset(release, art)
        self.title.set_text(release['title'])
        self.meta.set_text(release_caption(release))
        self.meta.set_visible(bool(self.meta.get_text()))
        self.front_button.set_active(True)
        self.disc_button.set_active(False)

    def update_face(self, face):
        (self.front_button if face == 'front' else self.back_button).set_active(True)

    def change_disc(self, button):
        shown = button.get_active()
        button.set_label(text('Slide in the record', 'Убрать пластинку') if shown else
                         text('Slide out the record', 'Достать пластинку'))
        self.canvas.toggle_disc(shown)
