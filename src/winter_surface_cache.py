"""Cache static GTK box materials while snow animates over them.

Only the CSS background/frame is retained. Live children, input routing and
layout stay with GTK. This avoids rerasterising large neumorphic shadows for
every tiny snow damage rectangle; no interface screenshots are taken.
"""
import ctypes as C
from ctypes.util import find_library
import weakref
from cover_pause_paint import bindings


class MaterialCache:
    MARGIN=88
    MAX_PIXELS=8_388_608

    def __init__(self,widget,owner):
        self.widget=widget;self.owner=weakref.ref(owner);self.closed=self.failed=False
        self.cairo,self.gobject,self.pointer=bindings();self.ptr=self.pointer(widget.__gpointer__,None)
        self.gtk=C.CDLL(find_library('gtk-3'))
        p=C.c_void_p;d=C.c_double
        for name,args in (('gtk_render_background',[p,p,d,d,d,d]),('gtk_render_frame',[p,p,d,d,d,d]),
                          ('gtk_container_propagate_draw',[p,p,p])):
            fn=getattr(self.gtk,name);fn.restype=None;fn.argtypes=args
        self.cairo.cairo_surface_status.restype=C.c_int;self.cairo.cairo_surface_status.argtypes=[p]
        self.cairo.cairo_surface_set_device_scale.restype=None
        self.cairo.cairo_surface_set_device_scale.argtypes=[p,d,d]
        self.surface=None;self.key=None;self.builds=0
        self.callback=C.CFUNCTYPE(C.c_int,p,p,p)(self.draw)
        self.handler=self.gobject.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)
        self.style_signal=widget.connect('style-updated',lambda *_:self.clear())

    def clear(self):
        if self.surface:self.cairo.cairo_surface_destroy(self.surface)
        self.surface=None;self.key=None

    def build(self,width,height,scale):
        self.clear();c=self.cairo;m=self.MARGIN
        surface=c.cairo_image_surface_create(0,(width+2*m)*scale,(height+2*m)*scale)
        if c.cairo_surface_status(surface):
            c.cairo_surface_destroy(surface);raise RuntimeError('Material cache allocation failed')
        c.cairo_surface_set_device_scale(surface,scale,scale);cr=c.cairo_create(surface)
        try:
            c.cairo_translate(cr,m,m)
            context=self.pointer(self.widget.get_style_context().__gpointer__,None)
            self.gtk.gtk_render_background(context,cr,0.,0.,width,height)
            self.gtk.gtk_render_frame(context,cr,0.,0.,width,height)
        except Exception:
            c.cairo_surface_destroy(surface);raise
        finally:c.cairo_destroy(cr)
        self.surface=surface;self.key=(width,height,scale);self.builds+=1

    def draw(self,_widget,cr,_data):
        owner=self.owner()
        if self.closed or self.failed:return False
        if not owner or not owner.enabled or owner.failed or owner.suspended:
            self.clear();return False
        width,height=self.widget.get_allocated_width(),self.widget.get_allocated_height()
        scale=max(1,self.widget.get_scale_factor())
        if (width+2*self.MARGIN)*(height+2*self.MARGIN)*scale*scale>self.MAX_PIXELS:
            self.clear();return False
        try:
            if self.key!=(width,height,scale):self.build(width,height,scale)
            self.cairo.cairo_save(cr)
            self.cairo.cairo_set_source_surface(cr,self.surface,-self.MARGIN,-self.MARGIN)
            self.cairo.cairo_paint(cr);self.cairo.cairo_restore(cr)
            for child in self.widget.get_children():
                self.gtk.gtk_container_propagate_draw(self.ptr,self.pointer(child.__gpointer__,None),cr)
            return True
        except Exception:
            self.failed=True;self.clear();return False

    def close(self):
        if self.closed:return
        self.closed=True
        if self.handler:self.gobject.g_signal_handler_disconnect(self.ptr,self.handler);self.handler=0
        if self.widget.handler_is_connected(self.style_signal):self.widget.disconnect(self.style_signal)
        self.clear()
