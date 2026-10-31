"""A satin cover seat and directional reflections, without a GL surface.

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
        'create':(p,p),'destroy':(None,p),'surface_flush':(None,p),
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


def rounded(c,cr,x,y,width,height,radius):
    radius=max(0,min(radius,width/2,height/2))
    c.cairo_new_path(cr);c.cairo_new_sub_path(cr)
    for cx,cy,a,b in ((x+width-radius,y+radius,-math.pi/2,0),
            (x+width-radius,y+height-radius,0,math.pi/2),
            (x+radius,y+height-radius,math.pi/2,math.pi),
            (x+radius,y+radius,math.pi,math.pi*1.5)):
        c.cairo_arc(cr,cx,cy,radius,a,b)
    c.cairo_close_path(cr)


def gradient(c,x0,y0,x1,y1,stops):
    pattern=c.cairo_pattern_create_linear(x0,y0,x1,y1)
    for stop in stops:c.cairo_pattern_add_color_stop_rgba(pattern,*stop)
    return pattern


def paint(c,cr,surface,size,radius,depth,wave,material):
    """Shared moving/settled drawing: the last frame has no material change."""
    depth=max(0,min(1,depth));inset=max(1.25,size*.0095)*depth
    top=inset+max(.35,size*.0022)*depth;span=size-2*inset
    inner_radius=radius*span/size
    c.cairo_save(cr)
    try:
        rounded(c,cr,0,0,size,size,radius);c.cairo_clip(cr)
        # An opaque, artwork-tinted matte removes the doubled outline of the
        # old floating print. The entire photograph remains inside the lip.
        c.cairo_set_source_rgba(cr,*material,1);c.cairo_paint(cr)
        seat=gradient(c,0,0,size,size,((0,0,0,0,.23*depth),(.48,0,0,0,0),(1,1,.91,.72,.045*depth)))
        try:c.cairo_set_source(cr,seat);c.cairo_paint(cr)
        finally:c.cairo_pattern_destroy(seat)
        lip=gradient(c,0,0,size,size,((0,1,.94,.80,.025*depth),(.45,1,.94,.80,0),(1,1,.91,.72,.12*depth)))
        try:
            rounded(c,cr,inset-.6,top-.6,span+1.2,span+1.2,inner_radius+.6)
            c.cairo_set_source(cr,lip);c.cairo_set_line_width(cr,1.2);c.cairo_stroke(cr)
        finally:c.cairo_pattern_destroy(lip)
        c.cairo_save(cr)
        rounded(c,cr,inset,top,span,span,inner_radius);c.cairo_clip(cr)
        c.cairo_save(cr)
        c.cairo_translate(cr,inset,top);c.cairo_scale(cr,span/size,span/size)
        c.cairo_set_source_surface(cr,surface,0,0)
        c.cairo_pattern_set_filter(c.cairo_get_source(cr),1)
        c.cairo_paint(cr);c.cairo_restore(cr)
        # Only the first few pixels catch the contact shadow. There is no
        # veil, saturation change or broad dark gradient across the picture.
        for x0,y0,x1,y1,alpha in ((0,top,0,top+max(3,size*.013),.17),
                (inset,0,inset+max(2,size*.009),0,.09)):
            shade=gradient(c,x0,y0,x1,y1,((0,0,0,0,alpha*depth),(.35,0,0,0,alpha*.32*depth),(1,0,0,0,0)))
            try:c.cairo_set_source(cr,shade);c.cairo_paint(cr)
            finally:c.cairo_pattern_destroy(shade)
        # A primary reflection and one weaker trailing crest. Directional
        # light, a narrow ridge and a quiet shadow avoid the concentric-halo
        # appearance of wide, evenly illuminated circles.
        for delay,gain in ((0.,1.),(.17,.34)):
            t=wave-delay
            if t<=0:continue
            strength=ease(t/.09)*(1-ease((t-.88)/.46))*math.exp(-1.05*t)*gain
            if strength<.0005:continue
            r=(.025+.64*t**.9)*size
            cx,cy=inset+span*.47,top+span*.45
            if r>size*1.4:continue
            for width,opacity,offset,shadow in ((max(4,size*.012),.011,0,False),
                    (max(1.8,size*.004),.035,0,False),(.8,.078,0,False),
                    (max(1.4,size*.003),.040,max(.8,size*.002),True)):
                if shadow:
                    stops=((0,0,0,0,0),(.5,0,0,0,0),(1,0,0,0,opacity*strength))
                else:
                    stops=((0,1,.94,.80,opacity*strength),(.4,1,.94,.80,opacity*.45*strength),(.85,1,.94,.80,0),(1,1,.94,.80,0))
                sheen=gradient(c,cx-r*.8,cy-r*.8,cx+r*.8,cy+r*.8,stops)
                try:
                    c.cairo_set_source(cr,sheen);c.cairo_set_line_width(cr,width)
                    c.cairo_new_path(cr);c.cairo_arc(cr,cx,cy,r+offset,0,math.tau);c.cairo_stroke(cr)
                finally:c.cairo_pattern_destroy(sheen)
        c.cairo_restore(cr)
    finally:c.cairo_restore(cr)


def image_surface(c,raw,size):
    if len(raw)!=size*size*4:raise ValueError('Invalid cover print')
    surface=c.cairo_image_surface_create(0,size,size)
    pixels=c.cairo_image_surface_get_data(surface)
    if not pixels:c.cairo_surface_destroy(surface);raise RuntimeError('Cover print allocation failed')
    C.memmove(pixels,raw,len(raw));c.cairo_surface_mark_dirty(surface)
    return surface


def settled_frame(raw,size,radius,material):
    """Prepare the final pose in the artwork worker using the same painter."""
    c,_,_=bindings();source=image_surface(c,raw,size)
    result=c.cairo_image_surface_create(0,size,size);cr=None
    try:
        pixels=c.cairo_image_surface_get_data(result)
        if not pixels:raise RuntimeError('Paused frame allocation failed')
        cr=c.cairo_create(result)
        paint(c,cr,source,size,radius,1.,2.,material);c.cairo_surface_flush(result)
        return C.string_at(pixels,size*size*4)
    finally:
        if cr:c.cairo_destroy(cr)
        c.cairo_surface_destroy(result);c.cairo_surface_destroy(source)


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

    def set_frame(self,raw,size,material=(.14,.14,.12)):
        if self.closed:return
        self.clear();self.size=size;self.material=tuple(material)
        self.surface=image_surface(self.cairo,raw,size)

    def draw(self,_widget,cr,_data):
        owner=self.owner()
        if self.closed or not owner or self.surface is None:return False
        paint(self.cairo,cr,self.surface,self.size,owner.radius,owner.depth,owner.wave,self.material)
        return False

    def close(self):
        if self.closed:return
        self.closed=True
        if self.handler:self.gobject.g_signal_handler_disconnect(self.pointer,self.handler);self.handler=0
        self.clear()
