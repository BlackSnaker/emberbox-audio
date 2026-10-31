"""A cached Cairo print and three soft crests, without a nested GL surface.

GTK already supplies Cairo. The C draw callback avoids requiring an additional
Python binding; all drawing and surface lifetimes remain on GTK's thread.
"""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache
import math
import weakref


@lru_cache(maxsize=1)
def bindings():
    cairo=C.CDLL(find_library('cairo'));gobject=C.CDLL(find_library('gobject-2.0'))
    p=C.c_void_p;d=C.c_double;i=C.c_int
    signatures={
        'image_surface_create':(p,i,i,i),'image_surface_get_data':(p,p),
        'surface_mark_dirty':(None,p),'surface_destroy':(None,p),
        'save':(None,p),'restore':(None,p),'new_path':(None,p),'new_sub_path':(None,p),
        'arc':(None,p,d,d,d,d,d),'close_path':(None,p),'clip':(None,p),
        'translate':(None,p,d,d),'scale':(None,p,d,d),'paint':(None,p),
        'set_source_surface':(None,p,p,d,d),'set_source_rgba':(None,p,d,d,d,d),
        'set_source':(None,p,p),'get_source':(p,p),'pattern_set_filter':(None,p,i),
        'pattern_create_linear':(p,d,d,d,d),'pattern_create_radial':(p,d,d,d,d,d,d),
        'pattern_add_color_stop_rgba':(None,p,d,d,d,d,d),'pattern_destroy':(None,p),
        'set_line_width':(None,p,d),'stroke':(None,p),
    }
    for name,(result,*args) in signatures.items():
        fn=getattr(cairo,'cairo_'+name);fn.restype=result;fn.argtypes=args
    pointer=C.pythonapi.PyCapsule_GetPointer
    pointer.restype=p;pointer.argtypes=[C.py_object,C.c_char_p]
    gobject.g_signal_connect_data.restype=C.c_ulong
    gobject.g_signal_connect_data.argtypes=[p,C.c_char_p,p,p,p,i]
    gobject.g_signal_handler_disconnect.restype=None
    gobject.g_signal_handler_disconnect.argtypes=[p,C.c_ulong]
    return cairo,gobject,pointer


def ease(t):
    t=max(0,min(1,t));return t*t*t*(t*(t*6-15)+10)


class CoverPainter:
    def __init__(self,canvas,owner):
        self.canvas=canvas;self.owner=weakref.ref(owner)
        self.cairo,self.gobject,pointer=bindings()
        self.pointer=pointer(canvas.__gpointer__,None)
        self.surface=None;self.raw=None;self.size=0;self.closed=False
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.gobject.g_signal_connect_data(self.pointer,b'draw',self.callback,None,None,0)

    def clear(self):
        if self.surface:self.cairo.cairo_surface_destroy(self.surface)
        self.surface=None;self.raw=None;self.size=0

    def set_frame(self,raw,size):
        if self.closed:return
        self.clear();self.raw=raw;self.size=size
        # Cairo owns the pixels, including when GTK retains a source pattern
        # beyond this draw. Dropping the Python snapshot cannot invalidate it.
        if len(raw)!=size*size*4:raise ValueError('Invalid cover print')
        self.surface=self.cairo.cairo_image_surface_create(0,size,size)
        pixels=self.cairo.cairo_image_surface_get_data(self.surface)
        if not pixels:self.clear();raise RuntimeError('Cover print allocation failed')
        C.memmove(pixels,raw,len(raw))
        self.cairo.cairo_surface_mark_dirty(self.surface)
        self.raw=None

    def rounded(self,cr,x,y,width,height,radius):
        c=self.cairo;radius=max(0,min(radius,width/2,height/2))
        c.cairo_new_path(cr);c.cairo_new_sub_path(cr)
        for cx,cy,a,b in ((x+width-radius,y+radius,-math.pi/2,0),
                (x+width-radius,y+height-radius,0,math.pi/2),
                (x+radius,y+height-radius,math.pi/2,math.pi),
                (x+radius,y+radius,math.pi,math.pi*1.5)):
            c.cairo_arc(cr,cx,cy,radius,a,b)
        c.cairo_close_path(cr)

    def draw(self,_widget,cr,_data):
        owner=self.owner()
        if self.closed or not owner or self.surface is None:return False
        c=self.cairo;size=self.size;depth=max(0,min(1,owner.depth))
        inset=max(1,round(size*.021))*depth
        top=inset+max(1,round(size*.003))*depth;span=size-2*inset
        c.cairo_save(cr)
        try:
            self.rounded(cr,0,0,size,size,owner.radius);c.cairo_clip(cr)
            c.cairo_set_source_rgba(cr,19/255,23/255,19/255,depth);c.cairo_paint(cr)
            c.cairo_save(cr)
            c.cairo_translate(cr,inset,top);c.cairo_scale(cr,span/size,span/size)
            c.cairo_set_source_surface(cr,self.surface,0,0)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr),1)
            c.cairo_paint(cr);c.cairo_restore(cr)
            shade=c.cairo_pattern_create_linear(0,0,0,max(16,size*.1))
            try:
                for at in (0.,.25,.5,.75,1.):
                    c.cairo_pattern_add_color_stop_rgba(shade,at,0,0,0,math.exp(-4*at)*55/255*depth)
                c.cairo_set_source(cr,shade);c.cairo_paint(cr)
            finally:c.cairo_pattern_destroy(shade)
            t=owner.wave
            strength=ease(t/.11)*(1-ease((t-1.05)/.65))*math.exp(-.65*t)
            if strength>.0001:
                width=(.023+.011*t)*size
                for index in range(3):
                    radius=(.015+.56*t-index*.066)*size
                    if radius<=width*2 or radius>size*1.45:continue
                    crest=c.cairo_pattern_create_radial(size*.46,size*.44,max(0,radius-width*2),
                        size*.46,size*.44,radius+width*2)
                    opacity=strength*(1-index*.23)
                    try:
                        for at,r,g,b,a in ((0,0,0,0,0),(.24,.10,.12,.10,.045),
                                (.45,1,.87,.63,.095),(.59,1,.87,.63,.025),(1,1,.87,.63,0)):
                            c.cairo_pattern_add_color_stop_rgba(crest,at,r,g,b,a*opacity)
                        c.cairo_set_source(cr,crest);c.cairo_set_line_width(cr,width*4)
                        c.cairo_new_path(cr);c.cairo_arc(cr,size*.46,size*.44,radius,0,math.tau);c.cairo_stroke(cr)
                    finally:c.cairo_pattern_destroy(crest)
        finally:c.cairo_restore(cr)
        return False

    def close(self):
        if self.closed:return
        self.closed=True
        if self.handler:self.gobject.g_signal_handler_disconnect(self.pointer,self.handler);self.handler=0
        self.clear()
