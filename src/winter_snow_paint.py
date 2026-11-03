"""Tiny Cairo masks on GTK's existing canvas; no GL overlay or frame buffers."""
import ctypes as C
import math
import weakref
from cover_pause_paint import bindings,rounded


class SnowPainter:
    def __init__(self,canvas,owner):
        self.owner=weakref.ref(owner);self.cairo,self.gobject,pointer=bindings()
        self.pointer=pointer(canvas.__gpointer__,None);self.closed=False
        self.draws=0
        c=self.cairo
        c.cairo_mask_surface.restype=None;c.cairo_mask_surface.argtypes=[C.c_void_p,C.c_void_p,C.c_double,C.c_double]
        self.mask=c.cairo_image_surface_create(2,32,32)
        c.cairo_surface_flush(self.mask)
        data=c.cairo_image_surface_get_data(self.mask)
        if not data:raise RuntimeError('Snow mask allocation failed')
        pixels=[]
        for y in range(32):
            for x in range(32):
                distance=math.hypot((x-15.5)/14.,(y-15.5)/14.)
                t=max(0.,min(1.,(1.05-distance)/.25));pixels.append(round(t*t*(3-2*t)*255))
        C.memmove(data,bytes(pixels),1024);c.cairo_surface_mark_dirty(self.mask)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.gobject.g_signal_connect_data(self.pointer,b'draw',self.callback,None,None,0)

    def draw(self,_widget,cr,_data):
        owner=self.owner()
        if not owner or self.closed or not owner.active:return False
        c=self.cairo
        try:
            c.cairo_save(cr)
            width,height=owner.area.get_allocated_width(),owner.area.get_allocated_height()
            inset=10. if not owner.stage and width<=320 else 0.
            rounded(c,cr,0,inset,width,max(1,height-2*inset),0 if owner.stage else 22);c.cairo_clip(cr)
            for x,y,size,alpha,h in owner.dots:
                if alpha<.004:continue
                c.cairo_save(cr);c.cairo_translate(cr,x,y)
                c.cairo_scale(cr,abs(size)/14.,max(.35,h)/14.)
                tint=(.96,.94,.86) if size<0 else (.94,.97,1.)
                c.cairo_set_source_rgba(cr,*tint,alpha)
                c.cairo_mask_surface(cr,self.mask,-16.,-16.)
                c.cairo_restore(cr)
            self.draws+=1
        except Exception:
            owner.failed=True
        finally:c.cairo_restore(cr)
        return False

    def close(self):
        if self.closed:return
        self.closed=True
        if self.handler:self.gobject.g_signal_handler_disconnect(self.pointer,self.handler);self.handler=0
        if self.mask:self.cairo.cairo_surface_destroy(self.mask);self.mask=None
