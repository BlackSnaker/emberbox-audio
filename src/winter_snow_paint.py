"""Tiny Cairo masks on GTK's existing canvas; no GL overlay or frame buffers."""
import ctypes as C
import math
import weakref
from cover_pause_paint import bindings,rounded


class SnowPainter:
    def __init__(self,canvas,owner):
        self.owner=weakref.ref(owner);self.cairo,self.gobject,pointer=bindings()
        self.pointer=pointer(canvas.__gpointer__,None);self.closed=False
        self.draws=0;self.presentations=0;self.packet_key=None;self.packet=[];self.painted_key=None
        self.extents=(C.c_double*4)()
        self.extent_ptrs=tuple(C.cast(C.byref(self.extents,i*C.sizeof(C.c_double)),C.POINTER(C.c_double)) for i in range(4))
        c=self.cairo
        c.cairo_clip_extents.restype=None;c.cairo_clip_extents.argtypes=[C.c_void_p]+[C.POINTER(C.c_double)]*4
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

    def prepare(self,dots):
        if dots is self.packet_key:return
        self.packet_key=dots;self.packet=[]
        for x,y,size,alpha,h in dots:
            if alpha<.004:continue
            radius=abs(size)
            self.packet.append((x-radius-2,y-h-2,x+radius+2,y+h+2,x,y,radius/14.,max(.35,h)/14.,
                                (.96,.94,.86) if size<0 else (.94,.97,1.),alpha))

    def draw(self,_widget,cr,_data):
        owner=self.owner()
        if not owner or self.closed or not owner.active:return False
        c=self.cairo;self.prepare(owner.dots)
        if not self.packet:return False
        # Other widgets (for example the sound meters) may repaint faster than
        # the snow. Skip sprites outside GTK's existing damage clip entirely.
        c.cairo_clip_extents(cr,*self.extent_ptrs)
        left,top,right,bottom=self.extents
        visible=[p for p in self.packet if p[0]<right and p[2]>left and p[1]<bottom and p[3]>top]
        if not visible:return False
        try:
            c.cairo_save(cr)
            if not owner.stage:
                width,height=owner.area.get_allocated_width(),owner.area.get_allocated_height()
                inset=10. if width<=320 else 0.
                rounded(c,cr,0,inset,width,max(1,height-2*inset),22);c.cairo_clip(cr)
            for _l,_t,_r,_b,x,y,sx,sy,tint,alpha in visible:
                c.cairo_save(cr);c.cairo_translate(cr,x,y);c.cairo_scale(cr,sx,sy)
                c.cairo_set_source_rgba(cr,*tint,alpha);c.cairo_mask_surface(cr,self.mask,-16.,-16.)
                c.cairo_restore(cr)
            self.draws+=1
            if self.painted_key is not owner.dots:
                self.painted_key=owner.dots;self.presentations+=1
        except Exception:owner.failed=True
        finally:c.cairo_restore(cr)
        return False

    def close(self):
        if self.closed:return
        self.closed=True
        if self.handler:self.gobject.g_signal_handler_disconnect(self.pointer,self.handler);self.handler=0
        if self.mask:self.cairo.cairo_surface_destroy(self.mask);self.mask=None
