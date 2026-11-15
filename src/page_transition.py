"""Finite page dissolves from two retained frames, without painting two GTK trees.

Only the catalogue viewport is captured; nothing is written to disk. Cairo
composites the two premultiplied frames on the presentation clock. Live widgets
keep their allocations and input routing, while their costly painting is paused.
"""
import ctypes as C
from gi.repository import Gtk,GLib
from cover_pause_paint import bindings,ease
from room_snapshot import snapshot


class PageTransition(Gtk.Overlay):
    DURATION=.28

    def __init__(self,live,completed=lambda:None):
        super().__init__();self.live=live;self.completed=completed;self.add(live)
        self.layer=Gtk.DrawingArea();self.layer.set_has_window(False)
        self.layer.set_can_focus(False);self.layer.set_no_show_all(True)
        self.add_overlay(self.layer);self.set_overlay_pass_through(self.layer,True)
        self.c,self.g,self.pointer=bindings()
        self.ptr=self.pointer(self.layer.__gpointer__,None)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw_frames)
        self.handler=self.g.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)
        self.before=self.after=self.canvas=self.cr=None;self.size=None;self.tick=0
        self.progress=0.;self.started=None;self.active=self.closed=False
        self.connect('unmap',lambda *_:self.finish())
        self.connect('size-allocate',self.resized)
        self.connect('destroy',lambda *_:self.close())
        self.motion_signal=self.get_settings().connect('notify::gtk-enable-animations',lambda *_:self.abort())

    def surface(self,widget):
        area=self.get_allocation().copy();area.x=area.y=0
        saved=widget.get_allocation().copy()
        try:w,h,raw=snapshot(widget,area)
        finally:widget.size_allocate(saved)
        frame=self.c.cairo_image_surface_create(0,w,h)
        self.c.cairo_surface_flush(frame)
        C.memmove(self.c.cairo_image_surface_get_data(frame),raw,len(raw))
        self.c.cairo_surface_mark_dirty(frame)
        return frame,(w,h)

    def prepare(self):
        if self.closed or not self.get_mapped() or not self.get_settings().get_property('gtk-enable-animations'):
            self.finish();return
        allocation=self.get_allocation()
        if allocation.width<2 or allocation.height<2 or allocation.width*allocation.height>9_000_000:
            self.finish();return
        frame=None
        try:frame,size=self.surface(self if self.active else self.live)
        except (OSError,RuntimeError,AttributeError):pass
        self.finish()
        if frame:self.before,self.size=frame,size

    def begin(self):
        if not self.before:return
        try:
            self.after,size=self.surface(self.live)
            if not self.before or size[0]*size[1]>9_000_000:raise RuntimeError('Page viewport changed')
            self.size=size
        except (OSError,RuntimeError,AttributeError):self.finish();return
        self.canvas=self.c.cairo_image_surface_create(0,*self.size);self.cr=self.c.cairo_create(self.canvas)
        self.started=None;self.progress=0.;self.active=True
        self.live.set_opacity(0.);self.layer.show();self.layer.queue_draw()
        self.tick=self.add_tick_callback(self.advance)

    def resized(self,_widget,area):
        if self.active and self.size!=(area.width,area.height):self.abort()

    def abort(self):
        active=self.active;self.finish()
        if active:
            def notify():
                if not self.closed:self.completed()
                return False
            GLib.idle_add(notify,priority=GLib.PRIORITY_DEFAULT)

    def advance(self,_widget,clock):
        if not self.active:return False
        now=clock.get_frame_time()
        if self.started is None:self.started=now
        self.progress=max(0.,min(1.,(now-self.started)/1e6/self.DURATION))
        if self.progress>=1. or not self.get_settings().get_property('gtk-enable-animations'):
            self.tick=0;self.finish();self.completed();return False
        self.layer.queue_draw();return True

    def draw_frames(self,_widget,cr,_data):
        if not self.active or not self.before or not self.after:return False
        c=self.c;out=self.cr;t=ease(self.progress)
        # Reset the entire work surface before the weighted SOURCE operation.
        # A masked SOURCE followed by ADD retains part of the preceding frame
        # and accumulates brightness on every repaint (especially on retarget).
        c.cairo_set_operator(out,1);c.cairo_set_source_surface(out,self.before,0,0);c.cairo_paint(out)
        c.cairo_set_source_surface(out,self.after,0,0);c.cairo_paint_with_alpha(out,t)
        c.cairo_set_source_surface(cr,self.canvas,0,0);c.cairo_paint(cr)
        return True

    def finish(self):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.active=False;self.started=None
        self.layer.hide();self.live.set_opacity(1.)
        if self.cr:self.c.cairo_destroy(self.cr);self.cr=None
        for frame in (self.before,self.after,self.canvas):
            if frame:self.c.cairo_surface_destroy(frame)
        self.before=self.after=self.canvas=None;self.size=None

    def close(self):
        if self.closed:return
        self.closed=True;self.finish()
        self.get_settings().disconnect(self.motion_signal)
        self.g.g_signal_handler_disconnect(self.ptr,self.handler)
