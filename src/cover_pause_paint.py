"""A sculpted cover well and directional reflections, without a GL surface.

GTK already supplies Cairo. The C draw callback avoids an additional Python
binding. Live surfaces stay on GTK's thread; workers bake independent images.
"""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache
import math
import weakref
import numpy as np


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
        'rectangle':(None,p,d,d,d,d),'set_operator':(None,p,i),
        'translate':(None,p,d,d),'scale':(None,p,d,d),'paint':(None,p),'paint_with_alpha':(None,p,d),
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


def well_geometry(size,radius,depth):
    inset=max(1.5,size*.03)*depth
    top=inset+max(.35,size*.0025)*depth;span=size-2*inset
    return inset,top,span,radius*span/size+max(1.2,size*.009)*depth


def well_frame(size,radius,material):
    """Bake a smooth concave surface from its normals once outside GTK.

    A continuous height profile makes the shoulder round rather than a stack
    of bevels. A small outer crown meets the deep well, lit from the upper left.
    The full-resolution result is cached; none of this work runs per frame.
    """
    inset,top,span,inner_radius=well_geometry(size,radius,1)
    cx=inset+span/2;cy=top+span/2
    width=max(.7,inset*.33);sigma=max(.7,inset*.23)
    light=np.array((-.55,-.65,.525));light/=np.linalg.norm(light)
    half=light+np.array((0,0,1));half/=np.linalg.norm(half)
    tone=np.array(material)*255;warm=np.array((255,237,203))
    result=np.empty((size,size,4),np.uint8)
    flat=tone+warm*(half[2]**18*.75)*.10
    result[...,:3]=np.clip(flat[::-1]+.5,0,255);result[...,3]=255
    # Only the perimeter can be exposed. Avoid calculating normals under the
    # opaque picture: four narrow strips also bound temporary worker memory.
    band=min(size//2,math.ceil(inset+inner_radius+3))
    strips=((0,0,size,band),(0,size-band,size,band),
            (0,band,band,size-2*band),(size-band,band,band,size-2*band))
    for x,y,w,h in strips:
        if not w or not h:continue
        yy,xx=np.mgrid[y:y+h,x:x+w].astype(np.float32);xx+=.5;yy+=.5
        qx=np.abs(xx-cx)-(span/2-inner_radius);qy=np.abs(yy-cy)-(span/2-inner_radius)
        ox=np.maximum(qx,0);oy=np.maximum(qy,0);outside=np.hypot(ox,oy)
        length=np.maximum(outside,.0001)
        distance=outside+np.minimum(np.maximum(qx,qy),0)-inner_radius
        dx=np.where(outside>0,ox/length,np.where(qx>qy,1,0))*np.sign(xx-cx)
        dy=np.where(outside>0,oy/length,np.where(qy>=qx,1,0))*np.sign(yy-cy)
        curve=np.tanh(distance/width)
        slope=(inset*.95)/(2*width)*(1-curve*curve)
        offset=distance-inset*.68
        slope-=inset*.12*offset/(sigma*sigma)*np.exp(-.5*(offset/sigma)**2)
        norm=1/np.sqrt(1+slope*slope)
        nx=-slope*dx*norm;ny=-slope*dy*norm;nz=norm
        diffuse=np.maximum(0,nx*light[0]+ny*light[1]+nz*light[2])
        specular=np.maximum(0,nx*half[0]+ny*half[1]+nz*half[2])**18
        specular=np.maximum(0,specular-half[2]**18*.25)
        colours=tone*(.52+.80*diffuse[...,None])/(.52+.80*light[2])
        colours+=warm*specular[...,None]*.10
        qx=np.abs(xx-size/2)-(size/2-radius);qy=np.abs(yy-size/2)-(size/2-radius)
        outer=np.hypot(np.maximum(qx,0),np.maximum(qy,0))+np.minimum(np.maximum(qx,qy),0)-radius
        alpha=np.clip(.5-outer,0,1)
        result[y:y+h,x:x+w,:3]=np.clip(colours[...,::-1]*alpha[...,None]+.5,0,255)
        result[y:y+h,x:x+w,3]=(alpha*255+.5).astype(np.uint8)
    return result.tobytes()



def paint(c,cr,surface,size,radius,depth,wave,material,well):
    """Shared moving/settled drawing: the last frame has no material change."""
    depth=max(0,min(1,depth));inset,top,span,inner_radius=well_geometry(size,radius,depth)
    c.cairo_save(cr)
    try:
        rounded(c,cr,0,0,size,size,radius);c.cairo_clip(cr)
        # One continuous, artwork-tinted body. The entire photograph sinks
        # into it; the original print cannot show through beneath its edges.
        c.cairo_set_source_rgba(cr,*material,1);c.cairo_paint(cr)
        c.cairo_set_source_surface(cr,well,0,0);c.cairo_paint_with_alpha(cr,depth)
        lip=gradient(c,0,0,size,size,((0,0,0,0,.26*depth),(.42,0,0,0,0),(1,1,.92,.76,.20*depth)))
        try:
            rounded(c,cr,inset-.4,top-.4,span+.8,span+.8,inner_radius+.4)
            c.cairo_set_source(cr,lip);c.cairo_set_line_width(cr,.85);c.cairo_stroke(cr)
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
        for x0,y0,x1,y1,alpha in ((0,top,0,top+max(2,size*.018),.40),
                (inset,0,inset+max(1.5,size*.014),0,.28)):
            shade=gradient(c,x0,y0,x1,y1,((0,0,0,0,alpha*depth),(.35,0,0,0,alpha*.32*depth),(1,0,0,0,0)))
            c.cairo_save(cr)
            try:
                # Transparent gradient tails must not shade the entire cover.
                # Clip the work itself to the few pixels that catch a shadow.
                c.cairo_new_path(cr)
                if y1>y0:c.cairo_rectangle(cr,inset,top,span,y1-y0)
                else:c.cairo_rectangle(cr,inset,top,x1-x0,span)
                c.cairo_clip(cr);c.cairo_set_source(cr,shade);c.cairo_paint(cr)
            finally:c.cairo_restore(cr);c.cairo_pattern_destroy(shade)
        # A fine rounded glass edge sits inside the soft body. Its opposite
        # highlight separates the held print from the concave matte well.
        glass=gradient(c,inset,top,inset+span,top+span,
            ((0,1,.96,.85,.22*depth),(.42,1,.96,.85,.025*depth),
             (.7,1,.96,.85,0),(1,0,0,0,.12*depth)))
        try:
            rounded(c,cr,inset+.65,top+.65,span-1.3,span-1.3,max(0,inner_radius-.65))
            c.cairo_set_source(cr,glass);c.cairo_set_line_width(cr,max(.65,size*.0014));c.cairo_stroke(cr)
        finally:c.cairo_pattern_destroy(glass)
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
            for width,light,dark in ((max(4,size*.010),.012,.004),
                                     (max(1.2,size*.0026),.095,.040)):
                stops=((0,1,.94,.80,light*strength),(.4,1,.94,.80,light*.45*strength),
                       (.55,1,.94,.80,0),(.56,0,0,0,0),(1,0,0,0,dark*strength))
                sheen=gradient(c,cx-r*.8,cy-r*.8,cx+r*.8,cy+r*.8,stops)
                try:
                    c.cairo_set_source(cr,sheen);c.cairo_set_line_width(cr,width)
                    c.cairo_new_path(cr);c.cairo_arc(cr,cx,cy,r,0,math.tau);c.cairo_stroke(cr)
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


def settled_frame(raw,size,radius,material,well_raw):
    """Prepare the final pose in the artwork worker using the same painter."""
    c,_,_=bindings();source=image_surface(c,raw,size);well=None;result=None;cr=None
    try:
        well=image_surface(c,well_raw,size);result=c.cairo_image_surface_create(0,size,size)
        pixels=c.cairo_image_surface_get_data(result)
        if not pixels:raise RuntimeError('Paused frame allocation failed')
        cr=c.cairo_create(result)
        paint(c,cr,source,size,radius,1.,2.,material,well);c.cairo_surface_flush(result)
        return C.string_at(pixels,size*size*4)
    finally:
        if cr:c.cairo_destroy(cr)
        if result:c.cairo_surface_destroy(result)
        if well:c.cairo_surface_destroy(well)
        c.cairo_surface_destroy(source)


class CoverPainter:
    def __init__(self,canvas,owner):
        self.canvas=canvas;self.owner=weakref.ref(owner)
        self.cairo,self.gobject,pointer=bindings()
        self.pointer=pointer(canvas.__gpointer__,None)
        self.surface=self.well=self.buffer=self.context=None;self.size=0;self.closed=False
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.gobject.g_signal_connect_data(self.pointer,b'draw',self.callback,None,None,0)

    def clear(self):
        if self.context:self.cairo.cairo_destroy(self.context)
        if self.buffer:self.cairo.cairo_surface_destroy(self.buffer)
        if self.surface:self.cairo.cairo_surface_destroy(self.surface)
        if self.well:self.cairo.cairo_surface_destroy(self.well)
        self.surface=self.well=self.buffer=self.context=None;self.size=0

    def set_frame(self,raw,size,material,well_raw):
        if self.closed:return
        self.clear();self.size=size;self.material=tuple(material)
        self.surface=image_surface(self.cairo,raw,size)
        try:
            self.well=image_surface(self.cairo,well_raw,size)
            self.buffer=self.cairo.cairo_image_surface_create(0,size,size)
            if not self.cairo.cairo_image_surface_get_data(self.buffer):raise RuntimeError('Pause buffer allocation failed')
            self.context=self.cairo.cairo_create(self.buffer)
        except Exception:self.clear();raise

    def draw(self,_widget,cr,_data):
        owner=self.owner()
        if self.closed or not owner or self.surface is None:return False
        c=self.cairo
        # Keep vector work at the cover's logical resolution even on HiDPI.
        # GTK composites one finished image at the monitor scale. Both native
        # allocations are retained for the whole movement, not made per tick.
        c.cairo_set_operator(self.context,1);c.cairo_set_source_rgba(self.context,0,0,0,0)
        c.cairo_paint(self.context);c.cairo_set_operator(self.context,2)
        paint(c,self.context,self.surface,self.size,owner.radius,owner.depth,owner.wave,self.material,self.well)
        c.cairo_set_source_surface(cr,self.buffer,0,0)
        c.cairo_paint(cr)
        return False

    def close(self):
        if self.closed:return
        self.closed=True
        if self.handler:self.gobject.g_signal_handler_disconnect(self.pointer,self.handler);self.handler=0
        self.clear()
