"""Small, translucent optical materials for the listening-room toolbar.

Layered CSS reflections reuse the room behind the controls. No backdrop
readback, live blur or audio processing is needed. Tab changes use one tiny
owned snapshot and a finite presentation-clock lens animation.
"""
import ctypes as C
import math
from gi.repository import Gtk
from room_snapshot import snapshot
from cover_pause_paint import bindings,rounded,gradient,ease

CSS=b'''
.ember-stage .stage-header-glass .stage-top-nav {
 background-color: rgba(15,22,22,.13);
 background-image: linear-gradient(115deg,rgba(241,190,216,.035),rgba(255,244,219,0) 31%,rgba(175,229,236,.012) 76%,rgba(221,197,245,.035)),
                   linear-gradient(to bottom,rgba(255,255,246,.085),rgba(255,255,246,.012) 16%,rgba(255,255,246,0) 38%,rgba(255,255,246,0) 75%,rgba(210,221,255,.035));
 border: 1px solid rgba(225,234,230,.12);
 border-top-color: rgba(255,249,228,.25); border-left-color: rgba(192,231,241,.19);
 border-right-color: rgba(246,204,220,.15); border-bottom-color: rgba(207,202,243,.12);
 border-radius: 999px; padding: 3px;
 box-shadow: inset 1px 1px 2px rgba(255,252,232,.045),inset -1px -1px 2px rgba(220,213,250,.025),0 7px 20px rgba(0,0,0,.12);
}
.ember-stage .stage-header-glass button.stage-quiet {
 background-color: rgba(24,32,30,.10);
 background-image: linear-gradient(120deg,rgba(243,193,223,.04),rgba(255,250,235,0) 33%,rgba(174,229,241,.018) 78%,rgba(234,203,244,.045)),
                   linear-gradient(to bottom,rgba(255,255,244,.10),rgba(255,255,244,.012) 18%,rgba(255,255,244,0) 42%,rgba(255,255,244,0) 78%,rgba(217,224,255,.04));
 border: 1px solid rgba(225,234,228,.14);
 border-top-color: rgba(255,250,228,.29); border-left-color: rgba(188,233,243,.22);
 border-right-color: rgba(247,205,220,.18); border-bottom-color: rgba(211,205,246,.14);
 border-radius: 999px; padding: 7px 12px;
 color: #ded5bf;
 box-shadow: inset 1px 1px 2px rgba(255,255,239,.05),inset -1px -1px 2px rgba(216,220,252,.035),0 5px 13px rgba(0,0,0,.12);
}
.ember-stage .stage-header-glass button.stage-exit { border-radius: 999px; padding: 4px 9px; }
.ember-stage .stage-header-glass button.stage-tab {
 border: 1px solid transparent; border-radius: 21px; padding: 7px 13px;
 background-image: none; background-color: transparent; color: #c4bda9; box-shadow: none;
}
.ember-stage .stage-header-glass button.stage-tab:checked {
 background-color: rgba(202,224,217,.065);
 background-image: linear-gradient(125deg,rgba(255,239,208,.075),rgba(255,250,227,0) 39%,rgba(189,224,247,.018) 75%,rgba(229,196,244,.065));
 border-color: rgba(211,231,231,.20); border-top-color: rgba(255,252,234,.34);
 border-left-color: rgba(198,237,247,.27); border-right-color: rgba(246,207,233,.24);
 color: #fff0c9;
 box-shadow: inset 1px 1px 2px rgba(255,255,243,.07),inset -1px -1px 2px rgba(218,210,250,.045),0 3px 9px rgba(0,0,0,.12);
}
.ember-stage.nocturne-theme .stage-header-glass .stage-top-nav { background-color: rgba(10,15,16,.17); }
.ember-stage.nocturne-theme .stage-header-glass button.stage-quiet { background-color: rgba(19,27,28,.10); }
.ember-stage.mirrorball-theme .stage-header-glass .stage-top-nav { background-color: rgba(24,33,46,.13); }
.ember-stage.mirrorball-theme .stage-header-glass button.stage-quiet { background-color: rgba(34,45,59,.09); }
.ember-stage.christmas-theme .stage-header-glass .stage-top-nav { background-color: rgba(13,33,24,.17); }
.ember-stage.christmas-theme .stage-header-glass button.stage-quiet { background-color: rgba(25,48,34,.11); }
.ember-stage .stage-header-glass button.stage-quiet,
.ember-stage .stage-header-glass button.stage-tab {
 transition-property: background-color,border-color,box-shadow,color;
 transition-duration: 240ms; transition-timing-function: ease-out;
 outline-style: none; outline-width: 0;
}
.ember-stage .stage-header-glass button.stage-quiet:hover,
.ember-stage .stage-header-glass button.stage-tab:hover {
 background-color: rgba(210,232,226,.055); color: #fff4d9;
 border-color: rgba(218,237,241,.27); border-top-color: rgba(255,249,228,.38);
 border-right-color: rgba(248,212,235,.29);
 box-shadow: inset 1px 1px 3px rgba(255,255,241,.065),inset -1px -1px 3px rgba(218,209,250,.045),0 4px 15px rgba(0,0,0,.12);
}
.ember-stage .stage-header-glass button.stage-tab:checked:hover { background-color: rgba(210,232,226,.10); }
.ember-stage .stage-header-glass button.stage-quiet:active,
.ember-stage .stage-header-glass button.stage-tab:active {
 background-color: rgba(181,215,209,.04); border-color: rgba(225,236,232,.24);
 box-shadow: inset 0 2px 5px rgba(0,0,0,.17),inset 0 -1px 2px rgba(232,226,250,.08);
 transition-duration: 100ms;
}
.ember-stage .stage-header-glass button:disabled { color: #8e8d81; }
.ember-stage .small-screen .stage-header-glass .stage-top-nav button.stage-tab { padding: 6px 8px; font-size: 10px; }
.ember-stage .stage-header-glass .stage-top-nav.glass-flight button.stage-tab {
 background-color: transparent; background-image: none; border-color: transparent;
 box-shadow: none; transition-duration: 0ms;
}
'''


def lens_rect(start,end,progress):
    t=ease(progress);wave=math.sin(math.pi*max(0.,min(1.,progress)))
    x,y,w,h=(a+(b-a)*t for a,b in zip(start,end))
    stretch=min(14.,abs(end[0]-start[0])*.08)*wave
    return x-stretch/2,y+wave*.6,w+stretch,h-wave*1.2


class GlassNavigation(Gtk.Overlay):
    """A small moving lens; pixels beneath it are really resampled, not blurred."""
    DURATION=.64

    def __init__(self,nav):
        super().__init__();self.nav=nav;self.add(nav)
        self.layer=Gtk.DrawingArea();self.layer.set_has_window(False)
        self.layer.set_can_focus(False);self.layer.set_no_show_all(True)
        self.add_overlay(self.layer);self.set_overlay_pass_through(self.layer,True)
        self.c,self.g,self.pointer=bindings()
        self.c.cairo_fill_preserve.restype=None;self.c.cairo_fill_preserve.argtypes=[C.c_void_p]
        self.ptr=self.pointer(self.layer.__gpointer__,None)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw_lens)
        self.handler=self.g.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)
        self.frame=self.canvas=self.cr=None;self.current=None;self.rect=self.start=self.end=None
        self.frame_size=None
        self.tick=0;self.progress=self.age=0.;self.last=None;self.active=self.closed=self.handed_off=False
        self.connect('unmap',lambda *_:self.finish())
        self.connect('size-allocate',self.resized)
        self.connect('destroy',lambda *_:self.close())
        settings=self.get_settings()
        self.motion_signal=settings.connect('notify::gtk-enable-animations',lambda *_:self.finish())

    def select(self,button):
        if self.closed or button is self.current:return
        previous=self.current;self.current=button
        point=button.translate_coordinates(self.nav,0,0)
        end=(*point,button.get_allocated_width(),button.get_allocated_height()) if point else None
        if not previous or not end or not self.get_mapped() or not self.get_settings().get_property('gtk-enable-animations'):
            self.finish();self.rect=end;return
        point=previous.translate_coordinates(self.nav,0,0)
        start=self.rect if self.active else ((*point,previous.get_allocated_width(),previous.get_allocated_height()) if point else end)
        self.finish();self.start,self.end,self.rect=start,end,start
        allocation=self.nav.get_allocation().copy();area=allocation.copy();area.x=area.y=0
        if area.width>2048 or area.height>128:return
        self.nav.get_style_context().add_class('glass-flight')
        try:
            w,h,raw=snapshot(self.nav,area)
            self.frame_size=(w,h)
            self.frame=self.c.cairo_image_surface_create(0,w,h)
            self.c.cairo_surface_flush(self.frame)
            C.memmove(self.c.cairo_image_surface_get_data(self.frame),raw,len(raw))
            self.c.cairo_surface_mark_dirty(self.frame)
            self.canvas=self.c.cairo_image_surface_create(0,w,h);self.cr=self.c.cairo_create(self.canvas)
        except (OSError,RuntimeError,AttributeError):self.finish();return
        finally:self.nav.size_allocate(allocation)
        self.active=True;self.progress=self.age=0.;self.last=None
        self.nav.set_opacity(0.);self.layer.set_opacity(1.);self.layer.show();self.layer.queue_draw()
        self.tick=self.add_tick_callback(self.advance)

    def resized(self,_widget,allocation):
        if self.active and self.frame_size!=(allocation.width,allocation.height):self.finish()

    def advance(self,_widget,clock):
        if not self.active:return False
        now=clock.get_frame_time()
        if self.last is not None:self.age+=max(0.,min(.05,(now-self.last)/1e6))
        self.last=max(now,self.last or now)
        self.progress=min(1.,self.age/self.DURATION)
        self.rect=lens_rect(self.start,self.end,self.progress)
        if self.progress>=1.:
            self.tick=0;self.finish();return False
        if self.progress>=.82:
            if not self.handed_off:
                self.handed_off=True;self.nav.get_style_context().remove_class('glass-flight')
            alpha=ease((self.progress-.82)/.18)
            self.nav.set_opacity(alpha);self.layer.set_opacity(1.-alpha)
        self.layer.queue_draw();return True

    def draw_lens(self,_area,cr,_data):
        if not self.active or not self.frame:return False
        c=self.c;out=self.cr;x,y,w,h=self.rect
        # Replace a small retained canvas, never clear the live window.
        c.cairo_set_operator(out,1);c.cairo_set_source_surface(out,self.frame,0,0);c.cairo_paint(out)
        c.cairo_save(out)
        rounded(c,out,x,y,w,h,h/2);c.cairo_clip(out)
        c.cairo_translate(out,x+w/2,y+h/2)
        swell=math.sin(math.pi*self.progress)
        c.cairo_scale(out,1.+.035*swell,1.+.065*swell)
        c.cairo_translate(out,-x-w/2,-y-h/2)
        c.cairo_set_source_surface(out,self.frame,0,0)
        c.cairo_pattern_set_filter(c.cairo_get_source(out),1);c.cairo_paint(out)
        c.cairo_restore(out);c.cairo_set_operator(out,2)
        # Clear body, a refracting rim, and a highlight that bends with travel.
        direction=1. if self.end[0]>=self.start[0] else -1.
        film=gradient(c,x,y,x+w,y+h,((0,1.,.92,.76,.055),(.38,1.,1.,1.,0.),(.74,.65,.86,1.,.018),(1,.91,.72,.97,.055)))
        rim=gradient(c,x+direction*w*.12*swell,y,x+w-direction*w*.12*swell,y+h,
                     ((0,1.,.98,.90,.40),(.23,.68,.91,1.,.29),(.52,.9,.96,1.,.10),(.78,1.,.73,.89,.28),(1,.83,.79,1.,.24)))
        try:
            rounded(c,out,x+.5,y+.5,max(1.,w-1),max(1.,h-1),h/2)
            c.cairo_set_source(out,film);c.cairo_fill_preserve(out)
            c.cairo_set_source(out,rim);c.cairo_set_line_width(out,1.);c.cairo_stroke(out)
        finally:c.cairo_pattern_destroy(film);c.cairo_pattern_destroy(rim)
        c.cairo_set_source_surface(cr,self.canvas,0,0);c.cairo_paint(cr)
        return True

    def finish(self):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.active=False;self.handed_off=False;self.last=None
        self.nav.get_style_context().remove_class('glass-flight');self.nav.set_opacity(1.)
        self.layer.hide();self.layer.set_opacity(1.)
        if self.cr:self.c.cairo_destroy(self.cr);self.cr=None
        for surface in (self.frame,self.canvas):
            if surface:self.c.cairo_surface_destroy(surface)
        self.frame=self.canvas=None
        self.frame_size=None

    def close(self):
        if self.closed:return
        self.closed=True;self.finish()
        self.get_settings().disconnect(self.motion_signal)
        self.g.g_signal_handler_disconnect(self.ptr,self.handler)
