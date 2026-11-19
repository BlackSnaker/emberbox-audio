"""Slow Current: low-contrast, sound-shaped liquid interference.

Only a 360x216 retained canvas is repainted. No new audio capture, FFT,
network request or beat-triggered flash. Motion stays bounded in silence.
"""
import math
from gi.repository import Gdk
from velvet_theme import VelvetPaint, VelvetSurface

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
    def compose(self, _values):
        owner = self.owner()
        key = (round(owner.phase, 5), round(owner.energy, 4))
        if self.values == key:
            return
        self.values = key
        c, cr = self.c, self.cr
        c.cairo_set_operator(cr, 0); c.cairo_paint(cr); c.cairo_set_operator(cr, 2)
        phase, energy = key
        # Broad translucent mineral-colour ribbons. Their centres move by
        # millimetres per frame, never reverse or reset on a new track.
        palette = ((.63,.30,.38),(.22,.51,.49),(.66,.47,.27),(.39,.34,.62))
        for index, colour in enumerate(palette):
            angle = phase + index*1.7
            x = 180 + 156*math.sin(angle*.67+index)
            y = 108 + 88*math.cos(angle*.51+index*.8)
            c.cairo_save(cr)
            c.cairo_translate(cr, x, y)
            c.cairo_scale(cr, 190+energy*12, 108+17*math.sin(angle*.3))
            p = c.cairo_pattern_create_radial(0.,0.,0.,0.,0.,1.)
            for at, alpha in ((0.,.0),(.24,.13),(.40,.27),(.56,.12),(.75,.035),(1.,0.)):
                c.cairo_pattern_add_color_stop_rgba(p, at, *colour, alpha)
            c.cairo_set_source(cr,p); c.cairo_paint(cr)
            c.cairo_pattern_destroy(p); c.cairo_restore(cr)


class PsychedelicSurface(VelvetSurface):
    painter_type = LiquidPaint

    def __init__(self, *args, **kwargs):
        self.phase = .8
        self.energy = 0.
        super().__init__(*args, **kwargs)
        self.obscured = False
        self.signals.append((self.window,self.window.connect('window-state-event',self.window_state)))

    def set_cover(self, picture, animate=True):
        # No colour reset or image processing at a track boundary.
        if self.enabled and not self.closed:
            self.widget.queue_draw()
            self.resume()

    def resume(self):
        self.stop(settle=False)
        if self.closed or not self.enabled or not self.window.get_mapped() or self.suspended or self.obscured:
            return
        if self.window.get_settings().get_property('gtk-enable-animations'):
            self.tick = self.widget.add_tick_callback(self.advance)
        self.widget.queue_draw()

    def advance(self, _widget, clock):
        now = clock.get_frame_time()/1e6
        dt = max(0.,min(.05,now-self.last)) if self.last is not None else 0.
        self.last = now
        host = self.appearance.audio_host
        meter = getattr(host,'meter',None)
        target = 0.
        if host and getattr(host,'playing',False) and not getattr(getattr(host,'sound',None),'muted',False):
            import time
            if 0 <= time.monotonic()-getattr(meter,'last_sample',0) < .35:
                try: target = float(meter.rms_level)
                except (AttributeError,TypeError,ValueError): pass
                target = max(0.,min(1.,target)) if math.isfinite(target) else 0.
        # >=0.9s smoothing: music changes flow, never luminance or hue.
        self.energy += (target-self.energy)*-math.expm1(-dt/.9)
        self.phase += dt*(.055+.065*self.energy)
        if getattr(self, "painted_at", None) is None or now-self.painted_at >= 1/60-.001:
            self.painted_at = now
            self.widget.queue_draw()
        return True

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
