"""Slow Current: low-contrast, sound-shaped liquid interference.

Only a 180x108 retained canvas is repainted. No new audio capture, FFT,
network request or beat-triggered flash. Motion stays bounded in silence.
"""
import math
import ctypes as C
from gi.repository import Gdk, Gtk
from velvet_theme import VelvetPaint, VelvetSurface
from psychedelic_art import LiquidState, cover_swatches, FramePacer, lens_masks
from mirror_rhythm import SongRhythm
from mirror_optics import Optics
import time

CSS = b'''
.psychedelic-theme .card { background-color: #181921;
 background-image: linear-gradient(135deg,#292231,#171c24 58%,#20231f); }
window.ember-stage.psychedelic-theme { background-color: #12141b; }
window.ember-stage.psychedelic-theme.stage-opening { background-color: transparent; }
.psychedelic-theme .stage-console { background-color: #20212a;
 background-image: linear-gradient(135deg,rgba(51,41,54,.97),rgba(25,32,37,.97));
 border-color: rgba(225,195,153,.14); }
.psychedelic-theme .stage-art-shell, .psychedelic-theme .cover-surface {
 background-image: linear-gradient(135deg,rgba(222,186,151,.24),rgba(30,28,39,.9) 35%,rgba(15,25,31,.9) 78%,rgba(146,183,171,.15)); }
.psychedelic-theme .stage-overview-panel, .psychedelic-theme .dj-hero,
.psychedelic-theme .record-panel, .psychedelic-theme .editorial-card { background-color: rgba(21,24,31,.85); }
.psychedelic-theme .title, .psychedelic-theme .stage-track-title { color: #f5e7cf; }
.psychedelic-theme .stage-artist, .psychedelic-theme .artist { color: #d3c3af; }
.psychedelic-theme button.stage-line.stage-line-active { color: #ffe1ac;
 text-shadow: 0 0 12px rgba(243,175,112,.2); }
'''


class LiquidPaint(VelvetPaint):
    WIDTH, HEIGHT = 180, 108
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Five immutable alpha silhouettes. Each frame only transforms/tints them;
        # Cairo never rebuilds masks or evaluates radial gradients during motion.
        c=self.c
        c.cairo_mask_surface.restype=None
        c.cairo_mask_surface.argtypes=[C.c_void_p,C.c_void_p,C.c_double,C.c_double]
        self.lenses=[]
        for raw in lens_masks():
            lens=c.cairo_image_surface_create(2,128,128)
            c.cairo_surface_flush(lens)
            C.memmove(c.cairo_image_surface_get_data(lens),raw,len(raw))
            c.cairo_surface_mark_dirty(lens)
            self.lenses.append(lens)

    def close(self):
        if self.closed:return
        for lens in self.lenses:self.c.cairo_surface_destroy(lens)
        self.lenses=[]
        super().close()

    def compose(self, _values):
        owner = self.owner()
        key = (round(owner.phase, 5), round(owner.energy, 4), tuple(round(v,5) for v in owner.liquid.values),
               tuple(round(v,4) for v in owner.optics.values[:4]))
        if self.values == key:
            return
        self.values = key
        c, cr = self.c, self.cr
        c.cairo_set_operator(cr, 0); c.cairo_paint(cr); c.cairo_set_operator(cr, 2)
        c.cairo_save(cr)
        c.cairo_scale(cr,self.WIDTH/360,self.HEIGHT/216)
        phase, energy, material, response = key
        beat, _, bass, air = response
        # Broad translucent mineral-colour ribbons. Their centres move by
        # millimetres per frame, never reverse or reset on a new track.
        palette = tuple(material[i:i+3] for i in range(0,15,3))
        for index, colour in enumerate(palette):
            offset, aspect, spread, shoulder = material[15+index*4:19+index*4]
            angle = phase*(.75+offset*.4) + offset*math.tau + index*1.3
            # A continuous blend of drift, eddy and breathing. Independent
            # rates/offsets per song avoid a short, visibly repeating orbit.
            tide=.5+.5*math.sin(phase*(.19+spread*.09)+offset*math.tau)
            eddy=math.sin(angle*(.48+aspect*.32)+index)
            drift=math.sin(phase*(.31+spread*.23)+index*2.1)
            x = 180 + (100+spread*75)*(eddy*(1-tide*.55)+drift*tide*.55)
            y = 108 + (56+spread*40)*math.cos(angle*(.39+offset*.27)+index*.8)
            y += 12*math.sin(phase*(.22+aspect*.12)+index*1.6)
            # Measured accents move matter, never brightness or hue. The
            # same beat nudges each silhouette in its own gentle direction.
            x += 5*beat*math.sin(offset*math.tau)
            y += 3*air*math.cos(index+phase*.3)
            c.cairo_save(cr)
            c.cairo_translate(cr, x, y)
            width=(140+aspect*80+energy*12)*(.93+shoulder*.14)*(1+.055*math.sin(phase*.37+index))
            height=75+spread*48+17*math.sin(angle*.3)
            width *= 1+.045*bass+.025*beat
            height *= 1+.035*bass+.02*beat
            c.cairo_scale(cr,width/64,height/64)
            # At rest one mask per lens; transitions blend cached silhouettes.
            for shape,weight in enumerate(material[35+index*5:40+index*5]):
                if weight > .001:
                    c.cairo_set_source_rgba(cr,*colour,weight)
                    c.cairo_mask_surface(cr,self.lenses[shape],-64.,-64.)
            c.cairo_restore(cr)
        c.cairo_restore(cr)


class PsychedelicSurface(VelvetSurface):
    painter_type = LiquidPaint

    def __init__(self, *args, **kwargs):
        self.rhythm = SongRhythm('slow-current-'+str(id(self)))
        self.optics = Optics()
        self.pacer = FramePacer()
        self.phase = .8
        self.energy = 0.
        self.liquid = LiquidState()
        self.cover_swatches = None
        self.cover_stamp = None
        self.song = None
        self.song_check = 0.
        super().__init__(*args, **kwargs)
        self.materials = []
        self.obscured = False
        self.signals.append((self.window,self.window.connect('window-state-event',self.window_state)))

    def set_enabled(self, enabled):
        for material in self.materials:
            material.close()
        self.materials=[]
        super().set_enabled(enabled)
        if enabled and self.stage:
            # Repainting light must not rerasterise the hi-fi's static shadows.
            # Retain only materials; GTK still draws all live children/controls.
            from winter_surface_cache import MaterialCache
            def visit(widget):
                if ((isinstance(widget,Gtk.Button) and any(widget.get_style_context().has_class(name)
                        for name in ('stage-quiet','stage-tab','stage-transport'))) or
                        isinstance(widget,Gtk.Box) and any(widget.get_style_context().has_class(name)
                        for name in ('stage-console','stage-art-shell','cover-surface','lamp-well','stage-nav','stage-top-nav'))):
                    self.materials.append(MaterialCache(widget,self))
                if isinstance(widget,Gtk.Container):
                    for child in widget.get_children():visit(child)
            visit(self.overlay)

    def song_identity(self):
        host = self.appearance.audio_host
        def text(value):
            return value.get_text() if hasattr(value,'get_text') else str(value or '')
        return tuple(text(getattr(host,name,'')) for name in ('source','title','artist','album'))

    def set_cover(self, picture, animate=True):
        if not self.enabled or self.closed or picture is None:
            return
        from gi.repository import GdkPixbuf
        import hashlib
        small=picture.scale_simple(24,24,GdkPixbuf.InterpType.BILINEAR)
        self.cover_stamp=hashlib.sha256(small.get_pixels()).hexdigest()
        self.cover_swatches=cover_swatches(small)
        if not self.cover_swatches[6]:
            # Preserve genuinely black artwork instead of neutral amber fallback.
            raw=small.get_pixels();rgb=tuple(v/255 for v in raw[:3])
            self.cover_swatches=rgb+rgb+(1.,)
        self.song=self.song_identity()
        motion=animate and self.window.get_mapped() and self.window.get_settings().get_property('gtk-enable-animations')
        self.liquid.retarget(self.cover_swatches,(self.cover_stamp,self.song),motion)
        self.widget.queue_draw()
        self.resume()

    def resume(self):
        self.stop(settle=False)
        self.pacer.reset()
        if self.closed or not self.enabled or not self.window.get_mapped() or self.suspended or self.obscured:
            return
        if self.window.get_settings().get_property('gtk-enable-animations'):
            self.tick = self.widget.add_tick_callback(self.advance)
        if not self.window.get_settings().get_property('gtk-enable-animations'):
            self.liquid.settle()
        self.widget.queue_draw()

    def advance(self, _widget, clock):
        now = clock.get_frame_time()/1e6
        dt = max(0.,min(.05,now-self.last)) if self.last is not None else 0.
        self.last = now
        self.song_check += dt
        if self.song_check >= .5:
            self.song_check = 0.
            identity = self.song_identity()
            if identity != self.song and self.cover_swatches:
                self.song = identity
                self.liquid.retarget(self.cover_swatches,(self.cover_stamp,self.song))
        self.liquid.advance(dt)
        host = self.appearance.audio_host
        speed = self.rhythm.advance(host,time.monotonic(),dt)
        self.optics.advance(dt,self.rhythm)
        _, self.energy, _, _ = self.optics.values[:4]
        # Tempo changes velocity smoothly; the pattern's phase never resets.
        # Shared beat analysis runs in the existing meter, not in this tick.
        self.phase += dt*(.035+.04*self.energy+.035*speed)
        if self.pacer.due(now):
            self.widget.queue_draw()
        return True

    def stop(self, settle=True):
        self.rhythm.release()
        super().stop(settle)

    def set_suspended(self, value):
        self.suspended = bool(value)
        if self.suspended:
            self.stop()
        else:
            self.resume()

    def window_state(self, _window, event):
        self.obscured = bool(event.new_window_state & (Gdk.WindowState.ICONIFIED | Gdk.WindowState.WITHDRAWN))
        self.resume()
        return False
